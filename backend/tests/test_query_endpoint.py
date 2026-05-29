"""POST /query endpoint tests with the orchestrator + cap mocked."""

import json
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.agents import graph as graph_mod
from app.db import _pool_dep
from app.main import app
from app.middleware import daily_cap as dc
from app.middleware.daily_cap import check_daily_cap
from app.schemas import (
    MovieProfile,
    MovieRec,
    MusicProfile,
    MusicRec,
    Recommendation,
    TasteProfile,
)


def _rec() -> Recommendation:
    return Recommendation(
        mood_detected="reflective, cinematic",
        movies=[
            MovieRec(
                tmdb_id=329865,
                title="Arrival",
                year=2016,
                rating=7.9,
                genres=["Sci-Fi", "Drama"],
                reason="reflective sci-fi",
            )
        ],
        music=[
            MusicRec(
                spotify_uri="spotify:track:abc",
                track="Day One",
                artist="Hans Zimmer",
                album="Interstellar OST",
                mood_tag="cinematic ambient",
                reason="matches mood",
                spotify_url="https://open.spotify.com/track/abc",
            )
        ],
        pairing_note="Listen while you watch.",
    )


def _profile() -> TasteProfile:
    return TasteProfile(
        movie_profile=MovieProfile(genres=["Sci-Fi"], mood="reflective"),
        music_profile=MusicProfile(energy="calm", genres=["ambient"], mood="cinematic"),
        shared_mood="reflective, cinematic",
    )


def _parse_sse(text: str) -> list[tuple[str, dict]]:
    events: list[tuple[str, dict]] = []
    for block in text.strip().split("\n\n"):
        ev = None
        data = None
        for line in block.split("\n"):
            if line.startswith("event:"):
                ev = line[len("event:") :].strip()
            elif line.startswith("data:"):
                data = json.loads(line[len("data:") :].strip())
        if ev:
            events.append((ev, data))
    return events


@pytest.fixture
def fake_pool():
    pool = AsyncMock()
    pool.fetchrow = AsyncMock(return_value=None)
    pool.fetch = AsyncMock(return_value=[])
    pool.execute = AsyncMock(return_value="OK 1")
    return pool


@pytest.fixture
def client(fake_pool):
    """TestClient with PoolDep overridden to a stub. No lifespan."""
    app.dependency_overrides[_pool_dep] = lambda: fake_pool
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def patched_orchestrator(monkeypatch):
    monkeypatch.setattr(graph_mod, "_graph", None)
    monkeypatch.setattr(graph_mod, "get_all_memory", AsyncMock(return_value={}))
    monkeypatch.setattr(graph_mod, "profile", AsyncMock(return_value=_profile()))
    monkeypatch.setattr(graph_mod, "search_movies", AsyncMock(return_value=[]))
    monkeypatch.setattr(graph_mod, "search_music", AsyncMock(return_value=[]))
    monkeypatch.setattr(graph_mod, "rank_and_pair", AsyncMock(return_value=_rec()))
    monkeypatch.setattr(graph_mod, "append_to_list", AsyncMock())
    monkeypatch.setattr(graph_mod, "increment_llm_calls", AsyncMock(return_value=1))


def test_query_streams_milestones_then_final(client, patched_orchestrator, monkeypatch):
    monkeypatch.setattr(dc, "is_over_daily_cap", AsyncMock(return_value=False))
    r = client.post("/query", json={"query": "reflective", "session_id": "s1"})

    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")

    events = _parse_sse(r.text)
    names = [e[0] for e in events]
    assert names[0] == "ack"
    assert "node_done" in names
    assert names[-1] == "final"

    final_data = events[-1][1]
    assert final_data["movies"][0]["tmdb_id"] == 329865
    assert final_data["pairing_note"].startswith("Listen")


def test_query_returns_stub_when_over_daily_cap(client, patched_orchestrator):
    # Override the dependency directly rather than monkeypatching the function,
    # since FastAPI resolves the dep before our patch matters.
    from app.middleware.daily_cap import CAP_REACHED_REC

    app.dependency_overrides[check_daily_cap] = lambda: CAP_REACHED_REC
    try:
        r = client.post("/query", json={"query": "anything", "session_id": "s1"})
    finally:
        app.dependency_overrides.pop(check_daily_cap, None)

    assert r.status_code == 200
    events = _parse_sse(r.text)
    names = [e[0] for e in events]
    assert names == ["ack", "final"]  # no node_done — orchestrator skipped
    final = events[-1][1]
    assert "Demo limit reached" in final["pairing_note"]


def test_query_validates_body(client):
    r = client.post("/query", json={"query": "", "session_id": "s1"})
    assert r.status_code == 422
