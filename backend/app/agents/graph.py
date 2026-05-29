"""LangGraph orchestrator.

State machine (PRD §4):
  START
    -> load_memory      (reads user_memory for the session_id)
    -> profile          (Joint Profiler — 1 LLM call)
    -> search           (parallel TMDB-side + Spotify-side pgvector queries)
    -> rank_and_pair    (Ranker + Pairer — 1 LLM call)
    -> save_memory      (appends mood, watched/heard, increments daily counter)
    -> END

Gemini errors at the profile or rank steps trigger a one-shot fallback to
Groq (Llama 3.3 70B) with the same prompt + schema.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, TypedDict

import asyncpg
from langgraph.graph import END, START, StateGraph

from app.agents.profiler import PROFILER_SYSTEM, profile
from app.agents.ranker import RANKER_SYSTEM, _build_prompt, filter_seen, rank_and_pair, top_n
from app.agents.search import search_movies, search_music
from app.clients.gemini import GeminiError
from app.clients.groq_client import groq_chat
from app.memory import append_to_list, get_all_memory
from app.schemas import (
    MemoryKey,
    MovieCandidate,
    MusicCandidate,
    Recommendation,
    TasteProfile,
)
from app.usage import increment_llm_calls

log = logging.getLogger(__name__)

PAST_MOODS_MAX = 50


class GraphState(TypedDict, total=False):
    # input
    query: str
    session_id: str
    pool: asyncpg.Pool
    # intermediate
    memory: dict[str, Any]
    profile: TasteProfile
    movie_candidates: list[MovieCandidate]
    music_candidates: list[MusicCandidate]
    # output
    recommendation: Recommendation


# ---------- nodes ----------


async def _load_memory_node(state: GraphState) -> dict[str, Any]:
    memory = await get_all_memory(state["pool"], state["session_id"])
    return {"memory": memory}


async def _profile_node(state: GraphState) -> dict[str, Any]:
    try:
        prof = await profile(state["query"], memory=state.get("memory"))
    except GeminiError as e:
        log.warning("profile: Gemini failed (%s) — falling back to Groq", e)
        prof = await groq_chat(
            f"User query: {state['query']}",
            response_schema=TasteProfile,
            system=PROFILER_SYSTEM,
        )
    await increment_llm_calls(state["pool"])
    return {"profile": prof}


async def _search_node(state: GraphState) -> dict[str, Any]:
    movies, music = await asyncio.gather(
        search_movies(state["pool"], state["profile"]),
        search_music(state["pool"], state["profile"]),
    )
    return {"movie_candidates": movies, "music_candidates": music}


async def _rank_and_pair_node(state: GraphState) -> dict[str, Any]:
    try:
        rec = await rank_and_pair(
            state["profile"],
            state["movie_candidates"],
            state["music_candidates"],
            memory=state.get("memory"),
        )
    except GeminiError as e:
        log.warning("rank: Gemini failed (%s) — falling back to Groq", e)
        memory = state.get("memory") or {}
        movies, music = filter_seen(
            state["movie_candidates"],
            state["music_candidates"],
            memory.get("watched_movies") or [],
            memory.get("heard_tracks") or [],
        )
        movies, music = top_n(movies, music)
        if not movies or not music:
            rec = Recommendation(
                mood_detected=state["profile"].shared_mood,
                movies=[],
                music=[],
                pairing_note="Couldn't find a fresh pairing this time — try a different mood.",
            )
        else:
            rec = await groq_chat(
                _build_prompt(state["profile"], movies, music),
                response_schema=Recommendation,
                system=RANKER_SYSTEM,
            )
    await increment_llm_calls(state["pool"])
    return {"recommendation": rec}


async def _save_memory_node(state: GraphState) -> dict[str, Any]:
    pool = state["pool"]
    sid = state["session_id"]
    rec = state["recommendation"]
    prof = state["profile"]

    if prof.shared_mood:
        await append_to_list(
            pool, sid, MemoryKey.PAST_MOODS, prof.shared_mood, dedupe=False
        )
        # cap the list so memory doesn't grow forever
        moods = state.get("memory", {}).get(MemoryKey.PAST_MOODS) or []
        if len(moods) + 1 > PAST_MOODS_MAX:
            from app.memory import set_memory

            new_moods = (moods + [prof.shared_mood])[-PAST_MOODS_MAX:]
            await set_memory(pool, sid, MemoryKey.PAST_MOODS, new_moods)

    for m in rec.movies:
        await append_to_list(pool, sid, MemoryKey.WATCHED_MOVIES, m.tmdb_id)
    for t in rec.music:
        await append_to_list(pool, sid, MemoryKey.HEARD_TRACKS, t.spotify_uri)

    return {}


# ---------- graph build ----------


def build_graph():
    g: StateGraph = StateGraph(GraphState)
    g.add_node("load_memory", _load_memory_node)
    g.add_node("profile", _profile_node)
    g.add_node("search", _search_node)
    g.add_node("rank_and_pair", _rank_and_pair_node)
    g.add_node("save_memory", _save_memory_node)

    g.add_edge(START, "load_memory")
    g.add_edge("load_memory", "profile")
    g.add_edge("profile", "search")
    g.add_edge("search", "rank_and_pair")
    g.add_edge("rank_and_pair", "save_memory")
    g.add_edge("save_memory", END)

    return g.compile()


_graph = None


def get_graph():
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph


async def run(pool: asyncpg.Pool, query: str, session_id: str) -> Recommendation:
    """Run the orchestrator end-to-end. Returns the final Recommendation."""
    initial: GraphState = {"query": query, "session_id": session_id, "pool": pool}
    final = await get_graph().ainvoke(initial)
    return final["recommendation"]
