"""GameTile — single game tile widget."""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Gdk", "4.0")
gi.require_version("GdkPixbuf", "2.0")
gi.require_version("Pango", "1.0")

from gi.repository import Gdk, GdkPixbuf, Gio, Gtk, Pango  # noqa: E402

from vual import tables  # noqa: E402
from vual.i18n import _  # noqa: E402

COVER_RATIO = 1.5  # Height = Width * 1.5 (portrait)


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

        # CE button with table menu
        self._btn_ce = Gtk.MenuButton()
        self._btn_ce.set_icon_name("open-menu-symbolic")
        self._btn_ce.add_css_class("flat")
        self._btn_ce.add_css_class("tile-btn")
        self._update_ce_tooltip()

        ce_menu = Gio.Menu()
        ce_menu.append(_("Launch Cheat Engine"), "tile.launch-ce")
        ce_menu.append(_("Assign table\u2026"), "tile.assign-table")
        ce_menu.append(_("Remove table"), "tile.remove-table")

        pop = Gtk.PopoverMenu.new_from_model(ce_menu)
        self._btn_ce.set_popover(pop)

        # Actions
        group = Gio.SimpleActionGroup()

        act_launch = Gio.SimpleAction.new("launch-ce", None)
        act_launch.connect("activate", lambda *_: self._on_ce_clicked(None))
        group.add_action(act_launch)

        act_assign = Gio.SimpleAction.new("assign-table", None)
        act_assign.connect("activate", lambda *_: self._on_assign_table())
        group.add_action(act_assign)

        self._act_remove = Gio.SimpleAction.new("remove-table", None)
        self._act_remove.connect("activate", lambda *_: self._on_remove_table())
        self._act_remove.set_enabled(tables.get_table(self._app_id) is not None)
        group.add_action(self._act_remove)

        self.insert_action_group("tile", group)
        row.append(self._btn_ce)

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
        self._badge = Gtk.Box()
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
        if hasattr(self, "_on_launch"):
            self._on_launch(self._app_id, self._name)

    def _on_ce_clicked(self, _btn: Gtk.Button | None) -> None:
        if hasattr(self, "_on_launch_ce"):
            self._on_launch_ce(self._app_id, self._name)

    def _on_assign_table(self) -> None:
        if hasattr(self, "_on_pick_table"):
            self._on_pick_table(self._app_id)

    def _on_remove_table(self) -> None:
        tables.unbind(self._app_id)
        self._act_remove.set_enabled(False)
        self._update_ce_tooltip()

    def _update_ce_tooltip(self) -> None:
        name = tables.get_table_name(self._app_id)
        if name:
            self._btn_ce.set_tooltip_text(f"CE: {name}")
        else:
            self._btn_ce.set_tooltip_text(_("Launch Cheat Engine"))

    def mark_table_bound(self) -> None:
        """Refresh table indicator after binding."""
        self._act_remove.set_enabled(tables.get_table(self._app_id) is not None)
        self._update_ce_tooltip()

    def _on_switch_toggled(self, _switch: Gtk.Switch, state: bool) -> bool:
        self._is_active = state
        if hasattr(self, "_on_toggle"):
            self._on_toggle(self._app_id, state)
        return False

    def _on_reload_clicked(self, _btn: Gtk.Button) -> None:
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

    def connect_pick_table(self, callback) -> None:
        self._on_pick_table = callback
