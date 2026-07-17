from __future__ import annotations

import os
import platform
import subprocess
import sys

from app_info import (
    GAME_DATA_VERSION,
    PRODUCT_NAME,
    PRODUCT_SLUG,
    PRODUCT_VERSION,
)
from resource_resolver import (
    get_base_dir,
    get_resources_dir,
    get_src_dir,
    resource_path,
)

APP_NAME = PRODUCT_SLUG
APP_DISPLAY_NAME = PRODUCT_NAME
APP_VERSION = PRODUCT_VERSION
TESTING_VER = PRODUCT_VERSION
GAME_VERSION = GAME_DATA_VERSION


def get_base_directory() -> str:
    return get_base_dir()


def get_src_directory() -> str:
    return get_src_dir()


def get_resources_directory() -> str:
    return get_resources_dir()


ICON_PATH = resource_path(get_base_dir(), 'icon.ico')


def is_frozen() -> bool:
    if getattr(sys, 'frozen', False):
        return True
    executable = getattr(sys, 'executable', '') or ''
    return not os.path.basename(executable).lower().startswith('python')


def get_python_executable() -> str:
    return sys.executable


def get_versions() -> tuple[str, str]:
    return APP_VERSION, GAME_VERSION


def get_display_version() -> str:
    return APP_VERSION


def get_current_version() -> str:
    return APP_VERSION


def is_standalone() -> bool:
    return is_frozen()


def get_steam_save_path() -> str:
    if sys.platform == 'win32':
        return os.path.expandvars(r'%LOCALAPPDATA%\Pal\Saved\SaveGames')
    if sys.platform == 'darwin':
        return os.path.expanduser(
            '~/Library/Containers/com.pocketpair.palworld.mac/Data/'
            'Library/Application Support/Epic/Pal/Saved/SaveGames'
        )
    return os.path.expanduser('~/.local/share/Steam/steamapps/compatdata/1623730')


def get_preferred_save_path() -> str:
    from i18n import get_config_value

    stored = get_config_value('last_save_path', '')
    if stored and os.path.isdir(stored):
        return stored
    return get_steam_save_path()


def set_last_save_path(path: str) -> None:
    from i18n import set_config_value

    set_config_value('last_save_path', path)


def open_file_with_default_app(file_path: str) -> bool:
    if not os.path.exists(file_path):
        return False
    try:
        if platform.system() == 'Windows':
            os.startfile(file_path)
        elif platform.system() == 'Darwin':
            subprocess.run(['open', file_path], check=False)
        else:
            subprocess.run(['xdg-open', file_path], check=False)
        return True
    except OSError:
        return False
