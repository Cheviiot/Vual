"""Integrated protonhax — list & run Proton games, manage init script."""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
from pathlib import Path

# ── Managed paths ────────────────────────────────────────────────

MANAGED_DIR = Path.home() / ".local" / "share" / "vual" / "bin"
MANAGED_PATH = MANAGED_DIR / "protonhax"


def _runtime_dir() -> Path:
    xdg = os.environ.get("XDG_RUNTIME_DIR")
    if xdg:
        return Path(xdg) / "protonhax"
    return Path(f"/run/user/{os.getuid()}") / "protonhax"


# ── List running games ──────────────────────────────────────────


def list_running() -> list[str]:
    """Return app IDs of currently running Proton games."""
    phd = _runtime_dir()
    if not phd.is_dir():
        return []
    return sorted(d.name for d in phd.iterdir() if d.is_dir() and d.name.isdigit())


# ── Game context ────────────────────────────────────────────────

_ENV_RE = re.compile(r'^declare\s+-x\s+(\w+)="(.*)"$')


def _parse_bash_env(text: str) -> dict[str, str]:
    env: dict[str, str] = {}
    for line in text.splitlines():
        m = _ENV_RE.match(line)
        if m:
            env[m.group(1)] = m.group(2)
    return env


def get_game_context(app_id: str) -> dict | None:
    """Return {app_id, proton_exe, prefix, env} for a running game, or None."""
    game_dir = _runtime_dir() / app_id
    if not game_dir.is_dir():
        return None

    ctx: dict = {"app_id": app_id}

    exe_file = game_dir / "exe"
    if exe_file.exists():
        ctx["proton_exe"] = exe_file.read_text().strip()

    pfx_file = game_dir / "pfx"
    if pfx_file.exists():
        ctx["prefix"] = pfx_file.read_text().strip()

    env_file = game_dir / "env"
    if env_file.exists():
        ctx["env"] = _parse_bash_env(env_file.read_text())

    return ctx


# ── Run in Proton context ───────────────────────────────────────


def run_in_proton(
    app_id: str,
    executable: str,
    args: list[str] | None = None,
) -> subprocess.Popen | None:
    """Launch *executable* inside the Proton context of *app_id*.
    
    Args:
        app_id: Steam app ID.
        executable: Path to Windows executable.
        args: Optional list of arguments to pass to the executable.
    """
    ctx = get_game_context(app_id)
    if not ctx or "proton_exe" not in ctx:
        return None

    env = os.environ.copy()
    if "env" in ctx:
        env.update(ctx["env"])

    proton_exe = ctx["proton_exe"]
    cmd = [proton_exe, "run", executable]
    if args:
        cmd.extend(args)
    return subprocess.Popen(
        cmd,
        env=env,
        start_new_session=True,
    )


# ── Protonhax detection & management ────────────────────────────


def find_installed() -> str | None:
    """Return the path to protonhax (managed first, then system), or None."""
    if MANAGED_PATH.is_file():
        return str(MANAGED_PATH)
    return shutil.which("protonhax")


def is_managed() -> bool:
    """True if the managed copy exists."""
    return MANAGED_PATH.is_file()


def _script_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def needs_update() -> bool:
    """True if the managed copy exists but differs from the bundled version."""
    if not MANAGED_PATH.is_file():
        return False
    try:
        installed = MANAGED_PATH.read_text()
    except OSError:
        return True
    return _script_hash(installed) != _script_hash(INIT_SCRIPT)


def ensure_installed() -> Path:
    """Install the managed protonhax if missing or outdated. Returns its path."""
    if not MANAGED_PATH.is_file() or needs_update():
        return install_init_script(MANAGED_PATH)
    return MANAGED_PATH


# ── Bundled init script ─────────────────────────────────────────

INIT_SCRIPT = r"""#!/bin/bash
# protonhax — managed by Vual
# https://github.com/jcnils/protonhax (original)

phd=${XDG_RUNTIME_DIR:-/run/user/$UID}/protonhax

usage() {
    echo "Usage:"
    echo "protonhax init <cmd>"
    printf "\tShould only be called by Steam with \"protonhax init %%COMMAND%%\"\n"
    echo "protonhax ls"
    printf "\tLists all currently running games\n"
    echo "protonhax run <appid> <cmd>"
    printf "\tRuns <cmd> in the context of <appid> with proton\n"
    echo "protonhax cmd <appid>"
    printf "\tRuns cmd.exe in the context of <appid>\n"
    echo "protonhax exec <appid> <cmd>"
    printf "\tRuns <cmd> in the context of <appid>\n"
}

if [[ $# -lt 1 ]]; then
    usage
    exit 1
fi

c=$1
shift

if [[ "$c" == "init" ]]; then
    mkdir -p "$phd/$SteamAppId"
    printf "%s\n" "${@}" | grep -m 1 "/proton" > "$phd/$SteamAppId/exe"
    printf "%s" "$STEAM_COMPAT_DATA_PATH/pfx" > "$phd/$SteamAppId/pfx"
    declare -px > "$phd/$SteamAppId/env"
    "$@"
    ec=$?
    rm -r "$phd/$SteamAppId"
    exit $ec
elif [[ "$c" == "ls" ]]; then
    if [[ -d "$phd" ]]; then
        ls -1 "$phd"
    fi
elif [[ "$c" == "run" ]] || [[ "$c" == "cmd" ]] || [[ "$c" == "exec" ]]; then
    if [[ $# -lt 1 ]]; then
        usage
        exit 1
    fi
    if [[ ! -d "$phd" ]]; then
        printf "No app running with appid \"%s\"\n" "$1"
        exit 2
    fi
    if [[ ! -d "$phd/$1" ]]; then
        printf "No app running with appid \"%s\"\n" "$1"
        exit 2
    fi
    SteamAppId=$1
    shift

    source "$phd/$SteamAppId/env"

    if [[ "$c" == "run" ]]; then
        if [[ $# -lt 1 ]]; then
            usage
            exit 1
        fi
        exec "$(cat "$phd/$SteamAppId/exe")" run "$@"
    elif [[ "$c" == "cmd" ]]; then
        exec "$(cat "$phd/$SteamAppId/exe")" run "$(cat "$phd/$SteamAppId/pfx")/drive_c/windows/system32/cmd.exe"
    elif [[ "$c" == "exec" ]]; then
        if [[ $# -lt 1 ]]; then
            usage
            exit 1
        fi
        exec "$@"
    fi
else
    printf "Unknown command %s\n" "$c"
    usage
    exit 1
fi
"""


def install_init_script(target: Path | None = None) -> Path:
    """Write the protonhax shell script to *target* and make it executable."""
    if target is None:
        target = MANAGED_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(INIT_SCRIPT)
    target.chmod(0o755)
    return target
