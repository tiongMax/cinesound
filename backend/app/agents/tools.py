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


async def search_movies_by_title(title: str, *, limit: int = 3) -> dict[str, Any]:
    """Confirm a title the user mentioned exists in TMDB and pull its real genres + year.

    Used by the Profiler to ground the movie profile when the user references a
    specific title (e.g. "I just finished Interstellar") instead of hallucinating
    the metadata.
    """
    async with TMDBClient() as tmdb:
        results = await tmdb.search_movie(title)
    return {
        "query": title,
        "matches": [
            {
                "tmdb_id": r.get("id"),
                "title": r.get("title"),
                "year": (r.get("release_date") or "")[:4] or None,
                "overview": (r.get("overview") or "")[:200],
                "genre_ids": r.get("genre_ids", []),
                "vote_average": r.get("vote_average"),
            }
            for r in results[:limit]
        ],
    }


async def search_artists(name: str, *, limit: int = 3) -> dict[str, Any]:
    """Disambiguate an artist the user mentioned and pull their Spotify genre tags.

    Used by the Profiler when the user references an artist (e.g. "I love Kendrick")
    so the music profile is grounded in that artist's actual catalogue tags.
    """
    async with SpotifyClient() as spotify:
        artists = await spotify.search_artist(name, limit=limit)
    return {
        "query": name,
        "matches": [
            {
                "id": a.get("id"),
                "name": a.get("name"),
                "genres": a.get("genres", []),
                "popularity": a.get("popularity"),
            }
            for a in artists
        ],
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


SEARCH_MOVIES_BY_TITLE = ToolSpec(
    name="search_movies_by_title",
    description=(
        "Look up movies on TMDB by title. Use this ONLY when the user mentions a "
        "specific movie or show title in their query — never for vague mood queries. "
        "Returns top candidates with their real genres and overview so you can ground "
        "the movie profile in catalogue data instead of guessing."
    ),
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "title": types.Schema(
                type=types.Type.STRING,
                description="Movie or show title the user referenced",
            ),
        },
        required=["title"],
    ),
    handler=search_movies_by_title,
)


SEARCH_ARTISTS = ToolSpec(
    name="search_artists",
    description=(
        "Look up artists on Spotify by name. Use this ONLY when the user mentions a "
        "specific artist or band by name — never for vague mood queries. Returns top "
        "matches with their Spotify genre tags so you can ground the music profile."
    ),
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "name": types.Schema(
                type=types.Type.STRING,
                description="Artist or band name the user referenced",
            ),
        },
        required=["name"],
    ),
    handler=search_artists,
)


PROFILER_TOOLS: list[ToolSpec] = [SEARCH_MOVIES_BY_TITLE, SEARCH_ARTISTS]
