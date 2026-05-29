"""Thin async TMDB client.

Only the methods the agent graph actually calls. Trailers come from
`/movie/{id}/videos` — no YouTube Data API dependency.
"""

from __future__ import annotations

from typing import Any

import httpx

from app.config import settings

TMDB_BASE_URL = "https://api.themoviedb.org/3"
TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/w500"


class TMDBError(RuntimeError):
    pass


class TMDBClient:
    def __init__(self, api_key: str | None = None, client: httpx.AsyncClient | None = None):
        self.api_key = api_key or settings.tmdb_api_key
        if not self.api_key:
            raise TMDBError("TMDB_API_KEY is not configured")
        self._client = client or httpx.AsyncClient(base_url=TMDB_BASE_URL, timeout=10.0)
        self._owns_client = client is None

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def __aenter__(self) -> TMDBClient:
        return self

    async def __aexit__(self, *_exc) -> None:
        await self.aclose()

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        merged: dict[str, Any] = {"api_key": self.api_key}
        if params:
            merged.update(params)
        r = await self._client.get(path, params=merged)
        if r.status_code != 200:
            raise TMDBError(f"TMDB {path} -> {r.status_code}: {r.text[:200]}")
        return r.json()

    async def search_movie(self, query: str, *, page: int = 1) -> list[dict[str, Any]]:
        data = await self._get(
            "/search/movie",
            {"query": query, "page": page, "include_adult": False},
        )
        return data.get("results", [])

    async def get_movie(self, tmdb_id: int) -> dict[str, Any]:
        return await self._get(f"/movie/{tmdb_id}")

    async def get_videos(self, tmdb_id: int) -> list[dict[str, Any]]:
        data = await self._get(f"/movie/{tmdb_id}/videos")
        return data.get("results", [])

    async def get_trailer_url(self, tmdb_id: int) -> str | None:
        videos = await self.get_videos(tmdb_id)
        for v in videos:
            if v.get("site") == "YouTube" and v.get("type") == "Trailer":
                return f"https://youtube.com/watch?v={v['key']}"
        for v in videos:
            if v.get("site") == "YouTube":
                return f"https://youtube.com/watch?v={v['key']}"
        return None

    async def discover_popular(
        self, *, page: int = 1, sort_by: str = "popularity.desc"
    ) -> list[dict[str, Any]]:
        data = await self._get(
            "/discover/movie",
            {
                "page": page,
                "sort_by": sort_by,
                "include_adult": False,
                "vote_count.gte": 100,
            },
        )
        return data.get("results", [])

    @staticmethod
    def poster_url(poster_path: str | None) -> str | None:
        if not poster_path:
            return None
        return f"{TMDB_IMAGE_BASE}{poster_path}"
