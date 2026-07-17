from __future__ import annotations

import hashlib
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from palworld_aio.read_only_world import WorldLoadError, load_read_only_world
from palworld_aio.ui.main_window import MainWindow


PLAYER_UID = '11111111111111111111111111111111'


def _fixture_properties(path: Path) -> dict:
    if path.name.lower() != 'level.sav':
        return {
            'SaveData': {
                'value': {
                    'LastTransform': {
                        'value': {
                            'Translation': {
                                'value': {'x': 0.0, 'y': 0.0, 'z': 10.0}
                            }
                        }
                    }
                }
            }
        }

    world = {
        'GameTimeSaveData': {
            'value': {'RealDateTimeTicks': {'value': 20_000_000}}
        },
        'GroupSaveDataMap': {
            'value': [
                {
                    'key': 'guild-1',
                    'value': {
                        'GroupType': {'value': 'EPalGroupType::Guild'},
                        'RawData': {
                            'value': {
                                'guild_name': 'Read Only Guild',
                                'admin_player_uid': PLAYER_UID,
                                'base_camp_level': 7,
                                'base_ids': ['base-1'],
                                'players': [
                                    {
                                        'player_uid': PLAYER_UID,
                                        'player_info': {
                                            'player_name': 'Explorer',
                                            'last_online_real_time': 10_000_000,
                                        },
                                    }
                                ],
                            }
                        },
                    },
                }
            ]
        },
        'BaseCampSaveData': {
            'value': [
                {
                    'key': 'base-1',
                    'value': {
                        'RawData': {
                            'value': {
                                'transform': {
                                    'translation': {
                                        'x': 0.0,
                                        'y': 0.0,
                                        'z': 10.0,
                                    }
                                },
                                'area_range': 3500.0,
                            }
                        },
                        'WorkerDirector': {
                            'value': {
                                'RawData': {
                                    'value': {'container_id': 'workers-1'}
                                }
                            }
                        },
                    },
                }
            ]
        },
        'CharacterContainerSaveData': {
            'value': [
                {
                    'key': {'ID': 'workers-1'},
                    'value': {'Slots': {'value': {'values': [{}, {}]}}},
                }
            ]
        },
        'CharacterSaveParameterMap': {
            'value': [
                {
                    'key': {'PlayerUId': PLAYER_UID},
                    'value': {
                        'RawData': {
                            'value': {
                                'object': {
                                    'SaveParameter': {
                                        'struct_type': 'PalIndividualCharacterSaveParameter',
                                        'value': {
                                            'IsPlayer': {'value': True},
                                            'Level': {'value': 42},
                                        },
                                    }
                                }
                            }
                        }
                    },
                }
            ]
        },
    }
    return {'worldSaveData': {'value': world}}


@pytest.fixture
def world_fixture(tmp_path: Path) -> tuple[Path, Path]:
    level = tmp_path / 'Level.sav'
    player_dir = tmp_path / 'Players'
    player_dir.mkdir()
    player = player_dir / f'{PLAYER_UID}.sav'
    level.write_bytes(b'read-only-level-fixture')
    player.write_bytes(b'read-only-player-fixture')
    stamp_ns = 1_700_000_000_000_000_000
    os.utime(level, ns=(stamp_ns, stamp_ns))
    os.utime(player, ns=(stamp_ns, stamp_ns))
    return level, player


def _snapshot(path: Path) -> tuple[bytes, int, int, str]:
    data = path.read_bytes()
    stat = path.stat()
    return data, stat.st_size, stat.st_mtime_ns, hashlib.sha256(data).hexdigest()


def test_read_only_loader_preserves_every_input_byte(world_fixture) -> None:
    level, player = world_fixture
    before = {path: _snapshot(path) for path in world_fixture}
    with patch('palsav.io.save_sav') as save_sav:
        world = load_read_only_world(level, parser=_fixture_properties)
    after = {path: _snapshot(path) for path in world_fixture}

    assert before == after
    save_sav.assert_not_called()
    assert world.source_path == level.resolve()
    assert len(world.guilds) == 1
    assert len(world.bases) == 1
    assert len(world.players) == 1
    assert world.players[0].player_name == 'Explorer'
    assert world.players[0].level == 42
    assert world.bases[0].pal_count == 2


def test_map_navigation_and_overlays_do_not_touch_save(world_fixture, qapp) -> None:
    level, player = world_fixture
    before = {path: _snapshot(path) for path in world_fixture}
    world = load_read_only_world(level, parser=_fixture_properties)
    window = MainWindow()
    try:
        window._on_world_loaded(world)
        assert window.stack.currentWidget() is window.map_tab
        assert window.map_tab.read_only_label.isVisibleTo(window.map_tab)
        window.map_tab.show_bases.setChecked(False)
        window.map_tab.show_bases.setChecked(True)
        window.map_tab.show_radii.setChecked(False)
        window.map_tab.show_radii.setChecked(True)
        window.map_tab._show_details(world.bases[0])
        assert 'Read Only Guild' in window.map_tab.detail_label.text()
        window.close_world()
        assert window.loaded_world is None
    finally:
        window.close()

    after = {path: _snapshot(path) for path in world_fixture}
    assert before == after


def test_invalid_filename_is_rejected_without_modification(tmp_path: Path) -> None:
    source = tmp_path / 'World.sav'
    source.write_bytes(b'not-level')
    before = _snapshot(source)
    with pytest.raises(WorldLoadError, match='named Level.sav'):
        load_read_only_world(source, parser=_fixture_properties)
    assert _snapshot(source) == before


def test_parse_failure_does_not_modify_the_input(tmp_path: Path) -> None:
    source = tmp_path / 'Level.sav'
    source.write_bytes(b'unsupported')
    before = _snapshot(source)

    def fail(_path: Path) -> dict:
        raise ValueError('unsupported fixture')

    with pytest.raises(WorldLoadError, match='could not be parsed'):
        load_read_only_world(source, parser=fail)
    assert _snapshot(source) == before
