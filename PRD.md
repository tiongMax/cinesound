# Product Requirements Document
# CineSound — AI Entertainment Recommendation Agent

**Version:** 2.0
**Author:** CineSound Project
**Status:** Draft

---

## 1. Overview

### 1.1 Product Summary

CineSound is a multi-agent AI chatbot that delivers personalised movie and music recommendations in a single, unified experience. The user describes their mood, a recent watch, or a genre preference — and CineSound responds with matched film and music suggestions, complete with a cross-domain pairing note explaining why the two complement each other.

### 1.2 Problem Statement

Existing recommendation tools (Netflix, Spotify) operate in silos. Users who finish a film and want music that matches the same emotional tone, or who want a movie to match a playlist mood, have no single tool that bridges both. CineSound fills this gap.

### 1.3 Goals

- Deliver polished, paired movie + music recommendations from a single natural language query
- Demonstrate production-grade AI engineering skills for portfolio purposes
- Deploy publicly as a live, shareable project

### 1.4 Non-Goals

- Not a streaming platform — no media playback
- Not a social platform — no required user accounts in v1 (optional sign-in only)
- Not targeting high-volume production traffic in v1

---

## 2. Target Users

| User | Description |
|---|---|
| Primary | The developer (portfolio showcase for SWE interviews) |
| Secondary | Interviewers and recruiters evaluating the live demo |
| Tertiary | General public who discover the deployed app |

---

## 3. Core Features

### 3.1 Natural Language Input
Users type free-form queries such as:
- *"I just finished Interstellar, feeling reflective"*
- *"Something fun and upbeat for a Friday night"*
- *"I love Kendrick Lamar, what should I watch?"*

The agent handles vague, mood-based, or title-based inputs equally. Every query returns both a movie and a music recommendation — there is no single-domain mode.

### 3.2 Cross-Domain Recommendations
Every response returns both a movie and music recommendation, paired intentionally:
- Movie card: title, year, rating, genre, reason, trailer link, `tmdb_id`
- Music card: track/artist/album, mood tag, reason, Spotify link, `spotify_uri`
- Pairing note: one sentence explaining why the two complement each other
- Thumbs up / thumbs down on each card → feeds back into the taste profile

### 3.3 Device-Persistent Memory
The system remembers across sessions on the same device via an anonymous `session_id` cookie (1-year expiry):
- Watch history (to avoid re-recommending) — keyed by `tmdb_id`
- Heard tracks — keyed by `spotify_uri`
- Liked and disliked genres (from thumbs feedback)
- Dietary or content preferences (e.g. no horror, no explicit lyrics)
- Past mood patterns

**Optional sign-in:** a "Save your taste profile" button triggers Google one-tap sign-in. Cookie memory is migrated to a user ID, enabling cross-device persistence. Sign-in is never required to use the product.

### 3.4 Taste Profiling
Each query updates a live taste profile. A single Joint Profiler agent extracts:
- Themes and mood from the input
- Movie genre signals
- Music energy level (calm, upbeat, intense) and genre signals
- A shared mood label that bridges both domains

### 3.5 Structured Output
All responses are returned as validated JSON (Pydantic schema), rendered as clean recommendation cards in the UI — not raw text.

---

## 4. Agent Architecture

```
User Query
    ↓
🧠 Orchestrator Agent
   ├── Reads user memory
   └── Forwards query + memory context to profiler
         ↓
🎭 Joint Taste Profiler   (1 LLM call)
   → returns movie_profile + music_profile + shared_mood
         ↓
🔍 Search (parallel, no LLM)
   ├── TMDB API + pgvector (movie candidates)
   └── Spotify API + pgvector (music candidates)
         ↓
🏆 Ranker + Pairer        (1 LLM call)
   ├── Deterministic: cosine score + filter watched/heard
   └── LLM: pick final movie + track, write pairing note
         ↓
📦 Structured JSON Output
```

Three LLM calls maximum per query (Orchestrator routing, Joint Profiler, Ranker+Pairer).

### 4.1 Agent Descriptions

**Orchestrator Agent**
Reads memory context and forwards the query to the Joint Profiler. Lightweight routing only.

**Joint Taste Profiler**
Single LLM call that extracts themes, mood, genre signals, and energy level for both movie and music domains. Returns:
```json
{
  "movie_profile": { "themes": [...], "genres": [...], "mood": "..." },
  "music_profile": { "energy": "...", "genres": [...], "mood": "..." },
  "shared_mood": "reflective, cinematic"
}
```

