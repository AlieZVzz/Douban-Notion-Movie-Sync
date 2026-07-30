"""TMDB API client."""
from __future__ import annotations

from typing import Any, Optional

import requests

try:
    from ..http_client import create_retry_session
except ImportError:
    from http_client import create_retry_session

TMDB_API_BASE = "https://api.themoviedb.org/3"
TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/w500"


class TMDBClient:
    def __init__(
        self,
        api_key: str,
        *,
        timeout: float = 30,
        session: Optional[requests.Session] = None,
    ) -> None:
        self.api_key = api_key
        self.timeout = timeout
        self.session = session or create_retry_session()

    def _get(self, path: str, params: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        query = {"api_key": self.api_key, **(params or {})}
        response = self.session.get(
            f"{TMDB_API_BASE}{path}", params=query, timeout=self.timeout
        )
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict):
            raise ValueError("TMDB API returned a non-object JSON response")
        return data

    def search_movie(self, query: str, year: Optional[int] = None) -> Optional[int]:
        if not query.strip():
            return None
        params: dict[str, Any] = {
            "query": query,
            "language": "zh-CN",
            "include_adult": "false",
        }
        if year:
            params["year"] = year
        results = self._get("/search/movie", params).get("results", [])
        if not isinstance(results, list) or not results:
            return None
        movie_id = results[0].get("id")
        return int(movie_id) if movie_id is not None else None

    def poster_url(self, movie_id: int) -> Optional[str]:
        poster_path = self._get(f"/movie/{movie_id}", {"language": "zh-CN"}).get(
            "poster_path"
        )
        return f"{TMDB_IMAGE_BASE}{poster_path}" if poster_path else None


def search_movie(api_key: str, query: str) -> Optional[int]:
    return TMDBClient(api_key).search_movie(query)


def get_movie_poster(api_key: str, movie_id: int) -> Optional[str]:
    return TMDBClient(api_key).poster_url(movie_id)
