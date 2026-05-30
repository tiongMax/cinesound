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
TARGET_PAIRINGS = 3

RANKER_SYSTEM = """You are CineSound's pairing curator. You receive a user's
shared mood plus a shortlist of movie and music candidates that have already
been pre-filtered for taste. Your job:

1. Build **exactly 3 distinct pairings**, each one movie + one track + a
   per-pairing note. The 3 pairings should sit at different points along the
   shared mood — e.g. classic / left-field / palette-cleansing — not three
   variations of the same pick.
2. Within each pairing:
   - `reason` on the movie: one sentence on WHY this movie fits the mood.
   - `reason` on the music: one sentence on WHY this track fits the mood.
   - `pairing_note` on the pairing: 1-2 sentences on WHY the movie + track
     complement each other. Be specific and evocative; no clichés.
3. Set `mood_detected` to the shared mood verbatim.
4. Do not reuse the same movie or track across pairings.

You have two optional tools available:
 - `get_movie_details(tmdb_id)` — pulls a richer overview / tagline / runtime for a
   specific candidate. Use sparingly (max 1-2 calls) on the candidates you're most
   likely to pick.
 - `get_artist_top_tracks(artist_name)` — when the user named a reference artist
   in their query, use this to ground a music pick against that artist's catalogue.

Skip the tools entirely if the choices are already obvious. Use the candidate
metadata as-is for tmdb_id, spotify_uri, title, year, etc. Do not invent fields.
Output a single Recommendation JSON object with a `pairings` array of length 3."""


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
        f"Build {TARGET_PAIRINGS} distinct pairings."
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
        return Recommendation(
            mood_detected=profile.shared_mood,
            pairings=[],
            fallback_message=(
                "Couldn't find a fresh pairing this time — try a slightly different "
                "mood, or clear some of your watch history."
            ),
        )

    prompt = _build_prompt(profile, movies, music)
    rec = await gemini_chat_with_tools(
        prompt,
        tools=RANKER_TOOLS,
        response_schema=Recommendation,
        system=RANKER_SYSTEM,
        temperature=0.6,
    )
    return _enrich_pairings_with_preview_urls(rec, music)


def _enrich_pairings_with_preview_urls(
    rec: Recommendation, candidates: list[MusicCandidate]
) -> Recommendation:
    """Copy preview_url from candidates onto each picked pairing.

    The LLM doesn't see preview_url in the prompt — we splice it in by URI
    so the frontend can play the 30-second clip.
    """
    by_uri = {c.spotify_uri: c.preview_url for c in candidates}
    for p in rec.pairings:
        if p.music.preview_url is None:
            p.music.preview_url = by_uri.get(p.music.spotify_uri)
    return rec
