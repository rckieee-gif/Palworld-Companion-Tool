from __future__ import annotations

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
        limit = 2500 if location.map_type == 'tree' else 1000
        assert abs(location.coordinates[0]) <= limit
        assert abs(location.coordinates[1]) <= limit


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
