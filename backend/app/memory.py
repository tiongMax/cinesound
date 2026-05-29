"""User memory: small CRUD over the user_memory JSONB table.

Memory is keyed by (user_id, key). `user_id` is either an anonymous session
UUID stored in a cookie, or `"google:<sub>"` after sign-in. The migration
helper moves keys from one user_id to another and is used by /signin to
preserve pre-sign-in history.
"""

from __future__ import annotations

import json
from typing import Any

import asyncpg


async def get_memory(pool: asyncpg.Pool, user_id: str, key: str) -> Any | None:
    row = await pool.fetchrow(
        "SELECT value FROM user_memory WHERE user_id = $1 AND key = $2",
        user_id,
        key,
    )
    if row is None:
        return None
    # asyncpg returns JSONB as str by default; parse if needed
    value = row["value"]
    return json.loads(value) if isinstance(value, str) else value


async def get_all_memory(pool: asyncpg.Pool, user_id: str) -> dict[str, Any]:
    rows = await pool.fetch(
        "SELECT key, value FROM user_memory WHERE user_id = $1",
        user_id,
    )
    out: dict[str, Any] = {}
    for r in rows:
        v = r["value"]
        out[r["key"]] = json.loads(v) if isinstance(v, str) else v
    return out


async def set_memory(pool: asyncpg.Pool, user_id: str, key: str, value: Any) -> None:
    await pool.execute(
        """
        INSERT INTO user_memory (user_id, key, value, updated_at)
        VALUES ($1, $2, $3::jsonb, NOW())
        ON CONFLICT (user_id, key) DO UPDATE
        SET value = EXCLUDED.value, updated_at = NOW()
        """,
        user_id,
        key,
        json.dumps(value),
    )


async def append_to_list(
    pool: asyncpg.Pool, user_id: str, key: str, item: Any, *, dedupe: bool = True
) -> None:
    """Append `item` to the JSONB list stored at (user_id, key). Initialise if absent.

    With dedupe=True (default), the item is only added if it isn't already present.
    """
    current = await get_memory(pool, user_id, key)
    if current is None:
        current = []
    elif not isinstance(current, list):
        raise ValueError(f"memory key {key!r} is not a list (got {type(current).__name__})")
    if dedupe and item in current:
        return
    current.append(item)
    await set_memory(pool, user_id, key, current)


async def migrate_memory(
    pool: asyncpg.Pool, from_user_id: str, to_user_id: str
) -> int:
    """Move all keys from `from_user_id` to `to_user_id`.

    Conflicts on (to_user_id, key) keep the destination value (sign-in flow:
    if the signed-in user already has data on this device, that wins). Returns
    the number of rows migrated.
    """
    result = await pool.execute(
        """
        INSERT INTO user_memory (user_id, key, value, updated_at)
        SELECT $2, key, value, updated_at FROM user_memory WHERE user_id = $1
        ON CONFLICT (user_id, key) DO NOTHING
        """,
        from_user_id,
        to_user_id,
    )
    # delete source rows after copy
    await pool.execute("DELETE FROM user_memory WHERE user_id = $1", from_user_id)
    # asyncpg returns "INSERT 0 N" — parse the count
    parts = result.split()
    return int(parts[-1]) if parts and parts[-1].isdigit() else 0
