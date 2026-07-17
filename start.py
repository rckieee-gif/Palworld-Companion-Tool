from __future__ import annotations

from pathlib import Path
import sys


PROJECT_DIR = Path(__file__).resolve().parent
SRC_DIR = PROJECT_DIR / 'src'
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from bootup import main


if __name__ == '__main__':
    raise SystemExit(main())
