"""All data contracts for CineSound.

These models are the canonical types shared between agents, API routes,
and the database. The output schema (`Recommendation`) is also serialised
straight to the client per PRD §8.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


# ---------- Final output (PRD §8) ----------


class MovieRec(BaseModel):
    tmdb_id: int
    title: str
    year: int | None = None
    rating: float | None = None
    genres: list[str] = Field(default_factory=list)
    reason: str
    trailer_url: str | None = None
    poster_url: str | None = None


class MusicRec(BaseModel):
    spotify_uri: str
    track: str
    artist: str
    album: str | None = None
    mood_tag: str
    reason: str
    spotify_url: str
    album_art_url: str | None = None


class Recommendation(BaseModel):
    """Final response shape returned to the client."""

    mood_detected: str
    movies: list[MovieRec]
    music: list[MusicRec]
    pairing_note: str


# ---------- Taste profile (Joint Profiler output, T15) ----------


class MovieProfile(BaseModel):
    themes: list[str] = Field(default_factory=list)
    genres: list[str] = Field(default_factory=list)
    mood: str


class MusicProfile(BaseModel):
    energy: Literal["calm", "mellow", "upbeat", "intense"] = "mellow"
    genres: list[str] = Field(default_factory=list)
    mood: str


class TasteProfile(BaseModel):
    movie_profile: MovieProfile
    music_profile: MusicProfile
    shared_mood: str


# ---------- Candidates passed into the Ranker (T16 → T17) ----------


class MovieCandidate(BaseModel):
    tmdb_id: int
    title: str
    year: int | None = None
    rating: float | None = None
    genres: list[str] = Field(default_factory=list)
    overview: str | None = None
    trailer_url: str | None = None
    poster_url: str | None = None
    score: float = 0.0


class MusicCandidate(BaseModel):
    spotify_uri: str
    track: str
    artist: str
    album: str | None = None
    genre: str | None = None
    vibe_description: str | None = None
    spotify_url: str
    album_art_url: str | None = None
    score: float = 0.0


class RankerInput(BaseModel):
    profile: TasteProfile
    movie_candidates: list[MovieCandidate]
    music_candidates: list[MusicCandidate]


# ---------- API request / event types ----------


class QueryRequest(BaseModel):
    query: str = Field(min_length=1, max_length=1000)
    session_id: str = Field(min_length=1, max_length=128)


class Feedback(BaseModel):
    session_id: str
    tmdb_id: int | None = None
    spotify_uri: str | None = None
    vote: Literal["up", "down"]


class SignInRequest(BaseModel):
    id_token: str


# ---------- Memory keys (string constants used in user_memory rows) ----------


class MemoryKey:
    WATCHED_MOVIES = "watched_movies"        # list[int]   tmdb_ids
    HEARD_TRACKS = "heard_tracks"            # list[str]   spotify_uris
    LIKED_GENRES = "liked_genres"            # list[str]
    DISLIKED_GENRES = "disliked_genres"      # list[str]
    PAST_MOODS = "past_moods"                # list[str]
    CONTENT_PREFS = "content_prefs"          # dict[str, bool]  e.g. {"no_horror": true}
