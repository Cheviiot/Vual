"""Guide / onboarding page."""

from __future__ import annotations

from typing import TYPE_CHECKING

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk  # noqa: E402

from vual.i18n import _  # noqa: E402

if TYPE_CHECKING:
    from vual.config import Config


def build_guide_page(nav_view: Adw.NavigationView, config: Config, open_preferences) -> Adw.NavigationPage:
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

    prep_card = _build_card(
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
        flow_card.append(_build_step(index, step_title, step_desc))

    tips_card = _build_card(
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

    def on_close(_btn):
        config.guide_shown = True
        config.save()
        nav_view.pop()

    def on_preferences(_btn):
        on_close(_btn)
        open_preferences()

    prefs_btn = Gtk.Button(label=_("Open Settings"))
    prefs_btn.add_css_class("pill")
    prefs_btn.connect("clicked", on_preferences)
    actions.append(prefs_btn)

    start_btn = Gtk.Button(label=_("Open Library"))
    start_btn.add_css_class("suggested-action")
    start_btn.add_css_class("pill")
    start_btn.connect("clicked", on_close)
    actions.append(start_btn)
    content.append(actions)

    return Adw.NavigationPage(child=toolbar_view, title=_("Welcome to Vual"), tag="guide")


def _build_card(title: str, subtitle: str, items: list[str]) -> Gtk.Box:
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

        bullet = Gtk.Label(label="\u2022")
        bullet.add_css_class("guide-bullet")
        row.append(bullet)

        item_label = Gtk.Label(label=item, xalign=0, wrap=True)
        item_label.add_css_class("guide-list-text")
        row.append(item_label)
        card.append(row)

    return card


def _build_step(index: int, title: str, description: str) -> Gtk.Box:
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
