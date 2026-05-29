"""Tests for the Ranker's LLM tools (get_movie_details, get_artist_top_tracks)."""

from unittest.mock import AsyncMock

from app.agents import tools as tools_mod
from app.agents.tools import (
    GET_ARTIST_TOP_TRACKS,
    GET_MOVIE_DETAILS,
    RANKER_TOOLS,
    get_artist_top_tracks,
    get_movie_details,
)

# ---------- get_movie_details ----------


async def test_get_movie_details_returns_trimmed_dict(monkeypatch):
    fake = AsyncMock()
    fake.__aenter__ = AsyncMock(return_value=fake)
    fake.__aexit__ = AsyncMock(return_value=None)
    fake.get_movie = AsyncMock(
        return_value={
            "id": 329865,
            "title": "Arrival",
            "tagline": "Why are they here?",
            "overview": "A linguist works with the military to communicate with...",
            "runtime": 116,
            "release_date": "2016-11-11",
            "vote_average": 7.9,
            "genres": [{"name": "Sci-Fi"}, {"name": "Drama"}],
        }
    )
    monkeypatch.setattr(tools_mod, "TMDBClient", lambda: fake)

    out = await get_movie_details(329865)

    assert out["tmdb_id"] == 329865
    assert out["title"] == "Arrival"
    assert out["tagline"] == "Why are they here?"
    assert out["runtime_minutes"] == 116
    assert out["genres"] == ["Sci-Fi", "Drama"]


# ---------- get_artist_top_tracks ----------


async def test_get_artist_top_tracks_returns_top_n(monkeypatch):
    fake = AsyncMock()
    fake.__aenter__ = AsyncMock(return_value=fake)
    fake.__aexit__ = AsyncMock(return_value=None)
    fake.search_artist = AsyncMock(
        return_value=[
            {"id": "hz1", "name": "Hans Zimmer", "genres": ["score"], "popularity": 80}
        ]
    )
    fake.get_artist_top_tracks = AsyncMock(
        return_value=[
            {"name": "Day One", "album": {"name": "Interstellar OST"}, "popularity": 70},
            {"name": "Time", "album": {"name": "Inception OST"}, "popularity": 95},
        ]
    )
    monkeypatch.setattr(tools_mod, "SpotifyClient", lambda: fake)

    out = await get_artist_top_tracks("Hans Zimmer", limit=5)

    assert out["found"] is True
    assert out["artist"] == "Hans Zimmer"
    assert len(out["top_tracks"]) == 2
    assert out["top_tracks"][0]["track"] == "Day One"


async def test_get_artist_top_tracks_handles_unknown_artist(monkeypatch):
    fake = AsyncMock()
    fake.__aenter__ = AsyncMock(return_value=fake)
    fake.__aexit__ = AsyncMock(return_value=None)
    fake.search_artist = AsyncMock(return_value=[])
    monkeypatch.setattr(tools_mod, "SpotifyClient", lambda: fake)

    out = await get_artist_top_tracks("Unknown Artist")

    assert out["found"] is False
    assert out["top_tracks"] == []


# ---------- ToolSpec declarations ----------


def test_ranker_tools_registered():
    names = {t.name for t in RANKER_TOOLS}
    assert names == {"get_movie_details", "get_artist_top_tracks"}


def test_movie_details_declaration_requires_tmdb_id():
    assert "tmdb_id" in GET_MOVIE_DETAILS.parameters.required


def test_artist_tracks_declaration_requires_artist_name():
    assert "artist_name" in GET_ARTIST_TOP_TRACKS.parameters.required
