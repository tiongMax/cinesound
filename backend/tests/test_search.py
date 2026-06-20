"""Search module tests — gemini.embed_one and asyncpg pool both mocked."""

import json
from unittest.mock import AsyncMock

from app.agents import search
from app.agents.search import (
    _genres_for_movie,
    _profile_to_movie_query,
    _profile_to_music_query,
    search_movies,
    search_music,
)
from app.schemas import MovieProfile, MusicProfile, TasteProfile


def _profile() -> TasteProfile:
    return TasteProfile(
        movie_profile=MovieProfile(
            themes=["space", "time"], genres=["Sci-Fi", "Drama"], mood="reflective"
        ),
        music_profile=MusicProfile(
            energy="calm", genres=["ambient", "classical"], mood="cinematic ambient"
        ),
        shared_mood="reflective, cinematic",
    )


def _stub_movie_metadata(tmdb_id: int = 329865):
    return {
        "tmdb_id": tmdb_id,
        "title": "Arrival",
        "year": 2016,
        "rating": 7.9,
        "genre_ids": [878, 18],
        "overview": "A linguist works with the military...",
        "poster_path": "/abc.jpg",
    }


def _stub_music_metadata(uri: str = "spotify:track:abc"):
    return {
        "spotify_uri": uri,
        "track": "Day One",
        "artist": "Hans Zimmer",
        "album": "Interstellar OST",
        "genre": "ambient",
        "vibe_description": "Cinematic, contemplative ambient...",
        "spotify_url": "https://open.spotify.com/track/abc",
        "album_art_url": "https://i.scdn.co/x.jpg",
    }


# ---------- profile → query text ----------


def test_movie_query_includes_mood_and_genres():
    q = _profile_to_movie_query(_profile())
    assert "reflective" in q
    assert "Sci-Fi" in q
    assert "space" in q


def test_music_query_includes_energy():
    q = _profile_to_music_query(_profile())
    assert "energy: calm" in q
    assert "ambient" in q
    assert "cinematic" in q


# ---------- genre mapping ----------


def test_genres_for_movie_maps_tmdb_ids():
    assert _genres_for_movie({"genre_ids": [878, 18]}) == ["Sci-Fi", "Drama"]


def test_genres_for_movie_prefers_names_when_present():
    assert _genres_for_movie({"genres": ["Custom"]}) == ["Custom"]


def test_genres_for_movie_handles_empty():
    assert _genres_for_movie({}) == []


# ---------- search_movies ----------


async def test_search_movies_returns_candidates_in_score_order(monkeypatch):
    monkeypatch.setattr(search, "embed_one", AsyncMock(return_value=[0.1] * 768))
    pool = AsyncMock()
    pool.fetch = AsyncMock(
        return_value=[
            {"metadata": json.dumps(_stub_movie_metadata(329865)), "similarity": 0.92},
            {"metadata": _stub_movie_metadata(157336), "similarity": 0.88},
        ]
    )

    out = await search_movies(pool, _profile(), top_n=10)

    assert len(out) == 2
    assert out[0].tmdb_id == 329865
    assert out[0].score == 0.92
    assert out[0].genres == ["Sci-Fi", "Drama"]
    assert out[0].poster_url == "https://image.tmdb.org/t/p/w500/abc.jpg"


async def test_search_movies_passes_top_n_to_sql(monkeypatch):
    monkeypatch.setattr(search, "embed_one", AsyncMock(return_value=[0.1] * 768))
    pool = AsyncMock()
    pool.fetch = AsyncMock(return_value=[])
    await search_movies(pool, _profile(), top_n=7)
    args = pool.fetch.call_args[0]
    assert args[-1] == 7


# ---------- search_music ----------


async def test_search_music_parses_rows(monkeypatch):
    monkeypatch.setattr(search, "embed_one", AsyncMock(return_value=[0.1] * 768))
    pool = AsyncMock()
    pool.fetch = AsyncMock(
        return_value=[
            {"metadata": _stub_music_metadata(), "similarity": 0.81},
        ]
    )

    out = await search_music(pool, _profile())

    assert len(out) == 1
    assert out[0].spotify_uri == "spotify:track:abc"
    assert out[0].artist == "Hans Zimmer"
    assert out[0].score == 0.81
