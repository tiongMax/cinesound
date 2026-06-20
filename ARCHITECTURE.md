# CineSound — Architecture

## High-level overview

CineSound is a two-tier system:

```
[Next.js 16 frontend] --HTTP/SSE--> [FastAPI backend] --SQL--> [Postgres + pgvector]
                                          |
                                          +---> Gemini (LLM + embeddings)
                                          +---> Groq (LLM fallback)
                                          +---> TMDB API (movies)
                                          +---> Spotify API (music)
```

The backend is a single FastAPI process. Agent orchestration uses
**LangGraph** (`app/agents/graph.py`) to chain agents around shared state.
Each major user-visible feature gets its own route module under
`app/routes/`.

The frontend is a single-page **Next.js App Router** app: one main page
(`app/page.tsx` → `<Chat />`) plus a public read-only page for shared
pairings at `app/p/[code]/page.tsx`. State is local to the `<Chat />`
component; no Redux/Zustand.

## Backend modules

### `app/main.py` — composition root

Defines the FastAPI app, configures CORS via `settings.cors_origins`,
attaches the `slowapi` rate limiter, wires the asyncpg pool into the
lifespan, and includes the 6 route routers. The `lifespan` context
manager calls `init_pool()` only when `DATABASE_URL` is set, so the
app boots in tests without a database.

### `app/config.py` — environment

A single `Settings` class using `pydantic-settings`. Loads from `.env`
plus process env. Every field is `Optional` so a partial config still
imports — runtime errors surface at the call site (e.g., `TMDBClient`
raises `TMDBError` if `tmdb_api_key` is None).

### `app/db.py` — connection pool

Module-level `_pool: asyncpg.Pool | None` initialised in
`init_pool()`. `PoolDep = Annotated[asyncpg.Pool, Depends(_pool_dep)]`
is the type alias used by every route that needs DB access — it pulls
the pool off `request.app.state.db_pool`, which lets tests override
the dependency with a stub.

### `app/schemas.py` — Pydantic data contracts

All shared types live in one module. The canonical hierarchy:

```
Recommendation       → mood_detected, pairings: list[Pairing], fallback_message
  └─ Pairing         → movie: MovieRec, music: MusicRec, pairing_note
       ├─ MovieRec   → tmdb_id, title, year, genres, reason, trailer_url, poster_url
       └─ MusicRec   → spotify_uri, track, artist, mood_tag, reason, spotify_url,
                       album_art_url, preview_url

TasteProfile         → movie_profile: MovieProfile, music_profile: MusicProfile,
                       shared_mood: str

MovieCandidate / MusicCandidate    → richer internal types used between
                                     Search → Ranker, including a score float

Playlist             → mood_detected, title, intro, tracks: list[PlaylistTrack]

QueryRequest, Feedback, ShareRequest, ShareResponse, PlaylistRequest, SignInRequest
                     → API request/response shapes
```

`Recommendation` is **the** type returned by the orchestrator and consumed
by the frontend's `streamQuery` SSE parser.

### `app/agents/` — the LangGraph pipeline

5 nodes wired via `StateGraph(GraphState)` in `app/agents/graph.py`:

```
START
  → load_memory       (asyncio.gather over get_all_memory + load_recent_turns)
  → profile           (1 Gemini call w/ tools — see Profiler)
  → search            (asyncio.gather over search_movies + search_music)
  → rank_and_pair     (1 Gemini call w/ tools — see Ranker)
  → save_memory       (append_to_list for watched/heard + append_turn)
  → END
```

`GraphState` is a `TypedDict(total=False)` so each node returns only the
keys it updates. The state carries the asyncpg pool by reference — this
lets nodes do DB I/O without prop-drilling through agent signatures.

#### `agents/profiler.py`

One LLM call returning a `TasteProfile`. The system prompt includes 3
few-shot examples covering vague mood, title-based, and artist-based
queries. The profiler can optionally invoke `PROFILER_TOOLS`:
`search_movies_by_title` and `search_artists`, to ground itself against
real TMDB/Spotify catalogue data when the user references specific titles.
Memory snippet (disliked genres, recent moods) is folded into the prompt
via `_memory_snippet()`. If `recent_turns_summary` is provided, the
profiler interprets follow-up phrases ("darker", "another please")
against prior conversation.

#### `agents/search.py`

No LLM. `search_movies(pool, profile, top_n)` and
`search_music(pool, profile, top_n)` build a text query from the
relevant sub-profile, call `embed_one()` to get a 768-d vector, then
run a pgvector cosine search (`embedding <=> $1::vector`) and parse
rows into `MovieCandidate` / `MusicCandidate` lists. The TMDB genre
ID-to-name mapping is hardcoded in `TMDB_GENRE_MAP` since the seed
script stores only `genre_ids` from TMDB.

