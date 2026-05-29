# CineSound — Implementation Plan (Task DAG)

Tasks are grouped into **waves**. Every task in a wave can run in parallel; a wave cannot start until all tasks in earlier waves it depends on are complete.

Each task has explicit dependencies (`deps:`) so individual tasks can be assigned to parallel agents without needing the wave grouping if you prefer to dispatch by dependency only.

---

## Prerequisites (human, not agent)

Complete these before Wave 0. Store all secrets in `backend/.env` and `frontend/.env.local`.

- [ ] Create Neon project → `DATABASE_URL`
- [ ] TMDB API key → `TMDB_API_KEY`
- [ ] Spotify developer app (Client Credentials) → `SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET`
- [ ] Google AI Studio API key → `GEMINI_API_KEY`
- [ ] Groq API key → `GROQ_API_KEY`
- [ ] Google Cloud OAuth Client ID (for one-tap sign-in) → `GOOGLE_CLIENT_ID`
- [ ] Vercel account linked to GitHub
- [ ] Railway account linked to GitHub

---

## Git Workflow

Each task gets its own branch. Branches are short-lived, single-purpose, and merge back to `main` via PR before any dependent task starts.

**Branch naming:** `feat/t{NN}-{kebab-title}`
Examples:
- T01 → `feat/t01-backend-scaffold`
- T13 → `feat/t13-movie-seed-script`
- T19 → `feat/t19-query-endpoint`

**Rules for parallel agents:**

1. **Always branch from `main`.** Never branch from another task's feature branch — even when there's a dependency. Wait for the upstream task to merge to `main`, then branch from there. This keeps the graph flat and prevents compounding merge conflicts.
2. **One task = one branch = one PR.** No multi-task branches. If you discover a task is too big mid-flight, split it and open a follow-up task rather than ballooning the branch.
3. **Rebase before merging.** If `main` advanced while you worked, `git rebase main` and resolve conflicts on your branch — do not merge `main` into the feature branch.
4. **Squash merge to `main`.** One commit per task on the main history. PR title = task title; PR body links the task ID.
5. **Delete the branch after merge.** Keeps the remote tidy and makes the active work surface visible at a glance.
6. **Dependency handshake.** A task is only ready to start when *every* branch it depends on is merged to `main`. Agents should poll `main` (or read the merged-PR list) rather than coordinating directly.
7. **CI gate on `main`.** Lint + type-check + the relevant test for that task must pass before merge. No green CI = no merge, no matter how urgent the dependent task is.
8. **Never force-push to `main`.** Force-push on your own feature branch is fine pre-merge; never on `main`.

**Initial setup (one-time, before Wave 0):**
- `git init`, push initial commit to GitHub with `main` as default
- Protect `main`: require PR + green CI
- Add `.gitignore` covering `.env`, `node_modules/`, `__pycache__/`, `.next/`, `evals/runs/`, `backend/scripts/.vibe_cache.json`

---

## Wave Overview

```
Wave 0  ── Scaffold ────────────────┐
           T01  T02  T03  T30        │
                                     ▼
Wave 1  ── Integrations ────────────┐
           T04  T05  T06  T07  T08  T09
                                     ▼
Wave 2  ── Data layer + seed ───────┐
           T10  T11  T12  T13  T14   │
                                     ▼
Wave 3  ── Agents ──────────────────┐
           T15  T16  T17 → T18       │
                                     ▼
Wave 4  ── API endpoints ───────────┐
           T19  T20  T21  T22  T23   │
                                     ▼
Wave 5  ── Frontend ────────────────┐
           T24  T25  T26  T27  T28   │
                                     ▼
Wave 6  ── Eval ────────────────────┐
           T31                       │
                                     ▼
Wave 7  ── Deploy
           T32  T33 → T34
```

Tasks marked with **★** are on the critical path. Others can slip without delaying the project.

---

## Wave 0 — Scaffold (4 parallel)

### T01 ★ — Backend scaffold
**deps:** none
**scope:** FastAPI app skeleton with `/health` endpoint, async startup, env loading via `pydantic-settings`.
**output:** `backend/`, `backend/app/main.py`, `backend/pyproject.toml`, `backend/.env.example`
**done when:** `uvicorn app.main:app` runs locally; `GET /health` returns `{"status":"ok"}`.

### T02 ★ — Frontend scaffold
**deps:** none
**scope:** Next.js 14 app with App Router, Tailwind, shadcn/ui initialised, Framer Motion installed.
**output:** `frontend/`, base `app/layout.tsx`, `app/page.tsx` placeholder
**done when:** `npm run dev` renders an empty styled page.

