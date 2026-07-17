"""Source launcher for Palworld Companion Tools.

Dependencies are installed separately. This module intentionally contains no
updater or repository replacement logic.
"""

from __future__ import annotations

import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT_DIR / 'src'
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


def main() -> int:
    from palworld_aio.main import run_aio

    return run_aio()


if __name__ == '__main__':
    raise SystemExit(main())
