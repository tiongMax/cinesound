# Changelog

All notable changes to CineSound are documented in this file. The format
follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). This
project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

> ⚠️ Assumption: this is the first tagged release. The state at this
> entry corresponds to PRD v2.1 (see `PRD.md` header) and matches `main`
> at the time of writing. `backend/pyproject.toml` currently shows
> `version = "0.1.0"`; bump it to `1.0.0` when cutting this release.

---

## [1.0.0] — Initial release

### Added

**Agent pipeline (`app/agents/`)**
- `graph.py` — LangGraph `StateGraph` orchestrator wiring 5 nodes:
  `load_memory → profile → search → rank_and_pair → save_memory`.
  Catches Gemini errors at the profile and rank steps and falls back
  to Groq Llama 3.3 70B with the same Pydantic schema.
- `profiler.py` — Joint Taste Profiler agent returning a `TasteProfile`
  (movie profile + music profile + shared mood) in a single Gemini
  call. Few-shot system prompt with three example queries.
- `search.py` — `search_movies()` and `search_music()` using pgvector
  HNSW cosine search over 768-d Gemini embeddings; hardcoded
  `TMDB_GENRE_MAP` translates TMDB genre IDs to readable names.
- `ranker.py` — `rank_and_pair()` with deterministic
  `filter_seen()` + `top_n()` followed by one tool-enabled Gemini
  call returning three distinct pairings. `_enrich_pairings_with_preview_urls()`
  splices Spotify preview URLs post-LLM.
- `playlist.py` — `build_playlist()` reuses the profiler + search,
  then runs one Gemini call to curate N tracks (3–15) into an
  ordered playlist with a title and intro.
- `tools.py` — `ToolSpec` dataclass + 4 tools:
  `get_movie_details`, `get_artist_top_tracks` (RANKER_TOOLS) and
  `search_movies_by_title`, `search_artists` (PROFILER_TOOLS).

**LLM and outbound clients (`app/clients/`)**
- `gemini.py` — `gemini_chat()` for structured JSON output via
  `response_schema=PydanticModel`; `gemini_chat_with_tools()` implementing
  a manual function-calling loop with combined tool use + schema
  validation, bounded by `max_tool_iterations`.
- `groq_client.py` — `groq_chat()` mirroring the Gemini signature for
  fallback paths.
- `tmdb.py` — async TMDB v3 client with `search_movie`, `get_movie`,
  trailer URL extraction from `/movie/{id}/videos`, and
  `discover_popular()` for the seed script.
- `spotify.py` — Client Credentials flow with token cache,
  `search_track`, `search_artist`, `get_artist_top_tracks`, and a
  404-tolerant `get_related_artists()`.

**HTTP routes (`app/routes/`)**
- `POST /query` — SSE-streamed orchestrator with `ack` → `node_done` → `final` event sequence.
- `POST /playlist` — JSON endpoint producing a curated `Playlist`.
- `POST /feedback` — thumbs vote that looks up genres in `embeddings` and appends to liked/disliked.
- `POST /signin` — Google ID token verification via tokeninfo + memory migration.
- `GET /me` — taste profile snapshot (counts, top genres, recent moods, recent queries).
- `DELETE /me` — wipes session memory + conversation history.
- `POST /share` — allocates 8-char base32 short code, persists pairing.
- `GET /share/{short_code}` — public read for shared pairings.
- `GET /health`, `GET /health/db` — health checks.

**Middleware (`app/middleware/`)**
- `rate_limit.py` — `slowapi`-based 10 req/hr per-IP limiter on
  `/query` and `/playlist`.
- `daily_cap.py` — `check_daily_cap()` FastAPI dependency that returns
  the pre-built `CAP_REACHED_REC` when `DAILY_QUERY_CAP` is exceeded.

**Data layer**
- `migrations/001_init.sql` — `embeddings` (pgvector HNSW indexed),
  `user_memory`, `api_cache`, `conversations`, `daily_usage` tables.
- `migrations/002_shared_pairings.sql` — public share table with
  `short_code` PK and `created_at` index.
- `app/memory.py` — `get_memory`, `get_all_memory`, `set_memory`,
  `append_to_list` (with dedupe), `migrate_memory`.
- `app/cache.py` — `cache_get`/`cache_set` + `@cached` decorator.
- `app/usage.py` — `increment_llm_calls`, `is_over_daily_cap`.
- `app/conversation.py` — `load_recent_turns`, `append_turn`,
  `summarise_for_prompt` for conversational follow-up.

**Seed scripts (`scripts/`)**
- `migrate.py` — idempotent migration runner backed by a `_migrations`
  table.
- `seed_movies.py` — pulls ~5k popular movies from TMDB across 4 sort
  orders, embeds `overview` field, upserts on `tmdb_id`.
- `seed_music.py` — pulls top tracks across ~30 Spotify genres,
  generates one-paragraph "vibe descriptions" via Gemini (cached to
  `.vibe_cache.json` for idempotent re-runs), embeds and upserts on
  `spotify_uri`.

