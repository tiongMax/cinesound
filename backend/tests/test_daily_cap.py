"""Daily cap dependency unit tests."""

from unittest.mock import AsyncMock

from app.middleware import daily_cap as dc
from app.middleware.daily_cap import CAP_REACHED_REC, check_daily_cap


async def test_returns_stub_when_over_cap(monkeypatch):
    monkeypatch.setattr(dc, "is_over_daily_cap", AsyncMock(return_value=True))
    rec = await check_daily_cap(pool=AsyncMock())
    assert rec is CAP_REACHED_REC
    assert rec.fallback_message and "Demo limit reached" in rec.fallback_message
    assert rec.pairings == []


async def test_returns_none_when_under_cap(monkeypatch):
    monkeypatch.setattr(dc, "is_over_daily_cap", AsyncMock(return_value=False))
    assert await check_daily_cap(pool=AsyncMock()) is None
