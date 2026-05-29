"""Tests for the Gemini tool-calling loop (gemini_chat_with_tools)."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from google.genai import types
from pydantic import BaseModel

from app.agents.tools import ToolSpec
from app.clients import gemini as gem_mod
from app.clients.gemini import GeminiError, gemini_chat_with_tools


class _Out(BaseModel):
    answer: str


def _final_response(payload: dict | None, text: str | None = None) -> SimpleNamespace:
    """Build a fake Gemini response with no function_calls — just final JSON."""
    return SimpleNamespace(
        candidates=[
            SimpleNamespace(
                content=SimpleNamespace(parts=[SimpleNamespace(function_call=None)])
            )
        ],
        parsed=_Out.model_validate(payload) if payload else None,
        text=text or "",
    )


def _tool_call_response(name: str, args: dict) -> SimpleNamespace:
    """Build a fake Gemini response that requests a tool call."""
    fc = SimpleNamespace(name=name, args=args)
    part = SimpleNamespace(function_call=fc)
    content = SimpleNamespace(parts=[part])
    return SimpleNamespace(
        candidates=[SimpleNamespace(content=content)],
        parsed=None,
        text="",
    )


def _make_mock_client(responses: list):
    """Wire a mock matching the `client.aio.models.generate_content` shape."""
    mock_models = SimpleNamespace(generate_content=AsyncMock(side_effect=responses))
    mock_aio = SimpleNamespace(models=mock_models)
    return SimpleNamespace(aio=mock_aio)


# ---------- happy paths ----------


async def test_returns_immediately_when_no_tool_call(monkeypatch):
    """Model produces final JSON on the first turn — no tool execution at all."""
    client = _make_mock_client([_final_response({"answer": "direct"})])
    monkeypatch.setattr(gem_mod, "_client", client)
    monkeypatch.setattr(gem_mod.settings, "gemini_api_key", "fake")

    handler = AsyncMock(return_value={"unused": True})
    tool = ToolSpec(
        name="get_x",
        description="d",
        parameters=types.Schema(type=types.Type.OBJECT, properties={}, required=[]),
        handler=handler,
    )

    out = await gemini_chat_with_tools("hi", response_schema=_Out, tools=[tool])
    assert out.answer == "direct"
    handler.assert_not_awaited()


async def test_executes_one_tool_then_returns(monkeypatch):
    """Turn 1: model asks for a tool. Turn 2: model returns final JSON."""
    client = _make_mock_client(
        [
            _tool_call_response("get_x", {"q": "foo"}),
            _final_response({"answer": "after tool"}),
        ]
    )
    monkeypatch.setattr(gem_mod, "_client", client)
    monkeypatch.setattr(gem_mod.settings, "gemini_api_key", "fake")

    handler = AsyncMock(return_value={"value": 42})
    tool = ToolSpec(
        name="get_x",
        description="d",
        parameters=types.Schema(type=types.Type.OBJECT, properties={}, required=[]),
        handler=handler,
    )

    out = await gemini_chat_with_tools("hi", response_schema=_Out, tools=[tool])
    assert out.answer == "after tool"
    handler.assert_awaited_once_with(q="foo")


async def test_tool_handler_exception_returns_error_to_model(monkeypatch):
    """Handler raises — we feed the error back, model still returns final JSON next turn."""
    client = _make_mock_client(
        [
            _tool_call_response("get_x", {}),
            _final_response({"answer": "recovered"}),
        ]
    )
    monkeypatch.setattr(gem_mod, "_client", client)
    monkeypatch.setattr(gem_mod.settings, "gemini_api_key", "fake")

    handler = AsyncMock(side_effect=RuntimeError("oops"))
    tool = ToolSpec(
        name="get_x",
        description="d",
        parameters=types.Schema(type=types.Type.OBJECT, properties={}, required=[]),
        handler=handler,
    )

    out = await gemini_chat_with_tools("hi", response_schema=_Out, tools=[tool])
    assert out.answer == "recovered"


# ---------- failure modes ----------


async def test_max_iterations_raises(monkeypatch):
    """Model never stops requesting tools — we cap and raise."""
    # 3 tool calls in a row (max_tool_iterations=2 means we allow 2 tool turns,
    # then a 3rd turn must produce final response)
    responses = [
        _tool_call_response("get_x", {}),
        _tool_call_response("get_x", {}),
        _tool_call_response("get_x", {}),  # still asking — should fail
    ]
    client = _make_mock_client(responses)
    monkeypatch.setattr(gem_mod, "_client", client)
    monkeypatch.setattr(gem_mod.settings, "gemini_api_key", "fake")

    handler = AsyncMock(return_value={"ok": True})
    tool = ToolSpec(
        name="get_x",
        description="d",
        parameters=types.Schema(type=types.Type.OBJECT, properties={}, required=[]),
        handler=handler,
    )

    with pytest.raises(GeminiError, match="iterations"):
        await gemini_chat_with_tools(
            "hi", response_schema=_Out, tools=[tool], max_tool_iterations=2
        )


async def test_unknown_tool_falls_through(monkeypatch):
    """LLM asks for a tool we didn't register — we report it back and continue."""
    client = _make_mock_client(
        [
            _tool_call_response("nonexistent", {}),
            _final_response({"answer": "handled unknown"}),
        ]
    )
    monkeypatch.setattr(gem_mod, "_client", client)
    monkeypatch.setattr(gem_mod.settings, "gemini_api_key", "fake")

    tool = ToolSpec(
        name="real_tool",
        description="d",
        parameters=types.Schema(type=types.Type.OBJECT, properties={}, required=[]),
        handler=AsyncMock(),
    )

    out = await gemini_chat_with_tools("hi", response_schema=_Out, tools=[tool])
    assert out.answer == "handled unknown"


async def test_empty_tools_delegates_to_gemini_chat(monkeypatch):
    """When `tools=[]` we route through the plain gemini_chat path."""
    plain_mock = AsyncMock(return_value=_Out(answer="plain"))
    monkeypatch.setattr(gem_mod, "gemini_chat", plain_mock)

    out = await gemini_chat_with_tools("hi", response_schema=_Out, tools=[])
    assert out.answer == "plain"
    plain_mock.assert_awaited_once()
