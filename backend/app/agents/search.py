"""Search module — no LLM.

Embeds the relevant sub-profile, runs pgvector cosine search against the
seed corpus, returns MovieCandidate / MusicCandidate lists. The Ranker
(T17) is responsible for filtering against watched/heard memory.
"""

from __future__ import annotations

import asyncpg

from app.clients.gemini import embed_one
from app.schemas import MovieCandidate, MusicCandidate, TasteProfile

DEFAULT_TOP_N = 20


def _profile_to_movie_query(profile: TasteProfile) -> str:
    """Build the text we embed for movie search."""
    mp = profile.movie_profile
    parts = [profile.shared_mood, mp.mood]
    if mp.themes:
        parts.append("themes: " + ", ".join(mp.themes))
    if mp.genres:
        parts.append("genres: " + ", ".join(mp.genres))
    return ". ".join(p for p in parts if p)


def _profile_to_music_query(profile: TasteProfile) -> str:
    """Build the text we embed for music search."""
    mup = profile.music_profile
    parts = [profile.shared_mood, mup.mood, f"energy: {mup.energy}"]
    if mup.genres:
        parts.append("genres: " + ", ".join(mup.genres))
    return ". ".join(p for p in parts if p)


async def search_movies(
    pool: asyncpg.Pool, profile: TasteProfile, *, top_n: int = DEFAULT_TOP_N
) -> list[MovieCandidate]:
    vector = await embed_one(_profile_to_movie_query(profile))
    vec_literal = "[" + ",".join(str(x) for x in vector) + "]"
    rows = await pool.fetch(
        """
        SELECT
          metadata,
          1 - (embedding <=> $1::vector) AS similarity
        FROM embeddings
        WHERE type = 'movie'
        ORDER BY embedding <=> $1::vector
        LIMIT $2
        """,
        vec_literal,
        top_n,
    )
    return [_row_to_movie(r) for r in rows]


async def search_music(
    pool: asyncpg.Pool, profile: TasteProfile, *, top_n: int = DEFAULT_TOP_N
) -> list[MusicCandidate]:
    vector = await embed_one(_profile_to_music_query(profile))
    vec_literal = "[" + ",".join(str(x) for x in vector) + "]"
    rows = await pool.fetch(
        """
        SELECT
          metadata,
          1 - (embedding <=> $1::vector) AS similarity
        FROM embeddings
        WHERE type = 'music'
        ORDER BY embedding <=> $1::vector
        LIMIT $2
        """,
        vec_literal,
        top_n,
    )
    return [_row_to_music(r) for r in rows]


def _row_to_movie(row) -> MovieCandidate:
    m = _parse_metadata(row["metadata"])
    return MovieCandidate(
        tmdb_id=int(m["tmdb_id"]),
        title=m.get("title") or "Untitled",
        year=m.get("year"),
        rating=m.get("rating"),
        genres=_genres_for_movie(m),
        overview=m.get("overview"),
        poster_url=_poster_url(m.get("poster_path")),
        score=float(row["similarity"]),
    )


def _row_to_music(row) -> MusicCandidate:
    m = _parse_metadata(row["metadata"])
    return MusicCandidate(
        spotify_uri=m["spotify_uri"],
        track=m["track"],
        artist=m.get("artist", ""),
        album=m.get("album"),
        genre=m.get("genre"),
        vibe_description=m.get("vibe_description"),
        spotify_url=m.get("spotify_url") or _track_url(m["spotify_uri"]),
        album_art_url=m.get("album_art_url"),
        score=float(row["similarity"]),
    )


def _parse_metadata(value) -> dict:
    if isinstance(value, str):
        import json

        return json.loads(value)
    return dict(value)


# TMDB movie genre IDs (stable, from /genre/movie/list)
TMDB_GENRE_MAP: dict[int, str] = {
    28: "Action",
    12: "Adventure",
    16: "Animation",
    35: "Comedy",
    80: "Crime",
    99: "Documentary",
    18: "Drama",
    10751: "Family",
    14: "Fantasy",
    36: "History",
    27: "Horror",
    10402: "Music",
    9648: "Mystery",
    10749: "Romance",
    878: "Sci-Fi",
    10770: "TV Movie",
    53: "Thriller",
    10752: "War",
    37: "Western",
}


def _genres_for_movie(metadata: dict) -> list[str]:
    """Map TMDB genre_ids to readable names. Falls back to whatever `genres`
    field is present (for future seed runs that may pre-expand names)."""
    if names := metadata.get("genres"):
        return names
    ids = metadata.get("genre_ids") or []
    return [TMDB_GENRE_MAP[i] for i in ids if i in TMDB_GENRE_MAP]


def _poster_url(poster_path: str | None) -> str | None:
    if not poster_path:
        return None
    return f"https://image.tmdb.org/t/p/w500{poster_path}"


def _track_url(spotify_uri: str) -> str:
    kind, _, ident = spotify_uri.rpartition(":")
    kind = kind.split(":")[-1]
    return f"https://open.spotify.com/{kind}/{ident}"
