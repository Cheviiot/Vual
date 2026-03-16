"""Wine theme management for Proton prefixes.

Safely applies dark/light color schemes to Wine prefixes via registry.
Only modifies string and dword values — never touches binary/hex data.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterator

# Registry section pattern
_SECTION_RE = re.compile(r'^\[([^\]]+)\]', re.MULTILINE)

# Wine dark color scheme (Control Panel\Colors)
# Format: "R G B" strings
DARK_COLORS = {
    "ActiveBorder": "49 54 59",
    "ActiveTitle": "49 54 59",
    "AppWorkSpace": "30 30 30",
    "Background": "30 30 30",
    "ButtonAlternateFace": "49 54 59",
    "ButtonDkShadow": "20 20 20",
    "ButtonFace": "49 54 59",
    "ButtonHilight": "70 75 80",
    "ButtonLight": "60 65 70",
    "ButtonShadow": "35 38 41",
    "ButtonText": "230 230 230",
    "GradientActiveTitle": "49 54 59",
    "GradientInactiveTitle": "40 42 45",
    "GrayText": "128 128 128",
    "Hilight": "61 174 233",
    "HilightText": "255 255 255",
    "HotTrackingColor": "61 174 233",
    "InactiveBorder": "40 42 45",
    "InactiveTitle": "40 42 45",
    "InactiveTitleText": "128 128 128",
    "InfoText": "230 230 230",
    "InfoWindow": "49 54 59",
    "Menu": "49 54 59",
    "MenuBar": "49 54 59",
    "MenuHilight": "61 174 233",
    "MenuText": "230 230 230",
    "Scrollbar": "49 54 59",
    "TitleText": "230 230 230",
    "Window": "35 38 41",
    "WindowFrame": "49 54 59",
    "WindowText": "230 230 230",
}

# Standard light colors (Windows defaults)
LIGHT_COLORS = {
    "ActiveBorder": "180 180 180",
    "ActiveTitle": "153 180 209",
    "AppWorkSpace": "171 171 171",
    "Background": "0 0 0",
    "ButtonAlternateFace": "0 0 0",
    "ButtonDkShadow": "105 105 105",
    "ButtonFace": "240 240 240",
    "ButtonHilight": "255 255 255",
    "ButtonLight": "227 227 227",
    "ButtonShadow": "160 160 160",
    "ButtonText": "0 0 0",
    "GradientActiveTitle": "185 209 234",
    "GradientInactiveTitle": "215 228 242",
    "GrayText": "109 109 109",
    "Hilight": "0 120 215",
    "HilightText": "255 255 255",
    "HotTrackingColor": "0 102 204",
    "InactiveBorder": "244 247 252",
    "InactiveTitle": "191 205 219",
    "InactiveTitleText": "0 0 0",
    "InfoText": "0 0 0",
    "InfoWindow": "255 255 225",
    "Menu": "240 240 240",
    "MenuBar": "240 240 240",
    "MenuHilight": "0 120 215",
    "MenuText": "0 0 0",
    "Scrollbar": "200 200 200",
    "TitleText": "0 0 0",
    "Window": "255 255 255",
    "WindowFrame": "100 100 100",
    "WindowText": "0 0 0",
}

# Color scheme presets
COLOR_SCHEMES = {
    "dark": DARK_COLORS,
    "light": LIGHT_COLORS,
}

# DWM (Desktop Window Manager) settings for dark theme
# AccentColor is ABGR format as dword
DARK_DWM = {
    "AccentColor": 0xff3b3b3b,           # Dark gray accent
    "AccentColorInactive": 0xff2d2d2d,   # Darker inactive
    "ColorizationAfterglow": 0xc43b3b3b,
    "ColorizationColor": 0xc43b3b3b,
    "ColorizationColorBalance": 0x59,
    "ColorizationGlassAttribute": 0x01,
    "ColorPrevalence": 0x01,             # Use accent color on title bars
    "EnableWindowColorization": 0x01,
}

LIGHT_DWM = {
    "AccentColor": 0xffd77800,           # Blue accent (Windows default)
    "AccentColorInactive": 0xffdbdbdb,
    "ColorizationAfterglow": 0xc44f8bcd,
    "ColorizationColor": 0xc44f8bcd,
    "ColorizationColorBalance": 0x59,
    "ColorizationGlassAttribute": 0x01,
    "ColorPrevalence": 0x00,
    "EnableWindowColorization": 0x01,
}

DWM_SCHEMES = {
    "dark": DARK_DWM,
    "light": LIGHT_DWM,
}

# Explorer accent settings
DARK_EXPLORER = {
    "AccentColorMenu": 0xff3b3b3b,
}

LIGHT_EXPLORER = {
    "AccentColorMenu": 0xffd77800,
}

EXPLORER_SCHEMES = {
    "dark": DARK_EXPLORER,
    "light": LIGHT_EXPLORER,
}

# Vual's own Wine prefix
VUAL_PREFIX = Path.home() / ".local" / "share" / "vual" / "wine_prefix"


def get_vual_prefix() -> Path | None:
    """Return Vual's Wine prefix if it exists."""
    if VUAL_PREFIX.is_dir() and (VUAL_PREFIX / "user.reg").is_file():
        return VUAL_PREFIX
    return None


