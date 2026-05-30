"""GET /me — returns the current device's taste profile snapshot.

Drives the frontend taste-profile panel. Lightweight read-only view over
user_memory, scoped to whichever user_id the caller's session_id maps to.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query

from app.conversation import load_recent_turns
from app.db import PoolDep
from app.memory import get_all_memory


async def _delete_session_data(pool, session_id: str) -> dict[str, int]:
    """Wipe all per-session memory + conversation rows. Returns row counts deleted."""
    result_mem = await pool.execute(
        "DELETE FROM user_memory WHERE user_id = $1", session_id
    )
    result_conv = await pool.execute(
        "DELETE FROM conversations WHERE session_id = $1", session_id
    )

    def _count(result: str) -> int:
        parts = result.split()
        return int(parts[-1]) if parts and parts[-1].isdigit() else 0

    return {
        "memory_rows": _count(result_mem),
        "conversation_rows": _count(result_conv),
    }

router = APIRouter()

RECENT_MOODS_SHOWN = 10
RECENT_QUERIES_SHOWN = 5
TOP_GENRES_SHOWN = 8


@router.get("/me")
async def me_endpoint(
    pool: PoolDep,
    session_id: Annotated[str, Query(min_length=1, max_length=128)],
) -> dict:
    """Return a summary of what CineSound knows about this device."""
    memory = await get_all_memory(pool, session_id)
    turns = await load_recent_turns(pool, session_id, limit=RECENT_QUERIES_SHOWN)

    watched = memory.get("watched_movies") or []
    heard = memory.get("heard_tracks") or []
    liked = memory.get("liked_genres") or []
    disliked = memory.get("disliked_genres") or []
    past_moods = memory.get("past_moods") or []
    content_prefs = memory.get("content_prefs") or {}

    return {
        "session_id": session_id,
        "counts": {
            "watched_movies": len(watched),
            "heard_tracks": len(heard),
            "queries_with_mood": len(past_moods),
        },
        "top_liked_genres": _top_n_with_counts(liked, TOP_GENRES_SHOWN),
        "top_disliked_genres": _top_n_with_counts(disliked, TOP_GENRES_SHOWN),
        "recent_moods": (past_moods[-RECENT_MOODS_SHOWN:])[::-1],
        "recent_queries": [
            t.get("query", "") for t in turns if t.get("query")
        ][::-1],
        "content_prefs": content_prefs,
    }


@router.delete("/me")
async def delete_me(
    pool: PoolDep,
    session_id: Annotated[str, Query(min_length=1, max_length=128)],
) -> dict:
    """Wipe memory + conversation history for this session. Irreversible."""
    deleted = await _delete_session_data(pool, session_id)
    return {"session_id": session_id, "deleted": deleted}


def _top_n_with_counts(values: list, n: int) -> list[dict]:
    """Convert a list with possible repeats into [{genre, count}] sorted by count."""
    counts: dict[str, int] = {}
    for v in values:
        if isinstance(v, str):
            counts[v] = counts.get(v, 0) + 1
    sorted_items = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[:n]
    return [{"genre": g, "count": c} for g, c in sorted_items]