#### `agents/ranker.py`

Two steps in one module:

1. **Deterministic** — `filter_seen()` strips watched/heard items
   against memory; `top_n()` sorts by score descending and truncates
   to `TOP_N_PER_DOMAIN` (5).
2. **LLM** — one Gemini call via `gemini_chat_with_tools` returning
   a full `Recommendation` with **3 distinct pairings**. The ranker
   can call `RANKER_TOOLS`: `get_movie_details` and `get_artist_top_tracks`
   to deep-dive top candidates.

After the LLM returns, `_enrich_pairings_with_preview_urls()` splices
`preview_url` from the candidate list onto each picked music — the LLM
never sees preview URLs, avoiding hallucination.

When no candidates survive filtering, returns a `Recommendation` with
empty `pairings` and a populated `fallback_message`.

#### `agents/playlist.py`

End-to-end playlist builder: reuses the Joint Profiler, over-fetches
music candidates, filters heard tracks, then runs one Gemini call with
`response_schema=Playlist`. Preview URLs spliced on post-LLM by URI.

#### `agents/tools.py`

`ToolSpec` dataclass + four real tool functions:

- `get_movie_details(tmdb_id)` — full TMDB record
- `get_artist_top_tracks(artist_name)` — Spotify top-5 lookup
- `search_movies_by_title(title)` — TMDB title search
- `search_artists(name)` — Spotify artist disambiguation

`RANKER_TOOLS` and `PROFILER_TOOLS` are the two exported lists.

### `app/clients/` — outbound

| Module | Wraps |
|---|---|
| `tmdb.py` | TMDB v3 — `search_movie`, `get_movie`, `get_videos`, `discover_popular`, trailer extraction |
| `spotify.py` | Spotify Web API — Client Credentials flow with token cache, `search_track`, `search_artist`, `get_artist_top_tracks`, `get_related_artists` (with 404 graceful fallback) |
| `gemini.py` | `google-genai` SDK — `gemini_chat()` for structured-JSON output, `gemini_chat_with_tools()` for the manual tool-calling loop, `embed()`/`embed_one()` for `gemini-embedding-001` |
| `groq_client.py` | Groq Llama 3.3 70B — same `groq_chat()` signature as `gemini_chat()` so the orchestrator can swap on Gemini errors |

### `app/middleware/`

- `rate_limit.py` — `slowapi` `Limiter` keyed by remote address.
  `QUERY_RATE = "10/hour"` is applied to `/query` and `/playlist`.
- `daily_cap.py` — FastAPI dependency `check_daily_cap()` returns the
  pre-built `CAP_REACHED_REC` (a `Recommendation` with `fallback_message`)
  when `is_over_daily_cap()` is true. Cheaper than wrapping every endpoint.

### `app/memory.py`, `app/cache.py`, `app/usage.py`, `app/conversation.py`

Thin async CRUD over the four corresponding tables. `cache.py` exposes
a `@cached(pool_getter, namespace, ttl_seconds)` decorator for client
methods that benefit from de-duped API calls (currently used selectively;
the seed scripts and live agents access TMDB/Spotify directly).

### `app/routes/` — HTTP surface

Each module is a `APIRouter()`:

- `query.py` — `POST /query` returns `StreamingResponse(text/event-stream)`
  by iterating `graph.astream(initial, stream_mode="updates")` and
  emitting `ack`, `node_done`, `final`, `error` events.
- `feedback.py` — looks up the recommendation's genres in `embeddings`
  table and appends to `liked_genres` / `disliked_genres`.
- `signin.py` — verifies Google ID token via tokeninfo endpoint
  (async-friendly, no extra SDK), then calls `migrate_memory()`.
- `me.py` — `GET /me` returns memory summary + `recent_queries`,
  `DELETE /me` wipes everything for the session.
- `playlist.py` — `POST /playlist` runs the playlist agent, increments
  the LLM-call counter by 2 (profiler + playlist call).
- `share.py` — `POST /share` allocates an 8-char base32 short code,
  inserts into `shared_pairings`, retries on collision (5 attempts).
  `GET /share/{short_code}` is public; pattern-validated to lowercase
  alphanumeric only.

## Frontend modules

### `app/page.tsx` — root

Single export: `<Chat />`. Layout is a flex column: header (logo +
profile button + sign-in) → message list → input. The chat owns all
turn state — there is no global store.

### `app/p/[code]/page.tsx` — public shared pairing

Server-rendered (`async function` page). Calls `getShare(code)`
server-side; if the share doesn't exist, calls `notFound()`. Renders
the same `MovieCard` + `MusicCard` + `PairingNote` components used in
the main app, but without thumbs or share actions.

