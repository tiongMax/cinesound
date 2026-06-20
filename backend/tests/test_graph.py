"""Orchestrator graph tests — every external dep mocked.

We exercise the full graph end-to-end with stubbed agents and stubbed memory
to confirm the wiring (node order, state passing, fallback path) works.
"""

from unittest.mock import AsyncMock

from app.agents import graph as graph_mod
from app.agents.graph import run
from app.clients.gemini import GeminiError
from app.schemas import (  # noqa: I001
    MovieCandidate,
    MovieProfile,
    MovieRec,
    MusicCandidate,
    MusicProfile,
    MusicRec,
    Pairing,
    Recommendation,
    TasteProfile,
)


def _profile() -> TasteProfile:
    return TasteProfile(
        movie_profile=MovieProfile(genres=["Sci-Fi"], mood="reflective"),
        music_profile=MusicProfile(energy="calm", genres=["ambient"], mood="cinematic"),
        shared_mood="reflective, cinematic",
    )


def _rec() -> Recommendation:
    return Recommendation(
        mood_detected="reflective, cinematic",
        pairings=[
            Pairing(
                movie=MovieRec(
                    tmdb_id=329865,
                    title="Arrival",
                    year=2016,
                    rating=7.9,
                    genres=["Sci-Fi", "Drama"],
                    reason="reflective sci-fi",
                ),
                music=MusicRec(
                    spotify_uri="spotify:track:abc",
                    track="Day One",
                    artist="Hans Zimmer",
                    album="Interstellar OST",
                    mood_tag="cinematic ambient",
                    reason="matches mood",
                    spotify_url="https://open.spotify.com/track/abc",
                ),
                pairing_note="Listen to Hans Zimmer while watching Arrival.",
            )
        ],
    )


def _fake_pool():
    """Pool with all methods stubbed to harmless no-ops."""
    pool = AsyncMock()
    pool.fetchrow = AsyncMock(return_value=None)
    pool.fetch = AsyncMock(return_value=[])
    pool.execute = AsyncMock(return_value="OK 1")
    return pool


def _patch_all(monkeypatch, *, profile_fn=None, rec_fn=None):
    """Patch every external dep the graph touches."""
    # reset graph cache so we rebuild each test
    monkeypatch.setattr(graph_mod, "_graph", None)

    profile_fn = profile_fn or AsyncMock(return_value=_profile())
    monkeypatch.setattr(graph_mod, "profile", profile_fn)

    monkeypatch.setattr(
        graph_mod, "search_movies", AsyncMock(return_value=[_stub_movie()])
    )
    monkeypatch.setattr(
        graph_mod, "search_music", AsyncMock(return_value=[_stub_music()])
    )

    rec_fn = rec_fn or AsyncMock(return_value=_rec())
    monkeypatch.setattr(graph_mod, "rank_and_pair", rec_fn)

    monkeypatch.setattr(
        graph_mod, "get_all_memory", AsyncMock(return_value={})
    )
    monkeypatch.setattr(graph_mod, "append_to_list", AsyncMock())
    monkeypatch.setattr(graph_mod, "increment_llm_calls", AsyncMock(return_value=1))
    return profile_fn, rec_fn


def _stub_movie() -> MovieCandidate:
    return MovieCandidate(
        tmdb_id=329865,
        title="Arrival",
        year=2016,
        genres=["Sci-Fi"],
        score=0.9,
    )


def _stub_music() -> MusicCandidate:
    return MusicCandidate(
        spotify_uri="spotify:track:abc",
        track="Day One",
        artist="Hans Zimmer",
        spotify_url="https://open.spotify.com/track/abc",
        score=0.9,
    )


# ---------- happy path ----------


async def test_run_end_to_end_happy_path(monkeypatch):
    profile_fn, rec_fn = _patch_all(monkeypatch)
    pool = _fake_pool()

    result = await run(pool, "I just finished Interstellar", "session:abc")

    assert isinstance(result, Recommendation)
    assert result.pairings[0].pairing_note.startswith("Listen to Hans Zimmer")
    profile_fn.assert_awaited_once()
    rec_fn.assert_awaited_once()
    # both LLM nodes incremented usage
    assert graph_mod.increment_llm_calls.await_count == 2
    # memory was appended for mood + 1 movie + 1 track
    assert graph_mod.append_to_list.await_count == 3


# ---------- Gemini -> Groq fallback ----------


async def test_profile_falls_back_to_groq_on_gemini_error(monkeypatch):
    failing_profile = AsyncMock(side_effect=GeminiError("rate limit"))
    _patch_all(monkeypatch, profile_fn=failing_profile)
    monkeypatch.setattr(
        graph_mod, "groq_chat", AsyncMock(return_value=_profile())
    )
    pool = _fake_pool()

    result = await run(pool, "anything", "session:abc")
    assert result.pairings[0].movie.tmdb_id == 329865
    graph_mod.groq_chat.assert_awaited_once()


async def test_rank_falls_back_to_groq_on_gemini_error(monkeypatch):
    failing_rec = AsyncMock(side_effect=GeminiError("server error"))
    _patch_all(monkeypatch, rec_fn=failing_rec)
    monkeypatch.setattr(
        graph_mod, "groq_chat", AsyncMock(return_value=_rec())
    )
    pool = _fake_pool()

    result = await run(pool, "anything", "session:abc")
    assert result.pairings[0].pairing_note.startswith("Listen to Hans Zimmer")
    graph_mod.groq_chat.assert_awaited_once()
