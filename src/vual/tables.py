"""Cheat Engine table (.CT) storage and per-game binding.

Tables are stored in ~/.local/share/vual/tables/.
Bindings (app_id → filename) are persisted in tables.json alongside the files.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from gi.repository import GLib

TABLES_DIR = Path(GLib.get_user_data_dir()) / "vual" / "tables"
_MAP_FILE = TABLES_DIR / "tables.json"


# ── Internal helpers ─────────────────────────────────────────────

def _load_map() -> dict[str, str]:
    if _MAP_FILE.exists():
        try:
            return json.loads(_MAP_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _save_map(data: dict[str, str]) -> None:
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    _MAP_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


# ── Public API ───────────────────────────────────────────────────

def bind(app_id: str, src: str | Path) -> Path:
    """Copy a .CT file into the tables directory and bind it to *app_id*.

    Returns the destination path inside TABLES_DIR.
    """
    src = Path(src)
    TABLES_DIR.mkdir(parents=True, exist_ok=True)

    dest = TABLES_DIR / src.name
    if dest.resolve() != src.resolve():
        shutil.copy2(src, dest)

    data = _load_map()
    data[app_id] = dest.name
    _save_map(data)
    return dest


def unbind(app_id: str) -> None:
    """Remove the table binding for *app_id* (file kept on disk)."""
    data = _load_map()
    if app_id in data:
        del data[app_id]
        _save_map(data)


def get_table(app_id: str) -> Path | None:
    """Return the full path to the bound .CT file, or None."""
    data = _load_map()
    name = data.get(app_id)
    if not name:
        return None
    path = TABLES_DIR / name
    return path if path.is_file() else None


def get_table_name(app_id: str) -> str | None:
    """Return just the filename of the bound table, or None."""
    data = _load_map()
    return data.get(app_id)
