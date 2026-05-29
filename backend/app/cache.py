"""Tiny JSONB cache with TTL, backed by the api_cache table.

Used to avoid repeat TMDB / Spotify / embedding calls. Expired rows are
ignored by `cache_get`; a periodic cleanup of `expires_at < NOW()` is
out of scope for v1 (the row count stays small at our traffic).
"""

from __future__ import annotations

import functools
import hashlib
import json
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Any, TypeVar

import asyncpg

T = TypeVar("T")


async def cache_get(pool: asyncpg.Pool, key: str) -> Any | None:
    row = await pool.fetchrow(
        "SELECT response, expires_at FROM api_cache WHERE cache_key = $1",
        key,
    )
    if row is None:
        return None
    expires_at = row["expires_at"]
    # asyncpg returns naive datetimes; treat as UTC
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if expires_at < datetime.now(UTC):
        return None
    value = row["response"]
    return json.loads(value) if isinstance(value, str) else value


async def cache_set(pool: asyncpg.Pool, key: str, value: Any, *, ttl_seconds: int) -> None:
    expires_at = datetime.now(UTC) + timedelta(seconds=ttl_seconds)
    await pool.execute(
        """
        INSERT INTO api_cache (cache_key, response, expires_at)
        VALUES ($1, $2::jsonb, $3)
        ON CONFLICT (cache_key) DO UPDATE
        SET response = EXCLUDED.response, expires_at = EXCLUDED.expires_at
        """,
        key,
        json.dumps(value),
        expires_at.replace(tzinfo=None),  # asyncpg wants naive for TIMESTAMP
    )


def _make_cache_key(namespace: str, args: tuple, kwargs: dict) -> str:
    payload = json.dumps([args, kwargs], default=str, sort_keys=True)
    digest = hashlib.sha256(payload.encode()).hexdigest()[:32]
    return f"{namespace}:{digest}"


def cached(
    pool_getter: Callable[[], asyncpg.Pool | None],
    *,
    namespace: str,
    ttl_seconds: int,
) -> Callable[[Callable[..., Awaitable[T]]], Callable[..., Awaitable[T]]]:
    """Decorator for async functions whose return value is JSON-serialisable.

    If `pool_getter()` returns None the cache is bypassed (used in tests and
    when DB is unavailable). Cache key = sha256(namespace, args, kwargs).
    """

    def decorator(fn: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @functools.wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            pool = pool_getter()
            if pool is None:
                return await fn(*args, **kwargs)
            key = _make_cache_key(namespace, args, kwargs)
            cached_val = await cache_get(pool, key)
            if cached_val is not None:
                return cached_val  # type: ignore[return-value]
            result = await fn(*args, **kwargs)
            await cache_set(pool, key, result, ttl_seconds=ttl_seconds)
            return result

        return wrapper

    return decorator
