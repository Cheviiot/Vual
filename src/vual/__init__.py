"""Vual — launch Cheat Engine for Steam games via Proton."""

from pathlib import Path

__version__ = "0.2.0"
APP_ID = "io.github.vual"
APP_NAME = "Vual"

# Paths: try development first, then fall back to installed locations
_PKG_DIR = Path(__file__).parent
_DATA_DIR = _PKG_DIR.parent.parent / "data"

# Icon
_DEV_ICON = _DATA_DIR / "Vual.png"
ICON_PATH = _DEV_ICON if _DEV_ICON.exists() else None

# CSS (in package data)
_PKG_CSS = _PKG_DIR / "data" / "style.css"
CSS_PATH = _PKG_CSS if _PKG_CSS.exists() else None