### T03 ★ — Database schema migration
**deps:** none
**scope:** SQL migration file matching §7 of `PRD.md` (5 tables + HNSW index + cache expiry index). Apply via a simple `scripts/migrate.py`.
**output:** `backend/migrations/001_init.sql`, `backend/scripts/migrate.py`
**done when:** running migrate against the Neon URL creates all tables; `\d embeddings` shows the HNSW index.

### T30 — Eval query set
**deps:** none (can be authored anytime)
**scope:** Hand-write 25 rows into `evals/queries.csv` with columns `query, expected_mood, acceptable_movie_genres, acceptable_music_genres`. Cover the three example query styles from PRD §3.1 plus edge cases (vague mood, single artist, single film).
**output:** `evals/queries.csv`
**done when:** 25 rows committed; each row is a plausible user query with at least 2 acceptable genres per domain.

---

## Wave 1 — Core integrations (6 parallel)

### T04 ★ — Postgres connection layer
**deps:** T01, T03
**scope:** `asyncpg` pool initialised on FastAPI startup, exposed via dependency injection.
**output:** `backend/app/db.py`
**done when:** a smoke endpoint can `SELECT 1` from Neon.

### T05 ★ — TMDB client
**deps:** T01
**scope:** Async wrapper with methods `search_movie`, `get_movie`, `get_videos`, `discover_popular`. Use `/movie/{id}/videos` for trailers (filter `site=YouTube`, `type=Trailer`). No YouTube Data API.
**output:** `backend/app/clients/tmdb.py`
**done when:** unit test fetches "Interstellar" and returns trailer URL.

### T06 ★ — Spotify client
**deps:** T01
**scope:** Client Credentials flow with token refresh. Methods: `search_track`, `get_artist`, `get_artist_top_tracks`, `get_related_artists` (catch 404 gracefully — endpoint deprecation risk). No `/recommendations` or `/audio-features` calls.
**output:** `backend/app/clients/spotify.py`
**done when:** unit test fetches "Hans Zimmer" and returns top tracks.

### T07 ★ — Gemini client + embedding helper
**deps:** T01
**scope:** Two callables: `gemini_chat(messages, model, response_schema)` returning parsed Pydantic instance via `response_mime_type=application/json`, and `embed(texts: list[str]) -> list[list[float]]` using `text-embedding-004` (768d). Batch up to 100 texts per embedding call.
**output:** `backend/app/clients/gemini.py`
**done when:** can embed a string and round-trip a structured JSON chat call.

### T08 — Groq client (fallback)
**deps:** T01
**scope:** Thin wrapper around Groq's OpenAI-compatible chat endpoint, same interface as `gemini_chat`. Used by Orchestrator as fallback when Gemini errors.
**output:** `backend/app/clients/groq.py`
**done when:** can complete a chat call against Llama 3.3 70B.

### T09 ★ — Pydantic schemas
**deps:** T01
**scope:** Define all data contracts in one module: `Recommendation` (output schema from PRD §8), `MovieRec`, `MusicRec`, `TasteProfile` (movie_profile, music_profile, shared_mood), `RankerInput`, `Feedback`.
**output:** `backend/app/schemas.py`
**done when:** all schemas validate against the example JSON in PRD §8.

---

## Wave 2 — Data layer + seed (5 parallel)

### T10 ★ — Memory CRUD
**deps:** T04
**scope:** Functions `get_memory(user_id, key)`, `set_memory(user_id, key, value)`, `append_to_list(user_id, key, item)`, `migrate_memory(from_user_id, to_user_id)`. Keys per PRD §3.3.
**output:** `backend/app/memory.py`
**done when:** roundtrip test inserts and retrieves a watch history list; migrate copies all keys.

### T11 — Cache CRUD
**deps:** T04
**scope:** `cache_get(key)` returns parsed JSON or None if expired; `cache_set(key, value, ttl_seconds)`. Used by TMDB and Spotify clients via a `@cached(ttl=...)` decorator.
**output:** `backend/app/cache.py`
**done when:** decorating a TMDB call shows the second invocation skips the network.

### T12 — Daily usage counter
**deps:** T04
**scope:** `increment_llm_calls()` upserts today's row in `daily_usage`; `is_over_daily_cap()` reads `DAILY_QUERY_CAP` env var and compares.
**output:** `backend/app/usage.py`
**done when:** unit test increments and detects cap breach.

### T13 ★ — Movie seed script
**deps:** T05, T07, T04
**scope:** Script that pulls ~5k popular movies from TMDB `/discover/movie` (multiple pages, multiple sort orders), embeds the `overview` field with Gemini, inserts into `embeddings` with `type='movie'` and metadata `{tmdb_id, title, year, genres, trailer_url}`. Idempotent — skip if `tmdb_id` already present.
**output:** `backend/scripts/seed_movies.py`
**done when:** `SELECT count(*) FROM embeddings WHERE type='movie'` ≥ 4000.

