"""Configuration management for Vual.

Stores settings in ~/.config/vual/config.json
"""

import json
from dataclasses import dataclass, field
from pathlib import Path

_DEFAULT_PROTONHAX = str(Path.home() / ".local" / "share" / "vual" / "bin" / "protonhax")
_DEFAULT_TEMPLATE = f"{_DEFAULT_PROTONHAX} init %COMMAND%"
_DEFAULT_EXCLUDED = ["^Proton", "^Steam Linux Runtime"]

# Config file location
CONFIG_PATH = Path.home() / ".config" / "vual" / "config.json"


# Tile size presets: small=120, medium=150, large=180
TILE_SIZES = {"small": 120, "medium": 150, "large": 180}


@dataclass
class Config:
    """Application configuration.

    Attributes:
        ce_executable: Path to Cheat Engine executable.
        steam_path: Path to Steam installation directory.
        lookup_enabled: Whether to look up game info.
        launch_options_template: Template for Steam launch options.
        excluded_app_patterns: Regex patterns to exclude apps.
        window_width: Main window width.
        window_height: Main window height.
        color_scheme: Color scheme ("system", "light", "dark").
        tile_size: Tile size preset ("small", "medium", "large").
        sort_by: Sort order ("name", "status").
        ce_language: CE language ("system", "ru_RU").
        wine_theme: Wine color theme ("system", "dark", "light").
        app_language: Application UI language ("system", "en", "ru").
        transparent_window: Enable semi-transparent window background.
        guide_shown: Whether the startup guide has been shown.
    """

    ce_executable: str = "~/.local/share/vual/cheatengine/cheatengine-x86_64.exe"
    steam_path: str = "~/.local/share/Steam"
    lookup_enabled: bool = True
    launch_options_template: str = field(default_factory=lambda: _DEFAULT_TEMPLATE)
    excluded_app_patterns: list[str] = field(default_factory=lambda: _DEFAULT_EXCLUDED.copy())
    window_width: int = 1000
    window_height: int = 700
    color_scheme: str = "system"
    tile_size: str = "medium"
    sort_by: str = "name"
    ce_language: str = "system"
    wine_theme: str = "system"
    app_language: str = "system"
    transparent_window: bool = False
    guide_shown: bool = False

    # ════════════════════════════════════════════════════════════════
    # Load / Save
    # ════════════════════════════════════════════════════════════════

    @classmethod
    def load(cls) -> "Config":
        """Load configuration from JSON file.

        Returns:
            Config instance with loaded or default values.
        """
        if CONFIG_PATH.exists():
            try:
                data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
                return cls(
                    ce_executable=data.get("ce_executable", cls.ce_executable),
                    steam_path=data.get("steam_path", cls.steam_path),
                    lookup_enabled=data.get("lookup_enabled", cls.lookup_enabled),
                    launch_options_template=data.get("launch_options_template", _DEFAULT_TEMPLATE),
                    excluded_app_patterns=data.get("excluded_app_patterns", _DEFAULT_EXCLUDED.copy()),
                    window_width=data.get("window_width", cls.window_width),
                    window_height=data.get("window_height", cls.window_height),
                    color_scheme=data.get("color_scheme", cls.color_scheme),
                    tile_size=data.get("tile_size", cls.tile_size),
                    sort_by=data.get("sort_by", cls.sort_by),
                    ce_language=data.get("ce_language", cls.ce_language),
                    wine_theme=data.get("wine_theme", cls.wine_theme),
                    app_language=data.get("app_language", cls.app_language),
                    transparent_window=data.get("transparent_window", cls.transparent_window),
                    guide_shown=data.get("guide_shown", cls.guide_shown),
                )
            except (json.JSONDecodeError, OSError):
                pass
        return cls()

    def save(self) -> Path:
        """Save configuration to JSON file.

        Returns:
            Path to the saved config file.
        """
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "ce_executable": self.ce_executable,
            "steam_path": self.steam_path,
            "lookup_enabled": self.lookup_enabled,
            "launch_options_template": self.launch_options_template,
            "excluded_app_patterns": self.excluded_app_patterns,
            "window_width": self.window_width,
            "window_height": self.window_height,
            "color_scheme": self.color_scheme,
            "tile_size": self.tile_size,
            "sort_by": self.sort_by,
            "ce_language": self.ce_language,
            "wine_theme": self.wine_theme,
            "app_language": self.app_language,
            "transparent_window": self.transparent_window,
            "guide_shown": self.guide_shown,
        }
        CONFIG_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        return CONFIG_PATH

    # ════════════════════════════════════════════════════════════════
    # Derived Paths
    # ════════════════════════════════════════════════════════════════

    @property
    def steamapps_path(self) -> Path:
        """Path to Steam's steamapps directory."""
        return Path(self.steam_path).expanduser() / "steamapps"

    @property
    def ce_executable_path(self) -> Path:
        """Expanded path to CE executable."""
        return Path(self.ce_executable).expanduser()

    @property
    def ce_exists(self) -> bool:
        """Check if CE executable exists."""
        return self.ce_executable_path.is_file()
