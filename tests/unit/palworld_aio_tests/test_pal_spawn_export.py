from __future__ import annotations

from pathlib import Path
import runpy


_EXPORTER_PATH = (
    Path(__file__).resolve().parents[3]
    / 'scripts'
    / 'scrs'
    / 'pal_spawn_export.py'
)
_EXPORTER = runpy.run_path(
    str(_EXPORTER_PATH),
    run_name='pal_spawn_export_test_module',
)
build_spawn_payload = _EXPORTER['build_spawn_payload']


def test_spawn_export_joins_placement_and_wild_tables() -> None:
    map_rows = {
        'MainMap': {
            'landScapeRealPositionMin': {'X': -1000, 'Y': -1000},
            'landScapeRealPositionMax': {'X': 1000, 'Y': 1000},
        },
        'Tree': {
            'landScapeRealPositionMin': {'X': 2000, 'Y': 2000},
            'landScapeRealPositionMax': {'X': 4000, 'Y': 4000},
        },
    }
    placements = {
        'world-placement': {
            'SpawnerName': 'GrassSpawner',
            'Location': {'X': 100, 'Y': -200},
            'StaticRadius': 150,
        },
        'tree-placement': {
            'SpawnerName': 'WorldTreeSpawner',
            'Location': {'X': 3000, 'Y': 3500},
            'StaticRadius': 200,
        },
    }
    wild = {
        'world-spawn': {
            'SpawnerName': 'GrassSpawner',
            'Weight': 3,
            'OnlyTime': 'EPalTimeType::Day',
            'Pal_1': 'BOSS_TestPal',
            'LvMin_1': 5,
            'LvMax_1': 7,
        },
        'tree-spawn': {
            'SpawnerName': 'WorldTreeSpawner',
            'Weight': 1,
            'OnlyTime': 'EPalTimeType::Night',
            'Pal_1': 'TestPal',
            'LvMin_1': 20,
            'LvMax_1': 22,
        },
    }
    characters = {
        'pals': [{'asset': 'TestPal', 'name': 'Test Pal'}],
    }

    payload = build_spawn_payload(
        placements,
        wild,
        map_rows,
        characters,
        game_version='test-version',
    )

    assert payload['game_version'] == 'test-version'
    assert payload['counts']['placements'] == 2
    assert payload['counts']['matched_placements'] == 2
    assert payload['counts']['spawn_entries'] == 2
    assert payload['pals']['TestPal'] == {
        'name': 'Test Pal',
        'world': [[100, -200, 150, 5, 7, 1, 1.0]],
        'tree': [[3000, 3500, 200, 20, 22, 2, 1.0]],
    }
