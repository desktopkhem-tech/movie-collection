from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict


@dataclass
class Movie:
    name: str
    year: str = ""
    genre: str = ""
    rating: float = 0.0
    watched: bool = False
    favorite: bool = False
    watchlist: bool = False
    poster_path: str = ""
    file_path: str = ""
    tmdb_id: int | None = None

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "Movie":
        name = str(payload.get("name", "")).strip()
        if not name:
            raise ValueError("Movie name is required")

        rating_raw = payload.get("rating", 0)
        try:
            rating = float(rating_raw)
        except (TypeError, ValueError):
            rating = 0.0
        rating = max(0.0, min(10.0, rating))

        tmdb_id_raw = payload.get("tmdb_id")
        tmdb_id = None
        if tmdb_id_raw not in (None, ""):
            try:
                tmdb_id = int(tmdb_id_raw)
            except (TypeError, ValueError):
                tmdb_id = None

        return cls(
            name=name,
            year=str(payload.get("year", "")).strip(),
            genre=str(payload.get("genre", "")).strip(),
            rating=rating,
            watched=bool(payload.get("watched", False)),
            favorite=bool(payload.get("favorite", False)),
            watchlist=bool(payload.get("watchlist", False)),
            poster_path=str(payload.get("poster_path", "")).strip(),
            file_path=str(payload.get("file_path", "")).strip(),
            tmdb_id=tmdb_id,
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
