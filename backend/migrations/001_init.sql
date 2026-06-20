-- CineSound initial schema
-- Tables: embeddings, user_memory, api_cache, conversations, daily_usage
-- See PRD.md §7

CREATE EXTENSION IF NOT EXISTS vector;

-- RAG: movie and music embeddings (Gemini gemini-embedding-001, 768d)
CREATE TABLE IF NOT EXISTS embeddings (
    id        SERIAL PRIMARY KEY,
    type      TEXT NOT NULL CHECK (type IN ('movie', 'music')),
    title     TEXT NOT NULL,
    metadata  JSONB NOT NULL DEFAULT '{}'::jsonb,
    embedding VECTOR(768) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS embeddings_hnsw_idx
    ON embeddings USING hnsw (embedding vector_cosine_ops);

CREATE INDEX IF NOT EXISTS embeddings_type_idx
    ON embeddings (type);

-- Dedupe keys: tmdb_id for movies, spotify_uri for music (stored in metadata)
CREATE UNIQUE INDEX IF NOT EXISTS embeddings_movie_tmdb_id_idx
    ON embeddings ((metadata->>'tmdb_id'))
    WHERE type = 'movie';

CREATE UNIQUE INDEX IF NOT EXISTS embeddings_music_spotify_uri_idx
    ON embeddings ((metadata->>'spotify_uri'))
    WHERE type = 'music';

-- Memory: user preferences and history
-- user_id is either an anonymous session UUID or "google:<sub>" after sign-in
CREATE TABLE IF NOT EXISTS user_memory (
    user_id    TEXT NOT NULL,
    key        TEXT NOT NULL,
    value      JSONB NOT NULL,
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, key)
);

-- Cache: avoid repeat TMDB / Spotify / embedding calls
CREATE TABLE IF NOT EXISTS api_cache (
    cache_key   TEXT PRIMARY KEY,
    response    JSONB NOT NULL,
    expires_at  TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS api_cache_expires_at_idx
    ON api_cache (expires_at);

-- Conversation history per session
CREATE TABLE IF NOT EXISTS conversations (
    session_id  TEXT PRIMARY KEY,
    messages    JSONB NOT NULL DEFAULT '[]'::jsonb,
    updated_at  TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Daily LLM-call cost cap
CREATE TABLE IF NOT EXISTS daily_usage (
    day            DATE PRIMARY KEY,
    llm_call_count INT NOT NULL DEFAULT 0
);
