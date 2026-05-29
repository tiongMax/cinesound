"""Seed the embeddings table with ~2-5k tracks from Spotify.

Pipeline per track:
  1. Spotify /search by genre tag -> top N tracks
  2. Gemini Flash generates a one-paragraph "vibe description"
     (cached to .vibe_cache.json on disk so re-runs don't regenerate)
  3. Embed the vibe description with text-embedding-004 (768d)
  4. Upsert into embeddings on metadata->>'spotify_uri'

Usage:
    uv run python -m scripts.seed_music                       # default 30 genres x 50 tracks
    uv run python -m scripts.seed_music --per-genre 30
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pydantic import BaseModel  # noqa: E402

from app.clients.gemini import EMBED_DIM, embed, gemini_chat  # noqa: E402
from app.clients.spotify import SpotifyClient  # noqa: E402
from app.config import settings  # noqa: E402
from app.db import close_pool, init_pool  # noqa: E402

VIBE_CACHE_PATH = Path(__file__).resolve().parent / ".vibe_cache.json"

GENRES = [
    "pop",
    "rock",
    "indie",
    "hip-hop",
    "rap",
    "r&b",
    "soul",
    "electronic",
    "house",
    "techno",
    "ambient",
    "lo-fi",
    "jazz",
    "classical",
    "orchestral",
    "folk",
    "country",
    "metal",
    "punk",
    "alternative",
    "synthpop",
    "funk",
    "reggae",
    "blues",
    "gospel",
    "latin",
    "bossa nova",
    "k-pop",
    "j-pop",
    "dance",
]


class VibeOut(BaseModel):
    vibe_description: str


VIBE_SYSTEM = (
    "You write one-paragraph 'vibe descriptions' for songs that capture mood, "
    "energy, instrumentation, and the kind of moment the song fits. Keep it to "
    "2-4 sentences. No song titles, no artist names — just the feeling."
)


def load_vibe_cache() -> dict[str, str]:
    if not VIBE_CACHE_PATH.exists():
        return {}
    try:
        return json.loads(VIBE_CACHE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_vibe_cache(cache: dict[str, str]) -> None:
    VIBE_CACHE_PATH.write_text(json.dumps(cache, indent=2), encoding="utf-8")


async def generate_vibe(track: dict, cache: dict[str, str]) -> str:
    """Generate a vibe description, hitting the on-disk cache first."""
    uri = track["uri"]
    if uri in cache:
        return cache[uri]
    artists = ", ".join(a["name"] for a in track.get("artists", []))
    prompt = (
        f"Track: '{track['name']}' by {artists}. "
        f"Album: '{track.get('album', {}).get('name', 'unknown')}'.\n"
        "Write the vibe description."
    )
    try:
        out = await gemini_chat(prompt, response_schema=VibeOut, system=VIBE_SYSTEM)
        cache[uri] = out.vibe_description
        return out.vibe_description
    except Exception as e:
        print(f"  vibe gen failed for {uri}: {e}", file=sys.stderr)
        return ""


async def existing_spotify_uris(pool) -> set[str]:
    rows = await pool.fetch(
        "SELECT metadata->>'spotify_uri' AS uri FROM embeddings WHERE type='music'"
    )
    return {r["uri"] for r in rows if r["uri"]}


async def collect_tracks(spotify: SpotifyClient, per_genre: int) -> list[dict]:
    """Search Spotify for top tracks per genre, dedupe by URI."""
    seen: dict[str, dict] = {}
    for genre in GENRES:
        try:
            tracks = await spotify.search_track(f'genre:"{genre}"', limit=per_genre)
        except Exception as e:
            print(f"  spotify search failed for '{genre}': {e}", file=sys.stderr)
            continue
        added = 0
        for t in tracks:
            uri = t.get("uri")
            if uri and uri not in seen:
                t["_seed_genre"] = genre
                seen[uri] = t
                added += 1
        print(f"  {genre}: +{added} (total unique {len(seen)})")
    return list(seen.values())


async def insert_batch(
    pool, tracks: list[dict], vibes: list[str], vectors: list[list[float]]
) -> int:
    rows = []
    for t, vibe, v in zip(tracks, vibes, vectors, strict=True):
        if not vibe or len(v) != EMBED_DIM:
            continue
        metadata = {
            "spotify_uri": t["uri"],
            "track": t["name"],
            "artist": ", ".join(a["name"] for a in t.get("artists", [])),
            "album": t.get("album", {}).get("name"),
            "genre": t.get("_seed_genre"),
            "vibe_description": vibe,
            "spotify_url": t.get("external_urls", {}).get("spotify"),
            "album_art_url": SpotifyClient.album_art_url(t),
        }
        embedding_literal = "[" + ",".join(str(x) for x in v) + "]"
        rows.append((t["name"], json.dumps(metadata), embedding_literal))
    if not rows:
        return 0
    await pool.executemany(
        """
        INSERT INTO embeddings (type, title, metadata, embedding)
        VALUES ('music', $1, $2::jsonb, $3::vector)
        ON CONFLICT ((metadata->>'spotify_uri')) WHERE type = 'music' DO NOTHING
        """,
        rows,
    )
    return len(rows)


async def main(per_genre: int, batch_size: int) -> int:
    required = (
        settings.database_url,
        settings.spotify_client_id,
        settings.spotify_client_secret,
        settings.gemini_api_key,
    )
    if not all(required):
        print(
            "Missing env: DATABASE_URL, SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, GEMINI_API_KEY",
            file=sys.stderr,
        )
        return 1

    pool = await init_pool()
    cache = load_vibe_cache()
    print(f"Loaded {len(cache)} cached vibes from {VIBE_CACHE_PATH.name}")
    try:
        already = await existing_spotify_uris(pool)
        print(f"DB already has {len(already)} music rows")

        async with SpotifyClient() as spotify:
            tracks = await collect_tracks(spotify, per_genre)

        new_tracks = [t for t in tracks if t["uri"] not in already]
        print(f"After dedupe: {len(new_tracks)} new tracks to process")

        total_inserted = 0
        for i in range(0, len(new_tracks), batch_size):
            batch = new_tracks[i : i + batch_size]
            print(f"  batch {i // batch_size + 1}: generating vibes ({len(batch)} tracks)...")
            vibes = []
            for t in batch:
                vibe = await generate_vibe(t, cache)
                vibes.append(vibe)
            save_vibe_cache(cache)  # checkpoint after each batch

            valid_pairs = [(t, v) for t, v in zip(batch, vibes, strict=True) if v]
            if not valid_pairs:
                continue
            valid_tracks = [p[0] for p in valid_pairs]
            valid_vibes = [p[1] for p in valid_pairs]

            print(f"    embedding {len(valid_vibes)} vibes...")
            vectors = await embed(valid_vibes)
            inserted = await insert_batch(pool, valid_tracks, valid_vibes, vectors)
            total_inserted += inserted
            print(f"    inserted {inserted} (total {total_inserted})")

        print(f"\nDone. Inserted this run: {total_inserted}")
        return 0
    finally:
        await close_pool()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--per-genre", type=int, default=50, help="tracks per Spotify search")
    parser.add_argument("--batch-size", type=int, default=20, help="tracks per processing batch")
    args = parser.parse_args()
    sys.exit(asyncio.run(main(args.per_genre, args.batch_size)))
