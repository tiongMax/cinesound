"""Playlist agent — builds an N-track playlist for a given mood.

Pipeline:
  1. Reuse the Joint Profiler to get the music sub-profile + shared mood
  2. Run search_music with bigger top_n + filter against heard_tracks
  3. One LLM call orders N tracks + writes title + intro
"""

from __future__ import annotations

from typing import Any

import asyncpg

from app.agents.profiler import profile as run_profiler
from app.agents.search import search_music
from app.clients.gemini import gemini_chat
from app.schemas import MusicCandidate, Playlist

PLAYLIST_SYSTEM = """You are CineSound's playlist curator. Given a user's mood
plus a shortlist of candidate tracks pre-filtered for taste, you build a
playlist that:

1. Picks exactly N tracks (told to you in the prompt) — no more, no less.
2. Orders them as a *journey* — easing in, building, settling — not random.
3. Writes a `title` of 3-6 evocative words that captures the playlist's feel.
4. Writes an `intro` (1-2 sentences) describing the vibe the playlist holds.
5. For each track, writes a one-sentence `reason` explaining its place.

Use the candidate metadata as-is for spotify_uri, track, artist, album, urls.
Do not invent tracks. Set `mood_detected` to the user's shared mood verbatim."""


def _build_prompt(mood: str, length: int, candidates: list[MusicCandidate]) -> str:
    lines = [
        f"- spotify_uri={c.spotify_uri} | {c.track} — {c.artist} | "
        f"album={c.album} | genre={c.genre} | vibe: {(c.vibe_description or '')[:200]}"
        for c in candidates
    ]
    return (
        f"Mood: {mood}\n"
        f"Length: {length} tracks\n\n"
        f"Candidates ({len(candidates)} pre-ranked by similarity):\n"
        + "\n".join(lines)
        + f"\n\nBuild a {length}-track playlist."
    )


async def build_playlist(
    pool: asyncpg.Pool,
    query: str,
    *,
    length: int = 5,
    memory: dict[str, Any] | None = None,
) -> Playlist:
    """End-to-end playlist build. Returns a Playlist with N tracks."""
    profile_obj = await run_profiler(query, memory=memory)
    # Over-fetch so the LLM has room to skip mismatches and so we can filter heard tracks.
    candidates = await search_music(pool, profile_obj, top_n=max(length * 3, 20))

    heard = set((memory or {}).get("heard_tracks") or [])
    fresh = [c for c in candidates if c.spotify_uri not in heard]
    if len(fresh) < length:
        # Not enough fresh candidates — allow re-recommends rather than returning short
        fresh = candidates

    fresh = fresh[: max(length * 3, length)]
    prompt = _build_prompt(profile_obj.shared_mood, length, fresh)
    pl = await gemini_chat(
        prompt,
        response_schema=Playlist,
        system=PLAYLIST_SYSTEM,
        temperature=0.6,
    )
    # splice preview_urls onto the LLM's picks by URI
    by_uri = {c.spotify_uri: c.preview_url for c in fresh}
    for t in pl.tracks:
        if t.preview_url is None:
            t.preview_url = by_uri.get(t.spotify_uri)
    return pl
