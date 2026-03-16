"""Main application window — single-page tile grid."""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gio, GLib, Gtk  # noqa: E402

from vual import APP_NAME  # noqa: E402
from vual.config import Config  # noqa: E402
from vual.i18n import _  # noqa: E402


class VualWindow(Adw.ApplicationWindow):
    def __init__(self, config: Config, **kwargs) -> None:
        super().__init__(
            default_width=config.window_width,
            default_height=config.window_height,
            title=APP_NAME,
            **kwargs,
        )
        self.config = config
        self._build_ui()

    # ── UI construction ──────────────────────────────────────────

    def _build_ui(self) -> None:
        self.toast_overlay = Adw.ToastOverlay()
        self.set_content(self.toast_overlay)

        toolbar_view = Adw.ToolbarView()
        self.toast_overlay.set_child(toolbar_view)

        # Single main page
        from vual.ui.main_page import MainPage

        self.main_page = MainPage(config=self.config, window=self)

        # Header bar
        header = Adw.HeaderBar()
        header.add_css_class("flat")

        # Title widget: search + counter
        title_box = Gtk.Box(spacing=8)
        title_box.append(self.main_page._search)
        self._counter = Gtk.Label(css_classes=["games-counter"])
        title_box.append(self._counter)
        header.set_title_widget(title_box)

        b_refresh = Gtk.Button(
            icon_name="view-refresh-symbolic",
            css_classes=["flat", "header-btn"],
            tooltip_text=_("Refresh"),
        )
        b_refresh.connect("clicked", lambda _: self.main_page._load())
        header.pack_start(b_refresh)

        b_on = Gtk.Button(
            icon_name="object-select-symbolic",
            css_classes=["flat", "header-btn"],
            tooltip_text=_("Enable All"),
        )
        b_on.connect("clicked", self.main_page._on_enable_all)
        header.pack_start(b_on)

        b_off = Gtk.Button(
            icon_name="edit-clear-all-symbolic",
            css_classes=["flat", "header-btn"],
            tooltip_text=_("Disable All"),
        )
        b_off.connect("clicked", self.main_page._on_disable_all)
        header.pack_start(b_off)

        # Sort menu
        sort_menu = Gio.Menu()
        sort_menu.append(_("By name"), "win.sort::name")
        sort_menu.append(_("By status"), "win.sort::status")

        sort_btn = Gtk.MenuButton(
            icon_name="view-sort-descending-symbolic",
            css_classes=["flat", "header-btn"],
            menu_model=sort_menu,
            tooltip_text=_("Sort"),
        )
        header.pack_end(sort_btn)

        # Sort action
        sort_action = Gio.SimpleAction.new("sort", GLib.VariantType.new("s"))
        sort_action.connect("activate", self._on_sort_changed)
        self.add_action(sort_action)

        menu_button = Gtk.MenuButton(
            icon_name="open-menu-symbolic",
            css_classes=["flat", "header-btn"],
            menu_model=self._build_menu(),
        )
        header.pack_end(menu_button)
        toolbar_view.add_top_bar(header)

        toolbar_view.set_content(self.main_page)

    def _on_sort_changed(self, action: Gio.SimpleAction, param: GLib.Variant) -> None:
        sort_by = param.get_string()
        self.config.sort_by = sort_by
        self.main_page._update_sort()

    def update_counter(self, count: int) -> None:
        """Update the games counter label."""
        self._counter.set_label(_("%d games") % count)

    # ── App menu ─────────────────────────────────────────────────

    def _build_menu(self) -> Gio.Menu:
        menu = Gio.Menu()
        menu.append(_("Preferences"), "app.preferences")
        menu.append(_("About"), "app.about")
        menu.append(_("Quit"), "app.quit")
        return menu

    # ── Toast helper ─────────────────────────────────────────────

    def show_toast(self, message: str, timeout: int = 3) -> None:
        toast = Adw.Toast(title=message, timeout=timeout)
        self.toast_overlay.add_toast(toast)
        return False
