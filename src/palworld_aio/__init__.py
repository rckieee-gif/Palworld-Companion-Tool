"""Palworld Companion Tools application package."""

from pathlib import Path
import sys


_VENDORED_PALSAV = Path(__file__).resolve().parent.parent / 'palsav'
if _VENDORED_PALSAV.is_dir() and str(_VENDORED_PALSAV) not in sys.path:
    sys.path.insert(0, str(_VENDORED_PALSAV))


__all__: list[str] = []
