from __future__ import annotations

import palworld_coord

from palworld_aio.map.locations import (
    coordinates_from_save,
    load_fast_travel_locations,
    location_from_annotation,
)


def test_bundled_fast_travel_locations_cover_both_maps() -> None:
    locations = load_fast_travel_locations()

    assert len(locations) == 174
    assert sum(item.map_type == 'world' for item in locations) == 157
    assert sum(item.map_type == 'tree' for item in locations) == 17
    assert all(item.name and item.internal_id for item in locations)
    assert all(item.category == 'Fast Travel' for item in locations)
    assert all(item.source == 'bundled' for item in locations)


def test_fast_travel_coordinates_stay_inside_their_map() -> None:
    for location in load_fast_travel_locations():
        if location.map_type == 'tree':
            min_x, min_y, max_x, max_y = palworld_coord.get_treemap_map_bounds()
            assert min_x <= location.coordinates[0] <= max_x
            assert min_y <= location.coordinates[1] <= max_y
        else:
            assert abs(location.coordinates[0]) <= 1000
            assert abs(location.coordinates[1]) <= 1000


def test_tree_fast_travel_markers_use_the_full_map_extent() -> None:
    pixels = [
        palworld_coord.treemap_to_pixel(
            location.coordinates[0],
            location.coordinates[1],
            8192,
            8192,
        )
        for location in load_fast_travel_locations()
        if location.map_type == 'tree'
    ]

    assert max(x for x, _y in pixels) - min(x for x, _y in pixels) > 5000
    assert max(y for _x, y in pixels) - min(y for _x, y in pixels) > 5000


def test_save_coordinates_are_classified_consistently() -> None:
    locations = load_fast_travel_locations()

    for location in locations:
        x, y, _z = location.save_coordinates
        assert coordinates_from_save(x, y) == (
            location.coordinates,
            location.map_type,
        )


def test_point_annotation_becomes_a_local_map_location() -> None:
    location = location_from_annotation({
        'id': 'pin-1',
        'type': 'point',
        'name': 'Ore route',
        'description': 'Start here',
        'map_type': 'world',
        'x': 12.6,
        'y': -42.4,
    })

    assert location.location_id == 'pin-1'
    assert location.coordinates == (13, -42)
    assert location.category == 'My Pins'
    assert location.source == 'local'
