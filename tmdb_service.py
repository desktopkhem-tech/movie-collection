from __future__ import annotations

from functools import lru_cache
from typing import Any, Dict

import requests


class TMDBService:
    def __init__(self, api_key: str, base_url: str = "https://api.themoviedb.org/3") -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.image_base_url = "https://image.tmdb.org/t/p/w300"
        self.session = requests.Session()
        self._timeout = (4, 10)

    def _request_json(self, path: str, **params: Any) -> Dict[str, Any]:
        all_params = {"api_key": self.api_key, **params}
        response = self.session.get(f"{self.base_url}/{path.lstrip('/')}", params=all_params, timeout=self._timeout)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("Unexpected API response format")
        return payload

    @lru_cache(maxsize=256)
    def search_movie(self, query: str, year: str = "") -> Dict[str, Any]:
        query = query.strip()
        if not query:
            return {}
        params: Dict[str, Any] = {"query": query}
        if year:
            params["primary_release_year"] = year
        data = self._request_json("search/movie", **params)
        results = data.get("results") or []
        if not results and year:
            data = self._request_json("search/movie", query=query)
        return data

    @lru_cache(maxsize=512)
    def get_credits(self, tmdb_id: int) -> Dict[str, Any]:
        return self._request_json(f"movie/{tmdb_id}/credits")

    @lru_cache(maxsize=1024)
    def fetch_poster_bytes(self, poster_path: str) -> bytes:
        if not poster_path:
            return b""
        response = self.session.get(f"{self.image_base_url}{poster_path}", timeout=self._timeout)
        response.raise_for_status()
        return response.content