**Search (shared, no LLM)**
Calls TMDB API for movie data and Spotify Web API for tracks/artists/albums. Queries the pgvector store for semantic similarity matches against the seed corpus. Returns top-N candidates per domain.

**Ranker + Pairer**
Deterministic step scores candidates by cosine similarity to the taste profile and filters out anything in `watched_movies` / `heard_tracks`. The top-N survivors are passed to a single LLM call that selects the final movie and track and writes the pairing note in one structured JSON response.

---

## 5. AI Skills Demonstrated

| Skill | Implementation |
|---|---|
| Multi-Agent Orchestration | LangGraph — directed graph routing across agents |
| Tool Calling | TMDB API, Spotify Web API |
| RAG | pgvector semantic search over movie plots and music vibe descriptions |
| Memory | PostgreSQL-backed conversation and preference memory |
| Prompt Engineering | Per-agent system prompts with few-shot examples for edge cases |
| Structured Output | Pydantic models enforcing schema on every LLM response |
| Evaluation | Hand-curated eval set with scored runs committed to repo |

---

## 6. Tech Stack

### 6.1 Frontend
| Component | Technology |
|---|---|
| Framework | Next.js 14 |
| Styling | Tailwind CSS |
| UI Components | shadcn/ui |
| Animations | Framer Motion |
| Deployment | Vercel (free tier) |

### 6.2 Backend
| Component | Technology |
|---|---|
| Framework | FastAPI (Python 3.11) |
| Agent Framework | LangGraph |
| LLM (primary) | Gemini 2.5 Flash (Google AI Studio free tier) |
| LLM (fast/lightweight) | Groq — Llama 3.3 70B (free tier) |
| Embeddings | Gemini `text-embedding-004` (768d, free tier) |
| Rate limiting | `slowapi` middleware |
| Deployment | Railway ($5/mo credit, no spindown) |

### 6.3 Data Layer
| Purpose | Technology |
|---|---|
| Vector search (RAG) | PostgreSQL + pgvector extension (HNSW index) |
| User memory | PostgreSQL (JSONB) |
| API response cache | PostgreSQL (JSONB) |
| Hosting | Neon (serverless Postgres, free tier) |

### 6.4 External APIs
| Data | API | Cost |
|---|---|---|
| Movies | TMDB API (includes YouTube trailer keys via `/movie/{id}/videos`) | Free |
| Music | Spotify Web API (Client Credentials) | Free |

Spotify endpoints used:
- `GET /search` — track/artist/album lookup
- `GET /artists/{id}` and `/artists/{id}/top-tracks`
- `GET /artists/{id}/related-artists` *(verify availability before Day 1)*

The deprecated `/recommendations` and `/audio-features` endpoints are **not** used. Music similarity is handled entirely by the RAG seed corpus; Spotify API is used only to enrich results (URL, album art, preview).

---

## 7. Database Schema

```sql
-- RAG: movie and music embeddings
CREATE TABLE embeddings (
    id        SERIAL PRIMARY KEY,
    type      TEXT,           -- 'movie' or 'music'
    title     TEXT,
    metadata  JSONB,          -- rating, genre, urls, tmdb_id/spotify_uri, etc.
    embedding VECTOR(768)
);
CREATE INDEX ON embeddings USING hnsw (embedding vector_cosine_ops);

-- Memory: user preferences and history
CREATE TABLE user_memory (
    user_id    TEXT,          -- session_id cookie OR google sub if signed in
    key        TEXT,          -- 'watched_movies', 'liked_genres', etc.
    value      JSONB,
    updated_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (user_id, key)
);

-- Cache: avoid repeat API calls
CREATE TABLE api_cache (
    cache_key   TEXT PRIMARY KEY,
    response    JSONB,
    expires_at  TIMESTAMP
);
CREATE INDEX ON api_cache (expires_at);

-- Conversation history
CREATE TABLE conversations (
    session_id  TEXT PRIMARY KEY,
    messages    JSONB,
    updated_at  TIMESTAMP DEFAULT NOW()
);

-- Global daily cost cap
CREATE TABLE daily_usage (
    day            DATE PRIMARY KEY,
    llm_call_count INT DEFAULT 0
);
```

---

## 8. Structured Output Schema

