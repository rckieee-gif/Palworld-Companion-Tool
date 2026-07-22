from __future__ import annotations

import json
from pathlib import Path

from palworld_aio.game_data_validation import (
    build_game_data_manifest,
    validate_game_data,
    write_game_data_manifest,
)


def _write_json(path: Path, value: dict) -> None:
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=True) + '\n',
        encoding='utf-8',
    )


def _pal(name: str) -> dict:
    return {
        'name': name,
        'combi_rank': 100,
        'rarity': 1,
        'ignore_combi': False,
        'icon': f'/icons/pals/{name}.webp',
    }


def _create_data_dir(tmp_path: Path) -> Path:
    data_dir = tmp_path / 'game_data'
    icon_dir = data_dir / 'icons'
    pal_icon_dir = icon_dir / 'pals'
    pal_icon_dir.mkdir(parents=True)
    (icon_dir / 'T_icon_unknown.webp').write_bytes(b'unknown')
    for name in ('Alpha', 'Beta', 'Child'):
        (pal_icon_dir / f'{name}.webp').write_bytes(name.encode('ascii'))

    pal_info = {name: _pal(name) for name in ('Alpha', 'Beta', 'Child')}
    files = {
        'append_text.json': {},
        'boss_mapping.json': {'boss_defeat_flag_map': {}},
        'breedingdata.json': {
            'pal_info': pal_info,
            'unique_combos': [],
            'child_to_parents_formula': {
                'Child': [{'parent_a': 'Alpha', 'parent_b': 'Beta'}],
            },
            'child_to_parents_unique': {},
            'child_to_parents_ignore': {},
            'parent_to_children_formula': {
                'Alpha': [{'partner': 'Beta', 'child': 'Child'}],
            },
        },
        'characters.json': {
            'pals': [
                {
                    'name': name,
                    'asset': name,
                    'icon': f'/icons/pals/{name}.webp',
                }
                for name in ('Alpha', 'Beta', 'Child')
            ],
            'npcs': [],
            'friendship': {},
        },
        'fast_travel_points.json': {},
        'friendship.json': {},
        'items.json': {'items': [], 'items_dynamic': {}},
        'pal_spawns.json': {
            'pals': {},
            'map_bounds': {},
            'counts': {},
        },
        'pal_exp_table.json': {},
        'pals_learnset.json': {'learnset': {}},
        'relic_data.json': {},
        'skills.json': {'passives': [], 'skills': [], 'elements': []},
        'uidata.json': {'ui_icons': {}},
        'work_suitability.json': {'work_types': []},
        'world.json': {'structures': [], 'technology': [], 'lab_research': {}},
        'world_map_areas.json': {'areas': []},
    }
    for filename, value in files.items():
        _write_json(data_dir / filename, value)
    write_game_data_manifest(data_dir, game_data_version='test-1')
    return data_dir


def test_consistent_data_and_manifest_validate(tmp_path: Path) -> None:
    data_dir = _create_data_dir(tmp_path)

    report = validate_game_data(data_dir, expected_version='test-1')

    assert report.is_valid is True
    assert report.files_checked == 16
    assert report.icons_checked == 4
    assert report.known_icon_fallbacks == 0
    assert report.issues == ()


def test_manifest_generation_is_deterministic(tmp_path: Path) -> None:
    data_dir = _create_data_dir(tmp_path)

    first = build_game_data_manifest(data_dir, game_data_version='test-1')
    second = build_game_data_manifest(data_dir, game_data_version='test-1')

    assert first == second


def test_changed_data_file_fails_checksum_validation(tmp_path: Path) -> None:
    data_dir = _create_data_dir(tmp_path)
    _write_json(data_dir / 'append_text.json', {'changed': True})

    report = validate_game_data(data_dir, expected_version='test-1')

    assert report.is_valid is False
    assert 'file.checksum' in {issue.code for issue in report.errors}


def test_unknown_breeding_reference_fails_semantic_validation(tmp_path: Path) -> None:
    data_dir = _create_data_dir(tmp_path)
    path = data_dir / 'breedingdata.json'
    data = json.loads(path.read_text(encoding='utf-8'))
    data['child_to_parents_formula']['Child'][0]['parent_b'] = 'MissingPal'
    _write_json(path, data)
    write_game_data_manifest(data_dir, game_data_version='test-1')

    report = validate_game_data(data_dir, expected_version='test-1')

    assert report.is_valid is False
    assert 'breeding.reference' in {issue.code for issue in report.errors}


def test_known_missing_icon_is_a_visible_warning(tmp_path: Path) -> None:
    data_dir = _create_data_dir(tmp_path)
    path = data_dir / 'characters.json'
    data = json.loads(path.read_text(encoding='utf-8'))
    data['pals'][0]['icon'] = '/icons/pals/NotBundled.webp'
    _write_json(path, data)
    write_game_data_manifest(data_dir, game_data_version='test-1')

    report = validate_game_data(data_dir, expected_version='test-1')

    assert report.is_valid is True
    assert report.known_icon_fallbacks == 1
    assert [issue.code for issue in report.warnings] == ['icon.fallbacks']


def test_manifest_game_version_must_match_application(tmp_path: Path) -> None:
    data_dir = _create_data_dir(tmp_path)

    report = validate_game_data(data_dir, expected_version='different-version')

    assert report.is_valid is False
    assert 'manifest.game_version' in {issue.code for issue in report.errors}


def test_malformed_unique_field_returns_validation_error(tmp_path: Path) -> None:
    data_dir = _create_data_dir(tmp_path)
    path = data_dir / 'characters.json'
    data = json.loads(path.read_text(encoding='utf-8'))
    data['pals'][0]['asset'] = {'not': 'a scalar'}
    _write_json(path, data)
    write_game_data_manifest(data_dir, game_data_version='test-1')

    report = validate_game_data(data_dir, expected_version='test-1')

    assert report.is_valid is False
    assert 'schema.field_type' in {issue.code for issue in report.errors}
