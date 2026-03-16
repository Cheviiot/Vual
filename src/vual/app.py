"""Adw.Application for Vual."""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gdk, Gio, Gtk  # noqa: E402

from vual import APP_ID, APP_NAME, CSS_PATH, ICON_PATH, __version__  # noqa: E402
from vual.config import Config  # noqa: E402
from vual.i18n import init as init_i18n  # noqa: E402
from vual.window import VualWindow  # noqa: E402


class VualApp(Adw.Application):
    def __init__(self) -> None:
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.DEFAULT_FLAGS)
        self.config = Config.load()
        init_i18n(self.config.app_language)  # Initialize translations with saved language

    # ── Activate ─────────────────────────────────────────────────

    def do_activate(self) -> None:
        # Apply color scheme
        style_manager = Adw.StyleManager.get_default()
        scheme_map = {
            "light": Adw.ColorScheme.FORCE_LIGHT,
            "dark": Adw.ColorScheme.FORCE_DARK,
            "system": Adw.ColorScheme.DEFAULT,
        }
        style_manager.set_color_scheme(scheme_map.get(self.config.color_scheme, Adw.ColorScheme.DEFAULT))

        win = self.props.active_window
        if not win:
            win = VualWindow(application=self, config=self.config)
            win.set_default_size(self.config.window_width, self.config.window_height)
        win.present()

    # ── Startup: register actions ────────────────────────────────

    def do_startup(self) -> None:
        Adw.Application.do_startup(self)
        display = Gdk.Display.get_default()

        # Load application CSS
        if CSS_PATH and display:
            css_provider = Gtk.CssProvider()
            css_provider.load_from_path(str(CSS_PATH))
            Gtk.StyleContext.add_provider_for_display(
                display,
                css_provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
            )

        # Add custom icon path to theme (for development)
        if ICON_PATH and display:
            Gtk.IconTheme.get_for_display(display).add_search_path(str(ICON_PATH.parent))

        about_action = Gio.SimpleAction.new("about", None)
        about_action.connect("activate", self._on_about)
        self.add_action(about_action)

        prefs_action = Gio.SimpleAction.new("preferences", None)
        prefs_action.connect("activate", self._on_preferences)
        self.add_action(prefs_action)

        quit_action = Gio.SimpleAction.new("quit", None)
        quit_action.connect("activate", lambda *_: self.quit())
        self.add_action(quit_action)
        self.set_accels_for_action("app.quit", ["<primary>q"])

    # ── About dialog ─────────────────────────────────────────────

    def _on_about(self, _action: Gio.SimpleAction, _param: None) -> None:
        # Use dev icon name if in dev mode, otherwise use app_id (installed icon)
        icon_name = "Vual" if ICON_PATH else APP_ID
        about = Adw.AboutDialog(
            application_name=APP_NAME,
            application_icon=icon_name,
            version=__version__,
            developer_name="Cheviiot",
            website="https://github.com/Cheviiot/vual",
            issue_url="https://github.com/Cheviiot/vual/issues",
            developers=["Cheviiot"],
            copyright="© 2026 Cheviiot",
            license_type=Gtk.License.GPL_3_0,
        )
        about.present(self.props.active_window)

    # ── Preferences ──────────────────────────────────────────────

    def _on_preferences(self, _action: Gio.SimpleAction, _param: None) -> None:
        from vual.ui.preferences import PreferencesWindow

        win = PreferencesWindow(config=self.config, transient_for=self.props.active_window)
        win.present()
