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


async def test_embed_uses_current_model_and_768_dimensions(monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from app.clients import gemini

    mock_models = SimpleNamespace(
        embed_content=AsyncMock(
            return_value=SimpleNamespace(
                embeddings=[
                    SimpleNamespace(values=[0.1] * EMBED_DIM),
                    SimpleNamespace(values=[0.2] * EMBED_DIM),
                ]
            )
        )
    )
    monkeypatch.setattr(gemini, "_client", SimpleNamespace(aio=SimpleNamespace(models=mock_models)))
    monkeypatch.setattr(gemini.settings, "gemini_api_key", "fake")

    out = await embed(["movie mood", "music mood"])

    assert len(out) == 2
    call = mock_models.embed_content.await_args.kwargs
    assert call["model"] == "gemini-embedding-001"
    assert call["config"].output_dimensionality == EMBED_DIM
