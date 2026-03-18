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

        # Navigation view for guide/main switching
        self._nav_view = Adw.NavigationView()
        self.toast_overlay.set_child(self._nav_view)

        # Main page
        self._main_nav_page = self._build_main_page()
        self._nav_view.add(self._main_nav_page)

        # Apply transparency from config
        self.apply_transparency()

    def _build_main_page(self) -> Adw.NavigationPage:
        """Build the main games grid page."""
        from vual.ui.main_page import MainPage

        toolbar_view = Adw.ToolbarView()

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

        return Adw.NavigationPage(child=toolbar_view, title=APP_NAME, tag="main")

    def _on_sort_changed(self, _action: Gio.SimpleAction, param: GLib.Variant) -> None:
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
        menu.append(_("Guide"), "app.guide")
        return menu

    # ── Toast helper ─────────────────────────────────────────────

    def show_toast(self, message: str, timeout: int = 3) -> None:
        toast = Adw.Toast(title=message, timeout=timeout)
        self.toast_overlay.add_toast(toast)
        return False

    # ── Transparency ──────────────────────────────────────────────

    def apply_transparency(self) -> None:
        """Apply or remove transparent window CSS class."""
        if self.config.transparent_window:
            self.add_css_class("transparent-window")
        else:
            self.remove_css_class("transparent-window")

    # ── Guide page ───────────────────────────────────────────────

    def show_guide(self) -> None:
        """Show fullscreen guide page."""
        guide_page = self._build_guide_page()
        self._nav_view.push(guide_page)

    def _build_guide_page(self) -> Adw.NavigationPage:
        """Build the guide/onboarding page."""
        toolbar_view = Adw.ToolbarView()

        header = Adw.HeaderBar()
        header.add_css_class("flat")
        toolbar_view.add_top_bar(header)

        scroll = Gtk.ScrolledWindow(vexpand=True)
        toolbar_view.set_content(scroll)

        clamp = Adw.Clamp(maximum_size=760)
        scroll.set_child(clamp)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        content.add_css_class("guide-page")
        content.set_margin_top(28)
        content.set_margin_bottom(40)
        content.set_margin_start(24)
        content.set_margin_end(24)
        clamp.set_child(content)

        hero = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        hero.add_css_class("guide-hero")
        content.append(hero)

        eyebrow = Gtk.Label(label=_("Getting Started"), xalign=0)
        eyebrow.add_css_class("guide-eyebrow")
        hero.append(eyebrow)

        title = Gtk.Label(label=_("Set up Vual in a couple of minutes"), xalign=0)
        title.add_css_class("guide-title")
        title.set_wrap(True)
        hero.append(title)

        subtitle = Gtk.Label(
            label=_("Vual links Steam, Proton and Cheat Engine so you can launch the game first and open CE in the right prefix without manual setup every time."),
            xalign=0,
            wrap=True,
        )
        subtitle.add_css_class("guide-subtitle")
        hero.append(subtitle)

        prep_card = self._build_guide_card(
            _("Before you start"),
            _("Make sure the base tools are ready before enabling games."),
            [
                _("Install or download Cheat Engine in Settings"),
                _("Check that the Steam path points to the correct library"),
                _("Close Steam before changing launch options for many games"),
            ],
        )
        content.append(prep_card)

        flow_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        flow_card.add_css_class("guide-card")
        content.append(flow_card)

        flow_title = Gtk.Label(label=_("How Vual works"), xalign=0)
        flow_title.add_css_class("guide-card-title")
        flow_card.append(flow_title)

        flow_subtitle = Gtk.Label(
            label=_("The usual workflow is short and always the same."),
            xalign=0,
            wrap=True,
        )
        flow_subtitle.add_css_class("guide-card-subtitle")
        flow_card.append(flow_subtitle)

        steps = [
            (_("Pick a game"), _("Find the game in the library and enable the switch on its tile.")),
            (_("Start it from Steam"), _("Steam launches the game with protonhax and prepares the correct environment.")),
            (_("Open Cheat Engine"), _("Use the tile menu to launch CE directly for that running game.")),
            (_("Optional: attach a table"), _("Bind a .CT file once and Vual will pass it to Cheat Engine automatically.")),
        ]
        for index, (step_title, step_desc) in enumerate(steps, start=1):
            flow_card.append(self._build_guide_step(index, step_title, step_desc))

        tips_card = self._build_guide_card(
            _("Good to know"),
            _("A few things save time once the basics are configured."),
            [
                _("Use search in the header to filter large libraries quickly"),
                _("The menu button on each tile contains CE actions and table binding"),
                _("Window transparency can be toggled in Appearance settings"),
            ],
        )
        content.append(tips_card)

        actions = Gtk.Box(spacing=12)
        actions.set_halign(Gtk.Align.CENTER)
        actions.set_margin_top(12)

        prefs_btn = Gtk.Button(label=_("Open Settings"))
        prefs_btn.add_css_class("pill")
        prefs_btn.connect("clicked", self._on_guide_preferences)
        actions.append(prefs_btn)

        start_btn = Gtk.Button(label=_("Open Library"))
        start_btn.add_css_class("suggested-action")
        start_btn.add_css_class("pill")
        start_btn.connect("clicked", self._on_guide_close)
        actions.append(start_btn)
        content.append(actions)

        return Adw.NavigationPage(child=toolbar_view, title=_("Welcome to Vual"), tag="guide")

    def _build_guide_card(self, title: str, subtitle: str, items: list[str]) -> Gtk.Box:
        """Build a guide card with bullet rows."""
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        card.add_css_class("guide-card")

        title_label = Gtk.Label(label=title, xalign=0)
        title_label.add_css_class("guide-card-title")
        card.append(title_label)

        subtitle_label = Gtk.Label(label=subtitle, xalign=0, wrap=True)
        subtitle_label.add_css_class("guide-card-subtitle")
        card.append(subtitle_label)

        for item in items:
            row = Gtk.Box(spacing=10)
            row.add_css_class("guide-list-row")

            bullet = Gtk.Label(label="•")
            bullet.add_css_class("guide-bullet")
            row.append(bullet)

            item_label = Gtk.Label(label=item, xalign=0, wrap=True)
            item_label.add_css_class("guide-list-text")
            row.append(item_label)
            card.append(row)

        return card

    def _build_guide_step(self, index: int, title: str, description: str) -> Gtk.Box:
        """Build a single step row for the guide."""
        row = Gtk.Box(spacing=14)
        row.add_css_class("guide-step")

        badge = Gtk.Label(label=str(index))
        badge.add_css_class("guide-step-badge")
        badge.set_size_request(34, 34)
        badge.set_valign(Gtk.Align.START)
        row.append(badge)

        text_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)

        title_label = Gtk.Label(label=title, xalign=0)
        title_label.add_css_class("guide-step-title")
        text_box.append(title_label)

        desc_label = Gtk.Label(label=description, xalign=0, wrap=True)
        desc_label.add_css_class("guide-step-description")
        text_box.append(desc_label)

        row.append(text_box)
        return row

    def _on_guide_close(self, _btn: Gtk.Button) -> None:
        """Close guide and mark as shown."""
        self.config.guide_shown = True
        self.config.save()
        self._nav_view.pop()

    def _on_guide_preferences(self, _btn: Gtk.Button) -> None:
        """Open preferences from the guide."""
        self._on_guide_close(_btn)
        app = self.get_application()
        if app is not None:
            app.activate_action("preferences", None)
