"""Gemini wrapper: structured-JSON chat + batched embeddings.

`gemini_chat` returns a parsed Pydantic instance when given a `response_schema`.
`embed` produces 768-d vectors using `gemini-embedding-001` and batches to keep
under the per-call payload limit.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, TypeVar

from google import genai
from google.genai import types
from pydantic import BaseModel

from app.config import settings

if TYPE_CHECKING:
    from app.agents.tools import ToolSpec

log = logging.getLogger(__name__)

DEFAULT_CHAT_MODEL = "gemini-2.5-flash"
DEFAULT_LITE_MODEL = "gemini-2.5-flash-lite"
EMBED_MODEL = "gemini-embedding-001"
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


def _json_prompt_suffix(response_schema: type[BaseModel]) -> str:
    schema = json.dumps(response_schema.model_json_schema(), ensure_ascii=True)
    return (
        "\n\nReturn only a JSON object that validates against this JSON Schema. "
        "Do not wrap it in Markdown or add commentary.\n"
        f"{schema}"
    )


def _parse_response(resp: object, response_schema: type[T]) -> T:
    parsed = getattr(resp, "parsed", None)
    if parsed is not None:
        if not isinstance(parsed, response_schema):
            return response_schema.model_validate(parsed)
        return parsed

    text = (getattr(resp, "text", None) or "").strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    if not text:
        raise GeminiError(f"Gemini returned no parseable JSON: {text!r}")

    try:
        return response_schema.model_validate_json(text)
    except Exception as e:
        raise GeminiError(
            f"Gemini returned invalid JSON for {response_schema.__name__}: {text!r}"
        ) from e


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
        return _parse_response(resp, response_schema)
    if not isinstance(parsed, response_schema):
        # SDK sometimes returns dict — coerce
        return response_schema.model_validate(parsed)
    return parsed


async def gemini_chat_with_tools(
    prompt: str,
    *,
    response_schema: type[T],
    tools: list[ToolSpec],
    system: str | None = None,
    model: str = DEFAULT_CHAT_MODEL,
    temperature: float = 0.4,
    max_tool_iterations: int = 2,
) -> T:
    """Manual function-calling loop returning a Pydantic-validated final response.

    Pattern:
      1. Build FunctionDeclarations from the ToolSpecs.
      2. Call Gemini with tools, but parse the final JSON locally because
         Gemini does not support function calling with JSON response mime type.
      3. If the response contains function_calls, execute the handlers, append
         the function_response parts to history, repeat.
      4. When the model produces a final response with no function_calls,
         parse it against response_schema.

    Bounded by `max_tool_iterations` to keep cost predictable. A run that fails
    to terminate raises GeminiError rather than looping forever.
    """
    if not tools:
        return await gemini_chat(
            prompt,
            response_schema=response_schema,
            system=system,
            model=model,
            temperature=temperature,
        )

    client = _get_client()
    declarations = [
        types.FunctionDeclaration(
            name=t.name,
            description=t.description,
            parameters=t.parameters,
        )
        for t in tools
    ]
    handlers = {t.name: t.handler for t in tools}

    config = types.GenerateContentConfig(
        temperature=temperature,
        tools=[types.Tool(function_declarations=declarations)],
        system_instruction=system,
    )

    history: list[types.Content] = [
        types.Content(
            role="user",
            parts=[types.Part(text=prompt + _json_prompt_suffix(response_schema))],
        ),
    ]

    for iteration in range(max_tool_iterations + 1):
        resp = await client.aio.models.generate_content(
            model=model,
            contents=history,
            config=config,
        )
        candidate = resp.candidates[0] if resp.candidates else None
        if candidate is None or candidate.content is None:
            raise GeminiError("Gemini returned no candidate content")

        function_calls = [
            p.function_call for p in (candidate.content.parts or []) if p.function_call
        ]

        if not function_calls:
            # Final response — should be parseable JSON against schema
            return _parse_response(resp, response_schema)

        if iteration == max_tool_iterations:
            raise GeminiError(
                f"Gemini still requesting tools after {max_tool_iterations} iterations"
            )

        # Append the model's tool-call turn + execute each call
        history.append(candidate.content)
        tool_response_parts: list[types.Part] = []
        for fc in function_calls:
            handler = handlers.get(fc.name)
            if handler is None:
                result: object = {"error": f"unknown tool: {fc.name}"}
            else:
                try:
                    result = await handler(**dict(fc.args or {}))
                except Exception as e:
                    log.warning("tool %s failed: %s", fc.name, e)
                    result = {"error": str(e)[:200]}
            tool_response_parts.append(
                types.Part(
                    function_response=types.FunctionResponse(
                        name=fc.name,
                        response={"result": result},
                    )
                )
            )
        history.append(types.Content(role="user", parts=tool_response_parts))

    # Defensive — should be unreachable thanks to the iteration cap above
    raise GeminiError("tool loop terminated without a final response")


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
            config=types.EmbedContentConfig(output_dimensionality=EMBED_DIM),
        )
        for e in resp.embeddings:
            out.append(list(e.values))
    return out


async def embed_one(text: str, *, model: str = EMBED_MODEL) -> list[float]:
    vectors = await embed([text], model=model)
    return vectors[0]
