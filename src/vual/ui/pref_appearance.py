"""Appearance preferences page — theme, language, grid, Wine theme."""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, GLib, Gtk  # noqa: E402

from vual import wine_theme  # noqa: E402
from vual.i18n import _  # noqa: E402

if TYPE_CHECKING:
    from vual.ui.preferences import PreferencesWindow


def build_appearance_page(win: PreferencesWindow) -> Adw.PreferencesPage:
    """Build the Appearance preferences page."""
    cfg = win._config
    page = Adw.PreferencesPage(
        title=_("Appearance"),
        icon_name="preferences-desktop-appearance-symbolic",
    )

    # ── Theme group ──────────────────────────────────────────────
    theme_group = Adw.PreferencesGroup(title=_("Theme"))
    page.add(theme_group)

    theme_row = Adw.ComboRow(
        title=_("Color scheme"),
        subtitle=_("Light, dark, or system"),
    )
    model = Gtk.StringList.new([_("System"), _("Light"), _("Dark")])
    theme_row.set_model(model)
    idx = {"system": 0, "light": 1, "dark": 2}.get(cfg.color_scheme, 0)
    theme_row.set_selected(idx)
    theme_row.connect("notify::selected", lambda row, _: _on_theme_changed(win, row))
    theme_group.add(theme_row)

    # Language selection
    lang_row = Adw.ComboRow(
        title=_("Language"),
        subtitle=_("Application interface language"),
    )
    lang_model = Gtk.StringList.new([_("System"), _("English"), _("Русский")])
    lang_row.set_model(lang_model)
    lang_idx = {"system": 0, "en": 1, "ru": 2}.get(cfg.app_language, 0)
    lang_row.set_selected(lang_idx)
    lang_row.connect("notify::selected", lambda row, _: _on_app_lang_changed(win, row))
    theme_group.add(lang_row)

    # Transparent window toggle
    transparent_row = Adw.SwitchRow(
        title=_("Transparent window"),
        subtitle=_("Semi-transparent background"),
    )
    transparent_row.set_active(cfg.transparent_window)
    transparent_row.connect("notify::active", lambda row, _: _on_transparent_changed(win, row))
    theme_group.add(transparent_row)

    # ── Grid group ───────────────────────────────────────────────
    grid_group = Adw.PreferencesGroup(
        title=_("Grid"),
        description=_("Game display settings"),
    )
    page.add(grid_group)

    tile_row = Adw.ComboRow(
        title=_("Tile size"),
        subtitle=_("Cover size in library"),
    )
    tile_model = Gtk.StringList.new([_("Small (120px)"), _("Medium (150px)"), _("Large (180px)")])
    tile_row.set_model(tile_model)
    tile_idx = {"small": 0, "medium": 1, "large": 2}.get(cfg.tile_size, 1)
    tile_row.set_selected(tile_idx)
    tile_row.connect("notify::selected", lambda row, _: _on_tile_size_changed(win, row))
    grid_group.add(tile_row)

    sort_row = Adw.ComboRow(
        title=_("Sort"),
        subtitle=_("Default game order"),
    )
    sort_model = Gtk.StringList.new([_("By name"), _("By status")])
    sort_row.set_model(sort_model)
    sort_idx = {"name": 0, "status": 1}.get(cfg.sort_by, 0)
    sort_row.set_selected(sort_idx)
    sort_row.connect("notify::selected", lambda row, _: _on_sort_changed(win, row))
    grid_group.add(sort_row)

    # ── Wine theme group ─────────────────────────────────────────
    wine_group = Adw.PreferencesGroup(
        title=_("Wine Theme"),
        description=_("Color scheme for Cheat Engine and other Wine apps"),
    )
    page.add(wine_group)

    wine_theme_row = Adw.ComboRow(
        title=_("Color scheme"),
        subtitle=_("Applied to all Proton prefixes"),
    )
    wine_model = Gtk.StringList.new([_("System"), _("Dark"), _("Light")])
    wine_theme_row.set_model(wine_model)
    wine_idx = {"system": 0, "dark": 1, "light": 2}.get(cfg.wine_theme, 0)
    wine_theme_row.set_selected(wine_idx)

    wine_refresh_btn = Gtk.Button(
        icon_name="view-refresh-symbolic",
        valign=Gtk.Align.CENTER,
        css_classes=["flat"],
        tooltip_text=_("Reapply theme"),
    )

    wine_theme_row.connect(
        "notify::selected",
        lambda row, _: _on_wine_theme_changed(win, row, wine_refresh_btn),
    )
    wine_refresh_btn.connect(
        "clicked",
        lambda _: _on_wine_theme_refresh(win, wine_theme_row, wine_refresh_btn),
    )
    wine_theme_row.add_suffix(wine_refresh_btn)
    wine_group.add(wine_theme_row)

    return page


