"""TMDB client unit tests using respx to mock httpx."""

import httpx
import pytest
import respx

from app.clients.tmdb import TMDB_BASE_URL, TMDBClient


@pytest.fixture
def client():
    http = httpx.AsyncClient(base_url=TMDB_BASE_URL, timeout=5.0)
    return TMDBClient(api_key="test-key", client=http)


@respx.mock
async def test_search_movie(client: TMDBClient):
    respx.get(f"{TMDB_BASE_URL}/search/movie").mock(
        return_value=httpx.Response(
            200,
            json={"results": [{"id": 157336, "title": "Interstellar"}]},
        )
    )
    results = await client.search_movie("Interstellar")
    assert results[0]["title"] == "Interstellar"


@respx.mock
async def test_get_trailer_url_prefers_trailer_type(client: TMDBClient):
    respx.get(f"{TMDB_BASE_URL}/movie/157336/videos").mock(
        return_value=httpx.Response(
            200,
            json={
                "results": [
                    {"site": "YouTube", "type": "Teaser", "key": "teaser1"},
                    {"site": "YouTube", "type": "Trailer", "key": "trailer1"},
                ]
            },
        )
    )
    url = await client.get_trailer_url(157336)
    assert url == "https://youtube.com/watch?v=trailer1"


@respx.mock
async def test_get_trailer_url_none_when_empty(client: TMDBClient):
    respx.get(f"{TMDB_BASE_URL}/movie/157336/videos").mock(
        return_value=httpx.Response(200, json={"results": []}),
    )
    assert await client.get_trailer_url(157336) is None


def test_poster_url_helper():
    assert TMDBClient.poster_url("/abc.jpg") == "https://image.tmdb.org/t/p/w500/abc.jpg"
    assert TMDBClient.poster_url(None) is None
