-- Shareable pairing snapshots — anyone with the short_code can read.
-- Codes never expire (v1); cleanup can be added later if abused.

CREATE TABLE IF NOT EXISTS shared_pairings (
    short_code  TEXT PRIMARY KEY,
    pairing     JSONB NOT NULL,
    mood        TEXT NOT NULL,
    created_at  TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS shared_pairings_created_at_idx
    ON shared_pairings (created_at DESC);
