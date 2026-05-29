"""Pure scoring functions for the eval harness.

Kept separate from run.py so they're easy to unit-test and to import.
"""

from __future__ import annotations


def parse_pipe_list(field: str) -> list[str]:
    return [g.strip() for g in field.split("|") if g.strip()]


def parse_mood_tags(field: str) -> list[str]:
    return [m.strip().lower() for m in field.split(";") if m.strip()]


def score_mood_match(detected: str, expected_tags: list[str]) -> bool:
    """True if any expected mood tag appears (case-insensitive) in detected."""
    if not expected_tags or not detected:
        return False
    haystack = detected.lower()
    return any(tag in haystack for tag in expected_tags)


def score_genre_overlap(
    actual_genres: list[str], acceptable_genres: list[str]
) -> bool:
    """True if at least one actual genre is in the acceptable set (case-insensitive)."""
    if not actual_genres or not acceptable_genres:
        return False
    actual_lower = {g.lower() for g in actual_genres}
    acceptable_lower = {g.lower() for g in acceptable_genres}
    return bool(actual_lower & acceptable_lower)


def aggregate(rows: list[dict]) -> dict:
    """Roll up per-row scores into pass rates + counts."""
    n = len(rows)
    if n == 0:
        return {
            "mood_match_rate": 0.0,
            "movie_genre_match_rate": 0.0,
            "music_genre_match_rate": 0.0,
            "errors": 0,
        }
    errors = sum(1 for r in rows if r.get("error"))
    scored = [r for r in rows if not r.get("error")]
    if not scored:
        return {
            "mood_match_rate": 0.0,
            "movie_genre_match_rate": 0.0,
            "music_genre_match_rate": 0.0,
            "errors": errors,
        }
    return {
        "mood_match_rate": sum(1 for r in scored if r["scores"]["mood_match"]) / len(scored),
        "movie_genre_match_rate": sum(
            1 for r in scored if r["scores"]["movie_genre_match"]
        )
        / len(scored),
        "music_genre_match_rate": sum(
            1 for r in scored if r["scores"]["music_genre_match"]
        )
        / len(scored),
        "errors": errors,
    }