**Frontend (`frontend/`)**
- Next.js 16 App Router app with Tailwind + Framer Motion.
- `<Chat />` chat shell with SSE streaming, status transitions, and
  optimistic mutations.
- Card components: `MovieCard`, `MusicCard`, `PairingNote`,
  `RecommendationBlock`, `PlaylistBlock`.
- Interactions: `VoteButtons` (optimistic thumbs), `PreviewPlayer`
  (Spotify 30s preview), `MoodSpectrum` (3-axis nudge buttons that
  re-query via follow-up), `ShareButton` (clipboard-copy short link).
- `<TasteProfilePanel />` slide-over showing counts, top liked/disliked
  genres, recent moods, clickable recent queries, and a two-step
  reset button.
- `<SignInButton />` Google one-tap that gracefully hides when
  `NEXT_PUBLIC_GOOGLE_CLIENT_ID` is unset.
- Public page `/p/[code]` for shared pairings — server-rendered, no
  session state.
- `lib/queryClient.ts` — fetch-based SSE parser (since `EventSource`
  is GET-only).

**Tooling and ops**
- `docker-compose.yml` — local Postgres + pgvector on host port 15432
  to avoid clashing with system Postgres installs.
- `backend/Dockerfile` + `backend/railway.toml` for Railway deployment.
- `frontend/vercel.json` for Vercel deployment.
- `DEPLOY.md` covering both deploys + a 7-step post-deploy smoke test
  with eval-harness acceptance criteria.
- `uv`-based Python dependency management (`backend/pyproject.toml`
  with `[dependency-groups].dev`, `uv.lock` committed).

**Quality**
- 121 backend tests across schemas, agents, clients, routes,
  middleware, and the tool-calling loop.
- Ruff linting + formatting configured in `pyproject.toml`.
- `evals/` harness — 25 hand-curated queries in `queries.csv`, scoring
  module in `scoring.py` (mood substring + genre overlap), SSE-consuming
  runner in `run.py` that writes per-release JSON artifacts.

**Documentation**
- `PRD.md` v2.1 — product spec.
- `PLAN.md` — 34-task DAG with branch naming convention.
- `prd-fixes.md` — v1 → v2 change log.
- Per-task squash commits on `main` (~36 commits).

### Changed

- **Output schema (v2.0 → v2.1):** `Recommendation` was restructured
  from `{movies: list[MovieRec], music: list[MusicRec], pairing_note: str}`
  to `{pairings: list[Pairing], fallback_message: str | None}`, where
  each `Pairing` carries its own movie + music + note. The ranker now
  returns **3 distinct pairings** per query rather than one. Frontend
  components, eval scoring, and PRD §8 example updated accordingly.
- **Tool calling** added to both LLM-touching agents (Profiler +
  Ranker). Was a previously claimed PRD skill that the implementation
  did not yet honour.
- **Next.js bumped to 16.2.6** from initial scaffold (14.2.18) to
  resolve security advisories. `eslint` bumped to 9 to satisfy
  `eslint-config-next@16` peer requirement.
- **Backend package manager** switched to `uv` from a placeholder
  pip workflow; `[dependency-groups].dev` replaces
  `[project.optional-dependencies].dev`.
- **Local Postgres host port** moved from 5432 → 15432 in
  `docker-compose.yml` to avoid conflicts with any existing system
  Postgres install on the dev machine.

### Fixed

- **Squash-merge gotcha:** the workflow documented in
  `PLAN.md::Git Workflow` and reinforced in `prd-fixes.md` — never
  push feature branches that were already squash-merged locally, since
  re-PRing them would silently revert later changes to shared files.
- **Spotify deprecations:** the PRD originally relied on
  `/recommendations` and `/audio-features`. These were dropped for new
  Client Credentials apps. Music similarity is now handled entirely
  by the pgvector RAG corpus; Spotify is used only for search +
  enrichment.
- **YouTube Data API dependency removed:** TMDB's `/movie/{id}/videos`
  already returns YouTube trailer keys, so the redundant YouTube
  client (and its quota cost) was eliminated.
- **Embedding dimension:** initial schema used `VECTOR(1536)`
  (OpenAI ada-002). Changed to `VECTOR(768)` to match the actual
  embedding model (Gemini `text-embedding-004`).

### Removed

- The deprecated `movies` / `music` top-level arrays on `Recommendation`
  — replaced by `pairings` (see *Changed* above).
- The `pairing_note` top-level field on `Recommendation` — moved into
  `Pairing.pairing_note` (per-pairing). System-level messages now use
  the new `fallback_message` field instead.
- The original pre-uv `[project.optional-dependencies]` block in
  `backend/pyproject.toml`.

---

> ⚠️ Assumption: no prior tagged releases exist in git. If you'd like
> to retroactively tag earlier per-wave milestones (Wave 0 → Wave 7
> from `PLAN.md`), do so on the existing squash commits before pushing
> the `v1.0.0` tag — otherwise `git describe` will show all 36 commits
> as part of v1.0.0.
