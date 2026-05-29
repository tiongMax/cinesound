"""POST /feedback — thumbs up/down on a recommendation card.

The vote updates the user's `liked_genres` / `disliked_genres` based on the
genres of the recommended item. We look up the item in `embeddings` to
discover its genres (this is the canonical source — the frontend may not
have them in scope when emitting the vote).
"""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException

from app.agents.search import _genres_for_movie
from app.db import PoolDep
from app.memory import append_to_list
from app.schemas import Feedback, MemoryKey

router = APIRouter()


async def _movie_genres(pool, tmdb_id: int) -> list[str]:
    row = await pool.fetchrow(
        "SELECT metadata FROM embeddings WHERE type='movie' AND (metadata->>'tmdb_id')::int = $1",
        tmdb_id,
    )
    if row is None:
        return []
    m = row["metadata"]
    metadata = json.loads(m) if isinstance(m, str) else dict(m)
    return _genres_for_movie(metadata)


async def _music_genre(pool, spotify_uri: str) -> str | None:
    row = await pool.fetchrow(
        "SELECT metadata FROM embeddings WHERE type='music' AND metadata->>'spotify_uri' = $1",
        spotify_uri,
    )
    if row is None:
        return None
    m = row["metadata"]
    metadata = json.loads(m) if isinstance(m, str) else dict(m)
    return metadata.get("genre")


@router.post("/feedback", status_code=204)
async def feedback_endpoint(body: Feedback, pool: PoolDep) -> None:
    if body.tmdb_id is None and body.spotify_uri is None:
        raise HTTPException(400, "Either tmdb_id or spotify_uri must be provided")

    target_key = (
        MemoryKey.LIKED_GENRES if body.vote == "up" else MemoryKey.DISLIKED_GENRES
    )

    if body.tmdb_id is not None:
        for g in await _movie_genres(pool, body.tmdb_id):
            await append_to_list(pool, body.session_id, target_key, g)
    if body.spotify_uri is not None:
        g = await _music_genre(pool, body.spotify_uri)
        if g:
            await append_to_list(pool, body.session_id, target_key, g)
