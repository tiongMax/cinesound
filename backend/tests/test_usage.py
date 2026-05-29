"""Daily usage counter tests with mocked asyncpg."""

from unittest.mock import AsyncMock

from app.usage import get_today_count, increment_llm_calls, is_over_daily_cap


def make_pool(fetchrow_return=None):
    pool = AsyncMock()
    pool.fetchrow = AsyncMock(return_value=fetchrow_return)
    return pool


async def test_increment_returns_new_total():
    pool = make_pool({"llm_call_count": 7})
    total = await increment_llm_calls(pool, count=3)
    assert total == 7


async def test_get_today_count_returns_zero_when_no_row():
    pool = make_pool(None)
    assert await get_today_count(pool) == 0


async def test_is_over_daily_cap_true_when_count_meets_cap(monkeypatch):
    from app import usage

    monkeypatch.setattr(usage.settings, "daily_query_cap", 100)
    pool = make_pool({"llm_call_count": 100})
    assert await is_over_daily_cap(pool) is True


async def test_is_over_daily_cap_false_below(monkeypatch):
    from app import usage

    monkeypatch.setattr(usage.settings, "daily_query_cap", 100)
    pool = make_pool({"llm_call_count": 99})
    assert await is_over_daily_cap(pool) is False


async def test_zero_cap_means_immediately_over(monkeypatch):
    """DAILY_QUERY_CAP=0 forces every request into the stub path."""
    from app import usage

    monkeypatch.setattr(usage.settings, "daily_query_cap", 0)
    pool = make_pool(None)  # no row -> count is 0
    assert await is_over_daily_cap(pool) is True
