from __future__ import annotations

import os
import re
import subprocess
import threading
import tkinter as tk
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from tkinter import messagebox, ttk

import webbrowser
from PIL import Image, ImageTk

try:
    import customtkinter as ctk
except Exception:
    ctk = None

from data_store import MovieRepository
from models import Movie
from tmdb_service import TMDBService


class PosterCache:
    def __init__(self, max_items: int = 256) -> None:
        self._items: dict[tuple[str, tuple[int, int]], object] = {}
        self._order: list[tuple[str, tuple[int, int]]] = []
        self._max_items = max_items

    def get(self, key: tuple[str, tuple[int, int]]):
        return self._items.get(key)

    def put(self, key: tuple[str, tuple[int, int]], value: object) -> None:
        if key not in self._items:
            self._order.append(key)
        self._items[key] = value
        while len(self._order) > self._max_items:
            oldest = self._order.pop(0)
            self._items.pop(oldest, None)


class MovieCollectionManager:
    PAGE_SIZE = 30

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Movie Collection Manager")
        self.root.geometry("1200x760")

        self.repo = MovieRepository()
        self.settings = self.repo.load_settings()
        self.movies = self.repo.load_movies()
        self.poster_cache = PosterCache()
        self.tmdb = TMDBService(api_key="ea33b23284657d2f1881ac56474f943e")
        self.executor = ThreadPoolExecutor(max_workers=8)

        self.search_debounce_id: str | None = None
        self.filter_signature: tuple | None = None
        self.page = 0
        self.filtered_movies: list[Movie] = []
        self.card_widgets: list[tk.Widget] = []

        self._build_ui()
        self._bind_shortcuts()
        self.refresh_movie_list(force=True)

    def _build_ui(self) -> None:
        use_dark = bool(self.settings.get("dark_mode", True))
        if ctk:
            ctk.set_appearance_mode("dark" if use_dark else "light")
            ctk.set_default_color_theme("blue")

        outer = ctk.CTkFrame(self.root) if ctk else ttk.Frame(self.root, padding=10)
        outer.pack(fill="both", expand=True)

        toolbar = ctk.CTkFrame(outer) if ctk else ttk.Frame(outer)
        toolbar.pack(fill="x", padx=12, pady=12)

        self.search_var = tk.StringVar()
        self.search_entry = ctk.CTkEntry(toolbar, textvariable=self.search_var, width=260, placeholder_text="Search...") if ctk else ttk.Entry(toolbar, textvariable=self.search_var, width=40)
        self.search_entry.pack(side="left", padx=4)
        self.search_entry.bind("<KeyRelease>", self._on_search_change)

        self.sort_var = tk.StringVar(value="Title")
        sort_values = ["Title", "Year", "Rating"]
        self.sort_menu = ctk.CTkOptionMenu(toolbar, values=sort_values, variable=self.sort_var, command=lambda _: self.refresh_movie_list(force=True)) if ctk else ttk.Combobox(toolbar, values=sort_values, textvariable=self.sort_var, width=10, state="readonly")
        self.sort_menu.pack(side="left", padx=4)
        if not ctk:
            self.sort_menu.bind("<<ComboboxSelected>>", lambda _: self.refresh_movie_list(force=True))

        self.filter_var = tk.StringVar(value="All")
        filter_values = ["All", "Watched", "Unwatched", "Favorites", "Watchlist"]
        self.filter_menu = ctk.CTkOptionMenu(toolbar, values=filter_values, variable=self.filter_var, command=lambda _: self.refresh_movie_list(force=True)) if ctk else ttk.Combobox(toolbar, values=filter_values, textvariable=self.filter_var, width=12, state="readonly")
        self.filter_menu.pack(side="left", padx=4)
        if not ctk:
            self.filter_menu.bind("<<ComboboxSelected>>", lambda _: self.refresh_movie_list(force=True))

        btn = ctk.CTkButton if ctk else ttk.Button
        self.fetch_btn = btn(toolbar, text="Auto Fetch", command=self.auto_fetch_movie)
        self.fetch_btn.pack(side="left", padx=4)
        self.save_btn = btn(toolbar, text="Save", command=self.save_movies)
        self.save_btn.pack(side="left", padx=4)
        self.theme_btn = btn(toolbar, text="Toggle Theme", command=self.toggle_theme)
        self.theme_btn.pack(side="right", padx=4)

        body = ctk.CTkFrame(outer) if ctk else ttk.Frame(outer)
        body.pack(fill="both", expand=True, padx=12, pady=6)

        left = ctk.CTkFrame(body) if ctk else ttk.Frame(body)
        left.pack(side="left", fill="y", padx=(0, 8))
        right = ctk.CTkFrame(body) if ctk else ttk.Frame(body)
        right.pack(side="left", fill="both", expand=True)

        self.name_entry = ctk.CTkEntry(left, placeholder_text="Movie title", width=280) if ctk else ttk.Entry(left, width=36)
        self.name_entry.pack(pady=4)
        self.year_entry = ctk.CTkEntry(left, placeholder_text="Year", width=280) if ctk else ttk.Entry(left, width=36)
        self.year_entry.pack(pady=4)
        self.genre_entry = ctk.CTkEntry(left, placeholder_text="Genre", width=280) if ctk else ttk.Entry(left, width=36)
        self.genre_entry.pack(pady=4)
        self.rating_entry = ctk.CTkEntry(left, placeholder_text="Rating 0-10", width=280) if ctk else ttk.Entry(left, width=36)
        self.rating_entry.insert(0, "5.0")
        self.rating_entry.pack(pady=4)

        self.watched_var = tk.BooleanVar(value=False)
        self.favorite_var = tk.BooleanVar(value=False)
        self.watchlist_var = tk.BooleanVar(value=False)

        if ctk:
            ctk.CTkCheckBox(left, text="Watched", variable=self.watched_var).pack(anchor="w", padx=10)
            ctk.CTkCheckBox(left, text="Favorite", variable=self.favorite_var).pack(anchor="w", padx=10)
            ctk.CTkCheckBox(left, text="Watchlist", variable=self.watchlist_var).pack(anchor="w", padx=10)
        else:
            ttk.Checkbutton(left, text="Watched", variable=self.watched_var).pack(anchor="w")
            ttk.Checkbutton(left, text="Favorite", variable=self.favorite_var).pack(anchor="w")
            ttk.Checkbutton(left, text="Watchlist", variable=self.watchlist_var).pack(anchor="w")

        self.loading_label = (ctk.CTkLabel(left, text="") if ctk else ttk.Label(left, text=""))
        self.loading_label.pack(fill="x", pady=(8, 2))
        self.progress = ttk.Progressbar(left, mode="indeterminate")
        self.progress.pack(fill="x", pady=(0, 6))

        self.add_btn = btn(left, text="Add / Update", command=self.add_movie)
        self.add_btn.pack(fill="x", pady=4)
        self.delete_btn = btn(left, text="Delete Selected", command=self.delete_selected)
        self.delete_btn.pack(fill="x", pady=4)
        self.trailer_btn = btn(left, text="Open Trailer", command=self.open_trailer)
        self.trailer_btn.pack(fill="x", pady=4)

        self.selected_movie: Movie | None = None

        self.canvas = tk.Canvas(right, highlightthickness=0)
        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar = ttk.Scrollbar(right, orient="vertical", command=self.canvas.yview)
        scrollbar.pack(side="right", fill="y")
        self.canvas.configure(yscrollcommand=scrollbar.set)
        self.grid_frame = ctk.CTkFrame(self.canvas) if ctk else ttk.Frame(self.canvas)
        self.canvas.create_window((0, 0), window=self.grid_frame, anchor="nw")
        self.grid_frame.bind("<Configure>", lambda _: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda _: self.refresh_movie_list(force=False))
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

        self.status = ctk.CTkLabel(outer, text="Ready") if ctk else ttk.Label(outer, text="Ready")
        self.status.pack(fill="x", padx=12, pady=(0, 8))

        self.load_more_btn = btn(outer, text="Load More", command=self.load_next_page)
        self.load_more_btn.pack(pady=(0, 8))

    def _bind_shortcuts(self) -> None:
        self.root.bind("<Return>", lambda _: self.refresh_movie_list(force=True))
        self.root.bind("<Control-s>", lambda _: self.save_movies())
        self.root.bind("<Delete>", lambda _: self.delete_selected())

    def _on_mousewheel(self, event: tk.Event) -> None:
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        if self.canvas.yview()[1] > 0.95:
            self.load_next_page()

    def _on_search_change(self, _event=None) -> None:
        if self.search_debounce_id:
            self.root.after_cancel(self.search_debounce_id)
        self.search_debounce_id = self.root.after(250, lambda: self.refresh_movie_list(force=True))

    def _current_signature(self) -> tuple:
        return (
            self.search_var.get().strip().lower(),
            self.sort_var.get(),
            self.filter_var.get(),
            len(self.movies),
            self.canvas.winfo_width() // 180,
        )

    def refresh_movie_list(self, force: bool = False) -> None:
        signature = self._current_signature()
        if not force and signature == self.filter_signature:
            return

        self.filter_signature = signature
        self.page = 0
        search = signature[0]
        mode = self.filter_var.get()
        items = [m for m in self.movies if search in m.name.lower()]

        if mode == "Watched":
            items = [m for m in items if m.watched]
        elif mode == "Unwatched":
            items = [m for m in items if not m.watched]
        elif mode == "Favorites":
            items = [m for m in items if m.favorite]
        elif mode == "Watchlist":
            items = [m for m in items if m.watchlist]

        if self.sort_var.get() == "Year":
            items.sort(key=lambda m: m.year or "0", reverse=True)
        elif self.sort_var.get() == "Rating":
            items.sort(key=lambda m: m.rating, reverse=True)
        else:
            items.sort(key=lambda m: m.name.lower())

        self.filtered_movies = items
        for w in self.card_widgets:
            w.destroy()
        self.card_widgets.clear()
        self.load_next_page()

    def _grid_columns(self) -> int:
        width = max(260, self.canvas.winfo_width())
        return max(1, width // 190)

    def load_next_page(self) -> None:
        start = self.page * self.PAGE_SIZE
        end = start + self.PAGE_SIZE
        chunk = self.filtered_movies[start:end]
        if not chunk:
            self.load_more_btn.configure(state="disabled")
            return

        cols = self._grid_columns()
        existing = len(self.card_widgets)
        for idx, movie in enumerate(chunk):
            pos = existing + idx
            row, col = divmod(pos, cols)
            card = self._build_card(self.grid_frame, movie)
            card.grid(row=row, column=col, padx=8, pady=8, sticky="nsew")
            self.card_widgets.append(card)

        for c in range(cols):
            self.grid_frame.grid_columnconfigure(c, weight=1)

        self.page += 1
        self.load_more_btn.configure(state="normal" if end < len(self.filtered_movies) else "disabled")
        self.status.configure(text=f"Showing {min(end, len(self.filtered_movies))}/{len(self.filtered_movies)} movies")

    def _build_card(self, parent: tk.Widget, movie: Movie) -> tk.Widget:
        frame = ctk.CTkFrame(parent, corner_radius=10) if ctk else ttk.Frame(parent, relief="ridge", borderwidth=1)
        poster_label = ctk.CTkLabel(frame, text="Loading...", width=140, height=200) if ctk else ttk.Label(frame, text="Loading...", width=20)
        poster_label.pack(padx=6, pady=6)
        title = ctk.CTkLabel(frame, text=f"{movie.name}\n{movie.year} ★{movie.rating:.1f}", width=160, wraplength=150) if ctk else ttk.Label(frame, text=f"{movie.name}\n{movie.year} ★{movie.rating:.1f}", width=24)
        title.pack(padx=6, pady=(0, 4))

        flags = []
        if movie.favorite:
            flags.append("❤️")
        if movie.watchlist:
            flags.append("📌")
        if movie.watched:
            flags.append("✅")
        badge_text = " ".join(flags) if flags else ""
        badge = ctk.CTkLabel(frame, text=badge_text) if ctk else ttk.Label(frame, text=badge_text)
        badge.pack(pady=(0, 6))

        frame.bind("<Button-1>", lambda _e, m=movie: self.select_movie(m))
        for child in frame.winfo_children():
            child.bind("<Button-1>", lambda _e, m=movie: self.select_movie(m))

        self._bind_hover(frame)
        self._load_poster_async(movie, poster_label)
        return frame

    def _bind_hover(self, widget: tk.Widget) -> None:
        def on_enter(_):
            self._animate_bg(widget, 0)

        def on_leave(_):
            self._animate_bg(widget, 1)

        widget.bind("<Enter>", on_enter)
        widget.bind("<Leave>", on_leave)

    def _animate_bg(self, widget: tk.Widget, direction: int) -> None:
        if not ctk:
            return
        colors = ["#2b2e3b", "#343849"] if ctk.get_appearance_mode() == "Dark" else ["#e7ecf3", "#d7dfeb"]
        widget.configure(fg_color=colors[direction])

    def _load_poster_async(self, movie: Movie, label: tk.Widget) -> None:
        if not movie.poster_path:
            label.configure(text="No poster")
            return

        key = (movie.poster_path, (140, 200))
        cached = self.poster_cache.get(key)
        if cached is not None:
            label.configure(image=cached, text="")
            return

        def task() -> None:
            try:
                raw = self.tmdb.fetch_poster_bytes(movie.poster_path)
                image = Image.open(BytesIO(raw)).convert("RGB")
                image.thumbnail((140, 200), Image.Resampling.LANCZOS)
                poster = ctk.CTkImage(light_image=image, dark_image=image, size=(140, 200)) if ctk else ImageTk.PhotoImage(image)
                self.poster_cache.put(key, poster)
                self.root.after(0, lambda: label.configure(image=poster, text=""))
            except Exception:
                self.root.after(0, lambda: label.configure(text="Poster error"))

        self.executor.submit(task)

    def select_movie(self, movie: Movie) -> None:
        self.selected_movie = movie
        self.name_entry.delete(0, tk.END)
        self.name_entry.insert(0, movie.name)
        self.year_entry.delete(0, tk.END)
        self.year_entry.insert(0, movie.year)
        self.genre_entry.delete(0, tk.END)
        self.genre_entry.insert(0, movie.genre)
        self.rating_entry.delete(0, tk.END)
        self.rating_entry.insert(0, str(movie.rating))
        self.watched_var.set(movie.watched)
        self.favorite_var.set(movie.favorite)
        self.watchlist_var.set(movie.watchlist)

    def add_movie(self) -> None:
        name = self.name_entry.get().strip()
        if not name:
            messagebox.showwarning("Validation", "Movie title is required")
            return
        try:
            rating = float(self.rating_entry.get().strip() or "0")
        except ValueError:
            messagebox.showwarning("Validation", "Rating must be numeric")
            return

        movie = Movie(
            name=name,
            year=self.year_entry.get().strip(),
            genre=self.genre_entry.get().strip(),
            rating=max(0.0, min(10.0, rating)),
            watched=self.watched_var.get(),
            favorite=self.favorite_var.get(),
            watchlist=self.watchlist_var.get(),
            poster_path=self.selected_movie.poster_path if self.selected_movie else "",
            file_path=self.selected_movie.file_path if self.selected_movie else "",
            tmdb_id=self.selected_movie.tmdb_id if self.selected_movie else None,
        )

        if self.selected_movie and self.selected_movie in self.movies:
            idx = self.movies.index(self.selected_movie)
            self.movies[idx] = movie
        else:
            self.movies.append(movie)
        self.selected_movie = movie
        self.save_movies()
        self.refresh_movie_list(force=True)

    def delete_selected(self) -> None:
        if not self.selected_movie:
            return
        if not messagebox.askyesno("Delete", f"Delete '{self.selected_movie.name}'?"):
            return
        self.movies = [m for m in self.movies if m is not self.selected_movie]
        self.selected_movie = None
        self.save_movies()
        self.refresh_movie_list(force=True)

    def save_movies(self) -> None:
        try:
            self.repo.save_movies(self.movies)
            self.status.configure(text="Saved")
        except OSError as exc:
            messagebox.showerror("Save Error", str(exc))

    def _set_loading(self, text: str, active: bool) -> None:
        self.loading_label.configure(text=text)
        if active:
            self.progress.start(12)
        else:
            self.progress.stop()

    def auto_fetch_movie(self) -> None:
        query = self.name_entry.get().strip()
        year = self.year_entry.get().strip()
        if not query:
            messagebox.showwarning("Missing data", "Type a movie title first")
            return

        self._set_loading("Fetching TMDB data...", True)

        def task() -> None:
            try:
                data = self.tmdb.search_movie(query, year)
                results = data.get("results") or []
                if not results:
                    raise ValueError("Movie not found")
                best = results[0]
                title = best.get("title", query)
                release = str(best.get("release_date", ""))[:4]
                poster = best.get("poster_path", "")
                genre = ", ".join(str(x) for x in best.get("genre_ids", [])[:3])
                rating = float(best.get("vote_average", 0.0))
                tmdb_id = best.get("id")

                def apply_result() -> None:
                    self.name_entry.delete(0, tk.END)
                    self.name_entry.insert(0, title)
                    self.year_entry.delete(0, tk.END)
                    self.year_entry.insert(0, release)
                    self.genre_entry.delete(0, tk.END)
                    self.genre_entry.insert(0, genre)
                    self.rating_entry.delete(0, tk.END)
                    self.rating_entry.insert(0, f"{rating:.1f}")
                    if self.selected_movie:
                        self.selected_movie.poster_path = poster
                        self.selected_movie.tmdb_id = tmdb_id
                    self._set_loading("Fetch complete", False)
                    self.refresh_movie_list(force=True)

                self.root.after(0, apply_result)
            except Exception as exc:
                self.root.after(0, lambda: (self._set_loading(f"Error: {exc}", False), messagebox.showerror("TMDB", str(exc))))

        self.executor.submit(task)

    def open_trailer(self) -> None:
        movie = self.selected_movie
        if not movie:
            return
        webbrowser.open(f"https://www.youtube.com/results?search_query={movie.name}+{movie.year}+official+trailer")

    def toggle_theme(self) -> None:
        if not ctk:
            return
        mode = ctk.get_appearance_mode()
        dark = mode != "Dark"
        ctk.set_appearance_mode("dark" if dark else "light")
        self.settings["dark_mode"] = dark
        self.repo.save_settings(self.settings)


def main() -> None:
    root = tk.Tk()
    if os.name == "nt":
        try:
            subprocess.run(["chcp", "65001"], check=False, capture_output=True)
        except Exception:
            pass
    app = MovieCollectionManager(root)
    root.protocol("WM_DELETE_WINDOW", lambda: (app.executor.shutdown(wait=False, cancel_futures=True), root.destroy()))
    root.mainloop()


if __name__ == "__main__":
    main()