### T14 ★ — Music seed script
**deps:** T06, T07, T04
**scope:** Script that pulls top tracks across ~30 Spotify genres, generates a one-paragraph vibe description per track using Gemini Flash (cache LLM outputs to a local JSON file to avoid regeneration on rerun), embeds the description, inserts into `embeddings` with `type='music'` and metadata `{spotify_uri, track, artist, genre, vibe_description}`. Idempotent.
**output:** `backend/scripts/seed_music.py`, `backend/scripts/.vibe_cache.json`
**done when:** `SELECT count(*) FROM embeddings WHERE type='music'` ≥ 2000.

---

## Wave 3 — Agents (3 parallel, then 1)

### T15 ★ — Joint Profiler agent
**deps:** T07, T09, T10
**scope:** Single LLM call. Input: user query + memory snippet (recent moods, disliked genres). Output: `TasteProfile` Pydantic instance. Include 3 few-shot examples in the system prompt for vague, title-based, and artist-based queries.
**output:** `backend/app/agents/profiler.py`
**done when:** "I just finished Interstellar, feeling reflective" returns a profile with `shared_mood` containing "reflective" or "cinematic".

### T16 ★ — Search module
**deps:** T05, T06, T04, T07
**scope:** No LLM. Functions `search_movies(profile)` and `search_music(profile)`:
1. Embed the relevant sub-profile (`text-embedding-004`)
2. pgvector cosine search against `embeddings` (top 20)
3. Optionally enrich with a live TMDB/Spotify call for fresh metadata (cached)
4. Return candidate list

**output:** `backend/app/agents/search.py`
**done when:** given a "reflective sci-fi" profile, returns Arrival/Interstellar/Blade Runner 2049 in top 10.

### T17 ★ — Ranker + Pairer
**deps:** T07, T09, T10
**scope:** Two steps in one module:
1. **Deterministic:** compute similarity score against `TasteProfile`, filter out items in `watched_movies` / `heard_tracks`, keep top 5 per domain
2. **LLM:** single Gemini Flash call takes top candidates + `shared_mood`, returns the final `Recommendation` JSON (1 movie + 1 track + pairing note)

**output:** `backend/app/agents/ranker.py`
**done when:** given matched candidate lists, returns a valid `Recommendation` with a non-empty `pairing_note`.

### T18 ★ — Orchestrator (LangGraph)
**deps:** T15, T16, T17
**scope:** LangGraph state machine:
```
START → load_memory → profile (T15) → search (T16, parallel branches) → rank_and_pair (T17) → save_memory → END
```
Catch Gemini errors at any node and fall back to Groq (T08).
**output:** `backend/app/agents/graph.py`
**done when:** end-to-end invocation with a sample query returns a valid `Recommendation`.

---

## Wave 4 — API endpoints (5 parallel)

### T19 ★ — `POST /query` (SSE streaming)
**deps:** T18, T11, T12, T22, T23
**scope:** Accept `{query: str, session_id: str}`. Apply rate limit + daily cap. Run orchestrator. Stream intermediate progress events (`profile_done`, `search_done`, `final`) via SSE. Append final result to `conversations`.
**output:** `backend/app/routes/query.py`
**done when:** `curl -N` shows incremental events and final JSON.

### T20 — `POST /feedback`
**deps:** T10
**scope:** Accept `{session_id, tmdb_id?, spotify_uri?, vote: "up"|"down"}`. Append to `liked_genres` / `disliked_genres` based on the rec's stored genres.
**output:** `backend/app/routes/feedback.py`
**done when:** thumbs-down on a horror movie appends "Horror" to `disliked_genres`.

### T21 — `POST /signin`
**deps:** T10
**scope:** Verify Google ID token, extract `sub`, call `migrate_memory(session_id, "google:" + sub)`, set new auth cookie.
**output:** `backend/app/routes/signin.py`
**done when:** post-signin, a query returns memory previously written under the anonymous session.

### T22 — Rate limit middleware
**deps:** T01
**scope:** `slowapi` config: 10 requests / hour per IP on `/query`. Return 429 with retry-after header.
**output:** `backend/app/middleware/rate_limit.py`
**done when:** 11th request in an hour returns 429.

### T23 — Daily cap middleware
**deps:** T12
**scope:** Before `/query` runs, check `is_over_daily_cap()`. If true, return a stub `Recommendation` JSON with `pairing_note: "Demo limit reached, try tomorrow."`
**output:** `backend/app/middleware/daily_cap.py`
**done when:** setting `DAILY_QUERY_CAP=0` makes every request return the stub.

