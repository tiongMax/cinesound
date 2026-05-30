"""POST /playlist endpoint tests."""

from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.db import _pool_dep
from app.main import app
from app.middleware import daily_cap as dc
from app.routes import playlist as playlist_route
from app.schemas import Playlist, PlaylistTrack


@pytest.fixture
def fake_pool():
    pool = AsyncMock()
    pool.fetchrow = AsyncMock(return_value=None)
    pool.fetch = AsyncMock(return_value=[])
    pool.execute = AsyncMock(return_value="OK 1")
    return pool


@pytest.fixture
def client(fake_pool):
    app.dependency_overrides[_pool_dep] = lambda: fake_pool
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _stub_playlist() -> Playlist:
    return Playlist(
        mood_detected="reflective, cinematic",
        title="A Quiet Night Among Stars",
        intro="Slow-build ambient that meets you where you are.",
        tracks=[
            PlaylistTrack(
                spotify_uri="spotify:track:a",
                track="Day One",
                artist="Hans Zimmer",
                album="Interstellar OST",
                spotify_url="https://open.spotify.com/track/a",
                reason="Sets the contemplative tone.",
            )
        ],
    )


def test_playlist_validates_length(client, monkeypatch):
    monkeypatch.setattr(dc, "is_over_daily_cap", AsyncMock(return_value=False))
    r = client.post(
        "/playlist",
        json={"query": "rainy sunday", "session_id": "s1", "length": 1},
    )
    assert r.status_code == 422  # length must be >= 3


def test_playlist_returns_structured_playlist(client, monkeypatch):
    monkeypatch.setattr(dc, "is_over_daily_cap", AsyncMock(return_value=False))
    monkeypatch.setattr(playlist_route, "get_all_memory", AsyncMock(return_value={}))
    monkeypatch.setattr(
        playlist_route, "build_playlist", AsyncMock(return_value=_stub_playlist())
    )
    monkeypatch.setattr(playlist_route, "increment_llm_calls", AsyncMock(return_value=2))

    r = client.post(
        "/playlist",
        json={"query": "rainy sunday", "session_id": "s1", "length": 5},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["title"] == "A Quiet Night Among Stars"
    assert len(body["tracks"]) == 1
    assert body["tracks"][0]["spotify_uri"] == "spotify:track:a"


def test_playlist_returns_429_when_over_cap(client, monkeypatch):
    from app.middleware.daily_cap import CAP_REACHED_REC, check_daily_cap

    app.dependency_overrides[check_daily_cap] = lambda: CAP_REACHED_REC
    try:
        r = client.post(
            "/playlist",
            json={"query": "anything", "session_id": "s1", "length": 5},
        )
    finally:
        app.dependency_overrides.pop(check_daily_cap, None)
    assert r.status_code == 429