# ── Callbacks ────────────────────────────────────────────────────

def _on_theme_changed(win: PreferencesWindow, row: Adw.ComboRow) -> None:
    schemes = ["system", "light", "dark"]
    win._config.color_scheme = schemes[row.get_selected()]
    win._save()
    style = Adw.StyleManager.get_default()
    scheme_map = {
        "light": Adw.ColorScheme.FORCE_LIGHT,
        "dark": Adw.ColorScheme.FORCE_DARK,
        "system": Adw.ColorScheme.DEFAULT,
    }
    style.set_color_scheme(scheme_map.get(win._config.color_scheme, Adw.ColorScheme.DEFAULT))


def _on_tile_size_changed(win: PreferencesWindow, row: Adw.ComboRow) -> None:
    sizes = ["small", "medium", "large"]
    win._config.tile_size = sizes[row.get_selected()]
    win._save()


def _on_sort_changed(win: PreferencesWindow, row: Adw.ComboRow) -> None:
    sorts = ["name", "status"]
    win._config.sort_by = sorts[row.get_selected()]
    win._save()


def _on_app_lang_changed(win: PreferencesWindow, row: Adw.ComboRow) -> None:
    langs = ["system", "en", "ru"]
    win._config.app_language = langs[row.get_selected()]
    win._save()
    win._show_toast(_("Restart app to apply language"))


def _on_transparent_changed(win: PreferencesWindow, row: Adw.SwitchRow) -> None:
    win._config.transparent_window = row.get_active()
    win._save()
    if win._parent:
        win._parent.apply_transparency()


def _get_system_theme() -> str:
    style = Adw.StyleManager.get_default()
    return "dark" if style.get_dark() else "light"


def _on_wine_theme_changed(
    win: PreferencesWindow, row: Adw.ComboRow, refresh_btn: Gtk.Button,
) -> None:
    themes = ["system", "dark", "light"]
    theme = themes[row.get_selected()]
    win._config.wine_theme = theme
    win._save()

    actual_theme = _get_system_theme() if theme == "system" else theme

    row.set_sensitive(False)
    refresh_btn.set_sensitive(False)

    def worker() -> None:
        steamapps = win._config.steamapps_path
        success, failed = wine_theme.apply_theme_to_all(steamapps, actual_theme)
        GLib.idle_add(_on_wine_applied, win, row, refresh_btn, success, failed)

    threading.Thread(target=worker, daemon=True).start()


def _on_wine_theme_refresh(
    win: PreferencesWindow, row: Adw.ComboRow, refresh_btn: Gtk.Button,
) -> None:
    theme = win._config.wine_theme
    actual_theme = _get_system_theme() if theme == "system" else theme

    row.set_sensitive(False)
    refresh_btn.set_sensitive(False)

    def worker() -> None:
        steamapps = win._config.steamapps_path
        success, failed = wine_theme.apply_theme_to_all(steamapps, actual_theme)
        GLib.idle_add(_on_wine_applied, win, row, refresh_btn, success, failed)

    threading.Thread(target=worker, daemon=True).start()


def _on_wine_applied(
    win: PreferencesWindow, row: Adw.ComboRow, refresh_btn: Gtk.Button,
    success: int, failed: int,
) -> None:
    row.set_sensitive(True)
    refresh_btn.set_sensitive(True)
    if success > 0:
        win._show_toast(_("Theme applied to %d prefixes") % success)
    elif failed > 0:
        win._show_toast(_("Error applying to %d prefixes") % failed)
