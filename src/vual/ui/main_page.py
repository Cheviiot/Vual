"""Main games grid page.

Clean rewrite using Gtk.FlowBox + simple Gtk.Overlay tiles.
"""

from __future__ import annotations

import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import TYPE_CHECKING

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Gdk", "4.0")
gi.require_version("GdkPixbuf", "2.0")
gi.require_version("Pango", "1.0")

from gi.repository import Adw, Gdk, GdkPixbuf, GLib, Gtk, Pango

import requests

from vual import protonhax, steam
from vual.config import TILE_SIZES, Config
from vual.i18n import _

if TYPE_CHECKING:
    from vual.window import VualWindow


# ═══════════════════════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════════════════════

COVER_RATIO = 1.5  # Height = Width * 1.5 (portrait)
GRID_SPACING = 12  # Spacing between tiles
GRID_MARGIN = 16   # Margin around grid

# Steam cover URLs
COVER_URL = "https://steamcdn-a.akamaihd.net/steam/apps/{}/library_600x900_2x.jpg"
COVER_FALLBACK = "https://steamcdn-a.akamaihd.net/steam/apps/{}/header.jpg"

# Cache directory
CACHE_DIR = Path(GLib.get_user_cache_dir()) / "vual" / "covers"


# ═══════════════════════════════════════════════════════════════════════════════
# Cover loading utilities
# ═══════════════════════════════════════════════════════════════════════════════

def _cache_path(app_id: str) -> Path:
    """Get cache path for cover image."""
    return CACHE_DIR / f"{app_id}.jpg"


def _download_cover(app_id: str) -> Path | None:
    """Download cover from Steam CDN. Returns cache path or None."""
    cache = _cache_path(app_id)
    if cache.exists():
        return cache

    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    for url_template in (COVER_URL, COVER_FALLBACK):
        url = url_template.format(app_id)
        try:
            resp = requests.get(url, headers={"User-Agent": "Vual/1.0"}, timeout=10)
            if resp.status_code == 200:
                cache.write_bytes(resp.content)
                return cache
        except requests.RequestException:
            continue

    return None


def _load_pixbuf(path: Path, width: int, height: int) -> GdkPixbuf.Pixbuf | None:
    """Load and scale pixbuf from file.
    
    Handles landscape images by compositing them onto a blurred background.
    """
    try:
        original = GdkPixbuf.Pixbuf.new_from_file(str(path))
    except GLib.Error:
        return None

    ow, oh = original.get_width(), original.get_height()
    if ow < 1 or oh < 1:
        return None

    aspect = ow / oh
    
    # If image is landscape (wider than 4:3), create composite with blur
    if aspect > 1.33:
        return _create_landscape_composite(original, ow, oh, width, height)
    
    # Portrait or square: scale to fill
    return original.scale_simple(width, height, GdkPixbuf.InterpType.BILINEAR)


def _create_landscape_composite(
    original: GdkPixbuf.Pixbuf,
    ow: int, oh: int,
    width: int, height: int
) -> GdkPixbuf.Pixbuf:
    """Create a portrait tile from a landscape image.
    
    Composites the original image centered on a scaled/blurred background.
    """
    # Create background: scale original to fill tile (will be cropped/stretched)
    bg = original.scale_simple(width, height, GdkPixbuf.InterpType.BILINEAR)
    
    # Apply simple darkening to background (simulates blur effect)
    # We darken by compositing with a semi-transparent black
    dark = GdkPixbuf.Pixbuf.new(
        GdkPixbuf.Colorspace.RGB, True, 8, width, height
    )
    dark.fill(0x00000099)  # Black with ~60% opacity
    dark.composite(
        bg, 0, 0, width, height,
        0, 0, 1.0, 1.0,
        GdkPixbuf.InterpType.NEAREST, 180
    )
    
    # Scale original to fit width while preserving aspect ratio
    scale = width / ow
    scaled_w = width
    scaled_h = int(oh * scale)
    
    scaled = original.scale_simple(scaled_w, scaled_h, GdkPixbuf.InterpType.BILINEAR)
    
    # Center vertically
    y_offset = (height - scaled_h) // 2
    
    # Composite scaled image onto darkened background
    scaled.composite(
        bg,
        0, y_offset,  # dest x, y
        scaled_w, scaled_h,  # dest width, height
        0, y_offset,  # offset x, y
        1.0, 1.0,  # scale x, y
        GdkPixbuf.InterpType.BILINEAR,
        255  # full opacity
    )
    
    return bg