### `components/` — UI primitives

| Component | Role |
|---|---|
| `Chat.tsx` | Top-level state machine: turns, submitting state, profile refresh tick. Owns `runQuery()`, `handleVote()`, `handleMakePlaylist()`. |
| `RecommendationBlock.tsx` | Renders an entire `Recommendation` — header bar per pairing with `ShareButton`, then cards + note. |
| `MovieCard.tsx`, `MusicCard.tsx`, `PairingNote.tsx` | Atomic pairing pieces. Cards optionally accept `onVote`. |
| `PreviewPlayer.tsx` | Single-button audio player that toggles an `<audio>` element with `preload="none"`. |
| `VoteButtons.tsx` | Optimistic thumbs; locks after first vote. |
| `TasteProfilePanel.tsx` | Right-side slide-over (Framer Motion). Lazy-loaded on open. Shows counts, top liked/disliked genres, recent moods, recent queries (clickable replays), content prefs, and the two-step "Reset" button. |
| `PlaylistBlock.tsx` | Ordered list of `PlaylistTrack` with preview + Spotify links. |
| `MoodSpectrum.tsx` | Three axis pairs (tone/energy/feel) — each button submits a follow-up query via `runQuery(modifier)`. |
| `ShareButton.tsx` | Calls `POST /share`, writes link to clipboard, transitions through `idle → creating → copied`. |
| `SignInButton.tsx` | `@react-oauth/google` one-tap; gracefully hides when `NEXT_PUBLIC_GOOGLE_CLIENT_ID` is unset. |

### `lib/` — pure helpers

| File | Exports |
|---|---|
| `types.ts` | TS mirrors of backend Pydantic schemas. Kept in sync by hand. |
| `queryClient.ts` | `streamQuery()` — fetch-based SSE parser, since `EventSource` is GET-only. |
| `feedback.ts`, `playlist.ts`, `me.ts`, `share.ts` | Thin `fetch()` wrappers. |
| `session.ts` | `getOrCreateSessionId()` — generates `session:<uuid>` on first load, stores in 1-year cookie. |

## Data flow — full /query trace

1. `<Chat />` user submits → `runQuery(q)` → `streamQuery(q, sid, cb)`
2. SSE `POST /query` enters FastAPI → `slowapi` rate limit check → `check_daily_cap` dep
3. `query.py::_stream_orchestrator` yields `ack` → calls `graph.astream(...)`
4. Per-node yields: `load_memory_done` → `profile_done` → `search_done` → `rank_and_pair_done` → `save_memory_done`
5. Each node update splices into `last_state`; after the loop ends, the
   final `Recommendation` is yielded as `event: final`
6. Frontend `onFinal(rec)` updates the turn, bumps `profileTick`
   (which re-fetches `/me` next time the panel opens)

## Key design decisions

### Deterministic search, LLM-on-prose
The Search node is intentionally LLM-free. Cosine similarity is fast
and predictable; using an LLM here would burn cost and latency for no
quality win. The Ranker's LLM call is the *only* place prose quality
matters, and tool calling lets it deep-dive on top candidates when
necessary — see commit `feat: LLM tool calling at ranker`.

### One-pool, no Redis
The `embeddings`, `user_memory`, `api_cache`, `conversations`,
`daily_usage`, and `shared_pairings` tables all live in a single
Postgres instance. At our traffic this is fine. Avoiding Redis keeps
the deploy story to two services (backend + frontend) plus one DB.

### Splice preview URLs post-LLM, never via prompt
LLMs hallucinate URLs. The pattern in
`_enrich_pairings_with_preview_urls` and its playlist twin: pass
candidates to the LLM, let it pick by `spotify_uri`, then splice the
canonical preview URL on the way out.

### Squash-merge git workflow
Every task lands as a single commit on `main` via squash merge. Feature
branches are deleted immediately after. This keeps history readable as
a linear feature log and makes `git bisect` useful. The downside —
re-PRing a squashed branch silently overwrites later work — is
documented in `prd-fixes.md`.

### Idempotent migrations and seed scripts
`scripts/migrate.py` tracks applied filenames in a `_migrations` table
so it can re-run safely after every deploy. `scripts/seed_music.py`
checkpoints LLM-generated vibe descriptions to
`backend/scripts/.vibe_cache.json` so re-runs cost zero LLM calls.

### Tool calling bounded by iteration cap
`gemini_chat_with_tools` enforces `max_tool_iterations=2` by default.
Beyond that, `GeminiError` is raised — the orchestrator catches it and
falls back to Groq without tools as a degraded mode.
