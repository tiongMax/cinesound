"""Ranker + Pairer tests — gemini_chat_with_tools mocked."""

from unittest.mock import AsyncMock

from app.agents import ranker
from app.agents.ranker import filter_seen, rank_and_pair, top_n
from app.schemas import (
    MovieCandidate,
    MovieProfile,
    MovieRec,
    MusicCandidate,
    MusicProfile,
    MusicRec,
    Recommendation,
    TasteProfile,
)


def _profile() -> TasteProfile:
    return TasteProfile(
        movie_profile=MovieProfile(genres=["Sci-Fi"], mood="reflective"),
        music_profile=MusicProfile(energy="calm", genres=["ambient"], mood="cinematic"),
        shared_mood="reflective, cinematic",
    )


def _movie(tmdb_id: int, score: float, title: str = "Movie") -> MovieCandidate:
    return MovieCandidate(
        tmdb_id=tmdb_id, title=title, year=2020, genres=["Sci-Fi"], score=score
    )


def _music(uri: str, score: float, track: str = "Track") -> MusicCandidate:
    return MusicCandidate(
        spotify_uri=uri,
        track=track,
        artist="Artist",
        spotify_url=f"https://open.spotify.com/track/{uri.split(':')[-1]}",
        score=score,
    )


def _stub_rec() -> Recommendation:
    return Recommendation(
        mood_detected="reflective, cinematic",
        movies=[
            MovieRec(
                tmdb_id=329865,
                title="Arrival",
                year=2016,
                rating=7.9,
                genres=["Sci-Fi", "Drama"],
                reason="Same reflective sci-fi depth",
            )
        ],
        music=[
            MusicRec(
                spotify_uri="spotify:track:abc",
                track="Day One",
                artist="Hans Zimmer",
                album="Interstellar OST",
                mood_tag="cinematic ambient",
                reason="Matches the reflective mood",
                spotify_url="https://open.spotify.com/track/abc",
            )
        ],
        pairing_note="Listen while you watch for full effect.",
    )


# ---------- filter_seen ----------


def test_filter_seen_removes_watched_and_heard():
    movies = [_movie(1, 0.9), _movie(2, 0.8)]
    music = [_music("spotify:track:a", 0.9), _music("spotify:track:b", 0.8)]
    out_m, out_t = filter_seen(movies, music, [1], ["spotify:track:b"])
    assert [m.tmdb_id for m in out_m] == [2]
    assert [t.spotify_uri for t in out_t] == ["spotify:track:a"]


def test_filter_seen_passes_through_when_empty_memory():
    movies = [_movie(1, 0.9)]
    music = [_music("spotify:track:a", 0.9)]
    out_m, out_t = filter_seen(movies, music, [], [])
    assert len(out_m) == 1
    assert len(out_t) == 1


# ---------- top_n ----------


def test_top_n_sorts_by_score_desc_and_truncates():
    movies = [_movie(i, 0.1 * i) for i in range(1, 11)]
    music = [_music(f"spotify:track:{i}", 0.1 * i) for i in range(1, 11)]
    out_m, out_t = top_n(movies, music, n=3)
    assert [m.tmdb_id for m in out_m] == [10, 9, 8]
    assert [t.spotify_uri for t in out_t] == [
        "spotify:track:10",
        "spotify:track:9",
        "spotify:track:8",
    ]


# ---------- rank_and_pair ----------


async def test_rank_and_pair_returns_empty_pairing_when_all_filtered(monkeypatch):
    mock = AsyncMock(return_value=_stub_rec())
    monkeypatch.setattr(ranker, "gemini_chat_with_tools", mock)

    movies = [_movie(1, 0.9), _movie(2, 0.8)]
    music = [_music("spotify:track:a", 0.9)]
    memory = {"watched_movies": [1, 2], "heard_tracks": ["spotify:track:a"]}

    rec = await rank_and_pair(_profile(), movies, music, memory=memory)

    assert rec.movies == []
    assert rec.music == []
    assert "fresh" in rec.pairing_note.lower() or "different" in rec.pairing_note.lower()
    mock.assert_not_awaited()


async def test_rank_and_pair_calls_gemini_with_top_candidates(monkeypatch):
    mock = AsyncMock(return_value=_stub_rec())
    monkeypatch.setattr(ranker, "gemini_chat_with_tools", mock)

    movies = [_movie(i, 0.1 * i, f"Movie{i}") for i in range(1, 11)]
    music = [_music(f"spotify:track:{i}", 0.1 * i) for i in range(1, 11)]

    rec = await rank_and_pair(_profile(), movies, music)

    assert rec.pairing_note == "Listen while you watch for full effect."
    mock.assert_awaited_once()
    prompt = mock.await_args.args[0]
    # Top 5 movies (by score) should appear; bottom 5 should not
    assert "tmdb_id=10 " in prompt
    assert "tmdb_id=1 " not in prompt
    assert "tmdb_id=5 " not in prompt


async def test_rank_and_pair_filters_then_picks(monkeypatch):
    mock = AsyncMock(return_value=_stub_rec())
    monkeypatch.setattr(ranker, "gemini_chat_with_tools", mock)

    movies = [_movie(1, 0.95), _movie(2, 0.90)]
    music = [_music("spotify:track:a", 0.95), _music("spotify:track:b", 0.90)]
    memory = {"watched_movies": [1]}

    await rank_and_pair(_profile(), movies, music, memory=memory)

    prompt = mock.await_args.args[0]
    # tmdb_id=1 was filtered; tmdb_id=2 should appear
    assert "tmdb_id=2" in prompt
    assert "tmdb_id=1 " not in prompt
