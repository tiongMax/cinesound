"""Groq client smoke test — confirms it errors cleanly without an API key."""

import pytest

from app.clients.groq_client import GroqError, groq_chat
from app.schemas import TasteProfile


async def test_chat_raises_without_api_key(monkeypatch):
    from app.clients import groq_client

    monkeypatch.setattr(groq_client, "_client", None)
    monkeypatch.setattr(groq_client.settings, "groq_api_key", None)
    with pytest.raises(GroqError):
        await groq_chat("hi", response_schema=TasteProfile)
