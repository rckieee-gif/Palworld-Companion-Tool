from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Literal, Mapping

import palworld_coord

from palworld_aio.game_data import GameDataError, load_game_data


MapType = Literal['world', 'tree']
LocationSource = Literal['bundled', 'local']


@dataclass(frozen=True, slots=True)
class MapLocation:
    """A read-only point displayed by the native map explorer."""

    location_id: str
    internal_id: str
    name: str
    coordinates: tuple[int, int]
    map_type: MapType
    category: str
    source: LocationSource
    save_coordinates: tuple[float, float, float] | None = None
    description: str = ''


def coordinates_from_save(
    x: float,
    y: float,
) -> tuple[tuple[int, int], MapType]:
    world_point = palworld_coord.sav_to_map(x, y, new=True)
    if abs(world_point.x) <= 1000 and abs(world_point.y) <= 1000:
        return (world_point.x, world_point.y), 'world'

    tree_point = palworld_coord.sav_to_treemap(x, y)
    if abs(tree_point.x) <= 2500 and abs(tree_point.y) <= 2500:
        return (tree_point.x, tree_point.y), 'tree'

    raise GameDataError(
        f'Location coordinates are outside the bundled maps: {x}, {y}'
    )


@lru_cache(maxsize=1)
def load_fast_travel_locations() -> tuple[MapLocation, ...]:
    data = load_game_data('fast_travel_points.json')
    locations: list[MapLocation] = []

    for location_id, entry in data.items():
        if not isinstance(entry, Mapping):
            raise GameDataError(
                f'Fast-travel location {location_id} has an invalid format.'
            )
        try:
            x = float(entry['x'])
            y = float(entry['y'])
            z = float(entry['z'])
        except (KeyError, TypeError, ValueError) as exc:
            raise GameDataError(
                f'Fast-travel location {location_id} has invalid coordinates.'
            ) from exc

        internal_id = str(entry.get('id') or '').strip()
        name = str(entry.get('localized_name') or internal_id).strip()
        if not internal_id or not name:
            raise GameDataError(
                f'Fast-travel location {location_id} is missing its name or ID.'
            )
        coordinates, map_type = coordinates_from_save(x, y)
        locations.append(MapLocation(
            location_id=str(location_id),
            internal_id=internal_id,
            name=name,
            coordinates=coordinates,
            map_type=map_type,
            category='Fast Travel',
            source='bundled',
            save_coordinates=(x, y, z),
        ))

    return tuple(sorted(
        locations,
        key=lambda item: (item.map_type, item.name.casefold(), item.location_id),
    ))


def location_from_annotation(annotation: Mapping) -> MapLocation:
    if annotation.get('type') != 'point':
        raise ValueError('Only point annotations can be displayed as map locations.')
    map_type = str(annotation.get('map_type', 'world'))
    if map_type not in ('world', 'tree'):
        raise ValueError(f'Unsupported map type: {map_type}')

    return MapLocation(
        location_id=str(annotation['id']),
        internal_id=str(annotation['id']),
        name=str(annotation.get('name') or 'Map pin'),
        coordinates=(
            round(float(annotation['x'])),
            round(float(annotation['y'])),
        ),
        map_type=map_type,
        category='My Pins',
        source='local',
        description=str(annotation.get('description') or ''),
    )
