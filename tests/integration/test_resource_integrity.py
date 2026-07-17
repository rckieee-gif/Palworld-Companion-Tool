from __future__ import annotations

import json
from pathlib import Path
import struct

from resource_resolver import get_base_dir, resource_path


REQUIRED_FILES = (
    'assets/icons/app/icon.ico',
    'assets/icons/game/baseicon.webp',
    'assets/icons/game/playericon.webp',
    'assets/icons/game/zones.webp',
    'assets/maps/T_TreeMap.webp',
    'assets/maps/T_WorldMap.webp',
    'game_data/breedingdata.json',
    'game_data/characters.json',
    'game_data/items.json',
    'game_data/skills.json',
    'game_data/work_suitability.json',
    'game_data/icons/T_icon_unknown.webp',
    'i18n/en_US.json',
    'ui/themes/darkmode.qss',
    'ui/themes/lightmode.qss',
)

APP_ICON_SIZES = {
    (16, 16),
    (20, 20),
    (24, 24),
    (32, 32),
    (40, 40),
    (48, 48),
    (64, 64),
    (96, 96),
    (128, 128),
    (256, 256),
}


def test_retained_resources_exist(project_dir: Path) -> None:
    resources = project_dir / 'resources'
    missing = [relative for relative in REQUIRED_FILES if not (resources / relative).is_file()]
    assert missing == []


def test_retained_json_resources_parse(project_dir: Path) -> None:
    for path in (project_dir / 'resources').rglob('*.json'):
        json.loads(path.read_text(encoding='utf-8'))


def test_flat_resource_aliases_resolve() -> None:
    base = get_base_dir()
    assert Path(resource_path(base, 'icon.ico')).is_file()
    assert Path(resource_path(base, 'T_WorldMap.webp')).is_file()
    assert Path(resource_path(base, 'baseicon.webp')).is_file()


def test_app_icon_contains_windows_size_variants(project_dir: Path) -> None:
    source = project_dir / 'build' / 'branding' / 'app-icon.png'
    assert source.read_bytes().startswith(b'\x89PNG\r\n\x1a\n')

    icon = project_dir / 'resources' / 'assets' / 'icons' / 'app' / 'icon.ico'
    data = icon.read_bytes()
    reserved, image_type, image_count = struct.unpack_from('<HHH', data)
    assert (reserved, image_type, image_count) == (0, 1, len(APP_ICON_SIZES))

    sizes = set()
    for index in range(image_count):
        width, height = struct.unpack_from('<BB', data, 6 + (index * 16))
        sizes.add((width or 256, height or 256))
    assert sizes == APP_ICON_SIZES


def test_editor_guides_and_old_branding_are_not_retained(project_dir: Path) -> None:
    resources = project_dir / 'resources'
    for relative in ('tab_guide', 'readme', 'assets/branding'):
        directory = resources / relative
        assert not directory.exists() or not [
            path for path in directory.rglob('*') if path.is_file()
        ]
