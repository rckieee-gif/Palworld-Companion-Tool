from __future__ import annotations

from collections.abc import Mapping
import json
import logging
from pathlib import Path
from typing import Any

from resource_resolver import get_resources_dir, get_user_config_dir


LOGGER = logging.getLogger(__name__)
SUPPORTED_LANGUAGES = (
    'en_US',
    'zh_CN',
    'ru_RU',
    'fr_FR',
    'es_ES',
    'de_DE',
    'ja_JP',
    'ko_KR',
)
_CONFIG_PATH = Path(get_user_config_dir()) / 'config.json'
_RESOURCES_DIR = Path(get_resources_dir()) / 'i18n'
_LANG = 'en_US'
_RESOURCES: dict[str, dict[str, str]] = {}
_DEFAULT = object()


def _load_mapping(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding='utf-8'))
    except FileNotFoundError:
        return {}
    except (OSError, json.JSONDecodeError) as exc:
        LOGGER.warning('Could not read %s: %s', path, exc)
        return {}
    if not isinstance(value, Mapping):
        LOGGER.warning('Expected an object in %s', path)
        return {}
    return dict(value)


def _load_language(language: str) -> None:
    if language in _RESOURCES:
        return
    path = _RESOURCES_DIR / f'{language}.json'
    resource = _load_mapping(path)
    _RESOURCES[language] = {
        str(key): str(value) for key, value in resource.items()
    }


def _write_config(config: Mapping[str, Any]) -> None:
    _CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = _CONFIG_PATH.with_suffix('.json.tmp')
    temporary.write_text(
        json.dumps(dict(config), ensure_ascii=True, indent=2) + '\n',
        encoding='utf-8',
    )
    temporary.replace(_CONFIG_PATH)


def load_resources(language: str | None = None) -> None:
    global _LANG
    for supported in SUPPORTED_LANGUAGES:
        _load_language(supported)
    if language in SUPPORTED_LANGUAGES:
        _LANG = str(language)


def get_language() -> str:
    return _LANG


def set_language(language: str) -> None:
    global _LANG
    if language not in SUPPORTED_LANGUAGES:
        return
    _load_language(language)
    _LANG = language
    config = _load_mapping(_CONFIG_PATH)
    config['lang'] = language
    try:
        _write_config(config)
    except OSError as exc:
        LOGGER.warning('Could not save language preference: %s', exc)


def get_config_value(key: str, default: Any = None) -> Any:
    return _load_mapping(_CONFIG_PATH).get(key, default)


def set_config_value(key: str, value: Any) -> None:
    config = _load_mapping(_CONFIG_PATH)
    config[key] = value
    try:
        _write_config(config)
    except OSError as exc:
        LOGGER.warning('Could not save preference %s: %s', key, exc)


def init_language(default_lang: str = 'en_US') -> None:
    global _LANG
    config = _load_mapping(_CONFIG_PATH)
    selected = str(config.get('lang', default_lang))
    if selected not in SUPPORTED_LANGUAGES:
        selected = 'en_US'
    _load_language(selected)
    _load_language('en_US')
    _LANG = selected


def t(key: str, default: str | object = _DEFAULT, **values: Any) -> str:
    _load_language(_LANG)
    _load_language('en_US')
    translated = _RESOURCES.get(_LANG, {}).get(key)
    if translated is None:
        translated = _RESOURCES.get('en_US', {}).get(key)
    if translated is None:
        translated = key if default is _DEFAULT else str(default)
    if not values:
        return translated
    try:
        return translated.format(**values)
    except (KeyError, IndexError, ValueError):
        return translated


__all__ = [
    'SUPPORTED_LANGUAGES',
    'get_config_value',
    'get_language',
    'init_language',
    'load_resources',
    'set_config_value',
    'set_language',
    't',
]
