"""Cache CRUD + @cached decorator tests using mocked asyncpg + fake clock."""

import json
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

from app.cache import cache_get, cache_set, cached


def make_pool(fetchrow_return=None):
    pool = AsyncMock()
    pool.fetchrow = AsyncMock(return_value=fetchrow_return)
    pool.execute = AsyncMock()
    return pool


async def test_cache_get_returns_none_when_missing():
    pool = make_pool(None)
    assert await cache_get(pool, "k") is None


async def test_cache_get_returns_none_when_expired():
    past = datetime.now(UTC) - timedelta(seconds=10)
    pool = make_pool({"response": json.dumps({"x": 1}), "expires_at": past.replace(tzinfo=None)})
    assert await cache_get(pool, "k") is None


async def test_cache_get_returns_value_when_fresh():
    future = datetime.now(UTC) + timedelta(seconds=600)
    pool = make_pool({"response": json.dumps({"x": 1}), "expires_at": future.replace(tzinfo=None)})
    assert await cache_get(pool, "k") == {"x": 1}


async def test_cache_set_serialises_and_passes_expiry():
    pool = make_pool()
    await cache_set(pool, "k", {"a": [1, 2]}, ttl_seconds=60)
    args = pool.execute.call_args[0]
    assert args[1] == "k"
    assert json.loads(args[2]) == {"a": [1, 2]}
    assert isinstance(args[3], datetime)


# --- @cached decorator ---


async def test_cached_skips_network_on_second_call():
    """First call hits the underlying fn; second call uses the cached value."""
    pool = make_pool(None)  # first cache_get returns None

    call_count = 0

    @cached(lambda: pool, namespace="tmdb_test", ttl_seconds=60)
    async def fetch(x: int) -> dict[str, int]:
        nonlocal call_count
        call_count += 1
        return {"x": x}

    # first call -> miss
    out1 = await fetch(1)
    assert out1 == {"x": 1}
    assert call_count == 1

    # arrange the next fetchrow to return the cached value
    future = datetime.now(UTC) + timedelta(seconds=600)
    pool.fetchrow = AsyncMock(
        return_value={
            "response": json.dumps({"x": 1}),
            "expires_at": future.replace(tzinfo=None),
        }
    )

    out2 = await fetch(1)
    assert out2 == {"x": 1}
    assert call_count == 1  # underlying fn NOT called again


async def test_cached_bypasses_when_pool_is_none():
    @cached(lambda: None, namespace="x", ttl_seconds=60)
    async def fetch() -> int:
        return 42

    assert await fetch() == 42
