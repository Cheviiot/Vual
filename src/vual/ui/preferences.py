"""Preferences window — thin shell assembling page modules.

Uses Adw.PreferencesWindow with auto-save on changes.
"""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, GLib  # noqa: E402

from vual.config import Config  # noqa: E402
from vual.i18n import _  # noqa: E402
from vual.ui.pref_appearance import build_appearance_page  # noqa: E402
from vual.ui.pref_ce import build_ce_page  # noqa: E402
from vual.ui.pref_steam import build_steam_page  # noqa: E402


class PreferencesWindow(Adw.PreferencesWindow):
    """Preferences window with auto-save."""

    def __init__(self, config: Config, **kwargs) -> None:
        super().__init__(
            title=_("Preferences"),
            **kwargs,
        )
        self._config = config
        self._parent = kwargs.get("transient_for")
        self._building = True

        self._build_pages()
        self._building = False

    def _save(self) -> None:
        """Save config if not building UI."""
        if self._building:
            return
        self._config.save()

    def _show_toast(self, message: str) -> None:
        """Show a toast notification."""
        toast = Adw.Toast(title=message, timeout=3)
        self.add_toast(toast)

    def _build_pages(self) -> None:
        """Build all preference pages from modules."""
        for build in (build_appearance_page, build_steam_page, build_ce_page):
            page = build(self)
            page.connect("map", self._on_page_mapped)
            self.add(page)

    def _on_page_mapped(self, page: Adw.PreferencesPage) -> None:
        """Reset focus when switching pages to avoid auto-selecting EntryRow."""
        GLib.idle_add(self.set_focus, None)
