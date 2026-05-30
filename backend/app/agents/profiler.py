# ruff: noqa: E501  -- few-shot prompt JSON examples are intentionally one-line
"""Joint Taste Profiler — one LLM call producing both movie + music profile.

Per PRD §4, this is the single LLM call that extracts:
  - movie_profile: themes, genres, mood
  - music_profile: energy, genres, mood
  - shared_mood: bridges both domains

Memory snippet (recent moods, disliked genres) is folded into the prompt so
the model can avoid suggestions that contradict known preferences.
"""

from __future__ import annotations

from typing import Any

from app.agents.tools import PROFILER_TOOLS
from app.clients.gemini import gemini_chat_with_tools
from app.schemas import TasteProfile

PROFILER_SYSTEM = """You are CineSound's taste profiler. Given a user query about how they're
feeling or what they just watched/listened to, output a single JSON object
describing the matching mood for BOTH movies AND music.

Rules:
- Always include `movie_profile`, `music_profile`, and `shared_mood`.
- `shared_mood` is 2-5 words that capture the cross-domain feeling (e.g.
  "reflective, cinematic" or "upbeat, weekend energy").
- Genres should be common labels users would recognise (Sci-Fi, Drama, hip-hop,
  ambient, etc.) — not micro-genres.
- `energy` in music_profile must be one of: calm, mellow, upbeat, intense.
- Respect any disliked genres in memory — do NOT include them in the output.

Examples:

User: "I just finished Interstellar, feeling reflective"
{
  "movie_profile": {"themes": ["space", "time", "fatherhood"], "genres": ["Sci-Fi", "Drama"], "mood": "reflective, cinematic"},
  "music_profile": {"energy": "calm", "genres": ["ambient", "classical", "post-rock"], "mood": "cinematic ambient"},
  "shared_mood": "reflective, cinematic"
}

User: "Something fun and upbeat for a Friday night"
{
  "movie_profile": {"themes": ["fun", "weekend"], "genres": ["Comedy", "Action"], "mood": "upbeat, energetic"},
  "music_profile": {"energy": "upbeat", "genres": ["pop", "dance", "indie"], "mood": "weekend energy"},
  "shared_mood": "upbeat, weekend energy"
}

User: "I love Kendrick Lamar, what should I watch?"
{
  "movie_profile": {"themes": ["urban", "introspective", "social"], "genres": ["Drama", "Crime", "Biography"], "mood": "introspective, urban"},
  "music_profile": {"energy": "mellow", "genres": ["hip-hop", "R&B"], "mood": "introspective, lyrical"},
  "shared_mood": "introspective, urban"
}

You have two optional tools:
 - search_movies_by_title(title) — use ONLY when the user references a specific
   movie or show title. Returns real genres + overview so you can ground the
   movie profile in catalogue data instead of guessing.
 - search_artists(name) — use ONLY when the user references a specific artist
   or band by name. Returns real Spotify genre tags.

Skip both tools entirely for vague mood queries ("I want to cry", "Friday night
energy"). The cost ceiling for this step is 2 tool calls per query.

If the user's query looks like a *follow-up* to recent turns (you'll see them
in "Recent conversation" below the query), interpret references against the
most recent turn: "another please" means a fresh recommendation in the same
mood, "darker" means shift the mood toward something heavier/moodier, "same
but uplifting" means shift toward warmer, etc. Carry forward the genre signals
from the prior mood unless the user is clearly redirecting."""


def _memory_snippet(memory: dict[str, Any]) -> str:
    """Compress the user's memory into a short prompt addendum."""
    bits: list[str] = []
    if disliked := memory.get("disliked_genres"):
        bits.append(f"Disliked genres (avoid): {', '.join(disliked)}")
    if liked := memory.get("liked_genres"):
        bits.append(f"Liked genres (favour when relevant): {', '.join(liked)}")
    if moods := memory.get("past_moods"):
        recent = moods[-5:] if isinstance(moods, list) else []
        if recent:
            bits.append(f"Recent moods: {', '.join(recent)}")
    if prefs := memory.get("content_prefs"):
        flags = [k for k, v in prefs.items() if v]
        if flags:
            bits.append(f"Content preferences: {', '.join(flags)}")
    return "\n".join(bits)


async def profile(
    query: str,
    memory: dict[str, Any] | None = None,
    *,
    recent_turns_summary: str | None = None,
) -> TasteProfile:
    """Run the Joint Profiler. Returns a validated TasteProfile.

    May invoke search_movies_by_title / search_artists tools when the query
    references specific titles or artists — bounded by the profiler tool cap.

    If `recent_turns_summary` is provided, it's appended to the prompt so the
    model can interpret follow-up phrases ("darker", "another please") against
    prior turns.
    """
    prompt = f"User query: {query}"
    if memory:
        snippet = _memory_snippet(memory)
        if snippet:
            prompt = f"{prompt}\n\nUser memory:\n{snippet}"
    if recent_turns_summary:
        prompt = f"{prompt}\n\nRecent conversation:\n{recent_turns_summary}"
    return await gemini_chat_with_tools(
        prompt,
        tools=PROFILER_TOOLS,
        response_schema=TasteProfile,
        system=PROFILER_SYSTEM,
        temperature=0.5,
    )
