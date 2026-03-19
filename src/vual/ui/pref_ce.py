"""Cheat Engine preferences page — status, download, extract, protonhax, locale."""

from __future__ import annotations

import os
import subprocess
import threading
from pathlib import Path
from typing import TYPE_CHECKING

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gio, GLib, Gtk  # noqa: E402

from vual import cheatengine, protonhax  # noqa: E402
from vual.i18n import _  # noqa: E402

if TYPE_CHECKING:
    from vual.ui.preferences import PreferencesWindow


def build_ce_page(win: PreferencesWindow) -> Adw.PreferencesPage:
    """Build the Cheat Engine preferences page."""
    cfg = win._config
    page = Adw.PreferencesPage(
        title="Cheat Engine",
        icon_name="applications-games-symbolic",
    )

    # ── Status group ─────────────────────────────────────────────
    status_group = Adw.PreferencesGroup(title=_("Status"))
    page.add(status_group)

    ce_status_row = Adw.ActionRow(title="Cheat Engine", subtitle=_("Checking..."))
    ce_status_row.set_activatable(False)
    status_group.add(ce_status_row)

    ph_status_row = Adw.ActionRow(title="protonhax", subtitle=_("Checking..."))
    ph_status_row.set_activatable(False)
    status_group.add(ph_status_row)

    # ── Installation group ───────────────────────────────────────
    install_group = Adw.PreferencesGroup(
        title=_("Installation"),
        description=_("Cheat Engine setup and download"),
    )
    page.add(install_group)

    ce_path_row = Adw.EntryRow(title=_("Executable"))
    ce_path_row.set_text(cfg.ce_executable)
    ce_path_row.connect("changed", lambda row: _on_ce_path_changed(win, row, state))

    browse_btn = Gtk.Button(
        icon_name="document-open-symbolic",
        valign=Gtk.Align.CENTER,
        css_classes=["flat"],
        tooltip_text=_("Choose file"),
    )
    browse_btn.connect("clicked", lambda _: _on_browse_ce(win, ce_path_row, state))
    ce_path_row.add_suffix(browse_btn)
    install_group.add(ce_path_row)

    dl_row = Adw.ActionRow(title=_("Latest version"), subtitle=_("Click Check"))
    check_btn = Gtk.Button(label=_("Check"), valign=Gtk.Align.CENTER)
    check_btn.connect("clicked", lambda _: _on_check_release(win, dl_row, check_btn, state))
    dl_row.add_suffix(check_btn)
    install_group.add(dl_row)

    progress_row = Adw.ActionRow(title=_("Download"), subtitle="", visible=False)
    progress = Gtk.ProgressBar(valign=Gtk.Align.CENTER, show_text=True)
    progress.set_size_request(150, -1)
    progress_row.add_suffix(progress)
    install_group.add(progress_row)

    # ── protonhax group ──────────────────────────────────────────
    ph_group = Adw.PreferencesGroup(
        title="protonhax",
        description=_("Required for attaching to Proton games"),
    )
    page.add(ph_group)

    ph_row = Adw.ActionRow(
        title=_("Install or update"),
        subtitle=_("Downloads latest version from GitHub"),
    )
    ph_btn = Gtk.Button(label=_("Install"), valign=Gtk.Align.CENTER)
    ph_btn.connect("clicked", lambda _: _on_install_protonhax(win, state))
    ph_row.add_suffix(ph_btn)
    ph_group.add(ph_row)

    # ── Language group ───────────────────────────────────────────
    lang_group = Adw.PreferencesGroup(
        title=_("Language"),
        description=_("Cheat Engine interface language"),
    )
    page.add(lang_group)

    lang_row = Adw.ComboRow(title=_("Interface"), subtitle=_("Requires CE restart"))
    lang_model = Gtk.StringList.new([_("System"), _("Russian")])
    lang_row.set_model(lang_model)
    lang_idx = {"system": 0, "ru_RU": 1}.get(cfg.ce_language, 0)
    lang_row.set_selected(lang_idx)
    lang_row.connect("notify::selected", lambda row, _: _on_lang_changed(win, row))
    lang_group.add(lang_row)

    loc_row = Adw.ActionRow(title=_("Russian localization"), subtitle=_("Checking..."))
    loc_btn = Gtk.Button(label=_("Install"), valign=Gtk.Align.CENTER)
    loc_btn.connect("clicked", lambda _: _on_install_localization(win, loc_row, loc_btn))
    loc_row.add_suffix(loc_btn)
    lang_group.add(loc_row)

    # ── Debug group ──────────────────────────────────────────────
    debug_group = Adw.PreferencesGroup(title=_("Debug"))
    page.add(debug_group)

    test_row = Adw.ActionRow(
        title=_("Test launch"),
        subtitle=_("Launch CE via Wine (without game binding)"),
    )
    test_btn = Gtk.Button(
        label=_("Launch"),
        valign=Gtk.Align.CENTER,
        css_classes=["suggested-action"],
    )
    test_btn.connect("clicked", lambda _: _on_test_launch(win))
    test_row.add_suffix(test_btn)
    debug_group.add(test_row)

    # Shared mutable state for cross-function access
    state = _PageState(
        ce_status_row=ce_status_row,
        ph_status_row=ph_status_row,
        ce_path_row=ce_path_row,
        dl_row=dl_row,
        check_btn=check_btn,
        progress_row=progress_row,
        progress=progress,
        ph_btn=ph_btn,
        loc_row=loc_row,
        loc_btn=loc_btn,
        test_btn=test_btn,
    )

    # Initial status refresh
    _refresh_status(win, state)

    return page


