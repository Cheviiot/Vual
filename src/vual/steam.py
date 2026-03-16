"""Steam integration: VDF parsing, game discovery, and LaunchOptions management.

Core functionality:
- VDF (Valve Data File) parsing and writing
- Steam game discovery from appmanifest files
- LaunchOptions manipulation in localconfig.vdf
- Steam process control (detection, shutdown, restart)
"""

from __future__ import annotations

import re
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

# ── VDF parser / writer ──────────────────────────────────────────


def parse_vdf(content: str) -> dict[str, object]:
    """Parse Valve VDF text format into nested dictionaries.

    VDF is a key-value format used by Valve in Steam configuration files.
    Supports nested sections (dictionaries) and string values.

    Args:
        content: Raw VDF text content.

    Returns:
        Nested dict structure representing the VDF data.

    Example VDF:
        "UserLocalConfigStore"
        {
            "Software"
            {
                "Valve" "SomeValue"
            }
        }
    """

    def tokenize(text: str) -> list[tuple[str, str]]:
        tokens: list[tuple[str, str]] = []
        i = 0
        while i < len(text):
            if text[i].isspace():
                i += 1
            elif text[i : i + 2] == "//":
                while i < len(text) and text[i] != "\n":
                    i += 1
            elif text[i] == '"':
                i += 1
                start = i
                while i < len(text) and text[i] != '"':
                    i += 1
                tokens.append(("S", text[start:i]))
                i += 1
            elif text[i] in "{}":
                tokens.append(("B", text[i]))
                i += 1
            else:
                i += 1
        return tokens

    def parse_tokens(tokens: list, idx: int = 0) -> tuple[dict, int]:
        result: dict = {}
        while idx < len(tokens):
            tt, tv = tokens[idx]
            if tt == "S":
                key = tv
                idx += 1
                if idx >= len(tokens):
                    break
                nt, nv = tokens[idx]
                if nt == "B" and nv == "{":
                    idx += 1
                    nested, idx = parse_tokens(tokens, idx)
                    result[key] = nested
                elif nt == "S":
                    result[key] = nv
                    idx += 1
                elif nt == "B" and nv == "}":
                    break
            elif tt == "B" and tv == "}":
                idx += 1
                break
            else:
                idx += 1
        return result, idx

    tokens = tokenize(content)
    parsed, _ = parse_tokens(tokens)
    return parsed


def write_vdf(data: dict[str, object], indent: int = 0) -> str:
    """Serialize nested dictionaries into Valve VDF text format.

    Args:
        data: Dictionary to serialize.
        indent: Current indentation level (used internally for recursion).

    Returns:
        VDF-formatted string.
    """
    lines: list[str] = []
    tab = "\t" * indent
    for key, value in data.items():
        if isinstance(value, dict):
            lines.append(f'{tab}"{key}"')
            lines.append(f"{tab}{{")
            lines.append(write_vdf(value, indent + 1).rstrip())
            lines.append(f"{tab}}}")
        else:
            lines.append(f'{tab}"{key}"\t\t"{value}"')
    return "\n".join(lines) + "\n"


# ════════════════════════════════════════════════════════════════
# Config Discovery
# ════════════════════════════════════════════════════════════════


def find_localconfig_vdf(steam_path: str) -> Path | None:
    """Find the first localconfig.vdf file in Steam's userdata directory.

    This file contains per-user Steam settings including LaunchOptions
    for each game.

    Args:
        steam_path: Path to Steam installation directory (can use ~).

    Returns:
        Path to localconfig.vdf if found, None otherwise.
    """
    userdata = Path(steam_path).expanduser() / "userdata"
    if not userdata.exists():
        return None
    for cfg in userdata.rglob("localconfig.vdf"):
        return cfg
    return None


# ════════════════════════════════════════════════════════════════
# Game Manifest Reading
# ════════════════════════════════════════════════════════════════

# Cache for compiled regex patterns to avoid recompilation
_EXCLUDE_PATTERNS_CACHE: dict[tuple[str, ...], list[re.Pattern[str]]] = {}


def _get_compiled_patterns(patterns: Sequence[str] | None) -> list[re.Pattern[str]]:
    """Compile and cache exclusion regex patterns."""
    if not patterns:
        return []
    key = tuple(patterns)
    if key not in _EXCLUDE_PATTERNS_CACHE:
        _EXCLUDE_PATTERNS_CACHE[key] = [re.compile(p, re.IGNORECASE) for p in patterns]
    return _EXCLUDE_PATTERNS_CACHE[key]


def is_app_excluded(app_name: str, patterns: Sequence[str] | None) -> bool:
    """Check if app name matches any exclusion pattern.

    Args:
        app_name: Name of the Steam app.
        patterns: List of regex patterns to check against.

    Returns:
        True if app should be excluded.
    """
    return any(pat.search(app_name) for pat in _get_compiled_patterns(patterns))


