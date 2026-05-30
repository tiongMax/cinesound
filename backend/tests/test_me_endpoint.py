"""GET /me endpoint tests."""

from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.db import _pool_dep
from app.main import app
from app.routes import me as me_mod


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


def test_me_requires_session_id(client):
    r = client.get("/me")
    assert r.status_code == 422


def test_delete_me_wipes_session_data(client, fake_pool):
    fake_pool.execute = AsyncMock(side_effect=["DELETE 5", "DELETE 1"])
    r = client.request("DELETE", "/me", params={"session_id": "s1"})
    assert r.status_code == 200
    body = r.json()
    assert body["deleted"] == {"memory_rows": 5, "conversation_rows": 1}


def test_delete_me_requires_session_id(client):
    r = client.request("DELETE", "/me")
    assert r.status_code == 422


def test_me_returns_empty_state_for_new_session(client, monkeypatch):
    monkeypatch.setattr(me_mod, "get_all_memory", AsyncMock(return_value={}))
    monkeypatch.setattr(me_mod, "load_recent_turns", AsyncMock(return_value=[]))
    r = client.get("/me?session_id=session:new")
    assert r.status_code == 200
    body = r.json()
    assert body["session_id"] == "session:new"
    assert body["counts"] == {
        "watched_movies": 0,
        "heard_tracks": 0,
        "queries_with_mood": 0,
    }
    assert body["top_liked_genres"] == []
    assert body["recent_moods"] == []
    assert body["recent_queries"] == []


def test_me_returns_recent_queries_newest_first(client, monkeypatch):
    monkeypatch.setattr(me_mod, "get_all_memory", AsyncMock(return_value={}))
    monkeypatch.setattr(
        me_mod,
        "load_recent_turns",
        AsyncMock(
            return_value=[
                {"query": "older"},
                {"query": "middle"},
                {"query": "newest"},
            ]
        ),
    )
    r = client.get("/me?session_id=s1")
    assert r.json()["recent_queries"] == ["newest", "middle", "older"]


def test_me_returns_aggregated_state(client, monkeypatch):
    monkeypatch.setattr(me_mod, "load_recent_turns", AsyncMock(return_value=[]))
    monkeypatch.setattr(
        me_mod,
        "get_all_memory",
        AsyncMock(
            return_value={
                "watched_movies": [1, 2, 3],
                "heard_tracks": ["spotify:track:a", "spotify:track:b"],
                "liked_genres": ["Sci-Fi", "Drama", "Sci-Fi", "Sci-Fi"],
                "disliked_genres": ["Horror", "Horror"],
                "past_moods": [f"mood{i}" for i in range(15)],
                "content_prefs": {"no_horror": True},
            }
        ),
    )
    r = client.get("/me?session_id=s1")
    assert r.status_code == 200
    body = r.json()
    assert body["counts"]["watched_movies"] == 3
    assert body["counts"]["heard_tracks"] == 2
    assert body["counts"]["queries_with_mood"] == 15
    assert body["top_liked_genres"][0] == {"genre": "Sci-Fi", "count": 3}
    assert body["top_disliked_genres"][0] == {"genre": "Horror", "count": 2}
    # last 10, most recent first
    assert len(body["recent_moods"]) == 10
    assert body["recent_moods"][0] == "mood14"
    assert body["content_prefs"] == {"no_horror": True}
