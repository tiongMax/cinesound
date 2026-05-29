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

---

## Frontend → Vercel

The frontend lives in `frontend/`. Vercel auto-detects Next.js; `frontend/vercel.json` is only there for the framework hint.

### One-time setup

1. **Import the repo** at https://vercel.com/new → pick `tiongMax/cinesound`.
2. **Set the Root Directory** to `frontend` (Configure Project → Root Directory).
3. **Environment variables** (Project → Settings → Environment Variables):
   | Key | Value |
   |---|---|
   | `NEXT_PUBLIC_API_URL` | `https://<your-railway-url>` (no trailing slash) |
   | `NEXT_PUBLIC_GOOGLE_CLIENT_ID` | Google OAuth Web Client ID (Authorized origin must include the Vercel URL) |
4. **Deploy**. Vercel returns a `.vercel.app` URL.
5. **Go back to Railway** and add the Vercel URL to the backend's `CORS_ORIGINS` env var as a JSON list: `["https://<your-app>.vercel.app"]`. Trigger a backend redeploy.

### What happens on each push to `main`

- Vercel builds `next build` from the `frontend/` root, deploys to `<project>.vercel.app`, and assigns a preview URL to every non-`main` branch.

### Verifying the deploy

Open the Vercel URL. You should see the CineSound chat shell. Hard reload to clear any stale `session_id` cookie if testing fresh.
