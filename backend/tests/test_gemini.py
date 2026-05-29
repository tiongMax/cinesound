"""Gemini client smoke tests.

We deliberately don't mock the google-genai SDK — the surface is large and
mocks would be brittle. Real verification is an integration test executed
when GEMINI_API_KEY is configured.
"""

import pytest

from app.clients.gemini import EMBED_DIM, GeminiError, embed, gemini_chat
from app.schemas import TasteProfile


def test_imports_and_constants():
    assert EMBED_DIM == 768


async def test_chat_raises_without_api_key(monkeypatch):
    from app.clients import gemini

    monkeypatch.setattr(gemini, "_client", None)
    monkeypatch.setattr(gemini.settings, "gemini_api_key", None)
    with pytest.raises(GeminiError):
        await gemini_chat("hi", response_schema=TasteProfile)


async def test_embed_empty_returns_empty():
    assert await embed([]) == []
