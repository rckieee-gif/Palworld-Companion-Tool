from __future__ import annotations

import argparse
from collections import defaultdict
import json
import math
from pathlib import Path
from typing import Any, Mapping


SCHEMA_VERSION = 1
MAP_ROW_NAMES = {'world': 'MainMap', 'tree': 'Tree'}
PAL_ID_PREFIXES = (
    'BOSS_',
    'PREDATOR_',
    'RAID_',
    'GYM_',
    'SUMMON_',
    'TOWER_',
    'OILRIG_',
)


class SpawnExportError(ValueError):
    pass


def _unwrap_uasset_value(property_data: Mapping[str, Any]) -> Any:
    value = property_data.get('Value')
    if isinstance(value, list) and len(value) == 1:
        inner = value[0]
        if isinstance(inner, Mapping) and 'Value' in inner:
            return _unwrap_uasset_value(inner)
    return value


def _uassetapi_rows(value: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    exports = value.get('Exports')
    if not isinstance(exports, list):
        return {}
    for export in exports:
        if not isinstance(export, Mapping):
            continue
        table = export.get('Table')
        if not isinstance(table, Mapping):
            continue
        data = table.get('Data')
        if not isinstance(data, list):
            continue
        rows: dict[str, dict[str, Any]] = {}
        for row in data:
            if not isinstance(row, Mapping):
                continue
            name = str(row.get('Name') or '').strip()
            properties = row.get('Value')
            if not name or not isinstance(properties, list):
                continue
            rows[name] = {
                str(prop.get('Name')): _unwrap_uasset_value(prop)
                for prop in properties
                if isinstance(prop, Mapping) and prop.get('Name')
            }
        if rows:
            return rows
    return {}


def data_table_rows(value: Any) -> dict[str, dict[str, Any]]:
    """Read either an FModel table export or UAssetAPI JSON export."""

    if isinstance(value, Mapping):
        rows = value.get('Rows')
        if isinstance(rows, Mapping):
            return {
                str(key): dict(row)
                for key, row in rows.items()
                if isinstance(row, Mapping)
            }
        rows = _uassetapi_rows(value)
        if rows:
            return rows
    if isinstance(value, list):
        combined: dict[str, dict[str, Any]] = {}
        for table in value:
            combined.update(data_table_rows(table))
        if combined:
            return combined
    raise SpawnExportError('The input does not contain a readable data table.')


def load_data_table(path: str | Path) -> dict[str, dict[str, Any]]:
    source = Path(path)
    try:
        value = json.loads(source.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as exc:
        raise SpawnExportError(f'Could not read {source}: {exc}') from exc
    return data_table_rows(value)


def _number(value: Any, default: float = 0.0) -> float:
    if isinstance(value, Mapping):
        value = value.get('value', value.get('Value', default))
    if isinstance(value, str) and value.startswith('+'):
        value = value[1:]
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if math.isfinite(result) else default


def _vector(value: Any, field: str) -> tuple[float, float]:
    if not isinstance(value, Mapping):
        raise SpawnExportError(f'{field} is not a vector.')
    x = _number(value.get('X'), math.nan)
    y = _number(value.get('Y'), math.nan)
    if not math.isfinite(x) or not math.isfinite(y):
        raise SpawnExportError(f'{field} contains invalid coordinates.')
    return x, y


def extract_map_bounds(
    map_rows: Mapping[str, Mapping[str, Any]],
) -> dict[str, dict[str, list[float]]]:
    result: dict[str, dict[str, list[float]]] = {}
    for map_type, row_name in MAP_ROW_NAMES.items():
        row = map_rows.get(row_name)
        if not isinstance(row, Mapping):
            raise SpawnExportError(f'Map metadata is missing the {row_name} row.')
        minimum = _vector(row.get('landScapeRealPositionMin'), 'map minimum')
        maximum = _vector(row.get('landScapeRealPositionMax'), 'map maximum')
        if minimum[0] >= maximum[0] or minimum[1] >= maximum[1]:
            raise SpawnExportError(f'{row_name} map bounds are invalid.')
        result[map_type] = {
            'world_min': [minimum[0], minimum[1]],
            'world_max': [maximum[0], maximum[1]],
        }
    return result


def _canonical_pal_lookup(
    characters: Mapping[str, Any],
) -> tuple[dict[str, str], dict[str, str]]:
    rows = characters.get('pals')
    if not isinstance(rows, list):
        raise SpawnExportError('Character data does not contain a Pal list.')
    ids: dict[str, str] = {}
    names: dict[str, str] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        pal_id = str(row.get('asset') or '').strip()
        name = str(row.get('name') or '').strip()
        if pal_id and name:
            ids.setdefault(pal_id.casefold(), pal_id)
            names.setdefault(pal_id, name)
    if not ids:
        raise SpawnExportError('Character data does not contain usable Pal IDs.')
    return ids, names


def _normalize_pal_id(raw_id: Any, canonical: Mapping[str, str]) -> str | None:
    value = str(raw_id or '').strip()
    if not value or value.casefold() in {'none', 'null'}:
        return None
    candidates: list[str] = []
    stripped = value
    changed = True
    while changed:
        changed = False
        for prefix in PAL_ID_PREFIXES:
            if stripped.casefold().startswith(prefix.casefold()):
                stripped = stripped[len(prefix):]
                candidates.append(stripped)
                changed = True
                break
    candidates.append(value)
    for candidate in candidates:
        match = canonical.get(candidate.casefold())
        if match:
            return match
    return None


def _time_code(value: Any, unknown_values: set[str]) -> int:
    text = str(value or 'Undefined').split('::')[-1].strip()
    key = text.casefold()
    if key in {'', 'undefined', 'none', 'any', 'anytime'}:
        return 0
    if key.startswith('day'):
        return 1
    if key.startswith('night'):
        return 2
    unknown_values.add(text)
    return 0


def _inside(
    x: float,
    y: float,
    bounds: Mapping[str, list[float]],
) -> bool:
    minimum = bounds['world_min']
    maximum = bounds['world_max']
    return minimum[0] <= x <= maximum[0] and minimum[1] <= y <= maximum[1]


def _map_type_for_placement(
    spawner_name: str,
    x: float,
    y: float,
    map_bounds: Mapping[str, Mapping[str, list[float]]],
) -> str | None:
    if 'worldtree' in spawner_name.casefold():
        return 'tree' if _inside(x, y, map_bounds['tree']) else None
    if _inside(x, y, map_bounds['world']):
        return 'world'
    if _inside(x, y, map_bounds['tree']):
        return 'tree'
    return None


def build_spawn_payload(
    placement_rows: Mapping[str, Mapping[str, Any]],
    wild_rows: Mapping[str, Mapping[str, Any]],
    map_rows: Mapping[str, Mapping[str, Any]],
    characters: Mapping[str, Any],
    *,
    game_version: str,
) -> dict[str, Any]:
    map_bounds = extract_map_bounds(map_rows)
    canonical, pal_names = _canonical_pal_lookup(characters)
    unknown_pal_ids: set[str] = set()
    unknown_time_values: set[str] = set()

    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    group_weight_totals: dict[str, float] = defaultdict(float)
    for row_name, row in wild_rows.items():
        spawner_name = str(row.get('SpawnerName') or row_name).strip()
        if not spawner_name:
            continue
        weight = max(0.0, _number(row.get('Weight'), 0.0))
        pals: list[tuple[str, int, int]] = []
        for index in range(1, 4):
            raw_pal_id = row.get(f'Pal_{index}')
            if not raw_pal_id:
                continue
            pal_id = _normalize_pal_id(raw_pal_id, canonical)
            if pal_id is None:
                unknown_pal_ids.add(str(raw_pal_id))
                continue
            level_min = round(_number(row.get(f'LvMin_{index}'), 0.0))
            level_max = round(_number(row.get(f'LvMax_{index}'), level_min))
            pals.append((pal_id, level_min, max(level_min, level_max)))
        if not pals:
            continue
        groups[spawner_name].append({
            'weight': weight,
            'time': _time_code(row.get('OnlyTime'), unknown_time_values),
            'pals': tuple(dict.fromkeys(pals)),
        })
        group_weight_totals[spawner_name] += weight

    combined: dict[
        str,
        dict[str, dict[tuple[int, int, int, int, int, int], float]],
    ] = defaultdict(lambda: {'world': defaultdict(float), 'tree': defaultdict(float)})
    matched_placements = 0
    outside_placements = 0
    unmatched_placements = 0
    for row in placement_rows.values():
        spawner_name = str(row.get('SpawnerName') or '').strip()
        rows = groups.get(spawner_name)
        if not rows:
            unmatched_placements += 1
            continue
        try:
            x, y = _vector(row.get('Location'), 'spawn location')
        except SpawnExportError:
            outside_placements += 1
            continue
        map_type = _map_type_for_placement(
            spawner_name,
            x,
            y,
            map_bounds,
        )
        if map_type is None:
            outside_placements += 1
            continue
        radius = round(max(0.0, _number(row.get('StaticRadius'), 0.0)))
        total_weight = group_weight_totals.get(spawner_name, 0.0)
        if total_weight <= 0:
            total_weight = float(len(rows))
        matched_placements += 1
        for group in rows:
            probability = (
                group['weight'] / total_weight
                if group['weight'] > 0
                else 1.0 / len(rows)
            )
            for pal_id, level_min, level_max in group['pals']:
                key = (
                    round(x),
                    round(y),
                    radius,
                    level_min,
                    level_max,
                    group['time'],
                )
                combined[pal_id][map_type][key] += probability

    pals: dict[str, dict[str, Any]] = {}
    spawn_entry_count = 0
    for pal_id in sorted(combined, key=str.casefold):
        maps: dict[str, list[list[int | float]]] = {}
        for map_type in ('world', 'tree'):
            entries = [
                [*key, round(min(weight, 1.0), 5)]
                for key, weight in combined[pal_id][map_type].items()
            ]
            entries.sort(key=lambda item: (item[0], item[1], item[5], item[3]))
            if entries:
                maps[map_type] = entries
                spawn_entry_count += len(entries)
        if maps:
            pals[pal_id] = {'name': pal_names[pal_id], **maps}

    return {
        'schema_version': SCHEMA_VERSION,
        'game_version': str(game_version),
        'source_tables': [
            'DT_WorldMapUIData',
            'DT_PalSpawnerPlacement',
            'DT_PalWildSpawner',
        ],
        'map_bounds': map_bounds,
        'counts': {
            'pals': len(pals),
            'spawn_entries': spawn_entry_count,
            'placements': len(placement_rows),
            'matched_placements': matched_placements,
            'unmatched_placements': unmatched_placements,
            'outside_map_placements': outside_placements,
        },
        'unmatched_pal_ids': sorted(unknown_pal_ids, key=str.casefold),
        'unknown_time_values': sorted(unknown_time_values, key=str.casefold),
        'pals': pals,
    }


def _read_object(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    try:
        value = json.loads(source.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as exc:
        raise SpawnExportError(f'Could not read {source}: {exc}') from exc
    if not isinstance(value, dict):
        raise SpawnExportError(f'{source} must contain a JSON object.')
    return value


def main() -> int:
    parser = argparse.ArgumentParser(
        description='Build compact Pal spawn heatmap data from Palworld exports.',
    )
    parser.add_argument('--placement', required=True, type=Path)
    parser.add_argument('--wild', required=True, type=Path)
    parser.add_argument('--map-metadata', required=True, type=Path)
    parser.add_argument('--characters', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--game-version', required=True)
    args = parser.parse_args()

    payload = build_spawn_payload(
        load_data_table(args.placement),
        load_data_table(args.wild),
        load_data_table(args.map_metadata),
        _read_object(args.characters),
        game_version=args.game_version,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=True, separators=(',', ':')) + '\n',
        encoding='utf-8',
    )
    print(
        f"Wrote {payload['counts']['spawn_entries']} spawn entries for "
        f"{payload['counts']['pals']} Pals to {args.output}"
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