# ═══════════════════════════════════════════════════════════════════════════════
# GameTile — single game tile widget
# ═══════════════════════════════════════════════════════════════════════════════

class GameTile(Gtk.Overlay):
    """A single game tile with cover image and controls overlay."""

    __gtype_name__ = "VualGameTile"

    def __init__(self, app_id: str, name: str, is_active: bool, tile_width: int):
        super().__init__()

        self._app_id = app_id
        self._name = name
        self._is_active = is_active
        self._is_running = False
        self._width = tile_width
        self._height = int(tile_width * COVER_RATIO)

        # Fixed size container
        self.set_size_request(self._width, self._height)
        self.add_css_class("vual-tile")
        self.set_overflow(Gtk.Overflow.HIDDEN)

        # Cover image (fills the tile)
        self._picture = Gtk.Picture()
        self._picture.set_content_fit(Gtk.ContentFit.COVER)
        self._picture.set_size_request(self._width, self._height)
        self._picture.add_css_class("skeleton")
        self.set_child(self._picture)

        # Bottom info overlay
        self._build_info_box()

        # Top-left reload button
        self._build_reload_button()

        # Top-right running badge
        self._build_running_badge()

    def _build_info_box(self) -> None:
        """Create bottom info panel with name, buttons, and switch."""
        info = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        info.add_css_class("vual-tile-info")
        info.set_valign(Gtk.Align.END)
        info.set_halign(Gtk.Align.FILL)

        # Game name
        label = Gtk.Label(label=self._name)
        label.set_ellipsize(Pango.EllipsizeMode.END)
        label.set_max_width_chars(15)
        label.set_halign(Gtk.Align.START)
        label.add_css_class("heading")
        info.append(label)

        # Controls row: [Play] [CE] ---- [Switch]
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        row.set_halign(Gtk.Align.FILL)

        # Play button
        btn_play = Gtk.Button()
        btn_play.set_icon_name("media-playback-start-symbolic")
        btn_play.add_css_class("flat")
        btn_play.add_css_class("tile-btn")
        btn_play.set_tooltip_text(_("Launch game"))
        btn_play.connect("clicked", self._on_play_clicked)
        row.append(btn_play)

        # CE button
        btn_ce = Gtk.Button()
        btn_ce.set_icon_name("utilities-terminal-symbolic")
        btn_ce.add_css_class("flat")
        btn_ce.add_css_class("tile-btn")
        btn_ce.set_tooltip_text(_("Launch Cheat Engine"))
        btn_ce.connect("clicked", self._on_ce_clicked)
        row.append(btn_ce)

        # Spacer
        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        row.append(spacer)

        # Active switch
        self._switch = Gtk.Switch()
        self._switch.set_valign(Gtk.Align.CENTER)
        self._switch.set_active(self._is_active)
        self._switch.connect("state-set", self._on_switch_toggled)
        row.append(self._switch)

        info.append(row)
        self.add_overlay(info)

    def _build_reload_button(self) -> None:
        """Create reload button in top-left corner."""
        btn = Gtk.Button()
        btn.set_icon_name("view-refresh-symbolic")
        btn.add_css_class("flat")
        btn.add_css_class("vual-reload-btn")
        btn.set_valign(Gtk.Align.START)
        btn.set_halign(Gtk.Align.START)
        btn.set_margin_top(6)
        btn.set_margin_start(6)
        btn.set_tooltip_text(_("Refresh cover"))
        btn.connect("clicked", self._on_reload_clicked)
        self.add_overlay(btn)

    def _build_running_badge(self) -> None:
        """Create running badge in top-right corner."""
        self._badge = Gtk.Image.new_from_icon_name("media-playback-start-symbolic")
        self._badge.set_pixel_size(14)
        self._badge.add_css_class("vual-badge")
        self._badge.set_valign(Gtk.Align.START)
        self._badge.set_halign(Gtk.Align.END)
        self._badge.set_margin_top(6)
        self._badge.set_margin_end(6)
        self._badge.set_visible(False)
        self.add_overlay(self._badge)

    # ─── Properties ───────────────────────────────────────────────────────────

    @property
    def app_id(self) -> str:
        return self._app_id

    @property
    def name(self) -> str:
        return self._name

    @property
    def is_active(self) -> bool:
        return self._is_active

    @property
    def is_running(self) -> bool:
        return self._is_running

    # ─── Setters ──────────────────────────────────────────────────────────────

    def set_active_silent(self, active: bool) -> None:
        """Set switch without triggering callback."""
        self._is_active = active
        self._switch.handler_block_by_func(self._on_switch_toggled)
        self._switch.set_active(active)
        self._switch.handler_unblock_by_func(self._on_switch_toggled)

    def set_running(self, running: bool) -> None:
        """Update running badge visibility."""
        self._is_running = running
        self._badge.set_visible(running)

    def set_cover(self, pixbuf: GdkPixbuf.Pixbuf | None) -> None:
        """Set cover image from pixbuf."""
        self._picture.remove_css_class("skeleton")
        if pixbuf:
            texture = Gdk.Texture.new_for_pixbuf(pixbuf)
            self._picture.set_paintable(texture)
        else:
            self._picture.set_paintable(None)

    def resize(self, width: int) -> None:
        """Resize tile to new width."""
        self._width = width
        self._height = int(width * COVER_RATIO)
        self.set_size_request(self._width, self._height)
        self._picture.set_size_request(self._width, self._height)

    # ─── Callbacks ────────────────────────────────────────────────────────────

    def _on_play_clicked(self, _btn: Gtk.Button) -> None:
        """Emit play signal."""
        if hasattr(self, "_on_launch"):
            self._on_launch(self._app_id, self._name)

    def _on_ce_clicked(self, _btn: Gtk.Button) -> None:
        """Emit CE signal."""
        if hasattr(self, "_on_launch_ce"):
            self._on_launch_ce(self._app_id, self._name)

    def _on_switch_toggled(self, switch: Gtk.Switch, state: bool) -> bool:
        """Handle activation toggle."""
        self._is_active = state
        if hasattr(self, "_on_toggle"):
            self._on_toggle(self._app_id, state)
        return False

    def _on_reload_clicked(self, _btn: Gtk.Button) -> None:
        """Emit reload signal."""
        if hasattr(self, "_on_reload"):
            self._on_reload(self._app_id)

    # ─── Connect handlers ─────────────────────────────────────────────────────

    def connect_launch(self, callback) -> None:
        self._on_launch = callback

    def connect_launch_ce(self, callback) -> None:
        self._on_launch_ce = callback

    def connect_toggle(self, callback) -> None:
        self._on_toggle = callback

    def connect_reload(self, callback) -> None:
        self._on_reload = callback


