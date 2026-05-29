"""LLM tools exposed to the Ranker.

Each tool is a plain async function plus a JSON-schema declaration the LLM
sees. The Gemini tool-calling loop in `app.clients.gemini.gemini_chat_with_tools`
executes these on demand and feeds results back into the conversation.

We expose deliberately narrow tools (one-shot lookups, no chained reasoning)
so the LLM uses them as a refinement step over candidates the deterministic
ranker has already shortlisted.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from google.genai import types

from app.clients.spotify import SpotifyClient
from app.clients.tmdb import TMDBClient


@dataclass
class ToolSpec:
    """One callable tool the LLM may invoke."""

    name: str
    description: str
    parameters: types.Schema
    handler: Callable[..., Awaitable[Any]]


# ---------- handlers ----------


async def get_movie_details(tmdb_id: int) -> dict[str, Any]:
    """Fetch a richer view of a movie than the 200-char overview the ranker sees by default."""
    async with TMDBClient() as tmdb:
        m = await tmdb.get_movie(tmdb_id)
    return {
        "tmdb_id": m.get("id"),
        "title": m.get("title"),
        "tagline": m.get("tagline"),
        "overview": m.get("overview"),
        "runtime_minutes": m.get("runtime"),
        "release_date": m.get("release_date"),
        "vote_average": m.get("vote_average"),
        "genres": [g.get("name") for g in m.get("genres", []) if g.get("name")],
    }


async def get_artist_top_tracks(artist_name: str, *, limit: int = 5) -> dict[str, Any]:
    """Look up an artist's top tracks — useful when the user mentions a reference artist."""
    async with SpotifyClient() as spotify:
        artists = await spotify.search_artist(artist_name, limit=1)
        if not artists:
            return {"artist": artist_name, "found": False, "top_tracks": []}
        artist = artists[0]
        tracks = await spotify.get_artist_top_tracks(artist["id"])
    return {
        "artist": artist["name"],
        "found": True,
        "genres": artist.get("genres", []),
        "popularity": artist.get("popularity"),
        "top_tracks": [
            {
                "track": t.get("name"),
                "album": t.get("album", {}).get("name"),
                "popularity": t.get("popularity"),
            }
            for t in tracks[:limit]
        ],
    }


# ---------- declarations ----------


GET_MOVIE_DETAILS = ToolSpec(
    name="get_movie_details",
    description=(
        "Fetch full overview + tagline + cast genres + runtime + rating for a specific "
        "movie by its TMDB ID. Use this to deep-dive on the 1-2 movie candidates you're "
        "most likely to pick, when the short overview isn't enough to choose."
    ),
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "tmdb_id": types.Schema(
                type=types.Type.INTEGER,
                description="TMDB movie ID. Must be one of the candidate tmdb_ids you were given.",
            ),
        },
        required=["tmdb_id"],
    ),
    handler=get_movie_details,
)


GET_ARTIST_TOP_TRACKS = ToolSpec(
    name="get_artist_top_tracks",
    description=(
        "Look up an artist's top tracks on Spotify. Use this when the user mentioned a "
        "reference artist in their query and you want to ground the music pick against "
        "that artist's actual catalogue."
    ),
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "artist_name": types.Schema(
                type=types.Type.STRING,
                description="Artist name to search for on Spotify",
            ),
        },
        required=["artist_name"],
    ),
    handler=get_artist_top_tracks,
)


RANKER_TOOLS: list[ToolSpec] = [GET_MOVIE_DETAILS, GET_ARTIST_TOP_TRACKS]
