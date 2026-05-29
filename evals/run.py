"""Run the eval harness against a CineSound /query endpoint.

Reads evals/queries.csv, POSTs each row to /query, parses the SSE stream
for the final Recommendation, scores against expected_mood and acceptable
genres, and writes a per-row + aggregate JSON snapshot to evals/runs/.

Usage:
    cd backend
    uv run python ../evals/run.py                   # default localhost:8000
    uv run python ../evals/run.py --url https://...prod.../  --label prod
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx

EVALS_DIR = Path(__file__).resolve().parent
RUNS_DIR = EVALS_DIR / "runs"
QUERIES_CSV = EVALS_DIR / "queries.csv"

sys.path.insert(0, str(EVALS_DIR))
from scoring import (  # noqa: E402
    aggregate,
    parse_mood_tags,
    parse_pipe_list,
    score_genre_overlap,
    score_mood_match,
)


def load_queries() -> list[dict]:
    rows: list[dict] = []
    with QUERIES_CSV.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rows.append(
                {
                    "query": r["query"],
                    "expected_mood": parse_mood_tags(r["expected_mood"]),
                    "acceptable_movie_genres": parse_pipe_list(r["acceptable_movie_genres"]),
                    "acceptable_music_genres": parse_pipe_list(r["acceptable_music_genres"]),
                }
            )
    return rows


async def consume_query(
    client: httpx.AsyncClient, url: str, query: str, session_id: str
) -> dict:
    """POST /query and return the final Recommendation payload (or raise)."""
    final: dict | None = None
    last_error: str | None = None
    async with client.stream(
        "POST",
        f"{url}/query",
        json={"query": query, "session_id": session_id},
        timeout=60.0,
    ) as resp:
        resp.raise_for_status()
        buffer = ""
        async for chunk in resp.aiter_text():
            buffer += chunk
            while "\n\n" in buffer:
                block, buffer = buffer.split("\n\n", 1)
                event_name = None
                data_str = None
                for line in block.split("\n"):
                    if line.startswith("event:"):
                        event_name = line[len("event:") :].strip()
                    elif line.startswith("data:"):
                        data_str = line[len("data:") :].strip()
                if event_name == "final" and data_str:
                    final = json.loads(data_str)
                elif event_name == "error" and data_str:
                    last_error = json.loads(data_str).get("message", "unknown")
    if final is None:
        raise RuntimeError(last_error or "no final event received")
    return final


def score_row(row: dict, rec: dict) -> dict:
    """Score a single row against the model's recommendation."""
    movie_genres = [g for m in rec.get("movies", []) for g in m.get("genres", [])]
    music_genres = [t.get("mood_tag", "") for t in rec.get("music", [])]
    # also include any tags that appear in the mood_tag field
    return {
        "mood_match": score_mood_match(rec.get("mood_detected", ""), row["expected_mood"]),
        "movie_genre_match": score_genre_overlap(movie_genres, row["acceptable_movie_genres"]),
        "music_genre_match": score_genre_overlap(music_genres, row["acceptable_music_genres"]),
        "pairing_quality": None,  # filled by hand in the JSON afterwards
    }


def summarise_rec(rec: dict) -> dict:
    movie = rec.get("movies", [{}])[0] if rec.get("movies") else {}
    track = rec.get("music", [{}])[0] if rec.get("music") else {}
    return {
        "mood_detected": rec.get("mood_detected"),
        "movie_title": movie.get("title"),
        "movie_genres": movie.get("genres", []),
        "music_track": track.get("track"),
        "music_artist": track.get("artist"),
        "music_mood_tag": track.get("mood_tag"),
        "pairing_note": rec.get("pairing_note"),
    }


async def run(url: str, label: str | None) -> Path:
    queries = load_queries()
    print(f"Running {len(queries)} queries against {url} ...")
    session_id = f"eval:{int(time.time())}"

    rows: list[dict] = []
    async with httpx.AsyncClient() as client:
        for i, row in enumerate(queries, start=1):
            t0 = time.perf_counter()
            try:
                rec = await consume_query(client, url, row["query"], session_id)
                scores = score_row(row, rec)
                rows.append(
                    {
                        **row,
                        "result": summarise_rec(rec),
                        "scores": scores,
                        "response_time_s": round(time.perf_counter() - t0, 3),
                        "error": None,
                    }
                )
                marks = "".join(
                    "✓" if v is True else ("✗" if v is False else "?")
                    for v in scores.values()
                )
                print(f"  [{i:2d}/{len(queries)}] {marks} {row['query'][:60]}")
            except Exception as e:
                rows.append(
                    {
                        **row,
                        "result": None,
                        "scores": None,
                        "response_time_s": round(time.perf_counter() - t0, 3),
                        "error": str(e)[:300],
                    }
                )
                print(f"  [{i:2d}/{len(queries)}] !! {row['query'][:60]}  ({e})")

    agg = aggregate(rows)
    valid_times = [r["response_time_s"] for r in rows if not r["error"]]
    agg["avg_response_time_s"] = (
        round(sum(valid_times) / len(valid_times), 3) if valid_times else 0.0
    )

    run_ts = datetime.now(UTC).strftime("%Y-%m-%dT%H-%M-%SZ")
    suffix = f"-{label}" if label else ""
    out_path = RUNS_DIR / f"{run_ts}{suffix}.json"
    RUNS_DIR.mkdir(exist_ok=True)
    out_path.write_text(
        json.dumps(
            {
                "run_id": run_ts,
                "api_url": url,
                "num_queries": len(rows),
                "aggregate": agg,
                "rows": rows,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\nWrote {out_path}")
    print(f"  mood:  {agg['mood_match_rate']:.0%}")
    print(f"  movie: {agg['movie_genre_match_rate']:.0%}")
    print(f"  music: {agg['music_genre_match_rate']:.0%}")
    print(f"  avg latency: {agg['avg_response_time_s']}s")
    print(f"  errors: {agg['errors']}")
    return out_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://localhost:8000", help="CineSound API base URL")
    parser.add_argument("--label", default=None, help="optional suffix on the output filename")
    args = parser.parse_args()
    asyncio.run(run(args.url.rstrip("/"), args.label))
