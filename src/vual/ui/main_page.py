"""Main games grid page."""

from __future__ import annotations

import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gio, GLib, Gtk  # noqa: E402

from vual import protonhax, steam, tables  # noqa: E402
from vual.config import TILE_SIZES, Config  # noqa: E402
from vual.i18n import _  # noqa: E402
from vual.ui.covers import cache_path, download_cover, load_pixbuf  # noqa: E402
from vual.ui.game_tile import COVER_RATIO, GameTile  # noqa: E402

if TYPE_CHECKING:
    from vual.window import VualWindow


# ═══════════════════════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════════════════════

GRID_SPACING = 12
GRID_MARGIN = 16


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
            tile.connect_pick_table(self._on_pick_table)

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
            path = download_cover(app_id)
            if path:
                pixbuf = load_pixbuf(path, width, height)
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
        cache = cache_path(app_id)
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

        args: list[str] = []
        if self._cfg.ce_language != "system":
            args.extend(["--LANG", self._cfg.ce_language])

        ct = tables.get_table(app_id)
        if ct:
            args.append(str(ct))

        proc = protonhax.run_in_proton(app_id, str(self._cfg.ce_executable_path), args or None)
        if proc:
            self._win.show_toast(_("CE launched for %s") % name)
        else:
            self._win.show_toast(_("Failed to launch CE for %s") % name)

    def _on_pick_table(self, app_id: str) -> None:
        """Open file chooser to select a .CT table for *app_id*."""
        dialog = Gtk.FileDialog()
        dialog.set_title(_("Select Cheat Engine table"))

        f = Gtk.FileFilter()
        f.set_name(_("CE tables (*.CT)"))
        f.add_pattern("*.CT")
        f.add_pattern("*.ct")
        filters = Gio.ListStore.new(Gtk.FileFilter)
        filters.append(f)
        dialog.set_filters(filters)

        dialog.open(self._win, None, self._on_table_chosen, app_id)

    def _on_table_chosen(self, dialog: Gtk.FileDialog, result: Gio.AsyncResult, app_id: str) -> None:
        try:
            gfile = dialog.open_finish(result)
        except GLib.Error:
            return
        if not gfile:
            return
        path = gfile.get_path()
        if not path:
            return
        tables.bind(app_id, path)
        tile = self._tiles.get(app_id)
        if tile:
            tile.mark_table_bound()

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

