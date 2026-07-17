import os
import sys
from pathlib import Path


def _compute_root() -> Path:
    if hasattr(sys, '_PALWORLD_COMPANION_ROOT'):
        return Path(sys._PALWORLD_COMPANION_ROOT)
    _found_root: Path | None = None
    if os.path.isfile(sys.executable):
        _exe_dir = Path(os.path.realpath(sys.executable)).parent
        if (_exe_dir / 'resources').is_dir():
            _found_root = _exe_dir
        else:
            _parent = _exe_dir.parent
            if (_parent / 'resources').is_dir():
                _found_root = _parent
    if _found_root is None:
        _probe = Path(__file__).resolve().parent
        for _ in range(5):
            if (_probe / 'resources').is_dir():
                _found_root = _probe
                break
            _probe = _probe.parent
        if _found_root is None:
            _found_root = Path(__file__).resolve().parent.parent
    return _found_root


_RO = _compute_root()
if not hasattr(sys, '_PALWORLD_COMPANION_ROOT'):
    sys._PALWORLD_COMPANION_ROOT = str(_RO)

ROOT_DIR: Path = _RO
SRC_DIR: Path = ROOT_DIR / 'src'
RESOURCES_DIR: Path = ROOT_DIR / 'resources'
DATA_DIR: Path = SRC_DIR / 'data'
CONFIG_DIR: Path = DATA_DIR / 'configs'

import resource_resolver
_USER_CONFIG = resource_resolver.get_user_config_dir()
USER_CONFIG_DIR: Path = Path(_USER_CONFIG)
GUI_DIR: Path = RESOURCES_DIR / 'ui' / 'themes'
ASSETS_DIR: Path = RESOURCES_DIR / 'assets'
