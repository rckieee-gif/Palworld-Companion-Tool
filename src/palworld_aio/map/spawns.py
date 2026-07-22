from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Literal, Mapping

import palworld_coord

from app_info import GAME_DATA_VERSION
from palworld_aio.game_data import GameDataError, load_game_data


MapType = Literal['world', 'tree']
SpawnTimeFilter = Literal['all', 'day', 'night']


@dataclass(frozen=True, slots=True)
class PalSpawnPoint:
    world_x: int
    world_y: int
    radius: int
    level_min: int
    level_max: int
    time_code: int
    probability: float

    def is_visible_at(self, time_filter: SpawnTimeFilter) -> bool:
        if time_filter == 'day':
            return self.time_code in (0, 1)
        if time_filter == 'night':
            return self.time_code in (0, 2)
        return True


@dataclass(frozen=True, slots=True)
class PalSpawnSpecies:
    pal_id: str
    name: str
    icon: str
    world: tuple[PalSpawnPoint, ...]
    tree: tuple[PalSpawnPoint, ...]

    @property
    def label(self) -> str:
        return self.name

    def points_for(
        self,
        map_type: MapType,
        time_filter: SpawnTimeFilter = 'all',
    ) -> tuple[PalSpawnPoint, ...]:
        points = self.tree if map_type == 'tree' else self.world
        if time_filter == 'all':
            return points
        return tuple(point for point in points if point.is_visible_at(time_filter))


