"""Joint Profiler tests — gemini_chat is mocked."""

from unittest.mock import AsyncMock

from app.agents import profiler
from app.agents.profiler import _memory_snippet, profile
from app.schemas import MovieProfile, MusicProfile, TasteProfile


def _stub_profile() -> TasteProfile:
    return TasteProfile(
        movie_profile=MovieProfile(themes=["space"], genres=["Sci-Fi"], mood="reflective"),
        music_profile=MusicProfile(energy="calm", genres=["ambient"], mood="cinematic ambient"),
        shared_mood="reflective, cinematic",
    )


def test_memory_snippet_includes_disliked_and_liked():
    s = _memory_snippet(
        {
            "disliked_genres": ["Horror"],
            "liked_genres": ["Sci-Fi", "Drama"],
            "past_moods": ["reflective", "calm", "upbeat"],
        }
    )
    assert "Disliked genres (avoid): Horror" in s
    assert "Liked genres (favour when relevant): Sci-Fi, Drama" in s
    assert "Recent moods: reflective, calm, upbeat" in s


def test_memory_snippet_caps_past_moods_to_last_five():
    s = _memory_snippet({"past_moods": [f"m{i}" for i in range(10)]})
    assert "m5, m6, m7, m8, m9" in s
    assert "m0" not in s


def test_memory_snippet_handles_empty():
    assert _memory_snippet({}) == ""


async def test_profile_invokes_gemini_chat_with_schema(monkeypatch):
    mock = AsyncMock(return_value=_stub_profile())
    monkeypatch.setattr(profiler, "gemini_chat", mock)

    result = await profile("I just finished Interstellar")

    assert result.shared_mood == "reflective, cinematic"
    mock.assert_awaited_once()
    kwargs = mock.await_args.kwargs
    assert kwargs["response_schema"] is TasteProfile
    assert "Interstellar" in mock.await_args.args[0]


async def test_profile_appends_memory_snippet(monkeypatch):
    mock = AsyncMock(return_value=_stub_profile())
    monkeypatch.setattr(profiler, "gemini_chat", mock)

    await profile("upbeat plz", memory={"disliked_genres": ["Horror"]})

    prompt = mock.await_args.args[0]
    assert "User memory" in prompt
    assert "Horror" in prompt


async def test_profile_without_memory_omits_section(monkeypatch):
    mock = AsyncMock(return_value=_stub_profile())
    monkeypatch.setattr(profiler, "gemini_chat", mock)

    await profile("upbeat plz")

    prompt = mock.await_args.args[0]
    assert "User memory" not in prompt