def get_all_prefixes(steamapps: Path) -> Iterator[Path]:
    """Yield all Proton prefix paths under steamapps/compatdata."""
    compatdata = steamapps / "compatdata"
    if not compatdata.is_dir():
        return
    
    for entry in compatdata.iterdir():
        if not entry.is_dir():
            continue
        # Skip non-numeric (not app IDs)
        if not entry.name.isdigit():
            continue
        
        pfx = entry / "pfx"
        if pfx.is_dir():
            yield pfx


def _find_or_create_section(lines: list[str], section_name: str) -> int:
    """Find section index or create it. Returns index of first line after section header.
    
    Wine registry sections can have timestamps: [Section\\Name] 1234567890
    We match by prefix to handle this.
    """
    target = f"[{section_name}]"
    target_lower = target.lower()
    
    for i, line in enumerate(lines):
        stripped = line.strip().lower()
        # Match exact or with timestamp suffix
        if stripped == target_lower or stripped.startswith(target_lower + " "):
            return i + 1
    
    # Section not found — add at end
    if lines and lines[-1].strip():
        lines.append("")
    lines.append(target)
    lines.append("")
    return len(lines) - 1


def _set_string_value(lines: list[str], section_idx: int, key: str, value: str) -> None:
    """Set a string value in registry section. Only modifies string values."""
    # Find section end (next section or EOF)
    section_end = len(lines)
    for i in range(section_idx, len(lines)):
        if lines[i].startswith("["):
            section_end = i
            break
    
    # Look for existing key
    key_pattern = f'"{key}"='
    for i in range(section_idx, section_end):
        if lines[i].startswith(key_pattern):
            lines[i] = f'"{key}"="{value}"'
            return
    
    # Key not found — insert before section end
    insert_at = section_end
    # Find last non-empty line in section
    for i in range(section_end - 1, section_idx - 1, -1):
        if lines[i].strip():
            insert_at = i + 1
            break
    
    lines.insert(insert_at, f'"{key}"="{value}"')


def _set_dword_value(lines: list[str], section_idx: int, key: str, value: int) -> None:
    """Set a dword value in registry section."""
    # Find section end (next section or EOF)
    section_end = len(lines)
    for i in range(section_idx, len(lines)):
        if lines[i].startswith("["):
            section_end = i
            break
    
    # Format: "Key"=dword:00000000
    dword_str = f'"{key}"=dword:{value:08x}'
    
    # Look for existing key
    key_pattern = f'"{key}"='
    for i in range(section_idx, section_end):
        if lines[i].startswith(key_pattern):
            lines[i] = dword_str
            return
    
    # Key not found — insert before section end
    insert_at = section_end
    for i in range(section_end - 1, section_idx - 1, -1):
        if lines[i].strip():
            insert_at = i + 1
            break
    
    lines.insert(insert_at, dword_str)


