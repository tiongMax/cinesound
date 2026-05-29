"""POST /query — streams orchestrator milestones + final Recommendation via SSE.

Event stream contract:
    event: ack
    data: {"session_id": "..."}

    event: node_done
    data: {"node": "load_memory" | "profile" | "search" | "rank_and_pair" | "save_memory"}

    event: final
    data: <Recommendation JSON>

    event: error
    data: {"message": "..."}

Connection ends after `final` or `error`.
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from app.agents.graph import get_graph
from app.db import PoolDep
from app.middleware.daily_cap import check_daily_cap
from app.middleware.rate_limit import QUERY_RATE, limiter
from app.schemas import QueryRequest, Recommendation

CapDep = Annotated[Recommendation | None, Depends(check_daily_cap)]

log = logging.getLogger(__name__)

router = APIRouter()


def _sse(event: str, data: dict | str) -> str:
    if isinstance(data, dict):
        data = json.dumps(data)
    return f"event: {event}\ndata: {data}\n\n"


async def _stream_orchestrator(
    pool, query: str, session_id: str, cap_stub: Recommendation | None
) -> AsyncIterator[str]:
    yield _sse("ack", {"session_id": session_id})

    if cap_stub is not None:
        yield _sse("final", cap_stub.model_dump(mode="json"))
        return

    graph = get_graph()
    initial = {"query": query, "session_id": session_id, "pool": pool}
    last_state: dict = {}
    try:
        async for chunk in graph.astream(initial, stream_mode="updates"):
            for node, update in chunk.items():
                if isinstance(update, dict):
                    last_state.update(update)
                yield _sse("node_done", {"node": node})
    except Exception as e:
        log.exception("orchestrator failed")
        yield _sse("error", {"message": str(e)[:200]})
        return

    rec = last_state.get("recommendation")
    if rec is None:
        yield _sse("error", {"message": "orchestrator returned no recommendation"})
        return
    yield _sse("final", rec.model_dump(mode="json"))


@router.post("/query")
@limiter.limit(QUERY_RATE)
async def query_endpoint(
    body: QueryRequest,
    request: Request,
    pool: PoolDep,
    cap_stub: CapDep,
) -> StreamingResponse:
    """Stream the orchestrator's progress and final Recommendation as SSE."""
    return StreamingResponse(
        _stream_orchestrator(pool, body.query, body.session_id, cap_stub),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
