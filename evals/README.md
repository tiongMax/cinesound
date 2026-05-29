# CineSound Evals

Hand-curated eval set for CineSound. The runner (T31) reads `queries.csv`, calls the `/query` endpoint per row, and scores results.

## queries.csv format

| Column | Type | Notes |
|---|---|---|
| `query` | string | User's input. Standard CSV quoting if it contains commas. |
| `expected_mood` | string | Semicolon-separated mood tags (e.g. `reflective; cinematic`). |
| `acceptable_movie_genres` | string | Pipe-separated genres (e.g. `Sci-Fi\|Drama`). At least one must match. |
| `acceptable_music_genres` | string | Pipe-separated genres. At least one must match. |

## Scoring (T31)

For each row:
- **(a)** Mood detection: substring match against `expected_mood` tags OR embedding similarity ≥ 0.7
- **(b)** Genre overlap: ≥1 acceptable genre per domain in the returned recommendation
- **(c)** Pairing quality: human-graded 1–5, written into `runs/<date>.csv` after the auto-run

Runs are written to `runs/<date>.json`. The folder is gitignored — commit only `queries.csv` and (occasionally) a curated `runs/<date>-prod.json` snapshot for the portfolio README.