def apply_colors_to_prefix(pfx: Path, colors: dict[str, str], is_dark: bool) -> bool:
    """Apply color scheme to a single prefix.
    
    Modifies:
    - [Control Panel\\Colors] — color values as "R G B" strings
    - [Software\\Microsoft\\Windows\\CurrentVersion\\Themes\\Personalize] — dark mode flags
    
    Args:
        pfx: Path to prefix directory (containing user.reg).
        colors: Dict of color name -> "R G B" string values.
        is_dark: True for dark theme, False for light.
    
    Returns:
        True if successful, False otherwise.
    """
    user_reg = pfx / "user.reg"
    if not user_reg.is_file():
        return False
    
    try:
        content = user_reg.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    
    lines = content.splitlines()
    
    # Find or create Colors section
    colors_idx = _find_or_create_section(
        lines, 
        "Control Panel\\\\Colors"  # Escaped backslash for .reg format
    )
    
    # Apply each color
    for key, value in colors.items():
        _set_string_value(lines, colors_idx, key, value)
    
    # Find or create Personalize section (Windows 10+ dark mode)
    personalize_idx = _find_or_create_section(
        lines,
        "Software\\\\Microsoft\\\\Windows\\\\CurrentVersion\\\\Themes\\\\Personalize"
    )
    
    # Set dark mode flags: 0 = dark, 1 = light
    light_value = 0 if is_dark else 1
    _set_dword_value(lines, personalize_idx, "AppsUseLightTheme", light_value)
    _set_dword_value(lines, personalize_idx, "SystemUsesLightTheme", light_value)
    
    # Find or create DWM section for titlebar colors
    dwm_idx = _find_or_create_section(
        lines,
        "Software\\\\Microsoft\\\\Windows\\\\DWM"
    )
    
    # Apply DWM settings
    dwm_settings = DARK_DWM if is_dark else LIGHT_DWM
    for key, value in dwm_settings.items():
        _set_dword_value(lines, dwm_idx, key, value)
    
    # Find or create Explorer Accent section
    explorer_idx = _find_or_create_section(
        lines,
        "Software\\\\Microsoft\\\\Windows\\\\CurrentVersion\\\\Explorer\\\\Accent"
    )
    
    # Apply Explorer accent settings
    explorer_settings = DARK_EXPLORER if is_dark else LIGHT_EXPLORER
    for key, value in explorer_settings.items():
        _set_dword_value(lines, explorer_idx, key, value)
    
    # Find ThemeManager section and disable msstyles for dark theme
    # (Wine visual styles can override our color settings)
    theme_mgr_idx = _find_or_create_section(
        lines,
        "Software\\\\Microsoft\\\\Windows\\\\CurrentVersion\\\\ThemeManager"
    )
    
    if is_dark:
        # Disable visual styles to use our dark colors
        _set_string_value(lines, theme_mgr_idx, "ThemeActive", "0")
    else:
        _set_string_value(lines, theme_mgr_idx, "ThemeActive", "1")
    
    # Write back
    try:
        user_reg.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return True
    except OSError:
        return False


def apply_theme_to_all(steamapps: Path, theme: str) -> tuple[int, int]:
    """Apply theme to all Proton prefixes and Vual's own prefix.
    
    Args:
        steamapps: Path to Steam/steamapps directory.
        theme: Theme name ("dark", "light", or "system").
    
    Returns:
        Tuple of (success_count, fail_count).
    """
    if theme == "system" or theme not in COLOR_SCHEMES:
        return (0, 0)
    
    colors = COLOR_SCHEMES[theme]
    is_dark = (theme == "dark")
    success = 0
    failed = 0
    
    # Apply to Steam prefixes
    for pfx in get_all_prefixes(steamapps):
        if apply_colors_to_prefix(pfx, colors, is_dark):
            success += 1
        else:
            failed += 1
    
    # Apply to Vual's own prefix
    vual_pfx = get_vual_prefix()
    if vual_pfx:
        if apply_colors_to_prefix(vual_pfx, colors, is_dark):
            success += 1
        else:
            failed += 1
    
    return (success, failed)


def get_current_theme(pfx: Path) -> str | None:
    """Detect current theme from prefix colors.
    
    Returns:
        "dark", "light", or None if unknown.
    """
    user_reg = pfx / "user.reg"
    if not user_reg.is_file():
        return None
    
    try:
        content = user_reg.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    
    # Check Window background color
    match = re.search(r'"Window"="([^"]+)"', content)
    if not match:
        return None
    
    window_color = match.group(1)
    
    # Dark themes typically have dark Window color
    parts = window_color.split()
    if len(parts) == 3:
        try:
            r, g, b = int(parts[0]), int(parts[1]), int(parts[2])
            # If all RGB < 100, it's dark
            if r < 100 and g < 100 and b < 100:
                return "dark"
            # If all RGB > 200, it's light
            if r > 200 and g > 200 and b > 200:
                return "light"
        except ValueError:
            pass
    
    return None
