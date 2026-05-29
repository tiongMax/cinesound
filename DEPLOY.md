# CineSound Deployment

Production runs on Railway (backend) + Vercel (frontend) + Neon (Postgres). Free or near-free across all three.

---

## Prerequisites

- GitHub repo: `tiongMax/cinesound` (already pushed)
- Neon project with `DATABASE_URL` (pgvector extension enabled — already done by migration `001_init.sql`)
- API keys: TMDB, Spotify (Client ID + Secret), Gemini, Groq, Google OAuth Client ID
- Seed scripts run once against Neon: `uv run python -m scripts.seed_movies` and `uv run python -m scripts.seed_music`

---

## Backend → Railway

The backend lives in `backend/`. Build is `Dockerfile`-based (`backend/Dockerfile`), config in `backend/railway.toml`.

### One-time setup

1. **Create a Railway project** at https://railway.app (login with GitHub if you haven't).
2. **New Service → Deploy from GitHub repo** → pick `tiongMax/cinesound`.
3. **Set the Root Directory** to `backend` in the service settings. Railway will then find `railway.toml` and `Dockerfile`.
4. **Environment variables** (Service → Variables):
   | Key | Value |
   |---|---|
   | `DATABASE_URL` | Neon connection string |
   | `TMDB_API_KEY` | … |
   | `SPOTIFY_CLIENT_ID` | … |
   | `SPOTIFY_CLIENT_SECRET` | … |
   | `GEMINI_API_KEY` | … |
   | `GROQ_API_KEY` | … |
   | `GOOGLE_CLIENT_ID` | … |
   | `DAILY_QUERY_CAP` | `500` (tune to your free-tier budget) |
   | `CORS_ORIGINS` | `["https://<your-vercel-domain>"]` (JSON list) |
   | `APP_ENV` | `prod` |
5. **Generate a public domain** in Settings → Networking → "Generate Domain". Note the URL — you'll need it for Vercel's `NEXT_PUBLIC_API_URL`.

### What happens on each push to `main`

- Railway pulls the latest `main`, builds the Docker image, runs `python -m scripts.migrate` (idempotent — only pending migrations apply), then starts `uvicorn`.
- Healthcheck hits `/health`; deploys roll back automatically if it fails within 30s.

### Verifying the deploy

```
curl https://<your-railway-url>/health
# → {"status":"ok","env":"prod","db":true}

curl https://<your-railway-url>/health/db
# → {"status":"ok","select_1":1}
```
