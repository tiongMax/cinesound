"""Daily LLM-call budget tracker.

Each LLM call by an agent should call `increment_llm_calls(pool)`. Before
running the orchestrator, the /query endpoint checks `is_over_daily_cap(pool)`
to short-circuit and return a stub response when the day's budget is gone.

Today's row is created on demand by the UPSERT in `increment_llm_calls`.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import asyncpg

from app.config import settings


def _today() -> date:
    return datetime.now(UTC).date()


async def increment_llm_calls(pool: asyncpg.Pool, *, count: int = 1) -> int:
    """Add `count` to today's counter; return the new total."""
    row = await pool.fetchrow(
        """
        INSERT INTO daily_usage (day, llm_call_count)
        VALUES ($1, $2)
        ON CONFLICT (day) DO UPDATE
        SET llm_call_count = daily_usage.llm_call_count + EXCLUDED.llm_call_count
        RETURNING llm_call_count
        """,
        _today(),
        count,
    )
    return int(row["llm_call_count"])


async def get_today_count(pool: asyncpg.Pool) -> int:
    row = await pool.fetchrow(
        "SELECT llm_call_count FROM daily_usage WHERE day = $1",
        _today(),
    )
    return int(row["llm_call_count"]) if row else 0


async def is_over_daily_cap(pool: asyncpg.Pool) -> bool:
    """True when today's count >= DAILY_QUERY_CAP env var."""
    return await get_today_count(pool) >= settings.daily_query_cap
