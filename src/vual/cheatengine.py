"""Cheat Engine management: download, extraction, and version detection.

Provides functionality for:
- Fetching latest CE release info from cheatengine.org
- Downloading the installer with progress reporting
- Extracting using Wine from Proton (silent install)
- Detecting CE version from installed files
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import TYPE_CHECKING

import requests

if TYPE_CHECKING:
    from collections.abc import Callable

# Official Cheat Engine download page
CE_DOWNLOADS_URL = "https://cheatengine.org/downloads.php"

# Known Proton versions to search for Wine binary
_PROTON_DIRS = [
    "Proton - Experimental",
    "Proton 9.0",
    "Proton 8.0",
    "Proton 7.0",
]

# CE executable names in order of preference
_CE_EXECUTABLES = [
    "cheatengine-x86_64.exe",
    "cheatengine-i386.exe",
    "Cheat Engine.exe",
]


# ════════════════════════════════════════════════════════════════
# Release Info
# ════════════════════════════════════════════════════════════════


def get_latest_release() -> dict[str, str | int | None] | None:
    """Fetch latest Cheat Engine release info from official website.

    Scrapes cheatengine.org/downloads.php for the Windows installer link.

    Returns:
        Dict with keys: version, url, name, size (or None on error).
    """
    try:
        resp = requests.get(CE_DOWNLOADS_URL, timeout=15)
        resp.raise_for_status()
        text = resp.text

        # Extract version (e.g. "Cheat Engine 7.6")
        ver_m = re.search(r"Cheat Engine\s+([\d.]+)", text)
        version = ver_m.group(1) if ver_m else "unknown"

        # Find the first cloudfront .exe link (Windows installer)
        exe_m = re.search(r'href="(https://[^"]*cloudfront[^"]*\.exe)"', text, re.I)
        if not exe_m:
            return {"version": version, "url": None, "name": None, "size": 0}

        url = exe_m.group(1)
        name = f"CheatEngine{version.replace('.', '')}.exe"

        # Get file size via HEAD request
        size = 0
        try:
            head = requests.head(url, allow_redirects=True, timeout=10)
            size = int(head.headers.get("content-length", 0))
        except requests.RequestException:
            pass

        return {"version": version, "url": url, "name": name, "size": size}
    except (requests.RequestException, ValueError):
        return None


# ════════════════════════════════════════════════════════════════
# Download
# ════════════════════════════════════════════════════════════════


def download_file(
    url: str,
    dest: Path,
    progress_cb: Callable[[float], None] | None = None,
) -> bool:
    """Download a file with optional progress reporting.

    Args:
        url: URL to download.
        dest: Destination path for the file.
        progress_cb: Optional callback receiving progress (0.0-1.0).

    Returns:
        True on success, False on error.
    """
    try:
        resp = requests.get(url, stream=True, timeout=120)
        resp.raise_for_status()
        total = int(resp.headers.get("content-length", 0))
        downloaded = 0
        dest.parent.mkdir(parents=True, exist_ok=True)
        with open(dest, "wb") as f:
            for chunk in resp.iter_content(chunk_size=65536):
                f.write(chunk)
                downloaded += len(chunk)
                if progress_cb and total > 0:
                    progress_cb(downloaded / total)
        return True
    except requests.RequestException:
        return False


# ════════════════════════════════════════════════════════════════
# Proton Wine Discovery
# ════════════════════════════════════════════════════════════════


def find_proton_wine(steam_path: str = "~/.local/share/Steam") -> Path | None:
    """Find a Wine binary bundled with a Proton installation.

    Searches common Proton versions first, then falls back to any
    Proton directory in steamapps/common.

    Args:
        steam_path: Path to Steam installation (can use ~).

    Returns:
        Path to Wine binary, or None if not found.
    """
    steamapps = Path(steam_path).expanduser() / "steamapps" / "common"
    if not steamapps.is_dir():
        return None
    for name in _PROTON_DIRS:
        wine = steamapps / name / "files" / "bin" / "wine"
        if wine.is_file():
            return wine
    # Fallback: search any Proton directory
    for d in sorted(steamapps.iterdir(), reverse=True):
        if d.name.lower().startswith("proton"):
            wine = d / "files" / "bin" / "wine"
            if wine.is_file():
                return wine
    return None


# ════════════════════════════════════════════════════════════════
# Extraction
# ════════════════════════════════════════════════════════════════


def can_extract(steam_path: str = "~/.local/share/Steam") -> str | None:
    """Check if extraction is possible.

    Args:
        steam_path: Path to Steam installation.

    Returns:
        Name of extraction method ("wine") or None if unavailable.
    """
    if find_proton_wine(steam_path):
        return "wine"
    return None


def extract_installer(
    installer: Path,
    dest_dir: Path,
    steam_path: str = "~/.local/share/Steam",
) -> bool:
    """Extract Cheat Engine installer into destination directory.

    Uses Wine from Proton to run the silent installer. The CE installer
    is wrapped by zbShield which doesn't exit cleanly in silent mode,
    so we poll for completion and kill the process.

    Args:
        installer: Path to CE installer executable.
        dest_dir: Destination directory for extracted files.
        steam_path: Path to Steam installation.

    Returns:
        True on success, False on error.
    """
    wine = find_proton_wine(steam_path)
    if not wine:
        return False
    return _extract_via_wine(wine, installer, dest_dir)


def _extract_via_wine(wine: Path, installer: Path, dest_dir: Path) -> bool:
    """Run CE installer silently via Proton Wine and copy results."""
    cache_dir = Path.home() / ".cache" / "vual"
    cache_dir.mkdir(parents=True, exist_ok=True)
    wineserver = wine.parent / "wineserver"

    with tempfile.TemporaryDirectory(dir=cache_dir, prefix="ce_install_") as tmpdir:
        prefix = Path(tmpdir) / "prefix"
        prefix.mkdir()

        env = dict(os.environ)
        env.update({
            "WINEPREFIX": str(prefix),
            "WINEDLLOVERRIDES": "mshtml=d",
            "WINEDEBUG": "-all",
            "PATH": str(wine.parent) + ":" + env.get("PATH", ""),
        })

        # Initialize Wine prefix
        try:
            subprocess.run(
                [str(wine), "wineboot", "--init"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=120,
                env=env,
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            pass

        # Launch installer as a background process — zbShield wrapper
        # never exits cleanly in silent mode, so we poll for results.
        proc = subprocess.Popen(
            [
                str(wine),
                str(installer),
                "/VERYSILENT",
                "/SUPPRESSMSGBOXES",
                "/NORESTART",
                "/SP-",
                "/NORUN",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=env,
        )

        ce_src = prefix / "drive_c" / "Program Files" / "Cheat Engine"
        marker = ce_src / "cheatengine-x86_64.exe"
        completion = ce_src / "unins000.exe"

        # Poll until both the 64-bit CE exe AND the uninstaller appear
        # and the total file count stabilises for 3 consecutive seconds.
        prev_count = 0
        stable = 0
        try:
            for _ in range(180):  # max 3 minutes
                time.sleep(1)
                if marker.is_file() and completion.is_file():
                    cur = sum(1 for _ in ce_src.rglob("*"))
                    if cur == prev_count and cur > 50:
                        stable += 1
                        if stable >= 3:
                            break
                    else:
                        stable = 0
                    prev_count = cur
            else:
                # Timeout — use whatever we have if any
                if not ce_src.is_dir():
                    return False
        finally:
            proc.kill()
            try:
                subprocess.run(
                    [str(wineserver), "-k"],
                    env=env,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=10,
                )
            except (subprocess.TimeoutExpired, FileNotFoundError):
                pass
            time.sleep(1)

        if not ce_src.is_dir():
            return False

        # Move installed files to dest_dir
        dest_dir.mkdir(parents=True, exist_ok=True)
        for item in ce_src.iterdir():
            target = dest_dir / item.name
            if target.exists():
                if target.is_dir():
                    shutil.rmtree(target)
                else:
                    target.unlink()
            shutil.move(str(item), str(target))

        return True


# ════════════════════════════════════════════════════════════════
# Executable Detection
# ════════════════════════════════════════════════════════════════


def find_executable(search_dir: Path) -> Path | None:
    """Find the main CE executable in a directory.

    Searches for known CE executable names in order of preference.

    Args:
        search_dir: Directory to search recursively.

    Returns:
        Path to CE executable, or None if not found.
    """
    # Try known names first
    for name in _CE_EXECUTABLES:
        for hit in search_dir.rglob(name):
            return hit
    # Fallback: any cheatengine*.exe
    for hit in search_dir.rglob("cheatengine*.exe"):
        return hit
    return None


def detect_version(ce_path: Path) -> str | None:
    """Detect CE version from file names or paths.

    Args:
        ce_path: Path to CE installation.

    Returns:
        Version string (e.g., "7.6") or None if not detected.
    """
    # Check installer filename in cache (e.g. CheatEngine76.exe → 7.6)
    cache = Path.home() / ".cache" / "vual"
    if cache.is_dir():
        for f in cache.iterdir():
            if f.suffix == ".exe" and "cheatengine" in f.name.lower():
                m = re.search(r"(\d)(\d+)", f.stem)
                if m:
                    return f"{m.group(1)}.{m.group(2)}"

    # Check parent directory name
    for part in ce_path.parts:
        m = re.search(r"[Cc]heat.?[Ee]ngine\s*(\d+\.?\d*)", part)
        if m:
            return m.group(1)
    return None


# ════════════════════════════════════════════════════════════════
# Localization
# ════════════════════════════════════════════════════════════════

# Russian localization from official CE repo
_LOCALIZATION_API = (
    "https://api.github.com/repos/cheat-engine/cheat-engine/contents/"
    "Cheat%20Engine/bin/languages/ru_RU"
)
_LOCALIZATION_RAW = (
    "https://raw.githubusercontent.com/cheat-engine/cheat-engine/master/"
    "Cheat%20Engine/bin/languages/ru_RU/"
)
_LOCALIZATION_DIR = "ru_RU"


def get_languages_dir(ce_path: Path) -> Path | None:
    """Get the languages directory for CE installation.

    Args:
        ce_path: Path to CE executable.

    Returns:
        Path to languages directory, or None if invalid.
    """
    if ce_path.is_file():
        return ce_path.parent / "languages"
    return None


def is_localization_installed(ce_path: Path) -> bool:
    """Check if Russian localization is installed.

    Args:
        ce_path: Path to CE executable.

    Returns:
        True if ru_RU directory exists with .po files.
    """
    lang_dir = get_languages_dir(ce_path)
    if not lang_dir:
        return False
    ru_dir = lang_dir / _LOCALIZATION_DIR
    if not ru_dir.is_dir():
        return False
    # Check for at least one .po file
    return any(ru_dir.glob("*.po"))


def _get_localization_files() -> list[str]:
    """Fetch list of files in ru_RU localization directory from GitHub API."""
    try:
        resp = requests.get(_LOCALIZATION_API, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, list):
            return [item["name"] for item in data if item.get("type") == "file"]
    except (requests.RequestException, ValueError, KeyError):
        pass
    return []


def install_localization(
    ce_path: Path,
    progress_cb: Callable[[float], None] | None = None,
) -> bool:
    """Download and install Russian localization for Cheat Engine.

    Downloads ru_RU localization files from official CE repository
    and places them in the languages/ru_RU directory.

    Args:
        ce_path: Path to CE executable.
        progress_cb: Optional callback receiving progress (0.0-1.0).

    Returns:
        True on success, False on error.
    """
    lang_dir = get_languages_dir(ce_path)
    if not lang_dir:
        return False

    ru_dir = lang_dir / _LOCALIZATION_DIR
    ru_dir.mkdir(parents=True, exist_ok=True)

    files = _get_localization_files()
    if not files:
        return False

    total = len(files)
    downloaded = 0

    for filename in files:
        url = _LOCALIZATION_RAW + filename
        dest = ru_dir / filename
        try:
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
            dest.write_bytes(resp.content)
            downloaded += 1
            if progress_cb:
                progress_cb(downloaded / total)
        except requests.RequestException:
            # Continue with other files
            pass

    # Success if at least the main .po file downloaded
    return (ru_dir / "cheatengine-x86_64.po").is_file()
