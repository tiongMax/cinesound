"""POST /share + GET /share/{code} tests."""

import json
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.db import _pool_dep
from app.main import app


@pytest.fixture
def fake_pool():
    pool = AsyncMock()
    pool.fetchrow = AsyncMock(return_value=None)
    pool.execute = AsyncMock(return_value="INSERT 0 1")
    return pool


@pytest.fixture
def client(fake_pool):
    app.dependency_overrides[_pool_dep] = lambda: fake_pool
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _pairing_body() -> dict:
    return {
        "movie": {
            "tmdb_id": 329865,
            "title": "Arrival",
            "year": 2016,
            "rating": 7.9,
            "genres": ["Sci-Fi", "Drama"],
            "reason": "reflective",
        },
        "music": {
            "spotify_uri": "spotify:track:abc",
            "track": "Day One",
            "artist": "Hans Zimmer",
            "mood_tag": "cinematic",
            "reason": "matches",
            "spotify_url": "https://open.spotify.com/track/abc",
        },
        "pairing_note": "Listen while you watch.",
    }


def test_share_creates_code_and_returns_payload(client, fake_pool):
    r = client.post(
        "/share",
        json={"pairing": _pairing_body(), "mood": "reflective, cinematic"},
    )
    assert r.status_code == 200
    body = r.json()
    assert len(body["short_code"]) == 8
    assert body["short_code"].isalnum()
    assert body["mood"] == "reflective, cinematic"
    assert body["pairing"]["movie"]["tmdb_id"] == 329865


def test_get_share_returns_404_when_unknown(client):
    r = client.get("/share/aaaaaaaa")
    assert r.status_code == 404


def test_get_share_round_trip(client, fake_pool):
    fake_pool.fetchrow = AsyncMock(
        return_value={
            "pairing": json.dumps(_pairing_body()),
            "mood": "reflective",
        }
    )
    r = client.get("/share/abc23456")
    assert r.status_code == 200
    body = r.json()
    assert body["short_code"] == "abc23456"
    assert body["pairing"]["movie"]["title"] == "Arrival"


def test_get_share_rejects_invalid_code(client):
    r = client.get("/share/INVALID")
    assert r.status_code == 422
