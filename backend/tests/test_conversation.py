"""Conversation history CRUD + prompt-summary tests."""

import json
from unittest.mock import AsyncMock

from app.conversation import (
    MAX_TURNS_KEPT,
    TURNS_FED_TO_PROFILER,
    append_turn,
    load_recent_turns,
    summarise_for_prompt,
)


def make_pool(fetchrow_return=None):
    pool = AsyncMock()
    pool.fetchrow = AsyncMock(return_value=fetchrow_return)
    pool.execute = AsyncMock()
    return pool


async def test_load_recent_turns_returns_empty_when_no_row():
    pool = make_pool(None)
    assert await load_recent_turns(pool, "s1") == []


async def test_load_recent_turns_caps_to_limit():
    history = [{"query": f"q{i}"} for i in range(10)]
    pool = make_pool({"messages": history})
    out = await load_recent_turns(pool, "s1")
    assert len(out) == TURNS_FED_TO_PROFILER
    assert out[-1]["query"] == "q9"


async def test_load_recent_turns_parses_str_jsonb():
    pool = make_pool({"messages": json.dumps([{"query": "x"}])})
    out = await load_recent_turns(pool, "s1")
    assert out == [{"query": "x"}]


async def test_append_turn_creates_row():
    pool = make_pool(None)
    await append_turn(pool, "s1", {"query": "first"})
    args = pool.execute.call_args[0]
    saved = json.loads(args[2])
    assert len(saved) == 1
    assert saved[0]["query"] == "first"
    assert "ts" in saved[0]


async def test_append_turn_trims_to_max():
    existing = [{"query": f"q{i}"} for i in range(MAX_TURNS_KEPT)]
    pool = make_pool({"messages": existing})
    await append_turn(pool, "s1", {"query": "newest"})
    args = pool.execute.call_args[0]
    saved = json.loads(args[2])
    assert len(saved) == MAX_TURNS_KEPT
    assert saved[-1]["query"] == "newest"
    assert saved[0]["query"] == "q1"  # q0 evicted


def test_summarise_for_prompt_renders_compact_lines():
    s = summarise_for_prompt(
        [
            {
                "query": "reflective sci-fi",
                "shared_mood": "reflective, cinematic",
                "picks": [{"movie": "Arrival", "music": "Day One — Hans Zimmer"}],
            }
        ]
    )
    assert "reflective sci-fi" in s
    assert "Arrival" in s
    assert "Hans Zimmer" in s


def test_summarise_for_prompt_handles_empty():
    assert summarise_for_prompt([]) == ""
