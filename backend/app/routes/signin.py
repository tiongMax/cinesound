"""POST /signin — verify Google ID token, migrate memory.

The frontend gets an ID token from Google one-tap. We verify it against
Google's tokeninfo endpoint (async-friendly, no extra dependency), check
the audience matches our client_id, then migrate the anonymous session's
memory rows to `google:<sub>` so cross-device history works.
"""

from __future__ import annotations

import httpx
from fastapi import APIRouter, Cookie, HTTPException

from app.config import settings
from app.db import PoolDep
from app.memory import migrate_memory

router = APIRouter()

TOKENINFO_URL = "https://oauth2.googleapis.com/tokeninfo"


async def verify_google_id_token(id_token: str, expected_aud: str) -> dict:
    """Returns the verified token payload or raises HTTPException."""
    async with httpx.AsyncClient(timeout=5.0) as client:
        r = await client.get(TOKENINFO_URL, params={"id_token": id_token})
    if r.status_code != 200:
        raise HTTPException(401, "Invalid Google ID token")
    data = r.json()
    if data.get("aud") != expected_aud:
        raise HTTPException(401, "Token audience mismatch")
    if "sub" not in data:
        raise HTTPException(401, "Token missing subject")
    return data


@router.post("/signin")
async def signin_endpoint(
    body: dict,
    pool: PoolDep,
    session_id: str | None = Cookie(default=None),
) -> dict:
    """Exchange a Google ID token for a logged-in identity + migrate memory.

    Body: {"id_token": "..."}
    Returns: {"user_id": "google:<sub>", "migrated_keys": N}
    """
    if not settings.google_client_id:
        raise HTTPException(500, "Google sign-in is not configured on this server")

    token = body.get("id_token")
    if not token:
        raise HTTPException(400, "id_token is required")

    info = await verify_google_id_token(token, settings.google_client_id)
    google_uid = f"google:{info['sub']}"

    migrated = 0
    if session_id:
        migrated = await migrate_memory(pool, from_user_id=session_id, to_user_id=google_uid)

    return {"user_id": google_uid, "migrated_keys": migrated}