class PalSpawnRepository:
    """Validated read-only access to bundled Palworld spawn-table data."""

    def __init__(
        self,
        records: tuple[PalSpawnSpecies, ...],
        map_bounds: Mapping[str, tuple[float, float, float, float]],
    ):
        self._records = records
        self._map_bounds = dict(map_bounds)
        self._by_id = {record.pal_id.casefold(): record for record in records}
        by_name: dict[str, list[PalSpawnSpecies]] = {}
        for record in records:
            by_name.setdefault(record.name.casefold(), []).append(record)
        self._by_name = by_name

    @classmethod
    def from_game_data(cls) -> 'PalSpawnRepository':
        payload = load_game_data('pal_spawns.json')
        if payload.get('schema_version') != 1:
            raise GameDataError('Pal spawn data has an unsupported schema version.')
        if str(payload.get('game_version')) != GAME_DATA_VERSION:
            raise GameDataError(
                'Pal spawn data does not match the bundled game-data version.'
            )
        bounds = cls._parse_bounds(payload.get('map_bounds'))
        cls._validate_tree_bounds(bounds['tree'])
        icon_lookup = cls._icon_lookup()
        rows = payload.get('pals')
        if not isinstance(rows, Mapping):
            raise GameDataError('Pal spawn data does not contain a Pal index.')
        records: list[PalSpawnSpecies] = []
        for pal_id, value in rows.items():
            if not isinstance(value, Mapping):
                raise GameDataError(f'Pal spawn record {pal_id} is invalid.')
            name = str(value.get('name') or '').strip()
            normalized_id = str(pal_id).strip()
            if not normalized_id or not name:
                raise GameDataError('Pal spawn data contains an unnamed Pal.')
            world = cls._parse_points(
                value.get('world', []),
                normalized_id,
                'world',
                bounds['world'],
            )
            tree = cls._parse_points(
                value.get('tree', []),
                normalized_id,
                'tree',
                bounds['tree'],
            )
            if not world and not tree:
                continue
            records.append(PalSpawnSpecies(
                pal_id=normalized_id,
                name=name,
                icon=icon_lookup.get(normalized_id.casefold(), ''),
                world=world,
                tree=tree,
            ))
        if not records:
            raise GameDataError('Pal spawn data does not contain any spawn points.')
        return cls(
            tuple(sorted(
                records,
                key=lambda record: (record.name.casefold(), record.pal_id.casefold()),
            )),
            bounds,
        )

    @staticmethod
    def _parse_bounds(value: object) -> dict[str, tuple[float, float, float, float]]:
        if not isinstance(value, Mapping):
            raise GameDataError('Pal spawn data does not contain map bounds.')
        result: dict[str, tuple[float, float, float, float]] = {}
        for map_type in ('world', 'tree'):
            row = value.get(map_type)
            if not isinstance(row, Mapping):
                raise GameDataError(f'Pal spawn data is missing {map_type} bounds.')
            minimum = row.get('world_min')
            maximum = row.get('world_max')
            if (
                not isinstance(minimum, list)
                or not isinstance(maximum, list)
                or len(minimum) != 2
                or len(maximum) != 2
            ):
                raise GameDataError(f'Pal spawn {map_type} bounds are invalid.')
            try:
                bounds = tuple(float(item) for item in (*minimum, *maximum))
            except (TypeError, ValueError) as exc:
                raise GameDataError(
                    f'Pal spawn {map_type} bounds are invalid.'
                ) from exc
            if not all(math.isfinite(item) for item in bounds):
                raise GameDataError(f'Pal spawn {map_type} bounds are invalid.')
            min_x, min_y, max_x, max_y = bounds
            if min_x >= max_x or min_y >= max_y:
                raise GameDataError(f'Pal spawn {map_type} bounds are invalid.')
            result[map_type] = bounds
        return result

    @staticmethod
    def _validate_tree_bounds(bounds: tuple[float, float, float, float]) -> None:
        expected = palworld_coord.get_treemap_world_bounds()
        if any(
            not math.isclose(actual, wanted, abs_tol=0.01)
            for actual, wanted in zip(bounds, expected)
        ):
            raise GameDataError(
                'Pal spawn Tree bounds do not match the bundled map calibration.'
            )

    @staticmethod
    def _icon_lookup() -> dict[str, str]:
        characters = load_game_data('characters.json')
        rows = characters.get('pals')
        if not isinstance(rows, list):
            return {}
        result: dict[str, str] = {}
        for row in rows:
            if not isinstance(row, Mapping):
                continue
            pal_id = str(row.get('asset') or '').strip().casefold()
            icon = str(row.get('icon') or '').strip()
            if pal_id and icon:
                result.setdefault(pal_id, icon)
        return result

    @staticmethod
    def _parse_points(
        value: object,
        pal_id: str,
        map_type: MapType,
        bounds: tuple[float, float, float, float],
    ) -> tuple[PalSpawnPoint, ...]:
        if not isinstance(value, list):
            raise GameDataError(f'{pal_id} has an invalid {map_type} spawn list.')
        points: list[PalSpawnPoint] = []
        min_x, min_y, max_x, max_y = bounds
        for index, entry in enumerate(value):
            if not isinstance(entry, list) or len(entry) != 7:
                raise GameDataError(
                    f'{pal_id} has an invalid {map_type} spawn at index {index}.'
                )
            try:
                point = PalSpawnPoint(
                    world_x=int(entry[0]),
                    world_y=int(entry[1]),
                    radius=max(1, int(entry[2])),
                    level_min=max(0, int(entry[3])),
                    level_max=max(0, int(entry[4])),
                    time_code=int(entry[5]),
                    probability=float(entry[6]),
                )
            except (TypeError, ValueError) as exc:
                raise GameDataError(
                    f'{pal_id} has an invalid {map_type} spawn at index {index}.'
                ) from exc
            if (
                not min_x <= point.world_x <= max_x
                or not min_y <= point.world_y <= max_y
                or point.level_min > point.level_max
                or point.time_code not in (0, 1, 2)
                or not math.isfinite(point.probability)
                or not 0 < point.probability <= 1
            ):
                raise GameDataError(
                    f'{pal_id} has an out-of-range {map_type} spawn at index {index}.'
                )
            points.append(point)
        return tuple(points)

    @property
    def records(self) -> tuple[PalSpawnSpecies, ...]:
        return self._records

    def records_for_map(self, map_type: MapType) -> tuple[PalSpawnSpecies, ...]:
        return tuple(
            record
            for record in self._records
            if (record.tree if map_type == 'tree' else record.world)
        )

    def resolve(self, query: str) -> PalSpawnSpecies | None:
        key = query.strip().casefold()
        if not key:
            return None
        direct = self._by_id.get(key)
        if direct is not None:
            return direct
        matches = self._by_name.get(key, [])
        return matches[0] if len(matches) == 1 else None

    def bounds_for(self, map_type: MapType) -> tuple[float, float, float, float]:
        return self._map_bounds[map_type]


__all__ = [
    'MapType',
    'PalSpawnPoint',
    'PalSpawnRepository',
    'PalSpawnSpecies',
    'SpawnTimeFilter',
]
