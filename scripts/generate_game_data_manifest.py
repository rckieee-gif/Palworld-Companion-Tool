from __future__ import annotations

import argparse
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / 'src'
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from app_info import GAME_DATA_VERSION
from palworld_aio.game_data_validation import write_game_data_manifest


def main() -> int:
    parser = argparse.ArgumentParser(description='Generate the game-data manifest')
    parser.add_argument(
        '--data-dir',
        type=Path,
        default=PROJECT_ROOT / 'resources' / 'game_data',
    )
    parser.add_argument('--game-version', default=GAME_DATA_VERSION)
    args = parser.parse_args()

    output = write_game_data_manifest(
        args.data_dir,
        game_data_version=args.game_version,
    )
    print(f'Game-data manifest created: {output}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
