"""Spotify client unit tests with respx mocks for the auth + API calls."""

import httpx
import pytest
import respx

from app.clients.spotify import SPOTIFY_API_BASE, SPOTIFY_AUTH_URL, SpotifyClient


@pytest.fixture
def client():
    http = httpx.AsyncClient(timeout=5.0)
    return SpotifyClient(client_id="id", client_secret="secret", http=http)


def _mock_token():
    respx.post(SPOTIFY_AUTH_URL).mock(
        return_value=httpx.Response(200, json={"access_token": "fake", "expires_in": 3600})
    )


@respx.mock
async def test_search_track_caches_token(client: SpotifyClient):
    _mock_token()
    respx.get(f"{SPOTIFY_API_BASE}/search").mock(
        return_value=httpx.Response(
            200,
            json={"tracks": {"items": [{"id": "abc", "name": "Day One"}]}},
        )
    )
    a = await client.search_track("day one")
    b = await client.search_track("day one")
    assert a[0]["name"] == "Day One"
    # token endpoint called exactly once across two requests
    auth_calls = [r for r in respx.calls if str(r.request.url) == SPOTIFY_AUTH_URL]
    assert len(auth_calls) == 1
    assert len(b) == 1


@respx.mock
async def test_related_artists_returns_empty_on_404(client: SpotifyClient):
    _mock_token()
    respx.get(f"{SPOTIFY_API_BASE}/artists/xyz/related-artists").mock(
        return_value=httpx.Response(404, text="deprecated")
    )
    assert await client.get_related_artists("xyz") == []


def test_track_url_helper():
    assert SpotifyClient.track_url("spotify:track:abc") == "https://open.spotify.com/track/abc"


def test_album_art_url_helper():
    track = {"album": {"images": [{"url": "https://i.scdn.co/x.jpg"}]}}
    assert SpotifyClient.album_art_url(track) == "https://i.scdn.co/x.jpg"
    assert SpotifyClient.album_art_url({"album": {"images": []}}) is None
