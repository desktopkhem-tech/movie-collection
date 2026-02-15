print("NEW UI VERSION RUNNING")

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
try:
    import customtkinter as ctk
except Exception:
     ctk = None

import json
import os
import csv
import re
import requests
import webbrowser
from PIL import Image, ImageTk
from io import BytesIO
from datetime import datetime
from urllib.parse import quote

class MovieCollectionManager:
    def __init__(self, root):
        self.root = root
        self.root.title("Movie Collection Manager")
        self.root.geometry("1100x700")
        self.root.resizable(True, True)
        
        # TMDB API Configuration
        self.TMDB_API_KEY = "ea33b23284657d2f1881ac56474f943e"
        self.TMDB_BASE_URL = "https://api.themoviedb.org/3"
        self.TMDB_IMAGE_BASE_URL = "https://image.tmdb.org/t/p/w200"
        
        # Data file paths
        self.data_file = "movies_data.json"
        self.settings_file = "settings.json"
        self.movies = []
        
        # Current poster image, file path, and TMDB ID
        self.current_poster = None
        self.current_poster_url = None
        self.current_file_path = None
        self.current_tmdb_id = None
        # Selected index for grid/list selections
        self.selected_index = None
        # Simple image cache to avoid re-downloading posters
        self._image_cache = {}
        
        # Dark mode setting
        self.dark_mode = False
        self.font_default = ("Segoe UI", 10)
        self.font_title = ("Segoe UI", 18, "bold")
        self.font_heading = ("Segoe UI", 11, "bold")
        # Load settings and data

        self.load_settings()
        self.load_data()
        
        # Create UI
        # If customtkinter is available, set dark mode and theme
        if ctk:
            ctk.set_appearance_mode("dark")
            ctk.set_default_color_theme("blue")
        self.create_ui()
        
        # Apply theme
        self.apply_theme()
        
        # Display movies
        self.refresh_movie_list()
    
    def create_ui(self):
        if ctk:
            ctk.set_appearance_mode("dark")
            self.root.configure(bg="#1e1f26", padx=0, pady=0)
            
            # Main container
            main = ctk.CTkFrame(self.root, fg_color="#1e1f26", corner_radius=0)
            main.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)
            main.grid_rowconfigure(1, weight=1)
            main.grid_columnconfigure(0, weight=0)
            main.grid_columnconfigure(1, weight=1)
            
            # Header
            header = ctk.CTkFrame(main, fg_color="#2b2e3b", corner_radius=0)
            header.grid(row=0, column=0, sticky="ew", columnspan=2, padx=0, pady=0)
            logo = ctk.CTkLabel(header, text="🎬 Movie Collection", font=("Segoe UI", 20, "bold"), text_color="#3fa7ff")
            logo.pack(side=tk.LEFT, padx=20, pady=12)
            # Theme toggle on header (right)
            try:
                theme_btn = ctk.CTkButton(header, text="🌙", width=80, command=self.toggle_dark_mode, fg_color="#3fa7ff", text_color="white", corner_radius=8)
                theme_btn.pack(side=tk.RIGHT, padx=20, pady=12)
            except Exception:
                pass
            
            # Sidebar (200px fixed) - flush left
            sidebar = ctk.CTkFrame(main, fg_color="#2b2e3b", width=200, corner_radius=0)
            sidebar.grid(row=1, column=0, sticky="nsw", padx=0, pady=0)
            sidebar.grid_propagate(False)
            sidebar.pack_propagate(False)

            # Align buttons vertically centered
            sidebar_inner = ctk.CTkFrame(sidebar, fg_color="#2b2e3b")
            sidebar_inner.place(relx=0.5, rely=0.5, anchor=tk.CENTER)
            
            # Sidebar buttons (store for active styling)
            self.sidebar_buttons = {}
            home_btn = ctk.CTkButton(sidebar_inner, text="🏠  Home", command=lambda: self.set_active_tab('home'), fg_color="#2b2e3b", text_color="white", corner_radius=8)
            home_btn.pack(pady=8, padx=12, fill="x")
            self.sidebar_buttons['home'] = home_btn
            lib_btn = ctk.CTkButton(sidebar_inner, text="📚  Library", command=lambda: self.set_active_tab('library'), fg_color="#2b2e3b", text_color="white", corner_radius=8)
            lib_btn.pack(pady=8, padx=12, fill="x")
            self.sidebar_buttons['library'] = lib_btn
            add_btn = ctk.CTkButton(sidebar_inner, text="➕  Add Movie", command=lambda: self.set_active_tab('add'), fg_color="#2b2e3b", text_color="white", corner_radius=8)
            add_btn.pack(pady=8, padx=12, fill="x")
            self.sidebar_buttons['add'] = add_btn
            set_btn = ctk.CTkButton(sidebar_inner, text="⚙️  Settings", command=lambda: self.set_active_tab('settings'), fg_color="#2b2e3b", text_color="white", corner_radius=8)
            set_btn.pack(pady=8, padx=12, fill="x")
            self.sidebar_buttons['settings'] = set_btn
            
            # Content area
            content = ctk.CTkFrame(main, fg_color="#1e1f26", corner_radius=0)
            content.grid(row=1, column=1, sticky="nsew", padx=0, pady=0)
            content.grid_rowconfigure(0, weight=1)
            content.grid_columnconfigure(0, weight=1)
            
            # Page frames
            self.home_frame = ctk.CTkFrame(content, fg_color="#1e1f26", corner_radius=0)
            self.home_frame.grid(row=0, column=0, sticky="nsew")
            self.library_frame = ctk.CTkFrame(content, fg_color="#1e1f26", corner_radius=0)
            self.library_frame.grid(row=0, column=0, sticky="nsew")
            # Make library frame layout use grid so internal frames can expand
            try:
                self.library_frame.grid_rowconfigure(0, weight=0)
                self.library_frame.grid_rowconfigure(1, weight=1)
                self.library_frame.grid_columnconfigure(0, weight=1)
            except Exception:
                pass
            self.add_frame = ctk.CTkFrame(content, fg_color="#1e1f26", corner_radius=0)
            self.add_frame.grid(row=0, column=0, sticky="nsew")
            self.settings_frame = ctk.CTkFrame(content, fg_color="#1e1f26", corner_radius=0)
            self.settings_frame.grid(row=0, column=0, sticky="nsew")
            
            # HOME FRAME (Welcome + Stats + Recently Added)
            home_inner = ctk.CTkScrollableFrame(self.home_frame, fg_color="#1e1f26")
            home_inner.pack(fill='both', expand=True, padx=15, pady=15)

            welcome = ctk.CTkLabel(home_inner, text="Welcome to Movie Collection", font=("Segoe UI", 20, "bold"), text_color="#3fa7ff")

            # --- ADD MOVIE FRAME (form widgets) ---
            add_inner = ctk.CTkFrame(self.add_frame, fg_color="#1e1f26")
            add_inner.pack(padx=20, pady=20, fill='both', expand=True)

            ctk.CTkLabel(add_inner, text="Add New Movie", font=("Segoe UI", 16, "bold"), text_color="#3fa7ff").pack(pady=(0,12))

            self.movie_name_entry = ctk.CTkEntry(add_inner, placeholder_text="Movie Name", width=520, fg_color="#2b2e3b", border_color="#3fa7ff", text_color="white")
            self.movie_name_entry.pack(pady=8)

            self.year_entry = ctk.CTkEntry(add_inner, placeholder_text="Year", width=120, fg_color="#2b2e3b", border_color="#3fa7ff", text_color="white")
            self.year_entry.pack(pady=8)

            self.genre_entry = ctk.CTkEntry(add_inner, placeholder_text="Genre", width=520, fg_color="#2b2e3b", border_color="#3fa7ff", text_color="white")
            self.genre_entry.pack(pady=8)

            self.rating_spinbox = ctk.CTkEntry(add_inner, placeholder_text="Rating (0-10)", width=120, fg_color="#2b2e3b", border_color="#3fa7ff", text_color="white")
            self.rating_spinbox.insert(0, "5.0")
            self.rating_spinbox.pack(pady=8)

            self.file_path_entry = ctk.CTkEntry(add_inner, placeholder_text="File Path", width=520, fg_color="#2b2e3b", border_color="#3fa7ff", text_color="white")
            self.file_path_entry.pack(pady=8)

            btns = ctk.CTkFrame(add_inner, fg_color="#1e1f26")
            btns.pack(pady=12)
            self.watched_var = tk.BooleanVar()
            ctk.CTkCheckBox(btns, text="Watched", variable=self.watched_var, text_color="white").pack(side=tk.LEFT, padx=6)
            ctk.CTkButton(btns, text="📁 Attach", command=self.attach_file, fg_color="#3fa7ff", text_color="white").pack(side=tk.LEFT, padx=6)
            ctk.CTkButton(btns, text="🎬 Auto Fetch", command=self.auto_fetch_movie, fg_color="#3fa7ff", text_color="white").pack(side=tk.LEFT, padx=6)
            ctk.CTkButton(btns, text="➕ Add Movie", command=self.add_movie, fg_color="#3fa7ff", text_color="white").pack(side=tk.LEFT, padx=6)

            # Small poster preview in Add Movie form
            self.poster_label = ctk.CTkLabel(add_inner, text="No Poster", width=200, height=300, fg_color="#1e1f26", corner_radius=8, text_color="#888")
            self.poster_label.pack(pady=8)
            welcome.pack(pady=(10,12))

            stats_frame = ctk.CTkFrame(home_inner, fg_color="#2b2e3b", corner_radius=8)
            stats_frame.pack(fill='x', padx=20, pady=(0,12))
            stats_frame.grid_columnconfigure((0,1), weight=1)
            total_lbl = ctk.CTkLabel(stats_frame, text=f"Total movies: {len(self.movies)}", text_color="white")
            total_lbl.grid(row=0, column=0, padx=20, pady=12, sticky='w')
            watched_count = sum(1 for m in self.movies if m.get('watched'))
            watched_lbl = ctk.CTkLabel(stats_frame, text=f"Watched: {watched_count}", text_color="white")
            watched_lbl.grid(row=0, column=1, padx=20, pady=12, sticky='e')

            # Recently added posters
            recent_label = ctk.CTkLabel(home_inner, text="Recently Added", font=("Segoe UI", 14, "bold"), text_color="#3fa7ff")
            recent_label.pack(pady=(6,8), anchor='w', padx=20)
            recent_frame = ctk.CTkScrollableFrame(home_inner, height=220, fg_color="#1e1f26")
            recent_frame.pack(fill='x', padx=20)
            # Render up to 5 recent posters horizontally (skip entries without poster)
            recent_movies = [m for m in list(reversed(self.movies)) if m.get('poster_path')]
            recent_movies = recent_movies[:5]
            for m in recent_movies:
                card = ctk.CTkFrame(recent_frame, width=160, height=240, corner_radius=15, fg_color="#2b2e3b")
                card.pack(side=tk.LEFT, padx=8, pady=8)

                poster_path = m.get('poster_path')
                img_label = ctk.CTkLabel(card, text="", width=120, height=160, corner_radius=6)
                img_label.pack(pady=(8,6))

                # Load from cache or fetch
                try:
                    cache_key = f"{poster_path}_120_160"
                    if cache_key in self._image_cache:
                        ph = self._image_cache[cache_key]
                    else:
                        resp = requests.get(f"{self.TMDB_IMAGE_BASE_URL}{poster_path}", timeout=8)
                        resp.raise_for_status()
                        im = Image.open(BytesIO(resp.content)).convert('RGBA')
                        im.thumbnail((120,160), Image.Resampling.LANCZOS)
                        try:
                            ph = ctk.CTkImage(light_image=im, size=(120,160))
                        except Exception:
                            ph = ImageTk.PhotoImage(im)
                        self._image_cache[cache_key] = ph
                    try:
                        img_label.configure(image=ph, text='')
                    except Exception:
                        pass
                except Exception:
                    # If fetching fails, skip image and continue (do not show 'No Poster')
                    try:
                        img_label.configure(image='', text='')
                    except Exception:
                        pass

                title = ctk.CTkLabel(card, text=f"{m.get('name','')}\n{m.get('year','')}", wraplength=120, justify=tk.CENTER)
                title.pack(pady=(0,6))
            
            # LIBRARY FRAME
            lib_header = ctk.CTkFrame(self.library_frame, fg_color="#1e1f26")
            lib_header.grid(row=0, column=0, sticky="ew", padx=20, pady=(12, 0))
            
            self.search_entry = ctk.CTkEntry(lib_header, placeholder_text="Search movies...", width=300, fg_color="#2b2e3b", border_color="#3fa7ff", text_color="white")
            self.search_entry.pack(side=tk.LEFT, padx=(0, 12))
            self.search_entry.bind('<KeyRelease>', lambda e: self.refresh_movie_list())
            
            ctk.CTkButton(lib_header, text="🎬 Auto Fetch", command=self.auto_fetch_movie, fg_color="#3fa7ff", text_color="white", corner_radius=8).pack(side=tk.LEFT, padx=6)
            
            # Content area with grid + preview
            lib_content = ctk.CTkFrame(self.library_frame, fg_color="#1e1f26")
            lib_content.grid(row=1, column=0, sticky="nsew", padx=0, pady=12)
            lib_content.grid_rowconfigure(0, weight=1)
            lib_content.grid_columnconfigure(0, weight=1)

            # Movie grid (scrollable) - custom canvas-based scrolling for proper behavior
            scroll_frame = ctk.CTkFrame(lib_content, fg_color="#1e1f26", height=500)
            scroll_frame.grid(row=0, column=0, sticky="ew", padx=0, pady=0)
            scroll_frame.grid_propagate(False)

            # Create canvas and scrollbar
            self.canvas = tk.Canvas(scroll_frame, bg="#1e1f26", height=500, highlightthickness=0)
            self.scrollbar = ttk.Scrollbar(scroll_frame, orient="vertical", command=self.canvas.yview)
            self.canvas.configure(yscrollcommand=self.scrollbar.set)

            # Pack canvas and scrollbar
            self.canvas.pack(side="left", fill="both", expand=True)
            self.scrollbar.pack(side="right", fill="y")

            # Bind mouse wheel scrolling
            self.canvas.bind_all("<MouseWheel>", lambda e: self.canvas.yview_scroll(int(-1*(e.delta/120)), "units"))

            # Create frame inside canvas for cards
            self.grid_frame = ctk.CTkFrame(self.canvas, fg_color="#1e1f26")
            self.canvas.create_window((0,0), window=self.grid_frame, anchor="nw")

            # Update scrollregion when frame resizes
            self.grid_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))

            # Re-layout cards when the canvas resizes so grid becomes responsive
            try:
                self.canvas.bind('<Configure>', self._on_grid_resize)
                # store last width to avoid refresh loops
                try:
                    self._last_grid_width = self.canvas.winfo_width()
                except Exception:
                    self._last_grid_width = 0
            except Exception:
                pass
            
            # SETTINGS FRAME
            settings_inner = ctk.CTkFrame(self.settings_frame, fg_color="#1e1f26")
            settings_inner.pack(padx=40, pady=40, anchor="n")
            
            ctk.CTkLabel(settings_inner, text="Settings", font=("Segoe UI", 16, "bold"), text_color="#3fa7ff").pack(pady=(0, 20))
            
            def _toggle_theme():
                mode = ctk.get_appearance_mode()
                ctk.set_appearance_mode("light" if mode == "Dark" else "dark")
            
            self._toggle_theme = _toggle_theme
            ctk.CTkButton(settings_inner, text="🌙 Toggle Theme", command=_toggle_theme, fg_color="#3fa7ff", text_color="white", corner_radius=8).pack(pady=8, fill="x", ipady=8)
            
            ctk.CTkLabel(settings_inner, text="Font:", text_color="white").pack(pady=(16, 4), anchor="w")
            ctk.CTkOptionMenu(settings_inner, values=["Segoe UI", "Montserrat", "Poppins"], fg_color="#2b2e3b", button_color="#3fa7ff", text_color="white").pack(pady=4, fill="x")
            
            ctk.CTkLabel(settings_inner, text="TMDB API Key:", text_color="white").pack(pady=(16, 4), anchor="w")
            api_entry = ctk.CTkEntry(settings_inner, width=400, fg_color="#2b2e3b", border_color="#3fa7ff", text_color="white")
            api_entry.insert(0, self.TMDB_API_KEY)
            api_entry.pack(pady=4, ipady=8)
            
            # Status bar
            self.status_label = ctk.CTkLabel(main, text="Total movies: 0", text_color="#888", font=("Segoe UI", 9))
            self.status_label.grid(row=2, column=0, columnspan=2, sticky="ew", padx=20, pady=8)
            
            self.show_home()

        else:
            # Fallback to original ttk UI (minimal)
            self.main_frame = ttk.Frame(self.root, padding="10")
            self.main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
            self.root.columnconfigure(0, weight=1)
            self.root.rowconfigure(0, weight=1)
            self.main_frame.columnconfigure(0, weight=1)
            self.main_frame.rowconfigure(4, weight=1)
            self.title_label = ttk.Label(self.main_frame, text="🎬 Movie Collection Manager", font=self.font_title)
            self.title_label.grid(row=0, column=0, sticky=tk.W)
            self.status_label = ttk.Label(self.main_frame, text=f"Total movies: {len(self.movies)}", relief=tk.SUNKEN, anchor=tk.W)
            self.status_label.grid(row=6, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(10, 0))
    
    def show_cast_info(self):
        """Show cast and director information for selected movie"""
        # Determine selected movie (grid or tree)
        movie = None
        if hasattr(self, 'selected_index') and self.selected_index is not None:
            try:
                movie = self.movies[self.selected_index]
            except Exception:
                movie = None
        else:
            selected = getattr(self, 'tree', None)
            try:
                sel = self.tree.selection()
            except Exception:
                sel = None
            if not sel:
                messagebox.showwarning("Warning", "Please select a movie first!")
                return
            item = self.tree.item(sel[0])
            movie_name = item['values'][0]
            for m in self.movies:
                if m['name'] == movie_name:
                    movie = m
                    break

        if not movie:
            messagebox.showwarning("Warning", "Please select a movie first!")
            return

        tmdb_id = movie.get('tmdb_id')

        if not tmdb_id:
            messagebox.showinfo("No Data", "No cast information available.\nPlease use 'Auto Fetch' when adding the movie.")
            return

        try:
            credits_url = f"{self.TMDB_BASE_URL}/movie/{tmdb_id}/credits"
            params = {"api_key": self.TMDB_API_KEY}
            response = requests.get(credits_url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            cast = data.get('cast', [])[:5]
            crew = data.get('crew', [])
            directors = [person['name'] for person in crew if person.get('job') == 'Director']
            director = directors[0] if directors else "Unknown"

            # Create popup window
            cast_window = tk.Toplevel(self.root)
            cast_window.title(f"Cast & Crew - {movie.get('name','')}")
            cast_window.geometry("400x350")
            cast_window.resizable(False, False)
            if self.dark_mode:
                cast_window.configure(bg="#2b2b2b")

            title_label = ttk.Label(cast_window, text=f"🎬 {movie.get('name','')}", font=("Arial", 14, "bold"))
            title_label.pack(pady=(10,5))

            director_frame = ttk.LabelFrame(cast_window, text="Director", padding="10")
            director_frame.pack(fill=tk.X, padx=10, pady=5)
            director_label = ttk.Label(director_frame, text=f"🎬 {director}", font=("Arial", 10))
            director_label.pack(anchor=tk.W)

            cast_frame = ttk.LabelFrame(cast_window, text="Top 5 Cast Members", padding="10")
            cast_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
            if cast:
                for idx, actor in enumerate(cast, 1):
                    actor_name = actor.get('name', 'Unknown')
                    character = actor.get('character', 'Unknown')
                    actor_text = f"{idx}. {actor_name}\n   as {character}"
                    actor_label = ttk.Label(cast_frame, text=actor_text, font=("Arial", 9))
                    actor_label.pack(anchor=tk.W, pady=2)
            else:
                no_cast_label = ttk.Label(cast_frame, text="No cast information available")
                no_cast_label.pack(anchor=tk.W)

            close_button = ttk.Button(cast_window, text="Close", command=cast_window.destroy)
            close_button.pack(pady=10)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to fetch cast information:\n{str(e)}")
    
    def watch_trailer(self):
        """Search and open movie trailer on YouTube"""
        # Determine selected movie (grid or tree)
        movie = None
        if hasattr(self, 'selected_index') and self.selected_index is not None:
            try:
                movie = self.movies[self.selected_index]
            except Exception:
                movie = None
        else:
            selected = self.tree.selection()
            if not selected:
                messagebox.showwarning("Warning", "Please select a movie first!")
                return
            item = self.tree.item(selected[0])
            movie_name = item['values'][0]
            year = item['values'][1]
            for m in self.movies:
                if m['name'] == movie_name:
                    movie = m
                    break

        if movie:
            movie_name = movie.get('name')
            year = movie.get('year', '')
        else:
            messagebox.showwarning("Warning", "Please select a movie first!")
            return
        
        # Create search query
        search_query = f"{movie_name} {year} official trailer"
        youtube_search_url = f"https://www.youtube.com/results?search_query={quote(search_query)}"
        
        try:
            # Open in default browser
            webbrowser.open(youtube_search_url)
            self.status_label.configure(text=f"Opening trailer for: {movie_name}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open browser:\n{str(e)}")
    
    def toggle_dark_mode(self):
        """Toggle between dark and light mode"""
        self.dark_mode = not self.dark_mode
        self.apply_theme()
        self.save_settings()
    
    def apply_theme(self):
        """Apply dark or light theme to the application"""
        if self.dark_mode:
            # Dark mode colors
            bg_color = "#2b2b2b"
            fg_color = "#ffffff"
            entry_bg = "#3c3c3c"
            entry_fg = "#ffffff"
            button_text = "☀️ Light Mode"
            
            style = ttk.Style()
            style.theme_use('clam')

            style.configure("Treeview",
 	    background=entry_bg,
    	    foreground=fg_color,
    	    fieldbackground=entry_bg,
	    rowheight=28,
	    font=self.font_default)

            style.configure("Treeview.Heading",
            background="#141426",
            foreground="#ffffff",
            font=self.font_heading)

            style.map('Treeview', background=[('selected', '#7b3fe4')])
           
            # Configure root window
            self.root.configure(bg=bg_color)
            
            # Configure main frame
            self.main_frame.configure(style='Dark.TFrame')
            
            # Create dark theme style
            style = ttk.Style()
            style.theme_use('clam')
            
            # Configure styles for dark mode
            style.configure('Dark.TFrame', background=bg_color)
            style.configure('TLabel', background=bg_color, foreground=fg_color)
            style.configure('TLabelframe', background=bg_color, foreground=fg_color)
            style.configure('TLabelframe.Label', background=bg_color, foreground=fg_color)
            style.configure('TButton', background='#444444', foreground=fg_color)
            style.map('TButton', background=[('active', '#555555')])
            style.configure('TEntry', fieldbackground=entry_bg, foreground=entry_fg, bordercolor='#555555')
            style.configure('TCheckbutton', background=bg_color, foreground=fg_color)
            style.configure('Treeview', background=entry_bg, foreground=fg_color, fieldbackground=entry_bg)
            style.configure('Treeview.Heading', background='#444444', foreground=fg_color)
            style.map('Treeview', background=[('selected', '#0078d7')])
            
        else:
            # Light mode colors
            bg_color = "#f0f0f0"
            fg_color = "#000000"
            button_text = "🌙 Dark Mode"
            
            # Configure root window
            self.root.configure(bg=bg_color)
            
            # Reset to default theme
            style = ttk.Style()
            style.theme_use('vista' if os.name == 'nt' else 'clam')
        
        # Update dark mode button text
        if hasattr(self, 'dark_mode_button'):
            try:
                self.dark_mode_button.configure(text=button_text)
            except Exception:
                pass
    
    def attach_file(self):
        """Open file dialog to select movie file and auto-fetch from TMDB"""
        file_path = filedialog.askopenfilename(
            title="Select Movie File",
            filetypes=[
                ("Video Files", "*.mp4 *.mkv *.avi *.mov *.wmv *.flv *.webm"),
                ("MP4 Files", "*.mp4"),
                ("MKV Files", "*.mkv"),
                ("All Files", "*.*")
            ]
        )
        
        if not file_path:
            return
        
        try:
            self.current_file_path = file_path
            basename = os.path.basename(file_path)
            self.file_path_entry.delete(0, tk.END)
            self.file_path_entry.insert(0, basename)
            
            # Update status immediately
            self.status_label.configure(text="Auto detecting movie from file...")
            self.root.update()

            # Strong filename cleaning and year extraction
            name_no_ext = os.path.splitext(basename)[0]

            # Normalize separators to spaces
            s = re.sub(r'[._]+', ' ', name_no_ext)

            # Extract year (1900-2099) from original filename
            year_match = re.search(r'\b(19|20)\d{2}\b', name_no_ext)
            year_found = year_match.group(0) if year_match else ''
            
            if year_found:
                # remove year occurrences, including surrounding parentheses like (1981)
                s = re.sub(r'\(\s*' + re.escape(year_found) + r'\s*\)', ' ', s)
                s = re.sub(r'\b' + re.escape(year_found) + r'\b', ' ', s)

            # Remove bracketed content like [..] and {..} and any remaining parenthesis content
            s = re.sub(r'\[.*?\]|\{.*?\}|\(.*?\)', ' ', s)

            # Remove common tokens: resolutions, codecs, sources, audio/language, release tags
            tokens_pattern = r'\b(1080p|720p|2160p|4k|8k|x264|x265|h264|hevc|xvid|divx|web[- ]?dl|webrip|web[-_. ]?rip|blu[- ]?ray|brrip|bdrip|hdrip|dvdrip|hdcam|camrip|hdts|hdr|rip|yify|rarbg|proper|repack|extended|unrated|dual audio|dual-audio|dualaudio|multi|dubbed|subs|subbed|hindi|english)\b'
            s = re.sub(tokens_pattern, ' ', s, flags=re.IGNORECASE)

            # Remove any release-group at end after a dash or space (e.g., -GROUP)
            s = re.sub(r'[-]+[A-Za-z0-9]+$', ' ', s)

            # Remove leftover non-alphanumeric characters except spaces and colons
            s = re.sub(r'[^0-9A-Za-z:\s]', ' ', s)

            # Collapse spaces and trim
            cleaned = ' '.join(s.split()).strip()

            # Split into words and keep up to first 4 words
            words = cleaned.split()
            if len(words) > 4:
                keep = words[:4]
            else:
                keep = words

            cleaned_title = ' '.join(keep).strip()

            if not cleaned_title:
                # Fallback to filename without extension
                cleaned_title = name_no_ext

            # Update movie name field
            self.movie_name_entry.delete(0, tk.END)
            self.movie_name_entry.insert(0, cleaned_title)

            # Update year field if found
            if year_found:
                self.year_entry.delete(0, tk.END)
                self.year_entry.insert(0, year_found)

            # Force UI update
            self.root.update()
            
            # Now fetch from TMDB
            self._fetch_from_tmdb_for_filename(cleaned_title, year_found)

        except Exception as e:
            self.status_label.configure(text=f"Error: {str(e)}")

    def _fetch_from_tmdb_for_filename(self, movie_name, year_found):
        """Fetch movie data from TMDB for auto-detected filename"""
        try:
            if not movie_name:
                self.status_label.configure(text="No movie name to search")
                return

            self.status_label.configure(text="Fetching movie data from TMDB...")
            self.root.update()
            
            # Prepare search parameters
            year_param = year_found if year_found else ''
            
            # Clean title
            clean_name = re.sub(r'[^0-9A-Za-z\s:]', ' ', movie_name)
            clean_name = ' '.join(clean_name.split()).strip()
            
            if not clean_name:
                self.status_label.configure(text="Could not clean movie name")
                return
            
            # Search TMDB
            search_url = f"{self.TMDB_BASE_URL}/search/movie"
            params = {
                "api_key": self.TMDB_API_KEY,
                "query": clean_name
            }
            if year_param:
                params["primary_release_year"] = year_param

            response = requests.get(search_url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            # Retry without year if no results
            if not data.get('results') and year_param:
                params.pop("primary_release_year", None)
                response = requests.get(search_url, params=params, timeout=10)
                response.raise_for_status()
                data = response.json()

            if not data.get('results'):
                self.status_label.configure(text=f"Movie not found on TMDB: {clean_name}")
                return
            
            # Get first result
            movie = data['results'][0]
            
            # Extract movie data
            title = movie.get('title', clean_name)
            year = movie.get('release_date', '')[:4] if movie.get('release_date') else ''
            rating = movie.get('vote_average', 0)
            genre_ids = movie.get('genre_ids', [])
            poster_path = movie.get('poster_path')
            tmdb_id = movie.get('id')
            
            # Store TMDB ID
            self.current_tmdb_id = tmdb_id
            
            # Get genre names
            genre_names = self.get_genre_names(genre_ids)
            
            # Update all fields
            self.movie_name_entry.delete(0, tk.END)
            self.movie_name_entry.insert(0, title)
            
            self.year_entry.delete(0, tk.END)
            self.year_entry.insert(0, year)
            
            self.genre_entry.delete(0, tk.END)
            self.genre_entry.insert(0, genre_names)
            
            self.rating_spinbox.delete(0, tk.END)
            self.rating_spinbox.insert(0, f"{rating:.1f}")
            
            # Load poster
            if poster_path:
                self.current_poster_url = poster_path
                self.load_poster(poster_path)
                self.status_label.configure(text=f"✓ Auto-detected: {title} ({year})")
            else:
                self.status_label.configure(text=f"✓ Auto-detected: {title} ({year}) - No poster")
            
        except requests.exceptions.RequestException as e:
            self.status_label.configure(text=f"Network error: {str(e)}")
        except Exception as e:
            self.status_label.configure(text=f"Error fetching data: {str(e)}")
    
    def play_movie(self, event=None):
        """Play movie file in default player (double-click or button)"""
        movie = None
        # Prefer grid selection when available
        if hasattr(self, 'selected_index') and self.selected_index is not None:
            try:
                movie = self.movies[self.selected_index]
            except Exception:
                movie = None
        else:
            # Fallback to tree selection
            try:
                selected = self.tree.selection()
                if not selected:
                    if event is None:
                        messagebox.showwarning("Warning", "Please select a movie to play!")
                    return
                item = self.tree.item(selected[0])
                movie_name = item['values'][0]
                for m in self.movies:
                    if m['name'] == movie_name:
                        movie = m
                        break
            except Exception:
                movie = None

        if not movie:
            messagebox.showwarning("Warning", "Please select a movie to play!")
            return

        file_path = movie.get('file_path')

        if not file_path:
            messagebox.showinfo("No File", f"No video file attached to '{movie.get('name','')}'")
            return

        if not os.path.exists(file_path):
            messagebox.showerror("File Not Found", f"Video file not found:\n{file_path}\n\nPlease re-attach the file.")
            return

        try:
            # Use os.startfile for Windows to open with default player
            os.startfile(file_path)
            self.status_label.configure(text=f"Playing: {movie.get('name','')}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open video file:\n{str(e)}")
    
    def export_to_csv(self):
        """Export movie collection to CSV file"""
        if not self.movies:
            messagebox.showwarning("Warning", "No movies to export!")
            return
        
        # Ask user for save location
        file_path = filedialog.asksaveasfilename(
            title="Export to CSV",
            defaultextension=".csv",
            filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")],
            initialfile=f"movie_collection_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        )
        
        if not file_path:
            return
        
        try:
            with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
                # Define CSV headers
                fieldnames = ['Title', 'Year', 'Genre', 'Rating', 'Watched']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                
                # Write header
                writer.writeheader()
                
                # Write movie data
                for movie in self.movies:
                    writer.writerow({
                        'Title': movie.get('name', ''),
                        'Year': movie.get('year', ''),
                        'Genre': movie.get('genre', ''),
                        'Rating': movie.get('rating', ''),
                        'Watched': 'Yes' if movie.get('watched', False) else 'No'
                    })
            
            self.status_label.configure(text=f"Exported {len(self.movies)} movies to CSV")
            messagebox.showinfo("Success", f"Successfully exported {len(self.movies)} movies to:\n{file_path}")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export CSV:\n{str(e)}")
    
    def auto_fetch_movie(self):
        """Fetch movie data from TMDB API"""
        movie_name_raw = self.movie_name_entry.get().strip()

        if not movie_name_raw:
            messagebox.showwarning("Warning", "Please enter a movie name first!")
            return

        # Try to extract year from the name or from the Year field
        import re
        year_param = ''
        # Year from movie_name_raw
        m = re.search(r'\b(19|20)\d{2}\b', movie_name_raw)
        if m:
            year_param = m.group(0)
            movie_name = re.sub(r'\b(19|20)\d{2}\b', '', movie_name_raw).strip()
        else:
            movie_name = movie_name_raw

        # If Year field has a valid year, prefer it
        year_field = self.year_entry.get().strip()
        if re.match(r'^(19|20)\d{2}$', year_field):
            year_param = year_field

        # Clean title string to contain only words/spaces
        movie_name = re.sub(r'[^0-9A-Za-z\s:]', ' ', movie_name)
        movie_name = ' '.join(movie_name.split()).strip()
        
        # Show loading status
        self.status_label.configure(text="Fetching movie data from TMDB...")
        self.root.update()
        
        try:
            # Search for movie (prefer using primary_release_year when available)
            search_url = f"{self.TMDB_BASE_URL}/search/movie"
            params = {
                "api_key": self.TMDB_API_KEY,
                "query": movie_name
            }
            if year_param:
                params["primary_release_year"] = year_param

            response = requests.get(search_url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            # If no results and we had used year, retry without year as fallback
            if not data.get('results') and year_param:
                params.pop("primary_release_year", None)
                response = requests.get(search_url, params=params, timeout=10)
                response.raise_for_status()
                data = response.json()

            if not data.get('results'):
                # Inform user about fallback
                self.status_label.configure(text=f"Movie not found. Keeping cleaned title: {movie_name}")
                messagebox.showinfo("Not Found", f"No TMDB result for '{movie_name}'\n\nPlease review the title and edit manually.")
                return
            
            # Get first result
            movie = data['results'][0]
            
            # Extract data
            title = movie.get('title', movie_name)
            year = movie.get('release_date', '')[:4] if movie.get('release_date') else ''
            rating = movie.get('vote_average', 0)
            genre_ids = movie.get('genre_ids', [])
            poster_path = movie.get('poster_path')
            tmdb_id = movie.get('id')
            
            # Store TMDB ID for cast/crew lookup
            self.current_tmdb_id = tmdb_id
            
            # Fetch genre names
            genre_names = self.get_genre_names(genre_ids)
            
            # Update fields
            self.movie_name_entry.delete(0, tk.END)
            self.movie_name_entry.insert(0, title)
            
            self.year_entry.delete(0, tk.END)
            self.year_entry.insert(0, year)
            
            self.genre_entry.delete(0, tk.END)
            self.genre_entry.insert(0, genre_names)
            
            self.rating_spinbox.set(f"{rating:.1f}")
            
            # Load poster
            if poster_path:
                self.current_poster_url = poster_path
                self.load_poster(poster_path)
            else:
                self.current_poster = None
                self.current_poster_url = None
                self.poster_label.config(image='', text="No poster")
            
            self.status_label.configure(text=f"Successfully fetched: {title} ({year})")
            messagebox.showinfo("Success", f"Movie data fetched successfully!\n\n{title} ({year})")
            
        except requests.exceptions.RequestException as e:
            messagebox.showerror("Error", f"Failed to fetch movie data:\n{str(e)}")
            self.status_label.configure(text=f"Total movies: {len(self.movies)}")
        except Exception as e:
            messagebox.showerror("Error", f"An error occurred:\n{str(e)}")
            self.status_label.configure(text=f"Total movies: {len(self.movies)}")
    
    def get_genre_names(self, genre_ids):
        """Convert genre IDs to names"""
        # TMDB genre mapping
        genre_map = {
            28: "Action", 12: "Adventure", 16: "Animation", 35: "Comedy",
            80: "Crime", 99: "Documentary", 18: "Drama", 10751: "Family",
            14: "Fantasy", 36: "History", 27: "Horror", 10402: "Music",
            9648: "Mystery", 10749: "Romance", 878: "Science Fiction",
            10770: "TV Movie", 53: "Thriller", 10752: "War", 37: "Western"
        }
        
        genres = [genre_map.get(gid, "") for gid in genre_ids if gid in genre_map]
        return ", ".join(genres[:3])  # Limit to 3 genres
    
    def load_poster(self, poster_path):
        """Load and display movie poster"""
        try:
            poster_url = f"{self.TMDB_IMAGE_BASE_URL}{poster_path}"
            response = requests.get(poster_url, timeout=10)
            response.raise_for_status()
            
            # Load image
            image_data = Image.open(BytesIO(response.content)).convert('RGBA')

            # Thumb for grid
            thumb = image_data.copy()
            thumb.thumbnail((120, 180), Image.Resampling.LANCZOS)
            if ctk:
                try:
                    self.current_poster = ctk.CTkImage(light_image=thumb, size=(120,180))
                except Exception:
                    self.current_poster = ImageTk.PhotoImage(thumb)
            else:
                self.current_poster = ImageTk.PhotoImage(thumb)

            # Larger preview
            preview = image_data.copy()
            preview.thumbnail((200, 300), Image.Resampling.LANCZOS)
            if ctk:
                try:
                    self.current_preview_poster = ctk.CTkImage(light_image=preview, size=(200,300))
                except Exception:
                    self.current_preview_poster = ImageTk.PhotoImage(preview)
            else:
                self.current_preview_poster = ImageTk.PhotoImage(preview)

            # Update available labels
            try:
                self.poster_label.configure(image=self.current_poster, text="")
            except Exception:
                pass
            try:
                self.preview_image_label.configure(image=self.current_preview_poster, text="")
            except Exception:
                pass
            
        except Exception as e:
            print(f"Error loading poster: {e}")
            self.current_poster = None
            self.current_preview_poster = None
            try:
                self.poster_label.configure(image='', text="Poster\nfailed")
            except Exception:
                pass
            try:
                self.preview_image_label.configure(image='', text="Poster failed")
            except Exception:
                pass
    
    def add_movie(self):
        name = self.movie_name_entry.get().strip()
        genre = self.genre_entry.get().strip()
        year = self.year_entry.get().strip()
        
        if not name:
            messagebox.showwarning("Warning", "Please enter a movie name!")
            return
        
        try:
            rating = float(self.rating_spinbox.get())
            if rating < 0 or rating > 10:
                messagebox.showwarning("Warning", "Rating must be between 0 and 10!")
                return
        except ValueError:
            messagebox.showwarning("Warning", "Invalid rating value!")
            return
        
        watched = self.watched_var.get()
        
        movie = {
            "name": name,
            "year": year,
            "genre": genre,
            "rating": rating,
            "watched": watched,
            "poster_path": self.current_poster_url,
            "file_path": self.current_file_path,
            "tmdb_id": self.current_tmdb_id
        }
        
        self.movies.append(movie)
        self.save_data()
        self.refresh_movie_list()
        self.clear_inputs()
        messagebox.showinfo("Success", f"'{name}' added successfully!")
    
    def delete_movie(self):
        # Support deletion from grid selection or tree selection
        movie = None
        if hasattr(self, 'selected_index') and self.selected_index is not None:
            try:
                movie = self.movies[self.selected_index]
            except Exception:
                movie = None
        else:
            selected = self.tree.selection()
            if not selected:
                messagebox.showwarning("Warning", "Please select a movie to delete!")
                return
            item = self.tree.item(selected[0])
            movie_name = item['values'][0]
            for m in self.movies:
                if m['name'] == movie_name:
                    movie = m
                    break

        if not movie:
            messagebox.showwarning("Warning", "Please select a movie to delete!")
            return

        movie_name = movie.get('name')
        if messagebox.askyesno("Confirm Delete", f"Delete '{movie_name}'?"):
            try:
                self.movies.remove(movie)
            except Exception:
                # fallback: find by name
                for i, mm in enumerate(self.movies):
                    if mm.get('name') == movie_name:
                        self.movies.pop(i)
                        break

            self.save_data()
            self.selected_index = None
            self.refresh_movie_list()
            messagebox.showinfo("Success", "Movie deleted successfully!")
    
    def edit_movie(self):
        # Allow editing from grid selection or tree selection
        movie = None
        if hasattr(self, 'selected_index') and self.selected_index is not None:
            try:
                movie = self.movies[self.selected_index]
            except Exception:
                movie = None
        else:
            selected = self.tree.selection()
            if not selected:
                messagebox.showwarning("Warning", "Please select a movie to edit!")
                return
            item = self.tree.item(selected[0])
            values = item['values']
            for m in self.movies:
                if m['name'] == values[0]:
                    movie = m
                    break

        if not movie:
            messagebox.showwarning("Warning", "Please select a movie to edit!")
            return

        # Populate input fields
        try:
            self.movie_name_entry.delete(0, tk.END)
            self.movie_name_entry.insert(0, movie['name'])

            self.year_entry.delete(0, tk.END)
            self.year_entry.insert(0, movie.get('year', ''))

            self.genre_entry.delete(0, tk.END)
            self.genre_entry.insert(0, movie.get('genre', ''))

            # rating_spinbox may be CTkEntry or ttk.Spinbox
            try:
                self.rating_spinbox.delete(0, tk.END)
                self.rating_spinbox.insert(0, str(movie.get('rating', '')))
            except Exception:
                try:
                    self.rating_spinbox.set(movie.get('rating'))
                except Exception:
                    pass

            self.watched_var.set(movie.get('watched'))

            # Load poster if available
            self.current_poster_url = movie.get('poster_path')
            if self.current_poster_url:
                self.load_poster(self.current_poster_url)
            else:
                self.current_poster = None
                try:
                    self.poster_label.config(image='', text="No poster")
                except Exception:
                    pass

            # Load file path if available
            self.current_file_path = movie.get('file_path')
            try:
                self.file_path_entry.delete(0, tk.END)
                if self.current_file_path:
                    self.file_path_entry.insert(0, os.path.basename(self.current_file_path))
            except Exception:
                pass

            # Load TMDB ID
            self.current_tmdb_id = movie.get('tmdb_id')

            # Remove the movie (will be re-added when user clicks Add)
            try:
                self.movies.remove(movie)
            except Exception:
                pass
            self.refresh_movie_list()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to populate edit form:\n{e}")
    
    def clear_inputs(self):
        self.movie_name_entry.delete(0, tk.END)
        self.year_entry.delete(0, tk.END)
        self.genre_entry.delete(0, tk.END)
        self.rating_spinbox.delete(0, tk.END)
        self.rating_spinbox.insert(0, "5.0")
        self.watched_var.set(False)
        self.current_poster = None
        self.current_poster_url = None
        self.current_file_path = None
        self.current_tmdb_id = None
        self.poster_label.config(image='', text="No poster")
        self.file_path_entry.delete(0, tk.END)
    
    def clear_search(self):
        self.search_entry.delete(0, tk.END)
        self.refresh_movie_list()

    def _on_grid_resize(self, event=None):
        # Only refresh when width changes significantly to avoid flicker loops
        try:
            new_w = event.width if (event is not None and hasattr(event, 'width')) else (self.grid_frame.winfo_width() if hasattr(self, 'grid_frame') else 0)
        except Exception:
            new_w = 0

        last_w = getattr(self, '_last_grid_width', None)
        if last_w is not None:
            try:
                if abs(new_w - last_w) < 12:
                    return
            except Exception:
                pass
        try:
            self._last_grid_width = new_w
        except Exception:
            pass

        # Debounce and schedule refresh
        try:
            if hasattr(self, '_grid_resize_after_id'):
                self.root.after_cancel(self._grid_resize_after_id)
        except Exception:
            pass
        try:
            self._grid_resize_after_id = self.root.after(150, self.refresh_movie_list)
        except Exception:
            try:
                self.refresh_movie_list()
            except Exception:
                pass
    
    def refresh_movie_list(self):
        # If customtkinter UI is active, render poster grid; otherwise fill legacy treeview
        search_term = self.search_entry.get().lower() if hasattr(self, 'search_entry') else ''
        displayed_count = 0

        if ctk and hasattr(self, 'grid_frame'):
            # Clear grid
            for child in self.grid_frame.winfo_children():
                child.destroy()

            # Fixed card dimensions for consistent display
            card_w = 160  # Fixed width
            card_h = 240  # Fixed height (1.5 aspect ratio)

            # Calculate columns based on available width
            try:
                frame_width = max(1, self.canvas.winfo_width())
            except Exception:
                frame_width = 800

            # Dynamic column count based on frame width
            columns = max(1, frame_width // 180)

            # Configure grid columns
            for c in range(columns):
                try:
                    self.grid_frame.grid_columnconfigure(c, weight=1)
                except Exception:
                    pass

            for idx, movie in enumerate(self.movies):
                if search_term:
                    if not (search_term in movie['name'].lower() or search_term in movie.get('genre', '').lower() or search_term in str(movie.get('year', '')).lower()):
                        continue

                # Calculate row and column for this movie
                row = idx // columns
                col = idx % columns

                # Card frame with consistent sizing and padding
                card = ctk.CTkFrame(self.grid_frame, width=card_w, height=card_h, corner_radius=12, fg_color="#2b2e3b")
                card.grid(row=row, column=col, padx=12, pady=12, sticky="n")
                # Allow card to expand to fill column width
                card.grid_propagate(True)
                def on_enter(e):
                    card.configure(border_width=2, border_color="#3b82f6", width=170, height=250)

                def on_leave(e):
                    card.configure(border_width=0, width=160, height=240)

                card.bind("<Enter>", on_enter)
                card.bind("<Leave>", on_leave)

                # Header frame with delete button (absolute positioning)
                header_frame = ctk.CTkFrame(card, fg_color="transparent", height=30)
                header_frame.pack(fill="x", padx=8, pady=(8, 0))

                # Delete button (top-right corner) - single button
                def make_delete_cb(movie_idx):
                    def delete_cb():
                        if messagebox.askyesno("Delete", f"Delete '{self.movies[movie_idx].get('name')}'?"):
                            self.movies.pop(movie_idx)
                            self.save_data()
                            self.refresh_movie_list()
                            self.status_label.configure(text=f"Movie deleted. Total movies: {len(self.movies)}")
                    return delete_cb

                del_btn = ctk.CTkButton(header_frame, text="🗑️", width=32, height=32, corner_radius=6,
                                       fg_color="#e74c3c", text_color="white", command=make_delete_cb(idx),
                                       font=("Arial", 12))
                del_btn.pack(side=tk.RIGHT)

                # Poster image - centered and fixed size
                poster_path = movie.get('poster_path')
                poster_w = max(88, int(card_w * 0.62))
                poster_h = int(poster_w * 1.5)
                img_label = ctk.CTkLabel(card, text="No Poster", width=poster_w, height=poster_h, corner_radius=8,
                                         fg_color="#1e1f26", text_color="gray")
                img_label.pack(pady=(12,8))

                # Load cached image or fetch
                if poster_path:
                    cache_key = f"{poster_path}_{poster_w}_{poster_h}"
                    if cache_key in self._image_cache:
                        img_label.configure(image=self._image_cache[cache_key], text='')
                    else:
                        try:
                            resp = requests.get(f"{self.TMDB_IMAGE_BASE_URL}{poster_path}", timeout=8)
                            resp.raise_for_status()
                            im = Image.open(BytesIO(resp.content)).convert('RGBA')
                            im.thumbnail((poster_w, poster_h), Image.Resampling.LANCZOS)
                            if ctk:
                                try:
                                    ph = ctk.CTkImage(light_image=im, size=(poster_w, poster_h))
                                except Exception:
                                    ph = ImageTk.PhotoImage(im)
                            else:
                                ph = ImageTk.PhotoImage(im)
                            self._image_cache[cache_key] = ph
                            img_label.configure(image=ph, text='')
                        except Exception:
                            pass

                # Title & year - centered and fixed height
                title = movie.get('name', '')
                year = movie.get('year', '')
                lbl = ctk.CTkLabel(card, text=f"{title}\n({year})", wraplength=170, justify=tk.CENTER,
                                   fg_color="#2b2e3b", text_color="white", font=("Arial", 11, "bold"))
                lbl.pack(pady=(6, 4), fill="x", padx=6)

                # Rating badge - centered
                rating = movie.get('rating', 0)
                badge = ctk.CTkLabel(card, text=f"⭐ {rating}", width=80, height=28,
                                     fg_color="#3fa7ff", text_color="white", font=("Arial", 10, "bold"),
                                     corner_radius=6)
                badge.pack(pady=(0, 4))

                # Click behavior
                def make_cb(i):
                    return lambda e=None: self.select_movie(i)

                card.bind('<Button-1>', make_cb(idx))
                img_label.bind('<Button-1>', make_cb(idx))
                lbl.bind('<Button-1>', make_cb(idx))

                # Hover effects
                def on_enter(e, w=card):
                    try:
                        w.configure(border_width=2, border_color="#7b3fe4")
                    except Exception:
                        pass

                def on_leave(e, w=card):
                    try:
                        w.configure(border_width=0)
                    except Exception:
                        pass

                card.bind('<Enter>', on_enter)
                card.bind('<Leave>', on_leave)

                displayed_count += 1

            # No need to configure row weights - let the frame size to content

            # Update status
            if search_term:
                self.status_label.configure(text=f"Showing {displayed_count} of {len(self.movies)} movies")
            else:
                self.status_label.configure(text=f"Total movies: {len(self.movies)}")

        else:
            # Legacy treeview population
            if hasattr(self, 'tree'):
                for item in self.tree.get_children():
                    self.tree.delete(item)
                for movie in self.movies:
                    if (search_term in movie['name'].lower() or 
                        search_term in movie.get('genre', '').lower() or
                        search_term in str(movie.get('year', '')).lower()):
                        watched_text = "✓ Yes" if movie['watched'] else "✗ No"
                        year = movie.get('year', '')
                        has_file = "✓" if movie.get('file_path') else "✗"
                        self.tree.insert("", tk.END, values=(
                            movie['name'],
                            year,
                            movie.get('genre', ''),
                            f"{movie['rating']}/10",
                            watched_text,
                            has_file
                        ))
                        displayed_count += 1

            if search_term:
                try:
                    self.status_label.configure(text=f"Showing {displayed_count} of {len(self.movies)} movies")
                except Exception:
                    pass
            else:
                try:
                    self.status_label.configure(text=f"Total movies: {len(self.movies)}")
                except Exception:
                    pass

    # Page switching helpers
    def show_home(self):
        if hasattr(self, 'home_frame'):
            self.home_frame.tkraise()

    def show_library(self):
        if hasattr(self, 'library_frame'):
            self.library_frame.tkraise()

    def show_settings(self):
        if hasattr(self, 'settings_frame'):
            self.settings_frame.tkraise()

    def set_active_tab(self, tab_name):
        """Switch active tab and update sidebar button styles"""
        # Raise the requested frame
        try:
            if tab_name == 'home':
                self.home_frame.tkraise()
            elif tab_name == 'library':
                self.library_frame.tkraise()
                try:
                    self.refresh_movie_list()
                except Exception:
                    pass
            elif tab_name == 'add':
                self.add_frame.tkraise()
            elif tab_name == 'settings':
                self.settings_frame.tkraise()
        except Exception:
            pass

        # Update sidebar button visuals
        try:
            for key, btn in getattr(self, 'sidebar_buttons', {}).items():
                try:
                    if key == tab_name:
                        btn.configure(fg_color="#3fa7ff")
                    else:
                        btn.configure(fg_color="#2b2e3b")
                except Exception:
                    pass
        except Exception:
            pass

    def hide_detail_panel(self):
        """Deprecated - detail panel now uses popup overlay"""
        pass

    def open_selected_in_editor(self):
        """Open the selected movie in the Add/Edit form for editing"""
        try:
            if self.selected_index is None:
                return
            movie = self.movies[self.selected_index]
            # Populate add form fields
            try:
                self.movie_name_entry.delete(0, tk.END)
                self.movie_name_entry.insert(0, movie.get('name',''))
                self.year_entry.delete(0, tk.END)
                self.year_entry.insert(0, movie.get('year',''))
                self.genre_entry.delete(0, tk.END)
                self.genre_entry.insert(0, movie.get('genre',''))
                self.rating_spinbox.delete(0, tk.END)
                self.rating_spinbox.insert(0, str(movie.get('rating','')))
                self.watched_var.set(movie.get('watched', False))
                self.file_path_entry.delete(0, tk.END)
                if movie.get('file_path'):
                    self.file_path_entry.insert(0, os.path.basename(movie.get('file_path')))
                # Poster preview
                poster = movie.get('poster_path')
                if poster and poster in self._image_cache:
                    try:
                        self.poster_label.configure(image=self._image_cache[poster], text='')
                    except Exception:
                        pass
            except Exception:
                pass
            # Switch to add/edit tab
            self.set_active_tab('add')
        except Exception:
            pass

    def select_movie(self, index):
        """Select a movie from the grid/list and open detail popup"""
        try:
            self.selected_index = index
            self.show_movie_detail_popup()
        except Exception:
            self.selected_index = None
    
    def show_movie_detail_popup(self):
        """Display movie details in a popup window"""
        if self.selected_index is None or self.selected_index >= len(self.movies):
            return
        
        movie = self.movies[self.selected_index]
        
        # Create popup window
        popup = tk.Toplevel(self.root)
        popup.title(movie.get('name', 'Movie Details'))
        # Ensure popup is tall enough so buttons remain visible
        popup.geometry("520x640")
        popup.configure(bg="#1e1f26")
        popup.resizable(False, False)
        
        # Center on screen
        popup.update_idletasks()
        x = (popup.winfo_screenwidth() // 2) - (520 // 2)
        y = (popup.winfo_screenheight() // 2) - (700 // 2)
        popup.geometry(f"+{x}+{y}")
        
        # Title
        title_label = ctk.CTkLabel(popup, text=movie.get('name', ''), font=("Segoe UI", 18, "bold"), text_color="#3fa7ff")
        title_label.pack(pady=(16, 8))
        
        # Poster (reduced size to save space)
        poster_frame = ctk.CTkFrame(popup, fg_color="#2b2e3b", corner_radius=8)
        poster_frame.pack(padx=16, pady=(8,6))

        poster_label = ctk.CTkLabel(poster_frame, text="No Poster", width=200, height=280, fg_color="#1e1f26", corner_radius=8, text_color="#888")
        poster_label.pack(padx=10, pady=10)
        
        # Load poster image
        poster = movie.get('poster_path')
        if poster:
            if poster in self._image_cache:
                ph = self._image_cache[poster]
                try:
                    poster_label.configure(image=ph, text='')
                except Exception:
                    pass
            else:
                try:
                    resp = requests.get(f"{self.TMDB_IMAGE_BASE_URL}{poster}", timeout=8)
                    resp.raise_for_status()
                    im = Image.open(BytesIO(resp.content)).convert('RGBA')
                    im.thumbnail((200, 280), Image.Resampling.LANCZOS)
                    if ctk:
                        try:
                            ph = ctk.CTkImage(light_image=im, size=(200, 280))
                        except Exception:
                            ph = ImageTk.PhotoImage(im)
                    else:
                        ph = ImageTk.PhotoImage(im)
                    self._image_cache[poster] = ph
                    try:
                        poster_label.configure(image=ph, text='')
                    except Exception:
                        pass
                except Exception:
                    pass
        
        # Info (aligned labels)
        info_frame = ctk.CTkFrame(popup, fg_color="#2b2e3b", corner_radius=8)
        info_frame.pack(padx=16, pady=(6,8), fill="x")

        year = movie.get('year', '')
        genre = movie.get('genre', '')
        rating = movie.get('rating', '')
        watched = 'Yes' if movie.get('watched') else 'No'

        # Use a two-column layout for labels and values
        lbl_genre = ctk.CTkLabel(info_frame, text="Genre:", text_color="#888", anchor="w")
        val_genre = ctk.CTkLabel(info_frame, text=genre or "-", text_color="white", anchor="w")
        lbl_year = ctk.CTkLabel(info_frame, text="Year:", text_color="#888", anchor="w")
        val_year = ctk.CTkLabel(info_frame, text=year or "-", text_color="white", anchor="w")
        lbl_rating = ctk.CTkLabel(info_frame, text="Rating:", text_color="#888", anchor="w")
        val_rating = ctk.CTkLabel(info_frame, text=str(rating) if rating else "-", text_color="white", anchor="w")
        lbl_watched = ctk.CTkLabel(info_frame, text="Watched:", text_color="#888", anchor="w")
        val_watched = ctk.CTkLabel(info_frame, text=watched, text_color="white", anchor="w")

        # Grid them
        info_frame.grid_columnconfigure(0, weight=0)
        info_frame.grid_columnconfigure(1, weight=1)
        lbl_genre.grid(row=0, column=0, sticky="w", padx=(12,6), pady=(10,4))
        val_genre.grid(row=0, column=1, sticky="w", padx=(0,12), pady=(10,4))
        lbl_year.grid(row=1, column=0, sticky="w", padx=(12,6), pady=4)
        val_year.grid(row=1, column=1, sticky="w", padx=(0,12), pady=4)
        lbl_rating.grid(row=2, column=0, sticky="w", padx=(12,6), pady=4)
        val_rating.grid(row=2, column=1, sticky="w", padx=(0,12), pady=4)
        lbl_watched.grid(row=3, column=0, sticky="w", padx=(12,6), pady=(4,12))
        val_watched.grid(row=3, column=1, sticky="w", padx=(0,12), pady=(4,12))
        
        # Action buttons
        # Action buttons arranged in two columns
        actions_frame = ctk.CTkFrame(popup, fg_color="#1e1f26")
        # Pin actions to bottom so they're always visible
        actions_frame.pack(side=tk.BOTTOM, padx=16, pady=(8,12), fill="x")
        actions_frame.grid_columnconfigure(0, weight=1)
        actions_frame.grid_columnconfigure(1, weight=1)
        
        def close_popup():
            popup.destroy()
        
        def play_from_popup():
            self.play_movie()
            close_popup()
        
        def trailer_from_popup():
            self.watch_trailer()
            close_popup()
        
        def cast_from_popup():
            self.show_cast_info()
            # Don't close popup - let user keep details window open
        
        def edit_from_popup():
            self.open_selected_in_editor()
            close_popup()
        
        def delete_from_popup():
            if messagebox.askyesno("Delete", f"Delete '{movie.get('name')}'?"):
                self.delete_movie()
                close_popup()
        
        btn_play = ctk.CTkButton(actions_frame, text="▶️ Play", command=play_from_popup, fg_color="#3fa7ff", text_color="white", corner_radius=8)
        btn_trailer = ctk.CTkButton(actions_frame, text="🎥 Trailer", command=trailer_from_popup, fg_color="#3fa7ff", text_color="white", corner_radius=8)
        btn_cast = ctk.CTkButton(actions_frame, text="👥 View Cast", command=cast_from_popup, fg_color="#3fa7ff", text_color="white", corner_radius=8)
        btn_edit = ctk.CTkButton(actions_frame, text="✏️ Edit", command=edit_from_popup, fg_color="#3fa7ff", text_color="white", corner_radius=8)
        btn_delete = ctk.CTkButton(actions_frame, text="🗑️ Delete", command=delete_from_popup, fg_color="#e74c3c", text_color="white", corner_radius=8)
        btn_close = ctk.CTkButton(actions_frame, text="✕ Close", command=close_popup, fg_color="#555", text_color="white", corner_radius=8)

        # Place buttons in a grid (two per row)
        btn_play.grid(row=0, column=0, padx=6, pady=6, sticky="ew")
        btn_trailer.grid(row=0, column=1, padx=6, pady=6, sticky="ew")
        btn_cast.grid(row=1, column=0, padx=6, pady=6, sticky="ew")
        btn_edit.grid(row=1, column=1, padx=6, pady=6, sticky="ew")
        btn_delete.grid(row=2, column=0, padx=6, pady=6, sticky="ew")
        btn_close.grid(row=2, column=1, padx=6, pady=6, sticky="ew")
        
        # Make popup modal so it's focused and remains on top
        try:
            popup.transient(self.root)
            popup.grab_set()
        except Exception:
            pass
    
    def save_data(self):
        try:
            with open(self.data_file, 'w') as f:
                json.dump(self.movies, f, indent=2)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save data: {str(e)}")
    
    def load_data(self):
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, 'r') as f:
                    self.movies = json.load(f)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load data: {str(e)}")
                self.movies = []
        else:
            self.movies = []
    
    def save_settings(self):
        """Save application settings to JSON"""
        try:
            settings = {
                "dark_mode": self.dark_mode
            }
            with open(self.settings_file, 'w') as f:
                json.dump(settings, f, indent=2)
        except Exception as e:
            print(f"Failed to save settings: {e}")
    
    def load_settings(self):
        """Load application settings from JSON"""
        if os.path.exists(self.settings_file):
            try:
                with open(self.settings_file, 'r') as f:
                    settings = json.load(f)
                    self.dark_mode = settings.get('dark_mode', False)
            except Exception as e:
                print(f"Failed to load settings: {e}")
                self.dark_mode = False
        else:
            self.dark_mode = False

def main():
    root = tk.Tk()
    app = MovieCollectionManager(root)
    root.mainloop()

if __name__ == "__main__":
    main()
