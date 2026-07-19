from __future__ import annotations

from functools import lru_cache
import json
from pathlib import Path

from resource_resolver import get_resources_dir


class GameDataError(ValueError):
    pass


@lru_cache(maxsize=32)
def load_game_data(filename: str) -> dict:
    path = Path(get_resources_dir()) / 'game_data' / filename
    if not path.is_file():
        raise GameDataError(f'Required game-data file is missing: {filename}')
    try:
        value = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as exc:
        raise GameDataError(f'Could not read game-data file: {filename}') from exc
    if not isinstance(value, dict):
        raise GameDataError(f'Game-data file has an invalid format: {filename}')
    return value


def load_breeding_data() -> dict:
    data = load_game_data('breedingdata.json')
    if not isinstance(data.get('pal_info'), dict):
        raise GameDataError('Breeding data does not contain Pal information.')
    return data


def load_game_data_manifest() -> dict:
    data = load_game_data('manifest.json')
    if not isinstance(data.get('files'), dict):
        raise GameDataError('Game-data manifest does not contain file information.')
    return data
