from __future__ import annotations

from functools import lru_cache
import os

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap

from palworld_aio.game_data import load_game_data
from resource_resolver import get_resources_dir


def _game_data_path(relative: str) -> str:
    return os.path.join(get_resources_dir(), 'game_data', relative.lstrip('/'))


def resolve_icon_path(icon_path: str) -> str:
    if icon_path:
        candidate = _game_data_path(icon_path)
        if os.path.isfile(candidate):
            return candidate
        stem, _extension = os.path.splitext(candidate)
        for extension in ('.webp', '.png'):
            alternative = stem + extension
            if os.path.isfile(alternative):
                return alternative
    return _game_data_path('icons/T_icon_unknown.webp')


@lru_cache(maxsize=2048)
def pixmap_for_icon(icon_path: str, size: int = 48) -> QPixmap | None:
    path = resolve_icon_path(icon_path)
    if not os.path.isfile(path):
        return None
    pixmap = QPixmap(path)
    if pixmap.isNull():
        return None
    return pixmap.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)


def pal_pixmap(species: str, pal_info: dict, size: int = 48) -> QPixmap | None:
    return pixmap_for_icon(pal_info.get(species, {}).get('icon', ''), size)


@lru_cache(maxsize=1)
def _element_icons() -> dict[str, str]:
    result = {}
    for element in load_game_data('skills.json').get('elements', []):
        if not isinstance(element, dict):
            continue
        name = str(element.get('name') or '').lower()
        icons = element.get('icons', {}) or {}
        if name and isinstance(icons, dict):
            result[name] = str(icons.get('small') or icons.get('large') or '')
    return result


def element_pixmap(element_name: str, size: int = 18) -> QPixmap | None:
    aliases = {
        'ground': 'earth',
        'electric': 'electricity',
        'neutral': 'normal',
        'grass': 'leaf',
    }
    key = aliases.get(element_name.lower(), element_name.lower())
    return pixmap_for_icon(_element_icons().get(key, ''), size)
