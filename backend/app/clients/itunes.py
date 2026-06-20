"""Apple iTunes Search API client.

The project keeps the older `spotify_uri` / `spotify_url` response field names
for API compatibility, but new music rows use iTunes-backed values:

    spotify_uri = "itunes:track:<trackId>"
    spotify_url = trackViewUrl
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlencode

import httpx

ITUNES_SEARCH_URL = "https://itunes.apple.com/search"


class ITunesError(RuntimeError):
    pass


class ITunesClient:
    def __init__(self, http: httpx.AsyncClient | None = None, *, country: str = "US"):
        self._http = http or httpx.AsyncClient(timeout=10.0)
        self._owns_http = http is None
        self.country = country

    async def aclose(self) -> None:
        if self._owns_http:
            await self._http.aclose()

    async def __aenter__(self) -> ITunesClient:
        return self

    async def __aexit__(self, *_exc) -> None:
        await self.aclose()

    async def search_track(self, query: str, *, limit: int = 10) -> list[dict[str, Any]]:
        data = await self._search(
            {
                "term": query,
                "media": "music",
                "entity": "song",
                "limit": limit,
                "country": self.country,
            }
        )
        return data.get("results", [])

    async def search_artist(self, query: str, *, limit: int = 5) -> list[dict[str, Any]]:
        data = await self._search(
            {
                "term": query,
                "media": "music",
                "entity": "musicArtist",
                "limit": limit,
                "country": self.country,
            }
        )
        return data.get("results", [])

    async def get_artist_top_tracks(
        self, artist_id: int | str, *, limit: int = 10
    ) -> list[dict[str, Any]]:
        data = await self._search(
            {
                "term": str(artist_id),
                "media": "music",
                "entity": "song",
                "attribute": "artistTerm",
                "limit": limit,
                "country": self.country,
            }
        )
        return data.get("results", [])

    async def _search(self, params: dict[str, Any]) -> dict[str, Any]:
        r = await self._http.get(ITUNES_SEARCH_URL, params=params)
        if r.status_code != 200:
            query = urlencode(params)
            raise ITunesError(f"iTunes search failed for {query}: {r.status_code} {r.text[:200]}")
        return r.json()

    @staticmethod
    def track_uri(track: dict[str, Any]) -> str:
        return f"itunes:track:{track['trackId']}"

    @staticmethod
    def album_art_url(track: dict[str, Any], *, size: int = 600) -> str | None:
        url = track.get("artworkUrl100") or track.get("artworkUrl60")
        if not url:
            return None
        return url.replace("100x100bb", f"{size}x{size}bb").replace(
            "60x60bb", f"{size}x{size}bb"
        )
