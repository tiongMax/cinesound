"""Unit tests for the eval scoring functions in evals/scoring.py."""

import sys
from pathlib import Path

EVALS_DIR = Path(__file__).resolve().parents[2] / "evals"
sys.path.insert(0, str(EVALS_DIR))

from scoring import (  # noqa: E402
    aggregate,
    parse_mood_tags,
    parse_pipe_list,
    score_genre_overlap,
    score_mood_match,
)

# ---------- parsers ----------


def test_parse_pipe_list_strips_and_drops_empty():
    assert parse_pipe_list("Sci-Fi|Drama|") == ["Sci-Fi", "Drama"]
    assert parse_pipe_list("") == []


def test_parse_mood_tags_lowercases_and_splits():
    assert parse_mood_tags("Reflective; Cinematic") == ["reflective", "cinematic"]
    assert parse_mood_tags("") == []


# ---------- mood match ----------


def test_mood_match_true_on_substring():
    assert score_mood_match("reflective, cinematic", ["cinematic"]) is True


def test_mood_match_case_insensitive():
    assert score_mood_match("Cinematic, Calm", ["cinematic"]) is True


def test_mood_match_false_when_no_overlap():
    assert score_mood_match("upbeat, energetic", ["reflective"]) is False


def test_mood_match_empty_inputs():
    assert score_mood_match("", ["x"]) is False
    assert score_mood_match("anything", []) is False


# ---------- genre overlap ----------


def test_genre_overlap_true_on_any_match():
    assert score_genre_overlap(["Sci-Fi", "Drama"], ["Drama", "Comedy"]) is True


def test_genre_overlap_case_insensitive():
    assert score_genre_overlap(["sci-fi"], ["Sci-Fi"]) is True


def test_genre_overlap_false_when_disjoint():
    assert score_genre_overlap(["Horror"], ["Comedy"]) is False


# ---------- aggregate ----------


def test_aggregate_handles_empty():
    out = aggregate([])
    assert out["mood_match_rate"] == 0.0
    assert out["errors"] == 0


def test_aggregate_counts_errors_separately():
    rows = [
        {"error": "boom"},
        {
            "error": None,
            "scores": {
                "mood_match": True,
                "movie_genre_match": True,
                "music_genre_match": False,
                "pairing_quality": None,
            },
        },
        {
            "error": None,
            "scores": {
                "mood_match": False,
                "movie_genre_match": True,
                "music_genre_match": True,
                "pairing_quality": None,
            },
        },
    ]
    out = aggregate(rows)
    assert out["errors"] == 1
    assert out["mood_match_rate"] == 0.5
    assert out["movie_genre_match_rate"] == 1.0
    assert out["music_genre_match_rate"] == 0.5
