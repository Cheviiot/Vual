"""Preferences window — clean libadwaita implementation.

Uses Adw.PreferencesWindow with auto-save on changes.
"""

from __future__ import annotations

import threading
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gio, GLib, Gtk

from vual import cheatengine, protonhax, wine_theme
from vual.config import Config
from vual.i18n import _


class PreferencesWindow(Adw.PreferencesWindow):
    """Preferences window with auto-save."""

    def __init__(self, config: Config, **kwargs) -> None:
        super().__init__(
            title=_("Preferences"),
            **kwargs,
        )
        self._config = config
        self._parent = kwargs.get("transient_for")
        self._exclusion_rows: list[Adw.EntryRow] = []
        self._release_info: dict | None = None
        self._building = True  # Prevent saves during initial build

        self._build_pages()
        self._refresh_status()
        self._building = False

    def _save(self) -> None:
        """Save config if not building UI."""
        if self._building:
            return
        self._config.save()

    # ════════════════════════════════════════════════════════════════
    # Pages
    # ════════════════════════════════════════════════════════════════

    def _build_pages(self) -> None:
        """Build all preference pages."""
        for build in (self._build_appearance_page, self._build_steam_page, self._build_ce_page):
            page = build()
            page.connect("map", self._on_page_mapped)
            self.add(page)

    def _on_page_mapped(self, page: Adw.PreferencesPage) -> None:
        """Reset focus when switching pages to avoid auto-selecting EntryRow."""
        GLib.idle_add(self.set_focus, None)

    # ────────────────────────────────────────────────────────────────
    # Appearance Page
    # ────────────────────────────────────────────────────────────────

    def _build_appearance_page(self) -> Adw.PreferencesPage:
        page = Adw.PreferencesPage(
            title=_("Appearance"),
            icon_name="preferences-desktop-appearance-symbolic",
        )

        # Theme group
        theme_group = Adw.PreferencesGroup(title=_("Theme"))
        page.add(theme_group)

        self._theme_row = Adw.ComboRow(
            title=_("Color scheme"),
            subtitle=_("Light, dark, or system"),
        )
        model = Gtk.StringList.new([_("System"), _("Light"), _("Dark")])
        self._theme_row.set_model(model)
        idx = {"system": 0, "light": 1, "dark": 2}.get(self._config.color_scheme, 0)
        self._theme_row.set_selected(idx)
        self._theme_row.connect("notify::selected", self._on_theme_changed)
        theme_group.add(self._theme_row)

        # Language selection
        self._lang_app_row = Adw.ComboRow(
            title=_("Language"),
            subtitle=_("Application interface language"),
        )
        lang_app_model = Gtk.StringList.new([_("System"), "English", "Русский"])
        self._lang_app_row.set_model(lang_app_model)
        lang_app_idx = {"system": 0, "en": 1, "ru": 2}.get(self._config.app_language, 0)
        self._lang_app_row.set_selected(lang_app_idx)
        self._lang_app_row.connect("notify::selected", self._on_app_lang_changed)
        theme_group.add(self._lang_app_row)

        # Transparent window toggle
        self._transparent_row = Adw.SwitchRow(
            title=_("Transparent window"),
            subtitle=_("Semi-transparent background"),
        )
        self._transparent_row.set_active(self._config.transparent_window)
        self._transparent_row.connect("notify::active", self._on_transparent_changed)
        theme_group.add(self._transparent_row)

        # Grid group
        grid_group = Adw.PreferencesGroup(
            title=_("Grid"),
            description=_("Game display settings"),
        )
        page.add(grid_group)

        self._tile_row = Adw.ComboRow(
            title=_("Tile size"),
            subtitle=_("Cover size in library"),
        )
        tile_model = Gtk.StringList.new([_("Small (120px)"), _("Medium (150px)"), _("Large (180px)")])
        self._tile_row.set_model(tile_model)
        tile_idx = {"small": 0, "medium": 1, "large": 2}.get(self._config.tile_size, 1)
        self._tile_row.set_selected(tile_idx)
        self._tile_row.connect("notify::selected", self._on_tile_size_changed)
        grid_group.add(self._tile_row)

        self._sort_row = Adw.ComboRow(
            title=_("Sort"),
            subtitle=_("Default game order"),
        )
        sort_model = Gtk.StringList.new([_("By name"), _("By status")])
        self._sort_row.set_model(sort_model)
        sort_idx = {"name": 0, "status": 1}.get(self._config.sort_by, 0)
        self._sort_row.set_selected(sort_idx)
        self._sort_row.connect("notify::selected", self._on_sort_changed)
        grid_group.add(self._sort_row)

        # Wine theme group
        wine_group = Adw.PreferencesGroup(
            title=_("Wine Theme"),
            description=_("Color scheme for Cheat Engine and other Wine apps"),
        )
        page.add(wine_group)

        self._wine_theme_row = Adw.ComboRow(
            title=_("Color scheme"),
            subtitle=_("Applied to all Proton prefixes"),
        )
        wine_model = Gtk.StringList.new([_("System"), _("Dark"), _("Light")])
        self._wine_theme_row.set_model(wine_model)
        wine_idx = {"system": 0, "dark": 1, "light": 2}.get(self._config.wine_theme, 0)
        self._wine_theme_row.set_selected(wine_idx)
        self._wine_theme_row.connect("notify::selected", self._on_wine_theme_changed)
        
        # Refresh button
        self._wine_refresh_btn = Gtk.Button(
            icon_name="view-refresh-symbolic",
            valign=Gtk.Align.CENTER,
            css_classes=["flat"],
            tooltip_text=_("Reapply theme"),
        )
        self._wine_refresh_btn.connect("clicked", self._on_wine_theme_refresh)
        self._wine_theme_row.add_suffix(self._wine_refresh_btn)
        
        wine_group.add(self._wine_theme_row)

        return page

    def _on_theme_changed(self, row: Adw.ComboRow, _pspec) -> None:
        schemes = ["system", "light", "dark"]
        self._config.color_scheme = schemes[row.get_selected()]
        self._save()
        self._apply_theme()

    def _on_tile_size_changed(self, row: Adw.ComboRow, _pspec) -> None:
        sizes = ["small", "medium", "large"]
        self._config.tile_size = sizes[row.get_selected()]
        self._save()

    def _on_sort_changed(self, row: Adw.ComboRow, _pspec) -> None:
        sorts = ["name", "status"]
        self._config.sort_by = sorts[row.get_selected()]
        self._save()

    def _on_app_lang_changed(self, row: Adw.ComboRow, _pspec) -> None:
        langs = ["system", "en", "ru"]
        lang = langs[row.get_selected()]
        self._config.app_language = lang
        self._save()
        # Show restart hint
        self._show_toast(_("Restart app to apply language"))

    def _on_transparent_changed(self, row: Adw.SwitchRow, _pspec) -> None:
        self._config.transparent_window = row.get_active()
        self._save()
        if self._parent:
            self._parent.apply_transparency()

    def _apply_theme(self) -> None:
        style = Adw.StyleManager.get_default()
        schemes = {
            "light": Adw.ColorScheme.FORCE_LIGHT,
            "dark": Adw.ColorScheme.FORCE_DARK,
            "system": Adw.ColorScheme.DEFAULT,
        }
        style.set_color_scheme(schemes.get(self._config.color_scheme, Adw.ColorScheme.DEFAULT))

    def _get_system_theme(self) -> str:
        """Detect system color scheme. Returns 'dark' or 'light'."""
        style = Adw.StyleManager.get_default()
        return "dark" if style.get_dark() else "light"

    def _on_wine_theme_changed(self, row: Adw.ComboRow, _pspec) -> None:
        """Handle Wine theme change — save and apply immediately."""
        themes = ["system", "dark", "light"]
        theme = themes[row.get_selected()]
        self._config.wine_theme = theme
        self._save()
        
        # For "system", detect actual system theme
        actual_theme = self._get_system_theme() if theme == "system" else theme
        
        # Apply in background
        row.set_sensitive(False)
        self._wine_refresh_btn.set_sensitive(False)
        
        def worker() -> None:
            steamapps = self._config.steamapps_path
            success, failed = wine_theme.apply_theme_to_all(steamapps, actual_theme)
            GLib.idle_add(self._on_wine_theme_applied, row, success, failed)

        threading.Thread(target=worker, daemon=True).start()

    def _on_wine_theme_applied(self, row: Adw.ComboRow, success: int, failed: int) -> None:
        """Handle Wine theme application result."""
        row.set_sensitive(True)
        self._wine_refresh_btn.set_sensitive(True)
        
        if success > 0:
            self._show_toast(_("Theme applied to %d prefixes") % success)
        elif failed > 0:
            self._show_toast(_("Error applying to %d prefixes") % failed)

    def _on_wine_theme_refresh(self, _btn: Gtk.Button) -> None:
        """Refresh/reapply Wine theme to all prefixes."""
        theme = self._config.wine_theme
        actual_theme = self._get_system_theme() if theme == "system" else theme
        
        self._wine_theme_row.set_sensitive(False)
        self._wine_refresh_btn.set_sensitive(False)
        
        def worker() -> None:
            steamapps = self._config.steamapps_path
            success, failed = wine_theme.apply_theme_to_all(steamapps, actual_theme)
            GLib.idle_add(self._on_wine_theme_applied, self._wine_theme_row, success, failed)

        threading.Thread(target=worker, daemon=True).start()

    def _show_toast(self, message: str) -> None:
        """Show a toast notification."""
        toast = Adw.Toast(title=message, timeout=3)
        self.add_toast(toast)

    # ────────────────────────────────────────────────────────────────
    # Steam Page
    # ────────────────────────────────────────────────────────────────

    def _build_steam_page(self) -> Adw.PreferencesPage:
        page = Adw.PreferencesPage(
            title="Steam",
            icon_name="folder-games-symbolic",
        )

        # Paths group
        paths_group = Adw.PreferencesGroup(title=_("Paths"))
        page.add(paths_group)

        self._steam_row = Adw.EntryRow(title=_("Steam directory"))
        self._steam_row.set_text(self._config.steam_path)
        self._steam_row.connect("changed", self._on_steam_path_changed)

        steam_browse = Gtk.Button(
            icon_name="folder-open-symbolic",
            valign=Gtk.Align.CENTER,
            css_classes=["flat"],
            tooltip_text=_("Choose folder"),
        )
        steam_browse.connect("clicked", self._on_browse_steam)
        self._steam_row.add_suffix(steam_browse)
        paths_group.add(self._steam_row)

        # Launch options group
        launch_group = Adw.PreferencesGroup(
            title=_("Launch options"),
            description=_("LaunchOptions template for protonhax"),
        )
        page.add(launch_group)

        self._template_row = Adw.EntryRow(title=_("Template"))
        self._template_row.set_text(self._config.launch_options_template)
        self._template_row.connect("changed", self._on_template_changed)
        launch_group.add(self._template_row)

        hint_row = Adw.ActionRow(
            title="%COMMAND%",
            subtitle=_("Original launch command is substituted"),
        )
        hint_row.set_activatable(False)
        hint_row.add_css_class("dim-label")
        launch_group.add(hint_row)

        # Exclusions group
        excl_group = Adw.PreferencesGroup(
            title=_("Exclusions"),
            description=_("Regex patterns to hide apps"),
        )
        page.add(excl_group)
        self._excl_group = excl_group

        for pattern in self._config.excluded_app_patterns:
            self._add_exclusion_row(pattern)

        add_row = Adw.ActionRow(title=_("Add pattern"))
        add_btn = Gtk.Button(
            icon_name="list-add-symbolic",
            valign=Gtk.Align.CENTER,
            css_classes=["flat"],
        )
        add_btn.connect("clicked", self._on_add_exclusion)
        add_row.add_suffix(add_btn)
        add_row.set_activatable_widget(add_btn)
        excl_group.add(add_row)
        self._add_excl_row = add_row

        return page

    def _on_steam_path_changed(self, row: Adw.EntryRow) -> None:
        self._config.steam_path = row.get_text().strip()
        self._save()

    def _on_template_changed(self, row: Adw.EntryRow) -> None:
        self._config.launch_options_template = row.get_text().strip()
        self._save()

    def _on_browse_steam(self, _btn: Gtk.Button) -> None:
        dialog = Gtk.FileDialog(title=_("Select Steam directory"))
        dialog.select_folder(self, None, self._on_steam_folder_selected)

    def _on_steam_folder_selected(self, dialog: Gtk.FileDialog, result: Gio.AsyncResult) -> None:
        try:
            folder = dialog.select_folder_finish(result)
            if folder:
                path = folder.get_path()
                home = str(Path.home())
                display = path.replace(home, "~", 1) if path.startswith(home) else path
                self._steam_row.set_text(display)
        except GLib.Error:
            pass

    def _add_exclusion_row(self, text: str = "") -> Adw.EntryRow:
        row = Adw.EntryRow(title="Regex")
        row.set_text(text)
        row.connect("changed", self._on_exclusion_changed)

        remove_btn = Gtk.Button(
            icon_name="user-trash-symbolic",
            valign=Gtk.Align.CENTER,
            css_classes=["flat", "error"],
            tooltip_text=_("Remove"),
        )
        remove_btn.connect("clicked", self._on_remove_exclusion, row)
        row.add_suffix(remove_btn)

        self._exclusion_rows.append(row)
        self._excl_group.add(row)
        return row

    def _on_add_exclusion(self, _btn: Gtk.Button) -> None:
        row = self._add_exclusion_row()
        row.grab_focus()

    def _on_remove_exclusion(self, _btn: Gtk.Button, row: Adw.EntryRow) -> None:
        if row in self._exclusion_rows:
            self._exclusion_rows.remove(row)
        self._excl_group.remove(row)
        self._sync_exclusions()

    def _on_exclusion_changed(self, _row: Adw.EntryRow) -> None:
        self._sync_exclusions()

    def _sync_exclusions(self) -> None:
        self._config.excluded_app_patterns = [
            row.get_text().strip()
            for row in self._exclusion_rows
            if row.get_text().strip()
        ]
        self._save()

    # ────────────────────────────────────────────────────────────────
    # Cheat Engine Page
    # ────────────────────────────────────────────────────────────────

    def _build_ce_page(self) -> Adw.PreferencesPage:
        page = Adw.PreferencesPage(
            title="Cheat Engine",
            icon_name="applications-games-symbolic",
        )

        # Status group
        status_group = Adw.PreferencesGroup(title=_("Status"))
        page.add(status_group)

        self._ce_status_row = Adw.ActionRow(
            title="Cheat Engine",
            subtitle=_("Checking..."),
        )
        self._ce_status_row.set_activatable(False)
        status_group.add(self._ce_status_row)

        self._ph_status_row = Adw.ActionRow(
            title="protonhax",
            subtitle=_("Checking..."),
        )
        self._ph_status_row.set_activatable(False)
        status_group.add(self._ph_status_row)

        # Installation group
        install_group = Adw.PreferencesGroup(
            title=_("Installation"),
            description=_("Cheat Engine setup and download"),
        )
        page.add(install_group)

        self._ce_path_row = Adw.EntryRow(title=_("Executable"))
        self._ce_path_row.set_text(self._config.ce_executable)
        self._ce_path_row.connect("changed", self._on_ce_path_changed)

        browse_btn = Gtk.Button(
            icon_name="document-open-symbolic",
            valign=Gtk.Align.CENTER,
            css_classes=["flat"],
            tooltip_text=_("Choose file"),
        )
        browse_btn.connect("clicked", self._on_browse_ce)
        self._ce_path_row.add_suffix(browse_btn)
        install_group.add(self._ce_path_row)

        self._dl_row = Adw.ActionRow(
            title=_("Latest version"),
            subtitle=_("Click Check"),
        )
        self._check_btn = Gtk.Button(
            label=_("Check"),
            valign=Gtk.Align.CENTER,
        )
        self._check_btn.connect("clicked", self._on_check_release)
        self._dl_row.add_suffix(self._check_btn)
        install_group.add(self._dl_row)

        self._progress_row = Adw.ActionRow(
            title=_("Download"),
            subtitle="",
            visible=False,
        )
        self._progress = Gtk.ProgressBar(
            valign=Gtk.Align.CENTER,
            show_text=True,
        )
        self._progress.set_size_request(150, -1)
        self._progress_row.add_suffix(self._progress)
        install_group.add(self._progress_row)

        # protonhax group
        ph_group = Adw.PreferencesGroup(
            title="protonhax",
            description=_("Required for attaching to Proton games"),
        )
        page.add(ph_group)

        ph_row = Adw.ActionRow(
            title=_("Install or update"),
            subtitle=_("Downloads latest version from GitHub"),
        )
        self._ph_btn = Gtk.Button(
            label=_("Install"),
            valign=Gtk.Align.CENTER,
        )
        self._ph_btn.connect("clicked", self._on_install_protonhax)
        ph_row.add_suffix(self._ph_btn)
        ph_group.add(ph_row)

        # Language group
        lang_group = Adw.PreferencesGroup(
            title=_("Language"),
            description=_("Cheat Engine interface language"),
        )
        page.add(lang_group)

        self._lang_row = Adw.ComboRow(
            title=_("Interface"),
            subtitle=_("Requires CE restart"),
        )
        lang_model = Gtk.StringList.new([_("System"), _("Russian")])
        self._lang_row.set_model(lang_model)
        lang_idx = {"system": 0, "ru_RU": 1}.get(self._config.ce_language, 0)
        self._lang_row.set_selected(lang_idx)
        self._lang_row.connect("notify::selected", self._on_lang_changed)
        lang_group.add(self._lang_row)

        self._loc_row = Adw.ActionRow(
            title=_("Russian localization"),
            subtitle=_("Checking..."),
        )
        self._loc_btn = Gtk.Button(
            label=_("Install"),
            valign=Gtk.Align.CENTER,
        )
        self._loc_btn.connect("clicked", self._on_install_localization)
        self._loc_row.add_suffix(self._loc_btn)
        lang_group.add(self._loc_row)

        # Debug group
        debug_group = Adw.PreferencesGroup(title=_("Debug"))
        page.add(debug_group)

        test_row = Adw.ActionRow(
            title=_("Test launch"),
            subtitle=_("Launch CE via Wine (without game binding)"),
        )
        self._test_btn = Gtk.Button(
            label=_("Launch"),
            valign=Gtk.Align.CENTER,
            css_classes=["suggested-action"],
        )
        self._test_btn.connect("clicked", self._on_test_launch)
        test_row.add_suffix(self._test_btn)
        debug_group.add(test_row)

        return page

    def _on_ce_path_changed(self, row: Adw.EntryRow) -> None:
        self._config.ce_executable = row.get_text().strip()
        self._save()
        self._refresh_status()

    def _on_browse_ce(self, _btn: Gtk.Button) -> None:
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
        dialog.open(self, None, self._on_ce_file_selected)

    def _on_ce_file_selected(self, dialog: Gtk.FileDialog, result: Gio.AsyncResult) -> None:
        try:
            gfile = dialog.open_finish(result)
            if gfile:
                path = gfile.get_path()
                home = str(Path.home())
                display = path.replace(home, "~", 1) if path.startswith(home) else path
                self._ce_path_row.set_text(display)
        except GLib.Error:
            pass

    # ────────────────────────────────────────────────────────────────
    # Status & Actions
    # ────────────────────────────────────────────────────────────────

    def _refresh_status(self) -> None:
        """Update CE and protonhax status."""
        # CE status
        if self._config.ce_exists:
            version = cheatengine.detect_version(self._config.ce_executable_path)
            ver_str = f" ({version})" if version else ""
            self._ce_status_row.set_subtitle(_("✓ Installed") + ver_str)
            self._test_btn.set_sensitive(True)
        else:
            self._ce_status_row.set_subtitle(_("✗ Not found"))
            self._test_btn.set_sensitive(False)

        # protonhax status
        ph_path = protonhax.find_installed()
        if ph_path:
            if protonhax.is_managed():
                if protonhax.needs_update():
                    self._ph_status_row.set_subtitle(_("⟳ Update available"))
                    self._ph_btn.set_label(_("Refresh"))
                else:
                    self._ph_status_row.set_subtitle(_("✓ Installed"))
                    self._ph_btn.set_label(_("Reinstall"))
            else:
                self._ph_status_row.set_subtitle(_("✓ External: %s") % ph_path)
        else:
            self._ph_status_row.set_subtitle(_("✗ Not installed"))
            self._ph_btn.set_label(_("Install"))

        # Localization status
        if self._config.ce_exists:
            if cheatengine.is_localization_installed(self._config.ce_executable_path):
                self._loc_row.set_subtitle(_("✓ Installed"))
                self._loc_btn.set_label(_("Reinstall"))
            else:
                self._loc_row.set_subtitle(_("Not installed"))
                self._loc_btn.set_label(_("Install"))
            self._loc_btn.set_sensitive(True)
        else:
            self._loc_row.set_subtitle(_("Cheat Engine required"))
            self._loc_btn.set_sensitive(False)

    def _on_test_launch(self, _btn: Gtk.Button) -> None:
        if not self._config.ce_exists:
            self.add_toast(Adw.Toast(title=_("Cheat Engine not found")))
            return

        wine = cheatengine.find_proton_wine(self._config.steam_path)
        if not wine:
            self.add_toast(Adw.Toast(title=_("Wine not found — install Proton")))
            return

        import os
        import subprocess

        env = os.environ.copy()
        prefix = Path.home() / ".local" / "share" / "vual" / "wine_prefix"
        prefix.mkdir(parents=True, exist_ok=True)
        env["WINEPREFIX"] = str(prefix)

        cmd = [str(wine), str(self._config.ce_executable_path)]
        if self._config.ce_language != "system":
            cmd.extend(["--LANG", self._config.ce_language])

        try:
            subprocess.Popen(
                cmd,
                env=env,
                start_new_session=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            self.add_toast(Adw.Toast(title=_("Cheat Engine launched")))
        except OSError as e:
            self.add_toast(Adw.Toast(title=_("Error: %s") % e))

    def _on_install_protonhax(self, _btn: Gtk.Button) -> None:
        try:
            protonhax.ensure_installed()
            self._refresh_status()
            self.add_toast(Adw.Toast(title=_("protonhax installed")))
        except OSError as e:
            self.add_toast(Adw.Toast(title=_("Error: %s") % e))

    def _on_lang_changed(self, row: Adw.ComboRow, _pspec) -> None:
        langs = ["system", "ru_RU"]
        self._config.ce_language = langs[row.get_selected()]
        self._save()

    def _on_install_localization(self, btn: Gtk.Button) -> None:
        if not self._config.ce_exists:
            self.add_toast(Adw.Toast(title=_("Cheat Engine not found")))
            return

        btn.set_sensitive(False)
        self._loc_row.set_subtitle(_("Downloading..."))

        def worker() -> None:
            ok = cheatengine.install_localization(self._config.ce_executable_path)
            GLib.idle_add(self._on_localization_done, ok, btn)

        threading.Thread(target=worker, daemon=True).start()

    def _on_localization_done(self, success: bool, btn: Gtk.Button) -> None:
        btn.set_sensitive(True)
        self._refresh_status()
        if success:
            self.add_toast(Adw.Toast(title=_("Localization installed")))
        else:
            self.add_toast(Adw.Toast(title=_("Failed to install localization")))

    # ────────────────────────────────────────────────────────────────
    # CE Download
    # ────────────────────────────────────────────────────────────────

    def _on_check_release(self, _btn: Gtk.Button) -> None:
        self._dl_row.set_subtitle(_("Checking..."))
        self._check_btn.set_sensitive(False)

        def worker() -> None:
            info = cheatengine.get_latest_release()
            GLib.idle_add(self._on_release_checked, info)

        threading.Thread(target=worker, daemon=True).start()

    def _on_release_checked(self, info: dict | None) -> None:
        self._check_btn.set_sensitive(True)

        if not info or not info.get("url"):
            self._dl_row.set_subtitle(_("Failed to get info"))
            return

        self._release_info = info
        version = info.get("version", "?")
        size_mb = info.get("size", 0) / 1_048_576

        subtitle = f"v{version}"
        if size_mb > 0:
            subtitle += f" ({size_mb:.1f} " + _("MB") + ")"
        self._dl_row.set_subtitle(subtitle)

        # Replace check button with download button
        self._dl_row.remove(self._check_btn)
        dl_btn = Gtk.Button(
            label=_("Download"),
            valign=Gtk.Align.CENTER,
            css_classes=["suggested-action"],
        )
        dl_btn.connect("clicked", self._on_download_ce)
        self._dl_row.add_suffix(dl_btn)
        self._download_btn = dl_btn

    def _on_download_ce(self, btn: Gtk.Button) -> None:
        if not self._release_info:
            return

        url = self._release_info["url"]
        name = self._release_info.get("name", "CheatEngine.exe")

        cache_dir = Path.home() / ".cache" / "vual"
        cache_dir.mkdir(parents=True, exist_ok=True)
        installer = cache_dir / name

        dest_dir = Path.home() / ".local" / "share" / "vual" / "cheatengine"

        self._progress_row.set_visible(True)
        self._progress_row.set_subtitle(_("Downloading: %s") % name)
        self._progress.set_fraction(0)
        btn.set_sensitive(False)

        def update_progress(frac: float) -> None:
            GLib.idle_add(self._progress.set_fraction, frac)

        def worker() -> None:
            ok = cheatengine.download_file(url, installer, progress_cb=update_progress)
            if not ok:
                GLib.idle_add(self._download_failed, btn)
                return
            GLib.idle_add(self._start_extraction, installer, dest_dir, btn)

        threading.Thread(target=worker, daemon=True).start()

    def _download_failed(self, btn: Gtk.Button) -> None:
        self._progress_row.set_visible(False)
        btn.set_sensitive(True)
        self.add_toast(Adw.Toast(title=_("Download failed")))

    def _start_extraction(self, installer: Path, dest_dir: Path, btn: Gtk.Button) -> None:
        self._progress_row.set_subtitle(_("Extracting..."))
        self._progress.set_fraction(0.5)

        def worker() -> None:
            extracted = cheatengine.extract_installer(
                installer, dest_dir, self._config.steam_path
            )
            exe = cheatengine.find_executable(dest_dir) if extracted else None
            GLib.idle_add(self._extraction_done, exe, extracted, installer, btn)

        threading.Thread(target=worker, daemon=True).start()

    def _extraction_done(
        self,
        exe_path: Path | None,
        extracted: bool,
        installer: Path,
        btn: Gtk.Button,
    ) -> None:
        self._progress_row.set_visible(False)
        btn.set_sensitive(True)

        if exe_path:
            home = str(Path.home())
            display = str(exe_path).replace(home, "~", 1)
            self._config.ce_executable = display
            self._ce_path_row.set_text(display)
            self._save()
            self._refresh_status()
            installer.unlink(missing_ok=True)
            self.add_toast(Adw.Toast(title=_("Cheat Engine installed")))
        elif extracted:
            self._refresh_status()
            self.add_toast(Adw.Toast(title=_("Extracted — specify path manually")))
        else:
            self.add_toast(Adw.Toast(title=_("Extraction failed")))