---

## Wave 5 — Frontend (5 parallel after T19 contract is stable)

### T24 ★ — Chat UI shell
**deps:** T02
**scope:** Single-page chat layout: input box bottom-fixed, message list scrolling, header with sign-in slot. Manage `session_id` cookie client-side (generate UUID on first load).
**output:** `frontend/app/page.tsx`, `frontend/components/Chat.tsx`
**done when:** typing and submitting echoes a placeholder response.

### T25 ★ — Recommendation cards
**deps:** T02, T09 (use schema as TypeScript types via codegen or hand-port)
**scope:** Two card components matching PRD §8 schema. Movie card shows poster (TMDB image URL), title, year, rating, genres, reason, trailer button. Music card shows album art, track, artist, mood tag, reason, Spotify button. Pairing note rendered as a styled callout between/below cards.
**output:** `frontend/components/MovieCard.tsx`, `MusicCard.tsx`, `PairingNote.tsx`
**done when:** Storybook or local mock renders cleanly with the PRD §8 example JSON.

### T26 ★ — SSE client integration
**deps:** T24, T25, T19
**scope:** Fetch streaming response from `/query`, render progressive states ("Thinking...", "Searching...", final cards) with Framer Motion transitions.
**output:** `frontend/lib/queryClient.ts`, wire into `Chat.tsx`
**done when:** submitting a query streams progress and lands on rendered cards.

### T27 — Thumbs feedback UI
**deps:** T25, T20
**scope:** Up/down buttons on each card; on click, POST to `/feedback` and show a brief confirmation. Optimistic UI.
**output:** updates to `MovieCard.tsx` / `MusicCard.tsx`, `frontend/lib/feedback.ts`
**done when:** clicking thumbs-down on a card persists to DB and shows confirmation.

### T28 — Google sign-in button
**deps:** T24, T21
**scope:** `@react-oauth/google` one-tap component in header. On success, POST ID token to `/signin`.
**output:** `frontend/components/SignInButton.tsx`
**done when:** signing in then refreshing keeps memory (verified via a follow-up query).

---

## Wave 6 — Eval (1 task)

### T31 ★ — Eval harness + runner
**deps:** T19, T30
**scope:** Script reads `evals/queries.csv`, calls `/query` for each row, scores:
- (a) mood detection: substring or embedding similarity ≥ 0.7
- (b) genre overlap: ≥1 acceptable genre per domain
- (c) pairing quality: write 1–5 score by hand into `evals/runs/<date>.csv` after the auto-run

Outputs `evals/runs/<date>.json` with per-row results and aggregate metrics.
**output:** `evals/run.py`, `evals/runs/<date>.json`
**done when:** running against localhost produces a scored JSON file.

---

## Wave 7 — Deploy

### T32 ★ — Backend deploy (Railway)
**deps:** all backend tasks (T19–T23)
**scope:** `railway.json` or `Procfile`, env vars wired in Railway dashboard, Postgres URL pointing at Neon. Auto-deploy on `main` branch push.
**output:** `backend/railway.json`, deployment URL
**done when:** `curl <railway-url>/health` returns ok.

### T33 ★ — Frontend deploy (Vercel)
**deps:** all frontend tasks (T26–T28)
**scope:** Set `NEXT_PUBLIC_API_URL` to Railway URL, link GitHub repo, configure build. Auto-deploy on `main`.
**output:** Vercel project linked, deployment URL
**done when:** Vercel URL loads the chat UI.

### T34 ★ — Smoke test against prod
**deps:** T32, T33
**scope:** Run T31's eval harness against the deployed Vercel URL. Verify: cards render, feedback persists, sign-in works, no errors in Railway logs.
**output:** `evals/runs/<date>-prod.json`
**done when:** all 25 eval queries return valid `Recommendation` JSON from prod.

---

## Parallelization summary for agents

If you can run **3 agents in parallel**, sensible groupings:

- **Wave 0:** assign T01, T02, T03 to three agents; T30 as a side task.
- **Wave 1:** group A (T04, T05), group B (T06, T07), group C (T08, T09).
- **Wave 2:** group A (T10, T11, T12), group B (T13), group C (T14).
- **Wave 3:** T15, T16, T17 in parallel; T18 sequential after.
- **Wave 4:** T22, T23 first (middleware); then T19, T20, T21 in parallel.
- **Wave 5:** T24, T25 first; then T26, T27, T28 in parallel.
- **Wave 6 / 7:** sequential.

Critical-path length is ~9 task-depths. With perfect parallelism and well-scoped agents, the build is achievable in roughly that many focused work sessions.
