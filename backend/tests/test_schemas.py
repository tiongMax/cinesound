"""Verify schemas round-trip against the PRD §8 example."""

from app.schemas import Recommendation

PRD_EXAMPLE = {
    "mood_detected": "reflective, emotional, cinematic",
    "movies": [
        {
            "tmdb_id": 329865,
            "title": "Arrival",
            "year": 2016,
            "rating": 7.9,
            "genres": ["Sci-Fi", "Drama"],
            "reason": "Same emotional sci-fi depth as Interstellar",
            "trailer_url": "https://youtube.com/watch?v=xxxxx",
        }
    ],
    "music": [
        {
            "spotify_uri": "spotify:track:abc",
            "track": "Day One",
            "artist": "Hans Zimmer",
            "album": "Interstellar OST",
            "mood_tag": "cinematic ambient",
            "reason": "Matches your reflective mood",
            "spotify_url": "https://open.spotify.com/track/abc",
        }
    ],
    "pairing_note": "Listen to Hans Zimmer while watching Arrival for the full effect.",
}


def test_recommendation_round_trip():
    rec = Recommendation.model_validate(PRD_EXAMPLE)
    assert rec.movies[0].tmdb_id == 329865
    assert rec.music[0].spotify_uri == "spotify:track:abc"
    assert rec.pairing_note.startswith("Listen to Hans Zimmer")
    redumped = rec.model_dump(exclude_none=True)
    assert redumped["movies"][0]["title"] == "Arrival"
