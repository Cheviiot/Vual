"""Internationalization support for Vual.

Provides gettext-based translation functions.
"""

from __future__ import annotations

import gettext
import locale
import os
from pathlib import Path

# Application domain
DOMAIN = "vual"

# Locale directories to search (in order)
_PKG_DIR = Path(__file__).parent
_LOCALE_DIRS = [
    _PKG_DIR / "locale",                          # In-package (installed/compiled)
    Path("/usr/share/locale"),                    # System-wide
    Path("/usr/local/share/locale"),              # Local install
]

# Global translator
_translator: gettext.GNUTranslations | gettext.NullTranslations | None = None
_current_lang: str = "system"


def _find_locale_dir() -> Path | None:
    """Find the first existing locale directory."""
    for d in _LOCALE_DIRS:
        if d.is_dir():
            return d
    return None


def _get_system_lang() -> str:
    """Get language code from system locale."""
    lang = os.environ.get("LANGUAGE") or os.environ.get("LANG", "en_US.UTF-8")
    return lang.split(".")[0].split("_")[0]  # e.g., "ru" from "ru_RU.UTF-8"


def init(lang: str = "system") -> None:
    """Initialize translations.
    
    Args:
        lang: Language code ("system", "en", "ru"). 
              "system" uses system locale.
    """
    global _translator, _current_lang
    _current_lang = lang
    
    # Get system locale
    try:
        locale.setlocale(locale.LC_ALL, "")
    except locale.Error:
        pass
    
    # Determine language to use
    if lang == "system":
        lang_code = _get_system_lang()
    else:
        lang_code = lang
    
    locale_dir = _find_locale_dir()
    
    if locale_dir:
        try:
            _translator = gettext.translation(
                DOMAIN,
                localedir=str(locale_dir),
                languages=[lang_code],
                fallback=True,
            )
        except OSError:
            _translator = gettext.NullTranslations()
    else:
        _translator = gettext.NullTranslations()


def set_language(lang: str) -> None:
    """Change application language.
    
    Args:
        lang: Language code ("system", "en", "ru").
    """
    init(lang)


def get_current_language() -> str:
    """Get current language setting."""
    return _current_lang


def _(message: str) -> str:
    """Translate a message string."""
    global _translator
    if _translator is None:
        init()
    return _translator.gettext(message) if _translator else message


def ngettext(singular: str, plural: str, n: int) -> str:
    """Translate a plural message."""
    global _translator
    if _translator is None:
        init()
    return _translator.ngettext(singular, plural, n) if _translator else (singular if n == 1 else plural)


# Initialize on import
init()
