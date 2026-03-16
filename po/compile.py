#!/usr/bin/env python3
"""Compile .po files to .mo files for runtime use."""

import subprocess
import sys
from pathlib import Path

PO_DIR = Path(__file__).parent
LOCALE_DIR = PO_DIR.parent / "src" / "vual" / "locale"


def compile_po():
    """Compile all .po files to .mo files."""
    for po_file in PO_DIR.glob("*.po"):
        lang = po_file.stem
        mo_dir = LOCALE_DIR / lang / "LC_MESSAGES"
        mo_dir.mkdir(parents=True, exist_ok=True)
        mo_file = mo_dir / "vual.mo"
        
        print(f"Compiling {po_file.name} -> {mo_file.relative_to(PO_DIR.parent)}")
        
        try:
            subprocess.run(
                ["msgfmt", "-o", str(mo_file), str(po_file)],
                check=True,
            )
        except FileNotFoundError:
            print("Error: msgfmt not found. Install gettext:")
            print("  sudo apt install gettext")
            sys.exit(1)
        except subprocess.CalledProcessError as e:
            print(f"Error compiling {po_file.name}: {e}")
            sys.exit(1)

    print("Done!")


if __name__ == "__main__":
    compile_po()
