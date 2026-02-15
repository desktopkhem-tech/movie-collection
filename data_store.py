from __future__ import annotations

import json
import os
import tempfile
from typing import List

from models import Movie


class MovieRepository:
    def __init__(self, data_file: str = "movies_data.json", settings_file: str = "settings.json") -> None:
        self.data_file = data_file
        self.settings_file = settings_file

    def load_movies(self) -> List[Movie]:
        if not os.path.exists(self.data_file):
            return []
        try:
            with open(self.data_file, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except (OSError, json.JSONDecodeError):
            return []

        movies: List[Movie] = []
        if isinstance(payload, list):
            for item in payload:
                if not isinstance(item, dict):
                    continue
                try:
                    movies.append(Movie.from_dict(item))
                except ValueError:
                    continue
        return movies

    def save_movies(self, movies: List[Movie]) -> None:
        payload = [movie.to_dict() for movie in movies]
        directory = os.path.dirname(self.data_file) or "."
        os.makedirs(directory, exist_ok=True)
        fd, temp_path = tempfile.mkstemp(dir=directory, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as temp:
                json.dump(payload, temp, indent=2)
            os.replace(temp_path, self.data_file)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def load_settings(self) -> dict:
        if not os.path.exists(self.settings_file):
            return {"dark_mode": True}
        try:
            with open(self.settings_file, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
            if not isinstance(payload, dict):
                return {"dark_mode": True}
            return {"dark_mode": bool(payload.get("dark_mode", True))}
        except (OSError, json.JSONDecodeError):
            return {"dark_mode": True}

    def save_settings(self, settings: dict) -> None:
        directory = os.path.dirname(self.settings_file) or "."
        os.makedirs(directory, exist_ok=True)
        with open(self.settings_file, "w", encoding="utf-8") as handle:
            json.dump(settings, handle, indent=2)
