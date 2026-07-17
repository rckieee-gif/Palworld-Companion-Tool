from __future__ import annotations

import os
from pathlib import Path
import sys

from app_info import PRODUCT_SLUG


def _compute_binary_root() -> str:
    cached = getattr(sys, '_PALWORLD_COMPANION_ROOT', None)
    if cached:
        return str(cached)

    executable_dir = Path(sys.executable).resolve().parent
    for candidate in (executable_dir, executable_dir.parent):
        if (candidate / 'resources').is_dir():
            return str(candidate)

    probe = Path(__file__).resolve().parent
    for candidate in (probe, *probe.parents):
        if (candidate / 'resources').is_dir():
            return str(candidate)
    return str(Path(__file__).resolve().parents[1])


sys._PALWORLD_COMPANION_ROOT = _compute_binary_root()


def get_base_dir() -> str:
    return str(sys._PALWORLD_COMPANION_ROOT)


def get_data_base() -> str:
    return get_base_dir()


def get_user_config_dir() -> str:
    override = os.environ.get('PALWORLD_COMPANION_CONFIG_DIR')
    if override:
        return os.path.abspath(os.path.expanduser(override))
    if sys.platform == 'win32':
        base = os.environ.get('APPDATA', os.path.expanduser('~'))
    elif sys.platform == 'darwin':
        base = os.path.join(os.path.expanduser('~'), 'Library', 'Application Support')
    else:
        base = os.environ.get(
            'XDG_CONFIG_HOME', os.path.join(os.path.expanduser('~'), '.config')
        )
    return os.path.join(base, PRODUCT_SLUG)


def get_resources_dir() -> str:
    return os.path.join(get_base_dir(), 'resources')


def get_src_dir() -> str:
    return os.path.join(get_base_dir(), 'src')


_RESOURCE_MAP = {
    'assets/fonts/HackNerdFont-Regular.ttf': 'assets/fonts/HackNerdFont-Regular.ttf',
    'assets/icons/app/icon.ico': 'assets/icons/app/icon.ico',
    'assets/icons/game/baseicon.webp': 'assets/icons/game/baseicon.webp',
    'assets/icons/game/playericon.webp': 'assets/icons/game/playericon.webp',
    'assets/icons/game/zones.webp': 'assets/icons/game/zones.webp',
    'assets/maps/T_TreeMap.webp': 'assets/maps/T_TreeMap.webp',
    'assets/maps/T_WorldMap.webp': 'assets/maps/T_WorldMap.webp',
    'HackNerdFont-Regular.ttf': 'assets/fonts/HackNerdFont-Regular.ttf',
    'icon.ico': 'assets/icons/app/icon.ico',
    'baseicon.webp': 'assets/icons/game/baseicon.webp',
    'playericon.webp': 'assets/icons/game/playericon.webp',
    'zones.webp': 'assets/icons/game/zones.webp',
    'T_TreeMap.webp': 'assets/maps/T_TreeMap.webp',
    'T_WorldMap.webp': 'assets/maps/T_WorldMap.webp',
}


def resource_path(base_dir: str, *parts: str) -> str:
    relative = os.path.join(*parts).replace('\\', '/')
    mapped = _RESOURCE_MAP.get(relative, relative)
    return os.path.join(base_dir, 'resources', mapped)
