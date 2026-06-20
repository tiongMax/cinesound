"""Seed the embeddings table with ~5k popular movies from TMDB.

Idempotent: rows are upserted on the unique index over metadata->>'tmdb_id'.
Embeds the TMDB `overview` field using Gemini's gemini-embedding-001 (768d).

Usage:
    uv run python -m scripts.seed_movies                 # default: 5k movies
    uv run python -m scripts.seed_movies --target 2000   # smaller corpus
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.clients.gemini import EMBED_DIM, embed  # noqa: E402
from app.clients.tmdb import TMDBClient  # noqa: E402
from app.config import settings  # noqa: E402
from app.db import close_pool, init_pool  # noqa: E402

# TMDB sort orders we cycle through to broaden the catalogue beyond pure popularity
SORT_ORDERS = [
    "popularity.desc",
    "vote_average.desc",
    "revenue.desc",
    "primary_release_date.desc",
]


def _to_year(release_date: str | None) -> int | None:
    if not release_date:
        return None
    try:
        return int(release_date.split("-")[0])
    except (ValueError, IndexError):
        return None


async def fetch_pages(client: TMDBClient, target: int) -> list[dict]:
    """Pull from TMDB until we have `target` unique movies (or run out of pages)."""
    seen: dict[int, dict] = {}
    for sort_by in SORT_ORDERS:
        page = 1
        while len(seen) < target and page <= 500:  # TMDB hard caps pages at 500
            try:
                results = await client.discover_popular(page=page, sort_by=sort_by)
            except Exception as e:
                print(f"  TMDB error sort={sort_by} page={page}: {e}", file=sys.stderr)
                break
            if not results:
                break
            for m in results:
                tmdb_id = m.get("id")
                if tmdb_id and tmdb_id not in seen and m.get("overview"):
                    seen[tmdb_id] = m
            page += 1
            if len(seen) >= target:
                break
        print(f"  sort={sort_by}: have {len(seen)} unique movies")
        if len(seen) >= target:
            break
    return list(seen.values())


async def existing_tmdb_ids(pool) -> set[int]:
    rows = await pool.fetch(
        "SELECT (metadata->>'tmdb_id')::int AS id FROM embeddings WHERE type='movie'"
    )
    return {r["id"] for r in rows if r["id"] is not None}


async def insert_batch(pool, movies: list[dict], vectors: list[list[float]]) -> int:
    """Bulk insert via executemany. Returns number of rows attempted."""
    rows = []
    for m, v in zip(movies, vectors, strict=True):
        if len(v) != EMBED_DIM:
            print(f"  skip {m['id']}: embedding dim {len(v)} != {EMBED_DIM}", file=sys.stderr)
            continue
        metadata = {
            "tmdb_id": m["id"],
            "title": m.get("title"),
            "year": _to_year(m.get("release_date")),
            "genre_ids": m.get("genre_ids", []),
            "rating": m.get("vote_average"),
            "overview": m.get("overview"),
            "poster_path": m.get("poster_path"),
        }
        embedding_literal = "[" + ",".join(str(x) for x in v) + "]"
        rows.append((m["title"] or "untitled", json.dumps(metadata), embedding_literal))
    if not rows:
        return 0
    await pool.executemany(
        """
        INSERT INTO embeddings (type, title, metadata, embedding)
        VALUES ('movie', $1, $2::jsonb, $3::vector)
        ON CONFLICT ((metadata->>'tmdb_id')) WHERE type = 'movie' DO NOTHING
        """,
        rows,
    )
    return len(rows)


async def main(target: int, batch_size: int) -> int:
    if not settings.database_url or not settings.tmdb_api_key or not settings.gemini_api_key:
        print(
            "Required env vars missing: DATABASE_URL, TMDB_API_KEY, GEMINI_API_KEY", file=sys.stderr
        )
        return 1

    pool = await init_pool()
    try:
        already = await existing_tmdb_ids(pool)
        print(f"DB already has {len(already)} movie rows")

        async with TMDBClient() as tmdb:
            print(f"Fetching from TMDB until we have {target} candidates...")
            movies = await fetch_pages(tmdb, target)
            print(f"Got {len(movies)} candidates from TMDB")

        new_movies = [m for m in movies if m["id"] not in already]
        print(f"After dedupe against DB: {len(new_movies)} new movies to embed")

        total_inserted = 0
        for i in range(0, len(new_movies), batch_size):
            batch = new_movies[i : i + batch_size]
            overviews = [m["overview"] for m in batch]
            print(f"  embed batch {i // batch_size + 1} ({len(batch)} items)...")
            vectors = await embed(overviews)
            inserted = await insert_batch(pool, batch, vectors)
            total_inserted += inserted
            print(f"    inserted {inserted} (total {total_inserted})")

        print(f"\nDone. Total inserted this run: {total_inserted}")
        return 0
    finally:
        await close_pool()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", type=int, default=5000, help="number of unique movies to seed")
    parser.add_argument("--batch-size", type=int, default=50, help="movies per embed call")
    args = parser.parse_args()
    sys.exit(asyncio.run(main(args.target, args.batch_size)))
