"""Gemini wrapper: structured-JSON chat + batched embeddings.

`gemini_chat` returns a parsed Pydantic instance when given a `response_schema`.
`embed` produces 768-d vectors using `text-embedding-004` and batches to keep
under the per-call payload limit.
"""

from __future__ import annotations

from typing import TypeVar

from google import genai
from google.genai import types
from pydantic import BaseModel

from app.config import settings

DEFAULT_CHAT_MODEL = "gemini-2.5-flash"
DEFAULT_LITE_MODEL = "gemini-2.5-flash-lite"
EMBED_MODEL = "text-embedding-004"
EMBED_DIM = 768
EMBED_BATCH = 100  # Gemini hard ceiling for batch embed

T = TypeVar("T", bound=BaseModel)


class GeminiError(RuntimeError):
    pass


_client: genai.Client | None = None


def _get_client() -> genai.Client:
    global _client
    if _client is not None:
        return _client
    if not settings.gemini_api_key:
        raise GeminiError("GEMINI_API_KEY is not configured")
    _client = genai.Client(api_key=settings.gemini_api_key)
    return _client


async def gemini_chat(
    prompt: str,
    *,
    response_schema: type[T],
    system: str | None = None,
    model: str = DEFAULT_CHAT_MODEL,
    temperature: float = 0.4,
) -> T:
    """One-shot chat call that returns a validated Pydantic instance.

    Uses Gemini's `response_mime_type=application/json` + `response_schema` to
    avoid post-hoc JSON-repair logic. Raises GeminiError if the model returns
    something that does not parse against `response_schema`.
    """
    client = _get_client()
    config = types.GenerateContentConfig(
        temperature=temperature,
        response_mime_type="application/json",
        response_schema=response_schema,
        system_instruction=system,
    )
    resp = await client.aio.models.generate_content(
        model=model,
        contents=prompt,
        config=config,
    )
    parsed = resp.parsed
    if parsed is None:
        raise GeminiError(f"Gemini returned no parseable JSON: {resp.text!r}")
    if not isinstance(parsed, response_schema):
        # SDK sometimes returns dict — coerce
        return response_schema.model_validate(parsed)
    return parsed


async def embed(texts: list[str], *, model: str = EMBED_MODEL) -> list[list[float]]:
    """Embed a list of strings, batched. Returns a list of 768-d vectors in input order."""
    if not texts:
        return []
    client = _get_client()
    out: list[list[float]] = []
    for i in range(0, len(texts), EMBED_BATCH):
        batch = texts[i : i + EMBED_BATCH]
        resp = await client.aio.models.embed_content(
            model=model,
            contents=batch,
        )
        for e in resp.embeddings:
            out.append(list(e.values))
    return out


async def embed_one(text: str, *, model: str = EMBED_MODEL) -> list[float]:
    vectors = await embed([text], model=model)
    return vectors[0]
