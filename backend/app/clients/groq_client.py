"""Groq fallback client mirroring `gemini_chat`'s signature.

When Gemini errors (rate limit, transient 5xx), the Orchestrator switches to
Groq for the same call shape. Groq exposes an OpenAI-compatible JSON-mode
that handles `response_format={"type": "json_object"}`; we then validate
against the Pydantic schema ourselves.
"""

from __future__ import annotations

from typing import TypeVar

from groq import AsyncGroq
from pydantic import BaseModel

from app.config import settings

DEFAULT_MODEL = "llama-3.3-70b-versatile"

T = TypeVar("T", bound=BaseModel)


class GroqError(RuntimeError):
    pass


_client: AsyncGroq | None = None


def _get_client() -> AsyncGroq:
    global _client
    if _client is not None:
        return _client
    if not settings.groq_api_key:
        raise GroqError("GROQ_API_KEY is not configured")
    _client = AsyncGroq(api_key=settings.groq_api_key)
    return _client


async def groq_chat(
    prompt: str,
    *,
    response_schema: type[T],
    system: str | None = None,
    model: str = DEFAULT_MODEL,
    temperature: float = 0.4,
) -> T:
    """Mirror of `gemini_chat` — returns a validated Pydantic instance."""
    client = _get_client()
    messages: list[dict[str, str]] = []
    if system:
        messages.append({"role": "system", "content": system})
    # Tell the model the schema explicitly — Groq's JSON mode does not
    # enforce schemas, only that output is valid JSON.
    schema_hint = response_schema.model_json_schema()
    messages.append(
        {
            "role": "user",
            "content": (f"{prompt}\n\nReturn JSON matching this schema:\n{schema_hint}"),
        }
    )
    resp = await client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        response_format={"type": "json_object"},
    )
    content = resp.choices[0].message.content
    if not content:
        raise GroqError("Groq returned an empty response")
    try:
        return response_schema.model_validate_json(content)
    except Exception as e:
        raise GroqError(f"Groq response did not match schema: {e}") from e