def get_game_info(app_id: str, steamapps: Path) -> dict[str, str]:
    """Read game information from appmanifest_<id>.acf.

    Args:
        app_id: Steam app ID.
        steamapps: Path to steamapps directory.

    Returns:
        Dict with keys: app_id, name, install_dir.
    """
    info: dict[str, str] = {"app_id": app_id, "name": f"Game {app_id}", "install_dir": ""}
    manifest = steamapps / f"appmanifest_{app_id}.acf"
    if not manifest.exists():
        return info

    try:
        text = manifest.read_text()
    except OSError:
        return info

    for line in text.splitlines():
        line = line.strip()
        if line.startswith('"name"'):
            parts = line.split('"', 3)
            if len(parts) >= 4:
                info["name"] = parts[3].rstrip('"')
        elif line.startswith('"installdir"'):
            parts = line.split('"', 3)
            if len(parts) >= 4:
                info["install_dir"] = parts[3].rstrip('"')
    return info


def get_installed_games(
    steamapps: Path,
    excluded_patterns: Sequence[str] | None = None,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """Get lists of installed Steam games.

    Args:
        steamapps: Path to steamapps directory.
        excluded_patterns: Regex patterns for apps to exclude.

    Returns:
        Tuple of (included_games, excluded_games), sorted by name.
    """
    included: list[dict[str, str]] = []
    excluded: list[dict[str, str]] = []

    if not steamapps.exists():
        return included, excluded
    for mf in steamapps.glob("appmanifest_*.acf"):
        aid = mf.stem.replace("appmanifest_", "")
        if not aid.isdigit():
            continue
        info = get_game_info(aid, steamapps)
        if is_app_excluded(info["name"], excluded_patterns):
            excluded.append(info)
        else:
            included.append(info)
    included.sort(key=lambda g: g["name"].lower())
    excluded.sort(key=lambda g: g["name"].lower())
    return included, excluded


# ════════════════════════════════════════════════════════════════
# LaunchOptions Management
# ════════════════════════════════════════════════════════════════

# VDF path to the apps section
_VDF_APP_PATH = ["UserLocalConfigStore", "Software", "Valve", "Steam", "apps"]


def _navigate_to_apps(data: dict[str, object]) -> dict[str, object] | None:
    """Navigate parsed VDF dict to the apps section.

    Path: UserLocalConfigStore -> Software -> Valve -> Steam -> apps
    """
    try:
        root = data.get("UserLocalConfigStore", data)
        return root.get("Software", {}).get("Valve", {}).get("Steam", {}).get("apps", {})
    except (TypeError, AttributeError):
        return None


def _navigate_vdf_lines(lines: list[str], path: list[str]) -> tuple[int, int]:
    """Navigate VDF text lines to find a section by key path.

    Args:
        lines: VDF file content split by lines.
        path: List of section keys to navigate.

    Returns:
        Tuple of (brace_line_index, brace_depth) for the opening brace
        of the target section, or (-1, -1) if not found.
    """
    target_idx = 0
    brace_depth = 0
    pending_key: str | None = None

    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped.startswith("//"):
            continue

        if stripped == "{":
            brace_depth += 1
            if (
                pending_key is not None
                and target_idx < len(path)
                and pending_key == path[target_idx]
                and brace_depth == target_idx + 1
            ):
                target_idx += 1
                if target_idx == len(path):
                    return i, brace_depth
            pending_key = None
            continue

        if stripped == "}":
            brace_depth -= 1
            pending_key = None
            continue

        m = re.match(r'^"([^"]*)"', stripped)
        if not m:
            pending_key = None
            continue

        rest = stripped[m.end() :].strip()
        if rest:
            # key-value pair on one line
            pending_key = None
        else:
            # section header — next line should be "{"
            pending_key = m.group(1)

    return -1, -1


def get_launch_options(app_id: str, localconfig_path: Path) -> str | None:
    """Return LaunchOptions string for app_id, or None if not set."""
    try:
        data = parse_vdf(localconfig_path.read_text())
    except OSError:
        return None
    apps = _navigate_to_apps(data)
    if not apps:
        return None
    section = apps.get(app_id) if isinstance(apps, dict) else None
    if isinstance(section, dict):
        return section.get("LaunchOptions")
    return None


def set_launch_options(app_id: str, value: str, localconfig_path: Path) -> bool:
    """Set LaunchOptions for *app_id* via surgical text edit (no full reserialization)."""
    try:
        text = localconfig_path.read_text()
    except OSError:
        return False

    old = get_launch_options(app_id, localconfig_path)
    if old and old != value:
        _create_backup(app_id, old)

    lines = text.splitlines(keepends=True)
    app_path = _VDF_APP_PATH + [app_id]
    brace_idx, brace_depth = _navigate_vdf_lines(lines, app_path)

    if brace_idx >= 0:
        # App section exists — find LaunchOptions or closing '}'
        launch_idx = -1
        close_idx = -1
        depth = brace_depth

        for i in range(brace_idx + 1, len(lines)):
            stripped = lines[i].strip()
            if not stripped or stripped.startswith("//"):
                continue
            if stripped == "{":
                depth += 1
                continue
            if stripped == "}":
                if depth == brace_depth:
                    close_idx = i
                    break
                depth -= 1
                continue
            if depth == brace_depth:
                km = re.match(r'^"([^"]*)"', stripped)
                if km and km.group(1) == "LaunchOptions":
                    launch_idx = i
                    break

        if launch_idx >= 0:
            old_line = lines[launch_idx]
            indent = old_line[: len(old_line) - len(old_line.lstrip())]
            lines[launch_idx] = f'{indent}"LaunchOptions"\t\t"{value}"\n'
        elif close_idx >= 0:
            cl = lines[close_idx]
            indent = cl[: len(cl) - len(cl.lstrip())] + "\t"
            lines.insert(close_idx, f'{indent}"LaunchOptions"\t\t"{value}"\n')
        else:
            return False
    else:
        # App section missing — create it inside "apps"
        apps_idx, apps_depth = _navigate_vdf_lines(lines, _VDF_APP_PATH)
        if apps_idx < 0:
            return False
        ai = lines[apps_idx][: len(lines[apps_idx]) - len(lines[apps_idx].lstrip())]
        ki = ai + "\t"
        vi = ki + "\t"
        block = [
            f'{ki}"{app_id}"\n',
            f"{ki}{{\n",
            f'{vi}"LaunchOptions"\t\t"{value}"\n',
            f"{ki}}}\n",
        ]
        for j, nl in enumerate(block):
            lines.insert(apps_idx + 1 + j, nl)

    try:
        localconfig_path.write_text("".join(lines))
        return True
    except OSError:
        return False


def remove_launch_options(app_id: str, localconfig_path: Path) -> bool:
    """Remove LaunchOptions for *app_id* via surgical text edit."""
    try:
        text = localconfig_path.read_text()
    except OSError:
        return False

    old = get_launch_options(app_id, localconfig_path)
    if not old:
        return False

    _create_backup(app_id, old)

    lines = text.splitlines(keepends=True)
    app_path = _VDF_APP_PATH + [app_id]
    brace_idx, brace_depth = _navigate_vdf_lines(lines, app_path)
    if brace_idx < 0:
        return False

    depth = brace_depth
    for i in range(brace_idx + 1, len(lines)):
        stripped = lines[i].strip()
        if not stripped or stripped.startswith("//"):
            continue
        if stripped == "{":
            depth += 1
            continue
        if stripped == "}":
            if depth == brace_depth:
                break
            depth -= 1
            continue
        if depth == brace_depth:
            km = re.match(r'^"([^"]*)"', stripped)
            if km and km.group(1) == "LaunchOptions":
                del lines[i]
                try:
                    localconfig_path.write_text("".join(lines))
                    return True
                except OSError:
                    return False
    return False


def _create_backup(game_id: str, original: str) -> None:
    """Create a backup file with the original LaunchOptions value."""
    backup_dir = Path.home() / ".local" / "share" / "vual" / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = backup_dir / f"launch_options_backup_{ts}.md"
    line = f"| {game_id} | {original} |\n"

    if backup.exists():
        with open(backup, "a") as f:
            f.write(line)
    else:
        with open(backup, "w") as f:
            f.write("# Launch Options Backup\n\n")
            f.write(f"Generated: {datetime.now().isoformat()}\n\n")
            f.write("| Game ID | Original LaunchOptions |\n")
            f.write("|---------|------------------------|\n")
            f.write(line)


# ════════════════════════════════════════════════════════════════
# Steam Process Control
# ════════════════════════════════════════════════════════════════


def is_steam_running() -> bool:
    """Check if the Steam client process is currently running.

    Uses /proc filesystem to detect Steam process.
    Excludes steamwebhelper processes.

    Returns:
        True if Steam main process is running.
    """
    proc = Path("/proc")
    if not proc.is_dir():
        return False
    for pid_dir in proc.iterdir():
        if not pid_dir.name.isdigit():
            continue
        try:
            cmdline = (pid_dir / "cmdline").read_bytes()
        except OSError:
            continue
        first_arg = cmdline.split(b"\x00", 1)[0]
        if first_arg.endswith(b"/steam") and b"steamwebhelper" not in cmdline:
            return True
    return False


def shutdown_steam() -> None:
    """Request a graceful Steam shutdown via CLI command."""
    subprocess.Popen(
        ["steam", "-shutdown"],
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def wait_steam_exit(timeout: float = 30.0) -> bool:
    """Wait for Steam to exit.

    Args:
        timeout: Maximum time to wait in seconds.

    Returns:
        True if Steam exited, False if timeout reached.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not is_steam_running():
            return True
        time.sleep(0.5)
    return False


def start_steam() -> None:
    """Launch Steam in the background."""
    subprocess.Popen(
        ["steam"],
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
