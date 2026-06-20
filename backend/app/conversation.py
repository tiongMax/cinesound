"""Short conversation history per session — enables follow-up queries.

A turn is recorded after each successful recommendation:
    {query, shared_mood, picks: [{movie, music}, ...], ts}

The orchestrator loads the last N turns and folds a compact summary into
the profiler prompt so the LLM can interpret refinements like "darker",
"another please", "same vibe but heavier".
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import asyncpg

MAX_TURNS_KEPT = 20
TURNS_FED_TO_PROFILER = 3


async def load_recent_turns(
    pool: asyncpg.Pool, session_id: str, *, limit: int = TURNS_FED_TO_PROFILER
) -> list[dict[str, Any]]:
    """Return the most recent `limit` turns for this session, newest last."""
    row = await pool.fetchrow(
        "SELECT messages FROM conversations WHERE session_id = $1", session_id
    )
    if row is None:
        return []
    value = row["messages"]
    messages = json.loads(value) if isinstance(value, str) else list(value or [])
    return messages[-limit:]


async def append_turn(
    pool: asyncpg.Pool,
    session_id: str,
    turn: dict[str, Any],
) -> None:
    """Append a turn to the session's history, trimmed to MAX_TURNS_KEPT."""
    stamped = {**turn, "ts": datetime.now(UTC).isoformat(timespec="seconds")}
    # Read-modify-write — the table is single-row per session, so contention is local.
    row = await pool.fetchrow(
        "SELECT messages FROM conversations WHERE session_id = $1", session_id
    )
    if row is None:
        existing: list[dict[str, Any]] = []
    else:
        v = row["messages"]
        existing = json.loads(v) if isinstance(v, str) else list(v or [])
    updated = (existing + [stamped])[-MAX_TURNS_KEPT:]
    await pool.execute(
        """
        INSERT INTO conversations (session_id, messages, updated_at)
        VALUES ($1, $2::jsonb, NOW())
        ON CONFLICT (session_id) DO UPDATE
        SET messages = EXCLUDED.messages, updated_at = NOW()
        """,
        session_id,
        json.dumps(updated),
    )


def summarise_for_prompt(turns: list[dict[str, Any]]) -> str:
    """Compact, model-friendly rendering of recent turns."""
    if not turns:
        return ""
    lines: list[str] = []
    for i, t in enumerate(turns, start=1):
        picks = t.get("picks") or []
        pick_str = "; ".join(
            f"{p.get('movie', '?')} + {p.get('music', '?')}" for p in picks
        )
        lines.append(
            f"{i}. Query: {t.get('query', '')!r}\n"
            f"   Mood: {t.get('shared_mood', '')}\n"
            f"   Picked: {pick_str or '(no picks)'}"
        )
    return "\n".join(lines)
