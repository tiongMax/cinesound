"""Daily-cap dependency.

Used as a FastAPI dependency on /query. When `is_over_daily_cap` returns True,
returns the stub Recommendation directly so the request never reaches the
expensive orchestrator. The caller decides how to surface this — for SSE the
/query route serialises this stub as the `final` event.
"""

from __future__ import annotations

from app.db import PoolDep
from app.schemas import Recommendation
from app.usage import is_over_daily_cap

CAP_REACHED_REC = Recommendation(
    mood_detected="(daily limit reached)",
    movies=[],
    music=[],
    pairing_note=(
        "Demo limit reached for today — CineSound is rate-limited to keep "
        "costs under control. Try again tomorrow."
    ),
)


async def check_daily_cap(pool: PoolDep) -> Recommendation | None:
    """Returns the stub Recommendation if over cap, else None."""
    if await is_over_daily_cap(pool):
        return CAP_REACHED_REC
    return None
