from __future__ import annotations

import json
from pathlib import Path

from palworld_aio.map.annotations import (
    AnnotationStore,
    scene_to_world,
    world_to_scene,
)


def test_annotations_are_stored_in_a_separate_json_file(tmp_path: Path) -> None:
    path = tmp_path / 'companion-config' / 'map_annotations.json'
    store = AnnotationStore(path)
    annotation_id = store.add({
        'type': 'rect',
        'name': 'Route notes',
        'x1': 20,
        'y1': -10,
        'x2': -5,
        'y2': 25,
    })

    payload = json.loads(path.read_text(encoding='utf-8'))
    assert payload['annotations'][0]['id'] == annotation_id
    assert payload['annotations'][0]['x1'] == -5.0
    assert path.suffix == '.json'
    assert not list(tmp_path.rglob('*.sav'))


def test_annotation_coordinates_round_trip() -> None:
    scene = world_to_scene(321, -456, 2048, 2048)
    world = scene_to_world(*scene, 2048, 2048)
    assert world == (321.0, -456.0)


def test_local_map_pin_is_persisted_outside_the_save(tmp_path: Path) -> None:
    path = tmp_path / 'companion-config' / 'map_annotations.json'
    store = AnnotationStore(path)
    pin_id = store.add({
        'type': 'point',
        'name': 'Mining route',
        'description': 'Coal and sulfur nearby',
        'map_type': 'world',
        'x': 123.5,
        'y': -456.25,
    })

    stored_pin = store.items()[0]
    assert stored_pin['id'] == pin_id
    assert stored_pin['map_type'] == 'world'
    assert stored_pin['x'] == 123.5
    assert not list(tmp_path.rglob('*.sav'))
