"""Verify schemas round-trip against the documented response shape."""

from app.schemas import Recommendation

EXAMPLE = {
    "mood_detected": "reflective, emotional, cinematic",
    "pairings": [
        {
            "movie": {
                "tmdb_id": 329865,
                "title": "Arrival",
                "year": 2016,
                "rating": 7.9,
                "genres": ["Sci-Fi", "Drama"],
                "reason": "Same emotional sci-fi depth as Interstellar",
                "trailer_url": "https://youtube.com/watch?v=xxxxx",
            },
            "music": {
                "spotify_uri": "spotify:track:abc",
                "track": "Day One",
                "artist": "Hans Zimmer",
                "album": "Interstellar OST",
                "mood_tag": "cinematic ambient",
                "reason": "Matches your reflective mood",
                "spotify_url": "https://open.spotify.com/track/abc",
            },
            "pairing_note": (
                "Listen to Hans Zimmer while watching Arrival for the full effect."
            ),
        }
    ],
}


def test_recommendation_round_trip():
    rec = Recommendation.model_validate(EXAMPLE)
    assert rec.mood_detected.startswith("reflective")
    assert len(rec.pairings) == 1
    p = rec.pairings[0]
    assert p.movie.tmdb_id == 329865
    assert p.music.spotify_uri == "spotify:track:abc"
    assert p.pairing_note.startswith("Listen to Hans Zimmer")
    assert rec.fallback_message is None


def test_recommendation_with_fallback_only():
    rec = Recommendation(
        mood_detected="(over cap)",
        pairings=[],
        fallback_message="try again tomorrow",
    )
    assert rec.pairings == []
    assert rec.fallback_message == "try again tomorrow"