```json
{
  "mood_detected": "reflective, emotional, cinematic",
  "movies": [
    {
      "tmdb_id": 329865,
      "title": "Arrival",
      "year": 2016,
      "rating": 7.9,
      "genres": ["Sci-Fi", "Drama"],
      "reason": "Same emotional sci-fi depth as Interstellar",
      "trailer_url": "https://youtube.com/watch?v=..."
    }
  ],
  "music": [
    {
      "spotify_uri": "spotify:track:...",
      "track": "Day One",
      "artist": "Hans Zimmer",
      "album": "Interstellar OST",
      "mood_tag": "cinematic ambient",
      "reason": "Matches your reflective mood",
      "spotify_url": "https://open.spotify.com/track/..."
    }
  ],
  "pairing_note": "Listen to Hans Zimmer while watching Arrival for the full effect."
}
```

`tmdb_id` and `spotify_uri` are the canonical dedupe keys against `watched_movies` and `heard_tracks` in memory.

---

## 9. Deployment Architecture

```
[Next.js — Vercel]
        ↕  HTTP / SSE streaming
[FastAPI — Railway]
        ↕
[PostgreSQL — Neon]
  pgvector | user_memory | api_cache | daily_usage
```

### 9.1 Deployment Notes
- Frontend auto-deploys to Vercel on every GitHub push
- Backend auto-deploys to Railway on every GitHub push
- Railway free credit ($5/mo) keeps the backend warm — no cold starts
- No Redis required — PostgreSQL handles memory, caching, and vector search at this scale

---

## 10. LLM Cost Strategy

To stay within free tier limits across both Gemini and Groq:

- Single Joint Profiler agent — one LLM call covers movie + music profiling
- Ranker + Pairer combine deterministic scoring with one LLM call for final picks and pairing note
- Cache TMDB and Spotify API responses in PostgreSQL to avoid repeat calls
- Hard target: **3 LLM calls per query maximum**

| Agent | Model | Reason |
|---|---|---|
| Orchestrator | Gemini Flash-Lite | Simple routing |
| Joint Profiler | Gemini Flash | Moderate reasoning |
| Ranker + Pairer | Gemini Flash | Highest quality needed |
| Fallback | Groq Llama 70B | Speed + free backup |

### 10.1 Abuse and Cost Caps
- **Per-IP rate limit:** 10 queries / hour via `slowapi`
- **Daily global cap:** `DAILY_QUERY_CAP` env var; when exceeded, return a cached "demo limit reached, try tomorrow" response
- Counter lives in the `daily_usage` table, incremented on each LLM call

---

## 11. RAG Seed Corpus

Built once, offline, before runtime:

**Movies (~5k rows):**
- Top-rated and popular titles via TMDB `/discover/movie`
- Embed the TMDB `overview` field with Gemini `text-embedding-004`
- Store `{tmdb_id, title, year, genres, overview, trailer_url}` in `embeddings.metadata`

**Music (~2–5k rows):**
- Top tracks across ~30 genres via Spotify `/search`
- For each track, generate a one-paragraph "vibe description" with Gemini Flash (cached to disk to avoid regeneration)
- Embed the vibe description with `text-embedding-004`
- Store `{spotify_uri, track, artist, genre, vibe_description}` in `embeddings.metadata`

Seed scripts live in `scripts/seed_*.py` and are documented in the repo README.

---

## 12. Evaluation

A small, hand-curated eval set is committed to the repo as `evals/queries.csv`:

| Column | Example |
|---|---|
| `query` | "I just finished Interstellar, feeling reflective" |
| `expected_mood` | "reflective, cinematic" |
| `acceptable_movie_genres` | `["Sci-Fi", "Drama"]` |
| `acceptable_music_genres` | `["ambient", "classical", "post-rock"]` |

Each run is scored on:
- **(a)** Mood detection match (substring / semantic similarity)
- **(b)** Genre overlap between recommendation and acceptable set
- **(c)** Human-graded pairing quality (1–5)

Results are committed to `evals/runs/<date>.json`. The README links to the latest run — this is the interview talking point.

---

## 13. Success Criteria

- Single query returns paired movie + music recommendation in under 10 seconds (warm backend)
- Memory persists correctly across sessions on the same device
- Optional sign-in migrates memory across devices without data loss
- All AI engineering skills (§5) are clearly demonstrable in the codebase
- Eval harness produces scored runs that improve over time
- App is publicly accessible via a Vercel URL
- No crashes during a standard interview demo flow

---

## 14. Future Enhancements (v2)

- Spotify OAuth — add recommended tracks directly to user's playlist
- Watchlist export — push movies to a Letterboxd or Notion list
- Weekly digest — email summary of new recommendations based on taste profile
- Mood-based playlist generation — full playlist, not just one track
- Multi-language support
