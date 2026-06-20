"""iTunes client unit tests with respx mocks for search calls."""

import httpx
import respx

from app.clients.itunes import ITUNES_SEARCH_URL, ITunesClient


@respx.mock
async def test_search_track_returns_results():
    client = ITunesClient(http=httpx.AsyncClient(timeout=5.0))
    respx.get(ITUNES_SEARCH_URL).mock(
        return_value=httpx.Response(
            200,
            json={"resultCount": 1, "results": [{"trackId": 123, "trackName": "Day One"}]},
        )
    )

    try:
        out = await client.search_track("day one")
    finally:
        await client.aclose()

    assert out[0]["trackName"] == "Day One"


@respx.mock
async def test_search_artist_returns_results():
    client = ITunesClient(http=httpx.AsyncClient(timeout=5.0))
    respx.get(ITUNES_SEARCH_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "resultCount": 1,
                "results": [{"artistId": 1, "artistName": "Hans Zimmer"}],
            },
        )
    )

    try:
        out = await client.search_artist("hans zimmer")
    finally:
        await client.aclose()

    assert out[0]["artistName"] == "Hans Zimmer"


def test_track_uri_helper():
    assert ITunesClient.track_uri({"trackId": 123}) == "itunes:track:123"


def test_album_art_url_helper():
    track = {"artworkUrl100": "https://is1-ssl.mzstatic.com/image/100x100bb.jpg"}
    assert ITunesClient.album_art_url(track) == "https://is1-ssl.mzstatic.com/image/600x600bb.jpg"
    assert ITunesClient.album_art_url({}) is None
