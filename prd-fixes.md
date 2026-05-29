# CineSound PRD — Proposed Fixes

Concrete fixes for each issue raised in the PRD review, in the same order.

## Blockers

### 1. Architecture vs. cost strategy
Collapse to one "Taste Profiler" agent that returns joint JSON:

```json
{ "movie_profile": {...}, "music_profile": {...}, "shared_mood": "..." }
```

Update §4 diagram: Orchestrator → Joint Profiler → (parallel TMDB + Spotify + pgvector tool calls, no LLM) → Ranker. Three LLM calls total, matches §10.

### 2. Embedding dimension
Switch to Gemini `text-embedding-004` (768d, free tier, same provider as the LLMs). Change schema to `VECTOR(768)`. Add to §6.2 under "Embeddings: Gemini text-embedding-004."

### 3. Memory without user accounts
Two-tier approach:

- **Default:** anonymous `session_id` cookie, 1-year expiry → device-scoped memory. Rename §3.3 to "Device-Persistent Memory" and be honest about the limitation.
- **Optional:** "Save your taste profile" button → Google one-tap sign-in, migrates cookie memory to user ID. Keeps §1.4 mostly intact (no required accounts) while making cross-device memory work.

### 4. Spotify API deprecations
Re-scope Music Search to what still works for new Client Credentials apps:

- `GET /search` (track/artist/album lookup) ✅
- `GET /artists/{id}` and `/artists/{id}/top-tracks` ✅
- `GET /artists/{id}/related-artists` — **verify status before Day 1**
- Drop any dependency on `/recommendations` and `/audio-features`. Replace with: RAG over the seed corpus does the "find similar music" job; Spotify API is only used to enrich (URL, art, preview).

## Architecture

### 5. Music RAG corpus
Build a 2–5k row seed corpus once, offline:

- Pull top tracks across ~30 genres via Spotify search
- For each, generate a one-paragraph "vibe description" with Gemini Flash (cached to disk), embed it
- Store `{track, artist, genre, vibe_description, spotify_uri}` in `embeddings`

This is an offline task, not runtime. Document the seed script in the repo.

### 6. Drop YouTube API
Remove from §6.4. In the movie tool, use TMDB `/movie/{id}/videos`, filter `site == "YouTube"` and `type == "Trailer"`, build URL as `https://youtube.com/watch?v={key}`. Zero quota cost.

### 7. Split Ranker responsibilities
Make the boundary explicit:

- **Ranker (deterministic, no LLM):** cosine similarity scoring + filter against `watched_movies` / `heard_tracks` → top-N candidates
- **Pairing step (LLM, part of Ranker call):** one Gemini Flash call takes top candidates + user mood, returns final picks + pairing note as one structured JSON

Still one LLM call, but the responsibilities are honest.

## Reality check

### 8. Cold starts
Pick one:

- **Cheap:** Railway $5/mo credit (no spindown) — **recommended**
- **Free but caveat:** Render + add to success criteria "under 10s after warmup; first request of idle session may take 30–60s"

Don't rely on UptimeRobot.

### 9. Add evals
Build an eval harness: a 25-row CSV with `query, expected_mood, acceptable_movie_genres, acceptable_music_genres`. Score each run on:

- (a) mood detection match
- (b) genre overlap
- (c) human-graded pairing quality (1–5)

Commit results to the repo. Mention in README — this is the interview talking point.

### 10. Abuse / cost cap
- Per-IP rate limit: 10 queries / hour (FastAPI `slowapi` middleware)
- Daily global counter in Postgres; if Gemini calls > N, return cached "demo limit reached, try tomorrow" message
- Add `DAILY_QUERY_CAP` env var

## Smaller fixes

- **Indexes:** Add to §7:
  ```sql
  CREATE INDEX ON embeddings USING hnsw (embedding vector_cosine_ops);
  CREATE INDEX ON api_cache (expires_at);
  ```
- **IDs in output schema:** Add `tmdb_id` to each movie, `spotify_uri` to each track. Use these as dedupe keys in memory.
- **Like/dislike capture:** Add thumbs up/down on each card → POST `/feedback` → append to `user_memory.liked_*` / `disliked_*`. Keeps memory grounded in real signal, not just LLM-inferred.
- **Single-domain intent:** Kill it. Product promise is always-paired. Orchestrator skips intent detection; every query gets both. Saves an LLM call too.
