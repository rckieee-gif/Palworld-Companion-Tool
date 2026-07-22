from __future__ import annotations

import json
from pathlib import Path

import pytest

from palworld_aio.map.progress import MapProgressStore


def test_map_progress_is_persisted_outside_the_save(tmp_path: Path) -> None:
    path = tmp_path / 'companion-config' / 'map_progress.json'
    store = MapProgressStore(path)

    store.set_found('fast-travel-1', True)

    assert store.is_found('fast-travel-1') is True
    assert MapProgressStore(path).items() == frozenset({'fast-travel-1'})
    assert json.loads(path.read_text(encoding='utf-8')) == {
        'version': 1,
        'found_location_ids': ['fast-travel-1'],
    }
    assert not list(tmp_path.rglob('*.sav'))


def test_map_progress_can_unmark_and_clear_locations(tmp_path: Path) -> None:
    path = tmp_path / 'map_progress.json'
    store = MapProgressStore(path)
    store.set_found('a', True)
    store.set_found('b', True)

    store.set_found('a', False)
    assert store.items() == frozenset({'b'})

    store.clear()
    assert store.items() == frozenset()


@pytest.mark.parametrize(
    'payload',
    (
        [],
        {'found_location_ids': 'fast-travel-1'},
        {'found_location_ids': ['']},
        {'found_location_ids': [3]},
    ),
)
def test_map_progress_rejects_invalid_data(
    tmp_path: Path,
    payload: object,
) -> None:
    path = tmp_path / 'map_progress.json'
    path.write_text(json.dumps(payload), encoding='utf-8')

    with pytest.raises(ValueError, match='invalid format'):
        MapProgressStore(path)
