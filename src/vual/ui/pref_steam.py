"""Steam preferences page — paths, launch options, exclusions."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gio, GLib, Gtk  # noqa: E402

from vual.i18n import _  # noqa: E402

if TYPE_CHECKING:
    from vual.ui.preferences import PreferencesWindow


def build_steam_page(win: PreferencesWindow) -> Adw.PreferencesPage:
    """Build the Steam preferences page."""
    cfg = win._config
    page = Adw.PreferencesPage(
        title="Steam",
        icon_name="folder-games-symbolic",
    )

    # ── Paths group ──────────────────────────────────────────────
    paths_group = Adw.PreferencesGroup(title=_("Paths"))
    page.add(paths_group)

    steam_row = Adw.EntryRow(title=_("Steam directory"))
    steam_row.set_text(cfg.steam_path)
    steam_row.connect("changed", lambda row: _on_steam_path_changed(win, row))

    steam_browse = Gtk.Button(
        icon_name="folder-open-symbolic",
        valign=Gtk.Align.CENTER,
        css_classes=["flat"],
        tooltip_text=_("Choose folder"),
    )
    steam_browse.connect("clicked", lambda _: _on_browse_steam(win, steam_row))
    steam_row.add_suffix(steam_browse)
    paths_group.add(steam_row)

    # ── Launch options group ─────────────────────────────────────
    launch_group = Adw.PreferencesGroup(
        title=_("Launch options"),
        description=_("LaunchOptions template for protonhax"),
    )
    page.add(launch_group)

    template_row = Adw.EntryRow(title=_("Template"))
    template_row.set_text(cfg.launch_options_template)
    template_row.connect("changed", lambda row: _on_template_changed(win, row))
    launch_group.add(template_row)

    hint_row = Adw.ActionRow(
        title="%COMMAND%",
        subtitle=_("Original launch command is substituted"),
    )
    hint_row.set_activatable(False)
    hint_row.add_css_class("dim-label")
    launch_group.add(hint_row)

    # ── Exclusions group ─────────────────────────────────────────
    excl_group = Adw.PreferencesGroup(
        title=_("Exclusions"),
        description=_("Regex patterns to hide apps"),
    )
    page.add(excl_group)

    exclusion_rows: list[Adw.EntryRow] = []
    win._exclusion_rows = exclusion_rows

    for pattern in cfg.excluded_app_patterns:
        _add_exclusion_row(win, excl_group, exclusion_rows, pattern)

    add_row = Adw.ActionRow(title=_("Add pattern"))
    add_btn = Gtk.Button(
        icon_name="list-add-symbolic",
        valign=Gtk.Align.CENTER,
        css_classes=["flat"],
    )
    add_btn.connect("clicked", lambda _: _on_add_exclusion(win, excl_group, exclusion_rows))
    add_row.add_suffix(add_btn)
    add_row.set_activatable_widget(add_btn)
    excl_group.add(add_row)

    return page


# ── Callbacks ────────────────────────────────────────────────────

def _on_steam_path_changed(win: PreferencesWindow, row: Adw.EntryRow) -> None:
    win._config.steam_path = row.get_text().strip()
    win._save()


def _on_template_changed(win: PreferencesWindow, row: Adw.EntryRow) -> None:
    win._config.launch_options_template = row.get_text().strip()
    win._save()


def _on_browse_steam(win: PreferencesWindow, steam_row: Adw.EntryRow) -> None:
    dialog = Gtk.FileDialog(title=_("Select Steam directory"))

    def on_result(dlg: Gtk.FileDialog, result: Gio.AsyncResult) -> None:
        try:
            folder = dlg.select_folder_finish(result)
            if folder:
                path = folder.get_path()
                home = str(Path.home())
                display = path.replace(home, "~", 1) if path.startswith(home) else path
                steam_row.set_text(display)
        except GLib.Error:
            pass

    dialog.select_folder(win, None, on_result)


def _add_exclusion_row(
    win: PreferencesWindow,
    group: Adw.PreferencesGroup,
    rows: list[Adw.EntryRow],
    text: str = "",
) -> Adw.EntryRow:
    row = Adw.EntryRow(title="Regex")
    row.set_text(text)
    row.connect("changed", lambda _: _sync_exclusions(win, rows))

    remove_btn = Gtk.Button(
        icon_name="user-trash-symbolic",
        valign=Gtk.Align.CENTER,
        css_classes=["flat", "error"],
        tooltip_text=_("Remove"),
    )
    remove_btn.connect("clicked", lambda _: _on_remove_exclusion(win, group, rows, row))
    row.add_suffix(remove_btn)

    rows.append(row)
    group.add(row)
    return row


def _on_add_exclusion(
    win: PreferencesWindow,
    group: Adw.PreferencesGroup,
    rows: list[Adw.EntryRow],
) -> None:
    row = _add_exclusion_row(win, group, rows)
    row.grab_focus()


def _on_remove_exclusion(
    win: PreferencesWindow,
    group: Adw.PreferencesGroup,
    rows: list[Adw.EntryRow],
    row: Adw.EntryRow,
) -> None:
    if row in rows:
        rows.remove(row)
    group.remove(row)
    _sync_exclusions(win, rows)


def _sync_exclusions(win: PreferencesWindow, rows: list[Adw.EntryRow]) -> None:
    win._config.excluded_app_patterns = [
        row.get_text().strip()
        for row in rows
        if row.get_text().strip()
    ]
    win._save()
