from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TESTS_ROOT = Path(__file__).resolve().parent
SRC_DIR = PROJECT_ROOT / 'src'
SCRIPTS_DIR = PROJECT_ROOT / 'scripts'
RESOURCES_DIR = PROJECT_ROOT / 'resources'
SAVE_TEST_DIR = TESTS_ROOT / 'save_test'

MODULE_MAP: dict[str, dict] = {
    'app_info': {'import_as': 'app_info', 'parent': 'src'},
    'bootup': {'import_as': 'bootup', 'parent': 'src'},
    'common': {'import_as': 'common', 'parent': 'src'},
    'i18n': {'import_as': 'i18n', 'parent': 'src'},
    'palworld_aio': {'import_as': 'palworld_aio', 'parent': 'src'},
    'palworld_coord': {'import_as': 'palworld_coord', 'parent': 'src'},
    'path_setup': {'import_as': 'path_setup', 'parent': 'src'},
    'resource_resolver': {'import_as': 'resource_resolver', 'parent': 'src'},
    'palsav': {'import_as': 'palsav', 'parent': 'src/palsav'},
    'check_theme_violations': {
        'import_as': 'check_theme_violations',
        'parent': 'scripts/scrs',
    },
}


def _resolve_parent(alias: str) -> Path:
    return PROJECT_ROOT / alias


def get_entry(logical_root: str) -> dict | None:
    return MODULE_MAP.get(logical_root)
