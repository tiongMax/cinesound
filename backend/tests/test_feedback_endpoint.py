"""POST /feedback tests."""

import json
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.db import _pool_dep
from app.main import app
from app.memory import set_memory  # noqa: F401 -- ensure module is loaded


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


def test_feedback_requires_target_id(client):
    r = client.post("/feedback", json={"session_id": "s1", "vote": "up"})
    assert r.status_code == 400


def test_thumbs_down_appends_to_disliked_genres(client, fake_pool):
    # First fetchrow: embeddings lookup for movie genres
    # Subsequent fetchrows: get_memory for liked/disliked genre append
    fake_pool.fetchrow = AsyncMock(
        side_effect=[
            {"metadata": json.dumps({"genre_ids": [27]})},  # Horror
            None,  # get_memory returns empty -> initialise list
        ]
    )

    r = client.post(
        "/feedback",
        json={"session_id": "s1", "vote": "down", "tmdb_id": 12345},
    )
    assert r.status_code == 204
    # set_memory was called with disliked_genres containing Horror
    execute_args = [c.args for c in fake_pool.execute.call_args_list]
    assert any(
        "user_memory" in args[0] and json.loads(args[3]) == ["Horror"]
        for args in execute_args
    )


def test_thumbs_up_appends_to_liked_genres_for_music(client, fake_pool):
    fake_pool.fetchrow = AsyncMock(
        side_effect=[
            {"metadata": json.dumps({"genre": "ambient"})},  # music genre lookup
            None,  # get_memory empty
        ]
    )

    r = client.post(
        "/feedback",
        json={
            "session_id": "s1",
            "vote": "up",
            "spotify_uri": "spotify:track:abc",
        },
    )
    assert r.status_code == 204
    execute_args = [c.args for c in fake_pool.execute.call_args_list]
    assert any(
        "user_memory" in args[0] and json.loads(args[3]) == ["ambient"]
        for args in execute_args
    )
