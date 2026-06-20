"""Memory CRUD unit tests using AsyncMock for the asyncpg pool.

Integration testing against a real Neon DB happens manually with .env wired.
"""

import json
from unittest.mock import AsyncMock

import pytest

from app.memory import (
    append_to_list,
    get_all_memory,
    get_memory,
    migrate_memory,
    set_memory,
)


def make_pool(*, fetchrow_return=None, fetch_return=None, execute_return="OK 1"):
    pool = AsyncMock()
    pool.fetchrow = AsyncMock(return_value=fetchrow_return)
    pool.fetch = AsyncMock(return_value=fetch_return or [])
    pool.execute = AsyncMock(return_value=execute_return)
    return pool


async def test_get_memory_returns_none_for_missing():
    pool = make_pool(fetchrow_return=None)
    assert await get_memory(pool, "u1", "watched_movies") is None


async def test_get_memory_parses_str_jsonb():
    pool = make_pool(fetchrow_return={"value": json.dumps([1, 2, 3])})
    assert await get_memory(pool, "u1", "watched_movies") == [1, 2, 3]


async def test_get_memory_passes_through_already_parsed():
    pool = make_pool(fetchrow_return={"value": [1, 2, 3]})
    assert await get_memory(pool, "u1", "watched_movies") == [1, 2, 3]


async def test_set_memory_serialises_to_json():
    pool = make_pool()
    await set_memory(pool, "u1", "liked_genres", ["Sci-Fi", "Drama"])
    args = pool.execute.call_args[0]
    assert args[1] == "u1"
    assert args[2] == "liked_genres"
    assert json.loads(args[3]) == ["Sci-Fi", "Drama"]


async def test_append_to_list_dedupes(monkeypatch):
    """Existing list contains the item — should not call set."""
    pool = make_pool(fetchrow_return={"value": [157336]})
    await append_to_list(pool, "u1", "watched_movies", 157336)
    # one fetchrow (get_memory), no execute call (no set_memory)
    assert pool.fetchrow.call_count == 1
    assert pool.execute.call_count == 0


async def test_append_to_list_inserts_new_item():
    pool = make_pool(fetchrow_return={"value": [157336]})
    await append_to_list(pool, "u1", "watched_movies", 329865)
    # set_memory was called
    assert pool.execute.call_count == 1
    args = pool.execute.call_args[0]
    assert json.loads(args[3]) == [157336, 329865]


async def test_append_to_list_initialises_empty():
    pool = make_pool(fetchrow_return=None)
    await append_to_list(pool, "u1", "watched_movies", 157336)
    args = pool.execute.call_args[0]
    assert json.loads(args[3]) == [157336]


async def test_append_to_list_rejects_non_list():
    pool = make_pool(fetchrow_return={"value": {"not": "a list"}})
    with pytest.raises(ValueError):
        await append_to_list(pool, "u1", "watched_movies", 1)


async def test_get_all_memory_aggregates_rows():
    pool = make_pool(
        fetch_return=[
            {"key": "watched_movies", "value": json.dumps([1, 2])},
            {"key": "liked_genres", "value": ["Sci-Fi"]},
        ]
    )
    result = await get_all_memory(pool, "u1")
    assert result == {"watched_movies": [1, 2], "liked_genres": ["Sci-Fi"]}


async def test_migrate_memory_returns_count():
    pool = make_pool(execute_return="INSERT 0 3")
    count = await migrate_memory(pool, "session:abc", "google:xyz")
    assert count == 3
    # two execute calls: insert + delete
    assert pool.execute.call_count == 2