class _PageState:
    """Holds widget references for the CE page."""

    def __init__(self, **kwargs):
        self.release_info: dict | None = None
        self.download_btn: Gtk.Button | None = None
        for k, v in kwargs.items():
            setattr(self, k, v)


# ── Status ───────────────────────────────────────────────────────

def _refresh_status(win: PreferencesWindow, state: _PageState) -> None:
    cfg = win._config

    # CE status
    if cfg.ce_exists:
        version = cheatengine.detect_version(cfg.ce_executable_path)
        ver_str = f" ({version})" if version else ""
        state.ce_status_row.set_subtitle(_("✓ Installed") + ver_str)
        state.test_btn.set_sensitive(True)
    else:
        state.ce_status_row.set_subtitle(_("✗ Not found"))
        state.test_btn.set_sensitive(False)

    # protonhax status
    ph_path = protonhax.find_installed()
    if ph_path:
        if protonhax.is_managed():
            if protonhax.needs_update():
                state.ph_status_row.set_subtitle(_("⟳ Update available"))
                state.ph_btn.set_label(_("Refresh"))
            else:
                state.ph_status_row.set_subtitle(_("✓ Installed"))
                state.ph_btn.set_label(_("Reinstall"))
        else:
            state.ph_status_row.set_subtitle(_("✓ External: %s") % ph_path)
    else:
        state.ph_status_row.set_subtitle(_("✗ Not installed"))
        state.ph_btn.set_label(_("Install"))

    # Localization status
    if cfg.ce_exists:
        if cheatengine.is_localization_installed(cfg.ce_executable_path):
            state.loc_row.set_subtitle(_("✓ Installed"))
            state.loc_btn.set_label(_("Reinstall"))
        else:
            state.loc_row.set_subtitle(_("Not installed"))
            state.loc_btn.set_label(_("Install"))
        state.loc_btn.set_sensitive(True)
    else:
        state.loc_row.set_subtitle(_("Cheat Engine required"))
        state.loc_btn.set_sensitive(False)


# ── Callbacks ────────────────────────────────────────────────────

def _on_ce_path_changed(win: PreferencesWindow, row: Adw.EntryRow, state: _PageState) -> None:
    win._config.ce_executable = row.get_text().strip()
    win._save()
    _refresh_status(win, state)


