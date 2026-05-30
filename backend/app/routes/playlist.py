"""POST /playlist — returns an N-track playlist for a given mood.

Not SSE; one-shot JSON response. Same rate limit + daily cap rules as /query.
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request

from app.agents.playlist import build_playlist
from app.db import PoolDep
from app.memory import get_all_memory
from app.middleware.daily_cap import check_daily_cap
from app.middleware.rate_limit import QUERY_RATE, limiter
from app.schemas import Playlist, PlaylistRequest, Recommendation
from app.usage import increment_llm_calls

log = logging.getLogger(__name__)
router = APIRouter()

CapDep = Annotated[Recommendation | None, Depends(check_daily_cap)]


@router.post("/playlist", response_model=Playlist)
@limiter.limit(QUERY_RATE)
async def playlist_endpoint(
    body: PlaylistRequest,
    request: Request,
    pool: PoolDep,
    cap_stub: CapDep,
) -> Playlist:
    if cap_stub is not None:
        raise HTTPException(
            status_code=429,
            detail="Demo limit reached for today — try again tomorrow.",
        )

    memory = await get_all_memory(pool, body.session_id)
    try:
        pl = await build_playlist(pool, body.query, length=body.length, memory=memory)
    except Exception as e:
        log.exception("playlist build failed")
        raise HTTPException(500, f"playlist build failed: {str(e)[:200]}") from e

    # 2 LLM calls (profiler + playlist)
    await increment_llm_calls(pool, count=2)
    return pl