# ═══════════════════════════════════════════════════════════════════════════════
# MainPage — the main games grid
# ═══════════════════════════════════════════════════════════════════════════════

class MainPage(Adw.Bin):
    """Main page with games grid."""

    __gtype_name__ = "VualMainPage"

    def __init__(self, config: Config, window: VualWindow):
        super().__init__()

        self._win = window
        self._cfg = config
        self._tiles: dict[str, GameTile] = {}
        self._search_text = ""
        self._loading = False
        self._auto_ce: str | None = None
        self._executor = ThreadPoolExecutor(max_workers=8)

        # Search entry (exposed for header bar)
        self._search = Gtk.SearchEntry()
        self._search.set_placeholder_text(_("Search..."))
        self._search.connect("search-changed", self._on_search_changed)

        # Build UI
        self._build_ui()

        # Load games on startup
        GLib.idle_add(self._load)

    def _build_ui(self) -> None:
        """Build the main page UI."""
        # Stack for loading/content states
        self._stack = Gtk.Stack()
        self._stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.set_child(self._stack)

        # Loading spinner
        spinner = Gtk.Spinner(spinning=True)
        spinner.set_size_request(48, 48)
        spinner.set_valign(Gtk.Align.CENTER)
        spinner.set_halign(Gtk.Align.CENTER)
        self._stack.add_named(spinner, "loading")

        # Empty state
        empty = Adw.StatusPage(
            icon_name="view-grid-symbolic",
            title=_("Games not found"),
            description=_("Check Steam path in settings"),
        )
        self._stack.add_named(empty, "empty")

        # Scrolled grid
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_vexpand(True)

        # FlowBox grid
        self._grid = Gtk.FlowBox()
        self._grid.set_homogeneous(False)
        self._grid.set_valign(Gtk.Align.START)
        self._grid.set_halign(Gtk.Align.CENTER)
        self._grid.set_row_spacing(GRID_SPACING)
        self._grid.set_column_spacing(GRID_SPACING)
        self._grid.set_selection_mode(Gtk.SelectionMode.NONE)
        self._grid.set_min_children_per_line(1)
        self._grid.set_max_children_per_line(20)
        self._grid.set_margin_start(GRID_MARGIN)
        self._grid.set_margin_end(GRID_MARGIN)
        self._grid.set_margin_top(GRID_MARGIN)
        self._grid.set_margin_bottom(GRID_MARGIN)
        self._grid.add_css_class("vual-grid")
        self._grid.set_filter_func(self._filter_func)
        self._grid.set_sort_func(self._sort_func)

        scroll.set_child(self._grid)
        self._stack.add_named(scroll, "games")

        self._stack.set_visible_child_name("loading")

    # ─── Public API ───────────────────────────────────────────────────────────

    def reload(self) -> None:
        """Reload games list."""
        self._load_games()

    # Alias for window.py compatibility
    _load = reload

    def search(self, text: str) -> None:
        """Filter games by search text."""
        self._search_text = text.lower().strip()
        self._grid.invalidate_filter()

    def _on_search_changed(self, entry: Gtk.SearchEntry) -> None:
        """Handle search entry changes."""
        self.search(entry.get_text())

    def apply_tile_size(self) -> None:
        """Apply current tile size from config."""
        width = TILE_SIZES.get(self._cfg.tile_size, 150)
        for tile in self._tiles.values():
            tile.resize(width)
            # Reload cover at new size
            self._load_cover(tile)

    def apply_sort(self) -> None:
        """Reapply sort order."""
        self._grid.invalidate_sort()

    # Alias for window.py compatibility
    _update_sort = apply_sort

    def update_running_state(self, running_ids: set[str]) -> None:
        """Update running badges based on active processes."""
        for app_id, tile in self._tiles.items():
            tile.set_running(app_id in running_ids)

    @property
    def games_count(self) -> int:
        """Number of loaded games."""
        return len(self._tiles)

    # ─── Filter & Sort ────────────────────────────────────────────────────────

    def _filter_func(self, child: Gtk.FlowBoxChild) -> bool:
        """Filter function for FlowBox."""
        if not self._search_text:
            return True
        tile = child.get_child()
        if isinstance(tile, GameTile):
            return self._search_text in tile.name.lower()
        return True

    def _sort_func(self, a: Gtk.FlowBoxChild, b: Gtk.FlowBoxChild) -> int:
        """Sort function for FlowBox."""
        tile_a = a.get_child()
        tile_b = b.get_child()
        if not isinstance(tile_a, GameTile) or not isinstance(tile_b, GameTile):
            return 0

        if self._cfg.sort_by == "status":
            # Active first, then by name
            if tile_a.is_active != tile_b.is_active:
                return -1 if tile_a.is_active else 1

        # Alphabetical
        return (tile_a.name.lower() > tile_b.name.lower()) - (tile_a.name.lower() < tile_b.name.lower())

    # ─── Loading ──────────────────────────────────────────────────────────────

    def _load_games(self) -> None:
        """Load games from Steam in background thread."""
        if self._loading:
            return
        self._loading = True
        self._stack.set_visible_child_name("loading")

        def worker():
            steamapps = self._cfg.steamapps_path
            if not steamapps.exists():
                GLib.idle_add(self._on_games_loaded, [])
                return

            # Get installed games using steam module
            included, _ = steam.get_installed_games(
                steamapps, self._cfg.excluded_app_patterns
            )

            # Check activation status for each game
            localconfig = steam.find_localconfig_vdf(self._cfg.steam_path)
            games = []
            for game in included:
                app_id = game["app_id"]
                name = game["name"]
                
                is_active = False
                if localconfig:
                    opts = steam.get_launch_options(app_id, localconfig)
                    if opts and "protonhax" in opts.lower():
                        is_active = True
                
                games.append((app_id, name, is_active))

            GLib.idle_add(self._on_games_loaded, games)

        threading.Thread(target=worker, daemon=True).start()

    def _on_games_loaded(self, games: list[tuple[str, str, bool]]) -> None:
        """Handle loaded games on main thread."""
        self._loading = False

        # Clear existing tiles
        while child := self._grid.get_first_child():
            self._grid.remove(child)
        self._tiles.clear()

        if not games:
            self._stack.set_visible_child_name("empty")
            self._win.update_counter(0)
            return

        # Get tile size
        width = TILE_SIZES.get(self._cfg.tile_size, 150)

        # Create tiles
        for app_id, name, is_active in games:
            tile = GameTile(app_id, name, is_active, width)
            tile.connect_launch(self._on_launch)
            tile.connect_launch_ce(self._on_launch_ce)
            tile.connect_toggle(self._on_toggle)
            tile.connect_reload(self._on_reload_cover)

            self._tiles[app_id] = tile
            self._grid.append(tile)

            # Load cover in background
            self._load_cover(tile)

        self._grid.invalidate_sort()
        self._stack.set_visible_child_name("games")
        self._win.update_counter(len(games))

        # Check running games
        self._check_running()

    def _load_cover(self, tile: GameTile) -> None:
        """Load cover image for tile in background."""
        app_id = tile.app_id
        width = tile._width
        height = tile._height

        def worker():
            path = _download_cover(app_id)
            if path:
                pixbuf = _load_pixbuf(path, width, height)
                GLib.idle_add(tile.set_cover, pixbuf)
            else:
                GLib.idle_add(tile.set_cover, None)

        self._executor.submit(worker)

    def _on_reload_cover(self, app_id: str) -> None:
        """Force reload cover from Steam."""
        tile = self._tiles.get(app_id)
        if not tile:
            return

        # Delete cached cover
        cache = _cache_path(app_id)
        if cache.exists():
            cache.unlink()

        # Re-add skeleton class and reload
        tile._picture.add_css_class("skeleton")
        tile._picture.set_paintable(None)
        self._load_cover(tile)

    # ─── Running detection ────────────────────────────────────────────────────

    def _check_running(self) -> None:
        """Check which games are currently running."""
        def worker():
            running_ids = set(protonhax.list_running())
            GLib.idle_add(self._on_running_checked, running_ids)

        threading.Thread(target=worker, daemon=True).start()

    def _on_running_checked(self, running_ids: set[str]) -> None:
        """Update running state on main thread."""
        self.update_running_state(running_ids)

        # Auto-launch CE if needed
        if self._auto_ce and self._auto_ce in running_ids:
            app_id = self._auto_ce
            tile = self._tiles.get(app_id)
            name = tile.name if tile else app_id
            self._auto_ce = None
            GLib.timeout_add_seconds(2, lambda: self._do_ce(app_id, name))

        # Schedule next check
        GLib.timeout_add_seconds(5, self._check_running)

    # ─── Actions ──────────────────────────────────────────────────────────────

    def _on_launch(self, app_id: str, name: str) -> None:
        """Launch game via Steam."""
        try:
            protonhax.ensure_installed()
        except OSError:
            pass

        subprocess.Popen(
            ["steam", f"steam://rungameid/{app_id}"],
            start_new_session=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self._win.show_toast(_("Launching %s...") % name)
        self._auto_ce = app_id

    def _on_launch_ce(self, app_id: str, name: str) -> None:
        """Launch CE for a game."""
        self._do_ce(app_id, name)

    def _do_ce(self, app_id: str, name: str) -> None:
        """Actually launch Cheat Engine."""
        if not self._cfg.ce_exists:
            self._win.show_toast(_("CE not found: %s") % self._cfg.ce_executable)
            return

        args = None
        if self._cfg.ce_language != "system":
            args = ["--LANG", self._cfg.ce_language]

        proc = protonhax.run_in_proton(app_id, str(self._cfg.ce_executable_path), args)
        if proc:
            self._win.show_toast(_("CE launched for %s") % name)
        else:
            self._win.show_toast(_("Failed to launch CE for %s") % name)

    def _on_toggle(self, app_id: str, active: bool) -> None:
        """Handle activation toggle."""
        tile = self._tiles.get(app_id)
        if not tile:
            return

        if active:
            self._apply_single(app_id, tile.name, "set")
        else:
            self._apply_single(app_id, tile.name, "remove")

    def _apply_single(self, app_id: str, name: str, mode: str) -> None:
        """Apply launch options for a single game."""
        if steam.is_steam_running():
            self._win.show_toast(_("Close Steam to change settings"))
            # Revert switch
            tile = self._tiles.get(app_id)
            if tile:
                tile.set_active_silent(mode != "set")
            return

        try:
            protonhax.ensure_installed()
        except OSError as e:
            self._win.show_toast(f"protonhax: {e}")
            return

        localconfig = steam.find_localconfig_vdf(self._cfg.steam_path)
        if not localconfig:
            self._win.show_toast(_("localconfig.vdf not found"))
            return

        if mode == "set":
            ok = steam.set_launch_options(app_id, self._cfg.launch_options_template, localconfig)
            verb = _("set")
        else:
            ok = steam.remove_launch_options(app_id, localconfig)
            verb = _("removed")

        if ok:
            self._win.show_toast(_("LaunchOptions %s for %s") % (verb, name))
        else:
            self._win.show_toast(_("Error changing settings for %s") % name)
            # Revert switch
            tile = self._tiles.get(app_id)
            if tile:
                tile.set_active_silent(mode != "set")

    # ─── Batch operations ─────────────────────────────────────────────────────

    def _on_enable_all(self, _btn) -> None:
        """Show dialog for enabling all games."""
        dlg = Adw.AlertDialog(
            heading=_("Enable for all games?"),
            body=self._cfg.launch_options_template,
        )
        dlg.add_response("cancel", _("Cancel"))
        dlg.add_response("ok", _("Enable"))
        dlg.set_response_appearance("ok", Adw.ResponseAppearance.SUGGESTED)
        dlg.choose(self._win, None, self._finish_enable)

    def _finish_enable(self, dlg, res) -> None:
        if dlg.choose_finish(res) != "ok":
            return
        try:
            protonhax.ensure_installed()
        except OSError as e:
            self._win.show_toast(f"protonhax: {e}")
            return
        ids = [aid for aid, t in self._tiles.items() if not t.is_active]
        if ids:
            self._apply_batch(ids, "set")

    def _on_disable_all(self, _btn) -> None:
        """Show dialog for disabling all games."""
        dlg = Adw.AlertDialog(
            heading=_("Disable for all games?"),
            body=_("LaunchOptions will be removed."),
        )
        dlg.add_response("cancel", _("Cancel"))
        dlg.add_response("ok", _("Disable"))
        dlg.set_response_appearance("ok", Adw.ResponseAppearance.DESTRUCTIVE)
        dlg.choose(self._win, None, self._finish_disable)

    def _finish_disable(self, dlg, res) -> None:
        if dlg.choose_finish(res) != "ok":
            return
        ids = [aid for aid, t in self._tiles.items() if t.is_active]
        if ids:
            self._apply_batch(ids, "remove")

    def _apply_batch(self, ids: list[str], mode: str) -> None:
        """Apply changes to multiple games."""
        if steam.is_steam_running():
            self._win.show_toast(_("Restarting Steam to apply..."))

            def wait_and_apply():
                steam.shutdown_steam()
                if not steam.wait_steam_exit(30):
                    GLib.idle_add(self._win.show_toast, _("Steam did not exit"))
                    return
                GLib.idle_add(self._write_batch, ids, mode, True)

            threading.Thread(target=wait_and_apply, daemon=True).start()
        else:
            self._write_batch(ids, mode, False)

    def _write_batch(self, ids: list[str], mode: str, restart: bool) -> None:
        """Write launch options for multiple games."""
        localconfig = steam.find_localconfig_vdf(self._cfg.steam_path)
        if not localconfig:
            self._win.show_toast(_("localconfig.vdf not found"))
            return

        ok = 0
        for app_id in ids:
            if mode == "set":
                result = steam.set_launch_options(app_id, self._cfg.launch_options_template, localconfig)
            else:
                result = steam.remove_launch_options(app_id, localconfig)

            if result:
                ok += 1
                tile = self._tiles.get(app_id)
                if tile:
                    tile.set_active_silent(mode == "set")

        if mode == "set":
            self._win.show_toast(_("LaunchOptions set for %d games") % ok)
        else:
            self._win.show_toast(_("LaunchOptions removed for %d games") % ok)

        if restart:
            steam.start_steam()

    def schedule_auto_launch(self, app_id: str) -> None:
        """Schedule auto CE launch for a game."""
        self._auto_ce = app_id