def _on_browse_ce(win: PreferencesWindow, ce_path_row: Adw.EntryRow, state: _PageState) -> None:
    dialog = Gtk.FileDialog(title=_("Select CE executable"))

    filters = Gio.ListStore.new(Gtk.FileFilter)
    exe_filter = Gtk.FileFilter()
    exe_filter.set_name(_("Executable files (*.exe)"))
    exe_filter.add_pattern("*.exe")
    filters.append(exe_filter)

    all_filter = Gtk.FileFilter()
    all_filter.set_name(_("All files"))
    all_filter.add_pattern("*")
    filters.append(all_filter)

    dialog.set_filters(filters)

    def on_result(dlg: Gtk.FileDialog, result: Gio.AsyncResult) -> None:
        try:
            gfile = dlg.open_finish(result)
            if gfile:
                path = gfile.get_path()
                home = str(Path.home())
                display = path.replace(home, "~", 1) if path.startswith(home) else path
                ce_path_row.set_text(display)
        except GLib.Error:
            pass

    dialog.open(win, None, on_result)


def _on_lang_changed(win: PreferencesWindow, row: Adw.ComboRow) -> None:
    langs = ["system", "ru_RU"]
    win._config.ce_language = langs[row.get_selected()]
    win._save()


def _on_install_protonhax(win: PreferencesWindow, state: _PageState) -> None:
    try:
        protonhax.ensure_installed()
        _refresh_status(win, state)
        win._show_toast(_("protonhax installed"))
    except OSError as e:
        win._show_toast(_("Error: %s") % e)


def _on_install_localization(
    win: PreferencesWindow, loc_row: Adw.ActionRow, loc_btn: Gtk.Button,
) -> None:
    cfg = win._config
    if not cfg.ce_exists:
        win._show_toast(_("Cheat Engine not found"))
        return

    loc_btn.set_sensitive(False)
    loc_row.set_subtitle(_("Downloading..."))

    def worker() -> None:
        ok = cheatengine.install_localization(cfg.ce_executable_path)
        GLib.idle_add(_on_localization_done, win, ok, loc_btn, loc_row)

    threading.Thread(target=worker, daemon=True).start()


def _on_localization_done(
    win: PreferencesWindow, success: bool, btn: Gtk.Button, loc_row: Adw.ActionRow,
) -> None:
    btn.set_sensitive(True)
    if success:
        loc_row.set_subtitle(_("✓ Installed"))
        btn.set_label(_("Reinstall"))
        win._show_toast(_("Localization installed"))
    else:
        loc_row.set_subtitle(_("Not installed"))
        win._show_toast(_("Failed to install localization"))


