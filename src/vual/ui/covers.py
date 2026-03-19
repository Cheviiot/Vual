"""Cover image loading and caching utilities."""

from __future__ import annotations

from pathlib import Path

import gi

gi.require_version("GdkPixbuf", "2.0")

from gi.repository import GdkPixbuf, GLib  # noqa: E402

import requests

# Steam cover URLs
COVER_URL = "https://steamcdn-a.akamaihd.net/steam/apps/{}/library_600x900_2x.jpg"
COVER_FALLBACK = "https://steamcdn-a.akamaihd.net/steam/apps/{}/header.jpg"

# Cache directory
CACHE_DIR = Path(GLib.get_user_cache_dir()) / "vual" / "covers"


def cache_path(app_id: str) -> Path:
    """Get cache path for cover image."""
    return CACHE_DIR / f"{app_id}.jpg"


def download_cover(app_id: str) -> Path | None:
    """Download cover from Steam CDN. Returns cache path or None."""
    cache = cache_path(app_id)
    if cache.exists():
        return cache

    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    for url_template in (COVER_URL, COVER_FALLBACK):
        url = url_template.format(app_id)
        try:
            resp = requests.get(url, headers={"User-Agent": "Vual/1.0"}, timeout=10)
            if resp.status_code == 200:
                cache.write_bytes(resp.content)
                return cache
        except requests.RequestException:
            continue

    return None


def load_pixbuf(path: Path, width: int, height: int) -> GdkPixbuf.Pixbuf | None:
    """Load and scale pixbuf from file.

    Handles landscape images by compositing them onto a blurred background.
    """
    try:
        original = GdkPixbuf.Pixbuf.new_from_file(str(path))
    except GLib.Error:
        return None

    ow, oh = original.get_width(), original.get_height()
    if ow < 1 or oh < 1:
        return None

    aspect = ow / oh

    # If image is landscape (wider than 4:3), create composite with blur
    if aspect > 1.33:
        return _create_landscape_composite(original, ow, oh, width, height)

    # Portrait or square: scale to fill
    return original.scale_simple(width, height, GdkPixbuf.InterpType.BILINEAR)


def _create_landscape_composite(
    original: GdkPixbuf.Pixbuf,
    ow: int, oh: int,
    width: int, height: int,
) -> GdkPixbuf.Pixbuf:
    """Create a portrait tile from a landscape image.

    Composites the original image centered on a scaled/blurred background.
    """
    # Create background: scale original to fill tile (will be cropped/stretched)
    bg = original.scale_simple(width, height, GdkPixbuf.InterpType.BILINEAR)

    # Apply simple darkening to background (simulates blur effect)
    dark = GdkPixbuf.Pixbuf.new(
        GdkPixbuf.Colorspace.RGB, True, 8, width, height
    )
    dark.fill(0x00000099)
    dark.composite(
        bg, 0, 0, width, height,
        0, 0, 1.0, 1.0,
        GdkPixbuf.InterpType.NEAREST, 180,
    )

    # Scale original to fit width while preserving aspect ratio
    scale = width / ow
    scaled_w = width
    scaled_h = int(oh * scale)

    scaled = original.scale_simple(scaled_w, scaled_h, GdkPixbuf.InterpType.BILINEAR)

    # Center vertically
    y_offset = (height - scaled_h) // 2

    # Composite scaled image onto darkened background
    scaled.composite(
        bg,
        0, y_offset,
        scaled_w, scaled_h,
        0, y_offset,
        1.0, 1.0,
        GdkPixbuf.InterpType.BILINEAR,
        255,
    )

    return bg
