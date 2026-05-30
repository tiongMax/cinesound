# CineSound

> Multi-agent recommendation system that pairs movies with music for a given mood — single natural-language query in, three movie+music pairings out, with an optional 5-track playlist follow-up.

![Tests](https://img.shields.io/badge/tests-121%20passing-brightgreen)
![Python](https://img.shields.io/badge/python-3.11-blue)
![Next.js](https://img.shields.io/badge/next.js-16.2.6-black)
![License](https://img.shields.io/badge/license-unspecified-lightgrey)

> ⚠️ Assumption: No `LICENSE` file exists in the repo. Badges shown as static. Add a CI badge after wiring GitHub Actions.

## What it does

Type a free-form query — "I just finished Interstellar, feeling reflective" — and CineSound runs a LangGraph orchestrator (Joint Profiler → parallel TMDB + Spotify pgvector search → Ranker + Pairer) that returns three distinct movie + music pairings plus a per-pairing note. Cards stream over SSE, each track has a 30-second Spotify preview, and a "Make a playlist" button generates a 5-track vibe-curated follow-up from the same pool. Memory persists per device (cookie) with optional Google one-tap migration to a cross-device user ID.

## Prerequisites

| Tool | Version | Why |
|---|---|---|
| **Docker Desktop** | any recent | Runs Postgres + pgvector locally |
| **Python** | 3.11 (pinned in `backend/.python-version`) | Backend runtime |
| **uv** | 0.11+ | Python package manager (`backend/pyproject.toml`) |
| **Node.js** | 20+ | Frontend build |
| **npm** | 10+ | Frontend deps |

External services needed for full functionality:
- A **Neon** project (or any Postgres 14+ with pgvector) — local Docker provided for dev
- API keys: **TMDB**, **Spotify** (Client ID + Secret), **Google AI Studio** (Gemini)
- Optional: **Groq** (fallback), **Google OAuth Client ID** (sign-in)

## Installation

### 1. Clone and bring up the local database

```bash
git clone https://github.com/tiongMax/cinesound.git
cd cinesound
docker compose up -d     # Postgres + pgvector on host port 15432
```

`docker-compose.yml` uses host port **15432** rather than the default 5432 to avoid clashing with a system Postgres install.

### 2. Backend

```bash
cd backend
uv sync                              # creates .venv, installs runtime + dev deps
cp .env.example .env                 # then fill in your API keys
uv run python -m scripts.migrate     # applies migrations/001_init.sql, 002_shared_pairings.sql
uv run uvicorn app.main:app --reload
```

Verify: `GET http://localhost:8000/health` → `{"status":"ok","env":"dev","db":true}`

### 3. Seed the RAG corpus

```bash
# from backend/
uv run python -m scripts.seed_movies --target 300       # ~5 min, small dev corpus
uv run python -m scripts.seed_music --per-genre 10      # ~5 min
```

For a production-sized corpus, drop the flags: `seed_movies` targets 5,000 titles, `seed_music` targets ~1,500 tracks across 30 genres.

### 4. Frontend

```bash
cd frontend
npm install
cp .env.local.example .env.local     # set NEXT_PUBLIC_API_URL=http://localhost:8000
npm run dev
```

Open http://localhost:3000.

## Usage examples

### Query the recommendation API directly

```bash
curl -N -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query":"I just finished Interstellar, feeling reflective","session_id":"demo:1"}'
```

The endpoint streams SSE events. The final `Recommendation` payload matches `app/schemas.py::Recommendation`:

```json
{
  "mood_detected": "reflective, cinematic",
  "pairings": [
    {
      "movie": { "tmdb_id": 329865, "title": "Arrival", "year": 2016, "genres": ["Sci-Fi", "Drama"], "reason": "...", "trailer_url": "..." },
      "music": { "spotify_uri": "spotify:track:...", "track": "Day One", "artist": "Hans Zimmer", "mood_tag": "cinematic ambient", "reason": "...", "spotify_url": "...", "preview_url": "..." },
      "pairing_note": "Listen to Hans Zimmer while watching Arrival for the full effect."
    }
  ],
  "fallback_message": null
}
```

### Build a 5-track playlist for any mood

```bash
curl -X POST http://localhost:8000/playlist \
  -H "Content-Type: application/json" \
  -d '{"query":"rainy sunday afternoon","session_id":"demo:1","length":5}'
```

### Run the eval harness

```bash
# from backend/
uv run python ../evals/run.py --url http://localhost:8000 --label local
```

Runs the 25 hand-curated queries in `evals/queries.csv` through `/query`, scores mood detection + genre overlap, and writes `evals/runs/<timestamp>-local.json`.

### Consume the SSE stream from a TypeScript client

The frontend's `streamQuery()` in `frontend/lib/queryClient.ts` shows the wire-format parser:

```ts
import { streamQuery } from "@/lib/queryClient";

await streamQuery("upbeat friday night", "demo:1", {
  onNode:  (node) => console.log("milestone:", node),
  onFinal: (rec)  => console.log("got pairings:", rec.pairings.length),
  onError: (msg)  => console.error(msg),
});
```

## Environment variables

### Backend (`backend/.env`)

| Variable | Description | Required | Default |
|---|---|---|---|
| `APP_ENV` | Environment tag returned in `/health` (`dev`, `prod`, etc.) | optional | `dev` |
| `DATABASE_URL` | Postgres connection string with pgvector extension available | **required** | `postgres://cinesound:cinesound@localhost:15432/cinesound` (matches `docker-compose.yml`) |
| `TMDB_API_KEY` | TMDB v3 API key for movie search + details | **required** | — |
| `SPOTIFY_CLIENT_ID` | Spotify app client ID (Client Credentials flow) | **required** | — |
| `SPOTIFY_CLIENT_SECRET` | Spotify app client secret | **required** | — |
| `GEMINI_API_KEY` | Google AI Studio API key for Gemini 2.5 Flash + `text-embedding-004` | **required** | — |
| `GROQ_API_KEY` | Groq API key for Llama 3.3 70B fallback when Gemini errors | optional | — |
| `GOOGLE_CLIENT_ID` | OAuth Web Client ID for one-tap sign-in; if unset, `/signin` returns 500 and the frontend hides the button | optional | — |
| `DAILY_QUERY_CAP` | Max LLM calls per day before `/query` and `/playlist` return the stub `CAP_REACHED_REC` (see `app/middleware/daily_cap.py`) | optional | `500` |
| `CORS_ORIGINS` | JSON list of allowed origins for the FastAPI CORS middleware | optional | `["http://localhost:3000"]` |

### Frontend (`frontend/.env.local`)

| Variable | Description | Required | Default |
|---|---|---|---|
| `NEXT_PUBLIC_API_URL` | Base URL of the FastAPI backend | **required** | `http://localhost:8000` |
| `NEXT_PUBLIC_GOOGLE_CLIENT_ID` | OAuth Client ID matching backend `GOOGLE_CLIENT_ID`; if unset, `<SignInButton />` renders nothing | optional | — |

## Project layout

```
backend/        FastAPI + LangGraph + uv
  app/
    agents/     profiler · search · ranker · graph · playlist · tools
    clients/    gemini · groq_client · tmdb · spotify
    middleware/ rate_limit · daily_cap
    routes/     query (SSE) · feedback · signin · me · playlist · share
  migrations/   001_init.sql · 002_shared_pairings.sql
  scripts/      migrate · seed_movies · seed_music
frontend/       Next.js 16 + Tailwind + Framer Motion
  app/          page.tsx (Chat), p/[code]/page.tsx (shared pairing view)
  components/   Chat · RecommendationBlock · MovieCard · MusicCard · PairingNote
                · PreviewPlayer · VoteButtons · TasteProfilePanel · PlaylistBlock
                · MoodSpectrum · ShareButton · SignInButton
  lib/          queryClient · feedback · session · me · playlist · share · types
evals/          queries.csv · scoring.py · run.py
docker-compose.yml
DEPLOY.md       Railway + Vercel + post-deploy smoke test
PRD.md  PLAN.md  prd-fixes.md
```

## License

> ⚠️ Assumption: no `LICENSE` file is present in the repo. Add one before public distribution; this README's badge should be updated to match (MIT recommended for portfolio projects).