def _on_test_launch(win: PreferencesWindow) -> None:
    cfg = win._config
    if not cfg.ce_exists:
        win._show_toast(_("Cheat Engine not found"))
        return

    wine = cheatengine.find_proton_wine(cfg.steam_path)
    if not wine:
        win._show_toast(_("Wine not found — install Proton"))
        return

    env = os.environ.copy()
    prefix = Path.home() / ".local" / "share" / "vual" / "wine_prefix"
    prefix.mkdir(parents=True, exist_ok=True)
    env["WINEPREFIX"] = str(prefix)

    cmd = [str(wine), str(cfg.ce_executable_path)]
    if cfg.ce_language != "system":
        cmd.extend(["--LANG", cfg.ce_language])

    try:
        subprocess.Popen(
            cmd,
            env=env,
            start_new_session=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        win._show_toast(_("Cheat Engine launched"))
    except OSError as e:
        win._show_toast(_("Error: %s") % e)


# ── Download & Extract ───────────────────────────────────────────

def _on_check_release(
    win: PreferencesWindow, dl_row: Adw.ActionRow,
    check_btn: Gtk.Button, state: _PageState,
) -> None:
    dl_row.set_subtitle(_("Checking..."))
    check_btn.set_sensitive(False)

    def worker() -> None:
        info = cheatengine.get_latest_release()
        GLib.idle_add(_on_release_checked, win, info, dl_row, check_btn, state)

    threading.Thread(target=worker, daemon=True).start()


def _on_release_checked(
    win: PreferencesWindow, info: dict | None,
    dl_row: Adw.ActionRow, check_btn: Gtk.Button, state: _PageState,
) -> None:
    check_btn.set_sensitive(True)

    if not info or not info.get("url"):
        dl_row.set_subtitle(_("Failed to get info"))
        return

    state.release_info = info
    version = info.get("version", "?")
    size_mb = info.get("size", 0) / 1_048_576

    subtitle = f"v{version}"
    if size_mb > 0:
        subtitle += f" ({size_mb:.1f} " + _("MB") + ")"

    # Check if installed version matches latest
    cfg = win._config
    installed = cheatengine.detect_version(cfg.ce_executable_path) if cfg.ce_exists else None
    already_installed = installed is not None and installed == version

    if already_installed:
        subtitle += " — " + _("already installed")

    dl_row.set_subtitle(subtitle)

    # Replace check button with download button
    dl_row.remove(check_btn)
    dl_btn = Gtk.Button(
        label=_("Download"),
        valign=Gtk.Align.CENTER,
        css_classes=["suggested-action"],
        sensitive=not already_installed,
    )
    dl_btn.connect("clicked", lambda _: _on_download_ce(win, state))
    dl_row.add_suffix(dl_btn)
    state.download_btn = dl_btn


def _on_download_ce(win: PreferencesWindow, state: _PageState) -> None:
    if not state.release_info:
        return

    url = state.release_info["url"]
    name = state.release_info.get("name", "CheatEngine.exe")

    cache_dir = Path.home() / ".cache" / "vual"
    cache_dir.mkdir(parents=True, exist_ok=True)
    installer = cache_dir / name

    dest_dir = Path.home() / ".local" / "share" / "vual" / "cheatengine"

    state.progress_row.set_visible(True)
    state.progress_row.set_subtitle(_("Downloading: %s") % name)
    state.progress.set_fraction(0)
    if state.download_btn:
        state.download_btn.set_sensitive(False)

    def update_progress(frac: float) -> None:
        GLib.idle_add(state.progress.set_fraction, frac)

    def worker() -> None:
        ok = cheatengine.download_file(url, installer, progress_cb=update_progress)
        if not ok:
            GLib.idle_add(_download_failed, state)
            return
        GLib.idle_add(_start_extraction, win, installer, dest_dir, state)

    threading.Thread(target=worker, daemon=True).start()


def _download_failed(state: _PageState) -> None:
    state.progress_row.set_visible(False)
    if state.download_btn:
        state.download_btn.set_sensitive(True)


def _start_extraction(
    win: PreferencesWindow, installer: Path, dest_dir: Path, state: _PageState,
) -> None:
    state.progress_row.set_subtitle(_("Extracting..."))
    state.progress.set_fraction(0.5)

    def worker() -> None:
        extracted = cheatengine.extract_installer(
            installer, dest_dir, win._config.steam_path,
        )
        exe = cheatengine.find_executable(dest_dir) if extracted else None
        GLib.idle_add(_extraction_done, win, exe, extracted, installer, state)

    threading.Thread(target=worker, daemon=True).start()


def _extraction_done(
    win: PreferencesWindow,
    exe_path: Path | None,
    extracted: bool,
    installer: Path,
    state: _PageState,
) -> None:
    state.progress_row.set_visible(False)
    if state.download_btn:
        state.download_btn.set_sensitive(True)

    if exe_path:
        home = str(Path.home())
        display = str(exe_path).replace(home, "~", 1)
        win._config.ce_executable = display
        state.ce_path_row.set_text(display)
        win._save()
        _refresh_status(win, state)
        installer.unlink(missing_ok=True)
        win._show_toast(_("Cheat Engine installed"))
    elif extracted:
        _refresh_status(win, state)
        win._show_toast(_("Extracted — specify path manually"))
    else:
        win._show_toast(_("Extraction failed"))
