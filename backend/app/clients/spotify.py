"""Spotify Web API client using Client Credentials flow.

Scope is limited to public catalog reads — no user-context endpoints. The
deprecated `/recommendations` and `/audio-features` endpoints are
intentionally NOT exposed; similarity is handled via the RAG seed corpus.
"""

from __future__ import annotations

import asyncio
import base64
import time
from typing import Any

import httpx

from app.config import settings

SPOTIFY_AUTH_URL = "https://accounts.spotify.com/api/token"
SPOTIFY_API_BASE = "https://api.spotify.com/v1"


class SpotifyError(RuntimeError):
    pass


class SpotifyClient:
    def __init__(
        self,
        client_id: str | None = None,
        client_secret: str | None = None,
        http: httpx.AsyncClient | None = None,
    ):
        self.client_id = client_id or settings.spotify_client_id
        self.client_secret = client_secret or settings.spotify_client_secret
        if not self.client_id or not self.client_secret:
            raise SpotifyError("SPOTIFY_CLIENT_ID / SPOTIFY_CLIENT_SECRET not configured")
        self._http = http or httpx.AsyncClient(timeout=10.0)
        self._owns_http = http is None
        self._token: str | None = None
        self._token_expires_at: float = 0.0
        self._token_lock = asyncio.Lock()

    async def aclose(self) -> None:
        if self._owns_http:
            await self._http.aclose()

    async def __aenter__(self) -> SpotifyClient:
        return self

    async def __aexit__(self, *_exc) -> None:
        await self.aclose()

    # ---------- auth ----------

    async def _get_token(self) -> str:
        # 30s clock skew buffer
        if self._token and time.time() < self._token_expires_at - 30:
            return self._token

        async with self._token_lock:
            if self._token and time.time() < self._token_expires_at - 30:
                return self._token

            creds = f"{self.client_id}:{self.client_secret}".encode()
            r = await self._http.post(
                SPOTIFY_AUTH_URL,
                data={"grant_type": "client_credentials"},
                headers={
                    "Authorization": "Basic " + base64.b64encode(creds).decode(),
                    "Content-Type": "application/x-www-form-urlencoded",
                },
            )
            if r.status_code != 200:
                raise SpotifyError(f"Spotify auth failed: {r.status_code} {r.text[:200]}")
            data = r.json()
            self._token = data["access_token"]
            self._token_expires_at = time.time() + int(data.get("expires_in", 3600))
            return self._token

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        token = await self._get_token()
        r = await self._http.get(
            SPOTIFY_API_BASE + path,
            params=params,
            headers={"Authorization": f"Bearer {token}"},
        )
        if r.status_code == 404:
            raise SpotifyError(f"Spotify {path} -> 404 (endpoint may be deprecated)")
        if r.status_code != 200:
            raise SpotifyError(f"Spotify {path} -> {r.status_code}: {r.text[:200]}")
        return r.json()

    # ---------- public reads ----------

    async def search_track(self, query: str, *, limit: int = 10) -> list[dict[str, Any]]:
        data = await self._get(
            "/search",
            {"q": query, "type": "track", "limit": limit},
        )
        return data.get("tracks", {}).get("items", [])

    async def search_artist(self, query: str, *, limit: int = 5) -> list[dict[str, Any]]:
        data = await self._get(
            "/search",
            {"q": query, "type": "artist", "limit": limit},
        )
        return data.get("artists", {}).get("items", [])

    async def get_artist(self, artist_id: str) -> dict[str, Any]:
        return await self._get(f"/artists/{artist_id}")

    async def get_artist_top_tracks(
        self, artist_id: str, *, market: str = "US"
    ) -> list[dict[str, Any]]:
        data = await self._get(f"/artists/{artist_id}/top-tracks", {"market": market})
        return data.get("tracks", [])

    async def get_related_artists(self, artist_id: str) -> list[dict[str, Any]]:
        """Status verify before relying on this — may be deprecated for new client IDs."""
        try:
            data = await self._get(f"/artists/{artist_id}/related-artists")
            return data.get("artists", [])
        except SpotifyError as e:
            if "404" in str(e):
                return []
            raise

    # ---------- helpers ----------

    @staticmethod
    def track_url(spotify_uri: str) -> str:
        # spotify:track:abc -> https://open.spotify.com/track/abc
        kind, _, ident = spotify_uri.rpartition(":")
        kind = kind.split(":")[-1]
        return f"https://open.spotify.com/{kind}/{ident}"

    @staticmethod
    def album_art_url(track: dict[str, Any]) -> str | None:
        images = track.get("album", {}).get("images", [])
        return images[0]["url"] if images else None
