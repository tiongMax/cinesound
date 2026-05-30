# CineSound

**Paired movie + music recommendations from a single natural-language query.**

> *"I just finished Interstellar, feeling reflective"* → an Arrival recommendation, a Hans Zimmer track, and a one-sentence note on why they go together.

🎬 [Live demo](#) · 📊 [Eval results](evals/runs/) · 📐 [PRD](PRD.md) · 🗺 [Implementation plan](PLAN.md)

> 🚧 *Demo URL pending deploy; eval run pending seed corpus.*

---

## What it does

Netflix and Spotify operate in silos. CineSound is a multi-agent system that bridges both — describe your mood, a recent watch, or a favourite artist, and you get one movie + one track + a pairing note explaining the cross-domain connection.

A typical query takes 3 LLM calls, hard-capped, and returns in <10s on a warm backend.

## What's actually novel

- **Conversational follow-up** — the orchestrator loads the last 3 turns from the `conversations` table and folds a compact summary into the profiler prompt, so "darker", "another please", "same vibe but uplifting" are interpreted against the most recent recommendation rather than treated as fresh queries.
- **Joint Taste Profiler** — one Gemini call extracts a movie profile *and* a music profile *and* a shared mood, instead of running two independent agents. Cheaper, more coherent recommendations.
- **Deterministic ranker + LLM pairer** — cosine similarity over pgvector ranks candidates; the LLM only handles the pairing prose. Keeps cost predictable and dedupe trivial.
- **LLM tool calling on both LLM-touching agents** — the **Profiler** gets `search_movies_by_title(title)` + `search_artists(name)` to ground itself against real TMDB/Spotify catalogue data when the user references specific titles or artists (instead of hallucinating genres); the **Ranker** gets `get_movie_details(tmdb_id)` + `get_artist_top_tracks(artist_name)` to deep-dive top candidates before picking the final pair. Each agent is capped at 2 tool iterations to keep cost predictable.
- **Committed eval harness** — 25 hand-curated queries scored on mood-match, genre overlap, and (human-graded) pairing quality. Every run lands in `evals/runs/<date>.json` — see [`evals/`](evals/).
- **Graceful fallback** — Gemini errors at the profile or rank step fall back to Groq Llama 70B with the same Pydantic schema, transparent to the caller.

## Example output

```json
{
  "mood_detected": "reflective, emotional, cinematic",
  "pairings": [
    {
      "movie": {
        "tmdb_id": 329865,
        "title": "Arrival",
        "year": 2016,
        "genres": ["Sci-Fi", "Drama"],
        "reason": "Same emotional sci-fi depth as Interstellar",
        "trailer_url": "https://youtube.com/..."
      },
      "music": {
        "spotify_uri": "spotify:track:...",
        "track": "Day One",
        "artist": "Hans Zimmer",
        "mood_tag": "cinematic ambient",
        "reason": "Matches your reflective mood",
        "spotify_url": "https://open.spotify.com/..."
      },
      "pairing_note": "Listen to Hans Zimmer while watching Arrival for the full effect."
    }
  ]
}
```

The ranker returns up to **3 distinct pairings** per query — different points along the shared mood (classic / left-field / palette-cleansing).

## Architecture

```
            POST /query  (SSE stream)
                  │
                  ▼
       ┌──────────────────────┐
       │ LangGraph Orchestrator│
       └──────────┬───────────┘
                  │
        load_memory  ─►  (user_memory JSONB)
                  │
            profile        🧠 Gemini Flash    (1 LLM call)
                  │
       ┌──────────┴──────────┐
       ▼                      ▼
  TMDB + pgvector       Spotify + pgvector   (parallel, no LLM)
       │                      │
       └──────────┬──────────┘
                  ▼
        rank_and_pair    🧠 Gemini Flash    (1 LLM call)
                  │           ↘ on error → Groq Llama 3.3 70B
                  ▼
        save_memory  ─►  (watched, heard, mood, prefs)
                  │
                  ▼
        event: final   { Recommendation JSON }
```

3 LLM calls per query (orchestrator routing, joint profiler, ranker+pairer). Daily call counter caps demo spend.

## How quality is measured

The eval harness in [`evals/`](evals/) reads 25 hand-written queries with expected mood tags + acceptable genre sets, streams each through `/query`, and scores:

| Metric | Threshold |
|---|---|
| Mood detection match (substring) | ≥ 70% |
| Movie genre overlap | ≥ 70% |
| Music genre overlap | ≥ 70% |
| Avg response time | ≤ 10s (warm) |
| Pairing quality (1–5, hand-graded) | filled after the auto-run |

```bash
cd backend
uv run python ../evals/run.py --url https://<prod> --label prod
```

Latest run: [`evals/runs/`](evals/runs/) *(pending first prod run)*

## Tech stack

| Layer | Choice | Why |
|---|---|---|
| Orchestration | LangGraph | `StateGraph` is the cleanest way to wire load_memory → profile → search → rank → save_memory |
| LLM (primary) | Gemini 2.5 Flash | structured-JSON output via `response_schema=PydanticModel` |
| LLM (fallback) | Groq Llama 3.3 70B | low-latency backup when Gemini rate-limits |
| Embeddings | `text-embedding-004` (768d) | same provider as the LLM; free tier |
| Vector DB | Postgres + pgvector (HNSW) | one DB for vectors, memory, cache, conversation history |
| Backend | FastAPI + asyncpg + uv | typed, fast, single-process |
| Frontend | Next.js 16 + Tailwind + Framer Motion | App Router, dark by default, streaming SSE |
| Deploy | Railway (backend) + Vercel (frontend) + Neon (DB) | all on free / $5/mo tiers |

## Run locally

```bash
# from repo root
docker compose up -d                  # Postgres + pgvector on :15432
cp backend/.env.example backend/.env  # fill in TMDB / Spotify / Gemini keys

cd backend
uv sync
uv run python -m scripts.migrate
uv run python -m scripts.seed_movies --target 300   # small seed for testing
uv run python -m scripts.seed_music --per-genre 10  # ~5 min total
uv run uvicorn app.main:app --reload

# in another terminal
cd frontend
cp .env.local.example .env.local      # set NEXT_PUBLIC_API_URL
npm install
npm run dev                           # http://localhost:3000
```

Detailed setup, including production deploy, in [`DEPLOY.md`](DEPLOY.md).

## Project status

- ✅ Wave 0–5: scaffolds, integrations, agents, API, frontend
- ✅ Wave 6: eval harness
- ✅ Wave 7: deploy configs + smoke test plan
- 🚧 First prod deploy + eval run

83 backend tests, ruff-clean, type-checked. Single-developer build over 28 squash-merged commits — see `git log --oneline` for the per-task history.

## Layout

```
backend/           FastAPI service: agents, clients, routes, tests
  app/agents/      profiler · search · ranker · graph (LangGraph)
  app/clients/     gemini · groq · tmdb · spotify
  app/routes/      query (SSE) · feedback · signin
  migrations/      001_init.sql
  scripts/         migrate · seed_movies · seed_music
frontend/          Next.js 16 chat UI
  components/      Chat · MovieCard · MusicCard · PairingNote · VoteButtons · SignInButton
  lib/             queryClient (SSE) · feedback · session · types
evals/             scoring lib + SSE-consuming runner + queries.csv
docker-compose.yml Local Postgres + pgvector
DEPLOY.md          Railway + Vercel + smoke test checklist
PRD.md             Product requirements (v2)
PLAN.md            34-task DAG with branch convention
```
