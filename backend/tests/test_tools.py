"""Tests for the Ranker's LLM tools (get_movie_details, get_artist_top_tracks)."""

from unittest.mock import AsyncMock

from app.agents import tools as tools_mod
from app.agents.tools import (
    GET_ARTIST_TOP_TRACKS,
    GET_MOVIE_DETAILS,
    PROFILER_TOOLS,
    RANKER_TOOLS,
    SEARCH_ARTISTS,
    SEARCH_MOVIES_BY_TITLE,
    get_artist_top_tracks,
    get_movie_details,
    search_artists,
    search_movies_by_title,
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
            {
                "artistId": 1,
                "artistName": "Hans Zimmer",
                "primaryGenreName": "Soundtrack",
            }
        ]
    )
    fake.search_track = AsyncMock(
        return_value=[
            {
                "trackName": "Day One",
                "collectionName": "Interstellar OST",
                "primaryGenreName": "Soundtrack",
                "previewUrl": "https://audio.example/day-one.m4a",
            },
            {
                "trackName": "Time",
                "collectionName": "Inception OST",
                "primaryGenreName": "Soundtrack",
            },
        ]
    )
    monkeypatch.setattr(tools_mod, "ITunesClient", lambda: fake)

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
    monkeypatch.setattr(tools_mod, "ITunesClient", lambda: fake)

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


# ---------- search_movies_by_title (profiler tool) ----------


async def test_search_movies_by_title_returns_top_matches(monkeypatch):
    fake = AsyncMock()
    fake.__aenter__ = AsyncMock(return_value=fake)
    fake.__aexit__ = AsyncMock(return_value=None)
    fake.search_movie = AsyncMock(
        return_value=[
            {
                "id": 157336,
                "title": "Interstellar",
                "release_date": "2014-11-05",
                "overview": "The adventures of a group of explorers...",
                "genre_ids": [12, 18, 878],
                "vote_average": 8.4,
            },
            {"id": 99, "title": "Interstellar Wars", "release_date": "2001-01-01"},
        ]
    )
    monkeypatch.setattr(tools_mod, "TMDBClient", lambda: fake)

    out = await search_movies_by_title("Interstellar")

    assert out["query"] == "Interstellar"
    assert len(out["matches"]) == 2
    assert out["matches"][0]["title"] == "Interstellar"
    assert out["matches"][0]["year"] == "2014"
    assert 878 in out["matches"][0]["genre_ids"]


# ---------- search_artists (profiler tool) ----------


async def test_search_artists_returns_top_matches(monkeypatch):
    fake = AsyncMock()
    fake.__aenter__ = AsyncMock(return_value=fake)
    fake.__aexit__ = AsyncMock(return_value=None)
    fake.search_artist = AsyncMock(
        return_value=[
            {
                "artistId": 2,
                "artistName": "Kendrick Lamar",
                "primaryGenreName": "Hip-Hop/Rap",
                "artistLinkUrl": "https://music.apple.com/us/artist/kendrick-lamar/id368183298",
            }
        ]
    )
    monkeypatch.setattr(tools_mod, "ITunesClient", lambda: fake)

    out = await search_artists("Kendrick")

    assert out["query"] == "Kendrick"
    assert out["matches"][0]["name"] == "Kendrick Lamar"
    assert "Hip-Hop/Rap" in out["matches"][0]["genres"]


# ---------- profiler tool declarations ----------


def test_profiler_tools_registered():
    names = {t.name for t in PROFILER_TOOLS}
    assert names == {"search_movies_by_title", "search_artists"}


def test_search_movies_declaration_requires_title():
    assert "title" in SEARCH_MOVIES_BY_TITLE.parameters.required


def test_search_artists_declaration_requires_name():
    assert "name" in SEARCH_ARTISTS.parameters.required
