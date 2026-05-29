"""Ranker + Pairer — deterministic filter, then a single LLM call.

Per PRD §4.1:
  1. Deterministic: filter out items in watched_movies / heard_tracks,
     keep top-N per domain by score
  2. LLM (one call): pick the final movie + track, write the pairing note,
     return the full Recommendation JSON
"""

from __future__ import annotations

from typing import Any

from app.agents.tools import RANKER_TOOLS
from app.clients.gemini import gemini_chat_with_tools
from app.schemas import MovieCandidate, MusicCandidate, Recommendation, TasteProfile

TOP_N_PER_DOMAIN = 5

RANKER_SYSTEM = """You are CineSound's pairing curator. You receive a user's
shared mood plus a shortlist of movie and music candidates that have already
been pre-filtered for taste. Your job:

1. Pick exactly ONE movie and ONE track from the lists that best fit the shared mood.
2. Write a one-sentence `reason` for each pick explaining WHY it matches the mood.
3. Write a `pairing_note` (1-2 sentences) explaining why the movie + track
   complement each other for the user's mood. The pairing note is the magic
   moment of the product — be specific, evocative, no clichés.
4. Set `mood_detected` to the shared mood verbatim.

You have two optional tools available:
 - `get_movie_details(tmdb_id)` — pulls a richer overview / tagline / runtime for a
   specific candidate. Use this sparingly (max 1-2 calls) when the short overview
   isn't enough to choose between top candidates.
 - `get_artist_top_tracks(artist_name)` — when the user named a reference artist in
   their query, use this to ground your music pick against that artist's catalogue.

Skip the tools entirely if the choice is already obvious. Use the candidate
metadata as-is for tmdb_id, spotify_uri, title, year, etc. Do not invent fields.
Output a single Recommendation JSON object."""


def filter_seen(
    movies: list[MovieCandidate],
    music: list[MusicCandidate],
    watched_movies: list[int],
    heard_tracks: list[str],
) -> tuple[list[MovieCandidate], list[MusicCandidate]]:
    """Strip out anything the user has already watched/heard."""
    watched = set(watched_movies)
    heard = set(heard_tracks)
    return (
        [m for m in movies if m.tmdb_id not in watched],
        [t for t in music if t.spotify_uri not in heard],
    )


def top_n(
    movies: list[MovieCandidate],
    music: list[MusicCandidate],
    *,
    n: int = TOP_N_PER_DOMAIN,
) -> tuple[list[MovieCandidate], list[MusicCandidate]]:
    return (
        sorted(movies, key=lambda m: m.score, reverse=True)[:n],
        sorted(music, key=lambda t: t.score, reverse=True)[:n],
    )


def _build_prompt(
    profile: TasteProfile,
    movies: list[MovieCandidate],
    music: list[MusicCandidate],
) -> str:
    movie_lines = [
        f"- tmdb_id={m.tmdb_id} | {m.title} ({m.year}) | genres={','.join(m.genres)} | "
        f"overview: {(m.overview or '')[:200]}"
        for m in movies
    ]
    music_lines = [
        f"- spotify_uri={t.spotify_uri} | {t.track} — {t.artist} | genre={t.genre} | "
        f"vibe: {(t.vibe_description or '')[:200]}"
        for t in music
    ]
    return (
        f"Shared mood: {profile.shared_mood}\n"
        f"Movie mood: {profile.movie_profile.mood}\n"
        f"Music mood: {profile.music_profile.mood}\n\n"
        f"Movie candidates:\n" + "\n".join(movie_lines) + "\n\n"
        "Music candidates:\n" + "\n".join(music_lines) + "\n\n"
        "Pick one movie + one track and write the pairing."
    )


async def rank_and_pair(
    profile: TasteProfile,
    movie_candidates: list[MovieCandidate],
    music_candidates: list[MusicCandidate],
    *,
    memory: dict[str, Any] | None = None,
) -> Recommendation:
    """Deterministic filter + 1 LLM call. Returns the final Recommendation."""
    memory = memory or {}
    watched = memory.get("watched_movies") or []
    heard = memory.get("heard_tracks") or []

    movies, music = filter_seen(movie_candidates, music_candidates, watched, heard)
    movies, music = top_n(movies, music)

    if not movies or not music:
        # No candidates left after filtering — return a graceful empty pairing
        return Recommendation(
            mood_detected=profile.shared_mood,
            movies=[],
            music=[],
            pairing_note=(
                "Couldn't find a fresh pairing this time — try a slightly different mood, "
                "or clear some of your watch history."
            ),
        )

    prompt = _build_prompt(profile, movies, music)
    return await gemini_chat_with_tools(
        prompt,
        tools=RANKER_TOOLS,
        response_schema=Recommendation,
        system=RANKER_SYSTEM,
        temperature=0.6,
    )
