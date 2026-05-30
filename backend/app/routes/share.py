"""POST /share + GET /share/{short_code} — public, anonymous share links for pairings.

Anyone with the short_code can view; no auth, no session_id. Used for
sending a specific pairing to a friend or putting in a portfolio.
"""

from __future__ import annotations

import json
import secrets

from fastapi import APIRouter, HTTPException, Path

from app.db import PoolDep
from app.schemas import Pairing, ShareRequest, ShareResponse

router = APIRouter()

CODE_ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"  # no 0/o/1/l/i confusables
CODE_LENGTH = 8
MAX_INSERT_RETRIES = 5


def _generate_code() -> str:
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))


@router.post("/share", response_model=ShareResponse)
async def share_endpoint(body: ShareRequest, pool: PoolDep) -> ShareResponse:
    pairing_json = body.pairing.model_dump_json()
    for _ in range(MAX_INSERT_RETRIES):
        code = _generate_code()
        try:
            await pool.execute(
                """
                INSERT INTO shared_pairings (short_code, pairing, mood)
                VALUES ($1, $2::jsonb, $3)
                """,
                code,
                pairing_json,
                body.mood,
            )
            return ShareResponse(short_code=code, pairing=body.pairing, mood=body.mood)
        except Exception as e:  # asyncpg.exceptions.UniqueViolationError on collision
            if "unique" not in str(e).lower():
                raise
    raise HTTPException(500, "Failed to allocate short code after retries")


@router.get("/share/{short_code}", response_model=ShareResponse)
async def get_share(
    pool: PoolDep,
    short_code: str = Path(min_length=4, max_length=16, pattern=r"^[a-z2-9]+$"),
) -> ShareResponse:
    row = await pool.fetchrow(
        "SELECT pairing, mood FROM shared_pairings WHERE short_code = $1",
        short_code,
    )
    if row is None:
        raise HTTPException(404, "Share not found")
    pairing_raw = row["pairing"]
    pairing_dict = json.loads(pairing_raw) if isinstance(pairing_raw, str) else pairing_raw
    return ShareResponse(
        short_code=short_code,
        pairing=Pairing.model_validate(pairing_dict),
        mood=row["mood"],
    )
