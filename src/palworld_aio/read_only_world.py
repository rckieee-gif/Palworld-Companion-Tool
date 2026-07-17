from __future__ import annotations

from dataclasses import dataclass
import hashlib
import logging
from pathlib import Path
from typing import Callable, Mapping

import palworld_coord
from palsav.archive import FArchiveReader
from palsav.io import load_sav
from palsav.paltypes import PALWORLD_CUSTOM_PROPERTIES


LOGGER = logging.getLogger(__name__)


class WorldLoadError(ValueError):
    """Raised when a selected world cannot be validated or decoded."""


@dataclass(frozen=True, slots=True)
class FileFingerprint:
    size: int
    modified_ns: int
    sha256: str


@dataclass(frozen=True, slots=True)
class GuildMarkerGroup:
    guild_id: str
    name: str
    leader_name: str
    level: int
    member_count: int
    last_seen: str
    last_seen_seconds: float | None


@dataclass(frozen=True, slots=True)
class BaseMarkerData:
    base_id: str
    guild_id: str
    guild_name: str
    leader_name: str
    guild_level: int
    member_count: int
    base_position: int
    pal_count: int
    coordinates: tuple[int, int]
    legacy_coordinates: tuple[int, int]
    save_coordinates: tuple[float, float, float]
    map_type: str
    radius: float


@dataclass(frozen=True, slots=True)
class PlayerMarkerData:
    player_uid: str
    player_name: str
    level: int | str
    guild_id: str
    guild_name: str
    last_seen: str
    last_seen_seconds: float | None
    coordinates: tuple[int, int]
    save_coordinates: tuple[float, float, float]
    map_type: str


@dataclass(frozen=True, slots=True)
class ReadOnlyWorldData:
    source_path: Path
    fingerprint: FileFingerprint
    guilds: tuple[GuildMarkerGroup, ...]
    bases: tuple[BaseMarkerData, ...]
    players: tuple[PlayerMarkerData, ...]
    warnings: tuple[str, ...] = ()

    @property
    def display_name(self) -> str:
        return self.source_path.parent.name or self.source_path.name


def fingerprint_file(path: Path) -> FileFingerprint:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    stat = path.stat()
    return FileFingerprint(stat.st_size, stat.st_mtime_ns, digest.hexdigest())


def _skip_decode(
    reader: FArchiveReader,
    type_name: str,
    size: int,
    _path: str,
) -> dict:
    if type_name == 'ArrayProperty':
        return {
            'skip_type': type_name,
            'array_type': reader.fstring(),
            'id': reader.optional_guid(),
            'value': reader.read(size),
        }
    if type_name == 'MapProperty':
        return {
            'skip_type': type_name,
            'key_type': reader.fstring(),
            'value_type': reader.fstring(),
            'id': reader.optional_guid(),
            'value': reader.read(size),
        }
    if type_name == 'StructProperty':
        return {
            'skip_type': type_name,
            'struct_type': reader.fstring(),
            'struct_id': reader.guid(),
            'id': reader.optional_guid(),
            'value': reader.read(size),
        }
    raise WorldLoadError(f'Unsupported property type: {type_name}')


def _safe_decoder(path: str, decoder: Callable) -> Callable:
    def decode(reader, type_name, size, current_path):
        position = reader.data.tell()
        try:
            result = decoder(reader, type_name, size, current_path)
            result['__skip__'] = False
            return result
        except (KeyError, TypeError, ValueError, EOFError, UnicodeError) as exc:
            LOGGER.warning('Could not decode %s (%s); retaining opaque bytes', path, exc)
            reader.data.seek(position)
            result = _skip_decode(reader, type_name, size, current_path)
            result['__skip__'] = True
            return result

    return decode


_READ_ONLY_CUSTOM_PROPERTIES = {
    path: (_safe_decoder(path, pair[0]), None)
    for path, pair in PALWORLD_CUSTOM_PROPERTIES.items()
}
for _heavy_path in (
    '.worldSaveData.MapObjectSaveData.MapObjectSaveData.WorldLocation',
    '.worldSaveData.MapObjectSaveData.MapObjectSaveData.WorldRotation',
    '.worldSaveData.MapObjectSaveData.MapObjectSaveData.Model.Value.EffectMap',
    '.worldSaveData.MapObjectSaveData.MapObjectSaveData.WorldScale3D',
    '.worldSaveData.FoliageGridSaveDataMap',
    '.worldSaveData.MapObjectSpawnerInStageSaveData',
):
    _READ_ONLY_CUSTOM_PROPERTIES[_heavy_path] = (_skip_decode, None)


def _decode_world_properties(path: Path) -> Mapping:
    return load_sav(
        str(path),
        custom_properties=_READ_ONLY_CUSTOM_PROPERTIES,
    ).properties


def _unwrap(value, default=None):
    while isinstance(value, dict) and 'value' in value:
        value = value['value']
    return default if value is None else value


def _normal_id(value) -> str:
    return str(_unwrap(value, '') or '').replace('-', '').lower()


def _format_elapsed(seconds: float | None) -> str:
    if seconds is None:
        return 'Unknown'
    seconds = max(0, int(seconds))
    if seconds < 60:
        return f'{seconds}s ago'
    minutes, seconds = divmod(seconds, 60)
    if minutes < 60:
        return f'{minutes}m {seconds}s ago'
    hours, minutes = divmod(minutes, 60)
    if hours < 24:
        return f'{hours}h {minutes}m ago'
    days, hours = divmod(hours, 24)
    return f'{days}d {hours}h ago'


def _world_save_data(properties: Mapping) -> Mapping:
    try:
        return properties['worldSaveData']['value']
    except (KeyError, TypeError):
        try:
            return properties['properties']['worldSaveData']['value']
        except (KeyError, TypeError) as exc:
            raise WorldLoadError('This file does not contain Palworld world data.') from exc


def _player_levels(world: Mapping) -> dict[str, int | str]:
    levels: dict[str, int | str] = {}
    for entry in world.get('CharacterSaveParameterMap', {}).get('value', []):
        try:
            parameter = entry['value']['RawData']['value']['object']['SaveParameter']
            raw = parameter['value']
            if parameter.get('struct_type') != 'PalIndividualCharacterSaveParameter':
                continue
            if not bool(_unwrap(raw.get('IsPlayer'), False)):
                continue
            uid = _normal_id(entry.get('key', {}).get('PlayerUId'))
            if uid:
                levels[uid] = _unwrap(raw.get('Level'), '?')
        except (KeyError, TypeError, AttributeError):
            continue
    return levels


def _worker_counts(world: Mapping) -> dict[str, int]:
    counts: dict[str, int] = {}
    for container in world.get('CharacterContainerSaveData', {}).get('value', []):
        try:
            container_id = _normal_id(container['key']['ID'])
            slots = container['value'].get('Slots', {}).get('value', {}).get('values', [])
            counts[container_id] = sum(slot is not None for slot in slots)
        except (KeyError, TypeError, AttributeError):
            continue
    return counts


def _map_coordinates(x: float, y: float) -> tuple[tuple[int, int], str]:
    world_point = palworld_coord.sav_to_map(x, y, new=True)
    if abs(world_point.x) <= 1000 and abs(world_point.y) <= 1000:
        return (world_point.x, world_point.y), 'world'
    tree_point = palworld_coord.sav_to_treemap(x, y)
    if abs(tree_point.x) <= 2500 and abs(tree_point.y) <= 2500:
        return (tree_point.x, tree_point.y), 'tree'
    return (world_point.x, world_point.y), 'world'


def _extract_world_markers(
    world: Mapping,
) -> tuple[
    tuple[GuildMarkerGroup, ...],
    tuple[BaseMarkerData, ...],
    list[dict],
]:
    tick = _unwrap(
        world.get('GameTimeSaveData', {})
        .get('value', {})
        .get('RealDateTimeTicks'),
        0,
    )
    base_entries = {
        _normal_id(entry.get('key')): entry.get('value', {})
        for entry in world.get('BaseCampSaveData', {}).get('value', [])
    }
    worker_counts = _worker_counts(world)

    guilds: list[GuildMarkerGroup] = []
    bases: list[BaseMarkerData] = []
    player_records: list[dict] = []
    for group in world.get('GroupSaveDataMap', {}).get('value', []):
        try:
            if _unwrap(group['value']['GroupType']) != 'EPalGroupType::Guild':
                continue
            guild_id = str(group.get('key', ''))
            raw = group['value']['RawData']['value']
        except (KeyError, TypeError):
            continue

        name = str(raw.get('guild_name') or 'Unnamed Guild')
        players = raw.get('players', []) or []
        admin_id = _normal_id(raw.get('admin_player_uid'))
        leader_name = 'Unknown'
        latest_online = None
        for player in players:
            uid = _normal_id(player.get('player_uid'))
            info = player.get('player_info', {}) or {}
            player_name = str(info.get('player_name') or 'Unknown')
            if uid == admin_id:
                leader_name = player_name
            online = info.get('last_online_real_time')
            if online is not None:
                latest_online = max(latest_online or online, online)
            player_records.append({
                'uid': uid,
                'name': player_name,
                'guild_id': guild_id,
                'guild_name': name,
                'last_online': online,
            })
        if leader_name == 'Unknown' and players:
            leader_name = str(
                (players[0].get('player_info', {}) or {}).get('player_name') or 'Unknown'
            )
        elapsed = None
        if tick and latest_online is not None:
            elapsed = (tick - latest_online) / 10_000_000.0

        guild_level = int(raw.get('base_camp_level', 1) or 1)
        guilds.append(GuildMarkerGroup(
            guild_id=guild_id,
            name=name,
            leader_name=leader_name,
            level=guild_level,
            member_count=len(players),
            last_seen=_format_elapsed(elapsed),
            last_seen_seconds=elapsed,
        ))

        base_position = 1
        for base_id_value in raw.get('base_ids', []) or []:
            base_id = str(base_id_value)
            base_value = base_entries.get(_normal_id(base_id_value))
            if not base_value:
                continue
            try:
                base_raw = base_value['RawData']['value']
                translation = base_raw['transform']['translation']
                x = float(translation['x'])
                y = float(translation['y'])
                z = float(translation.get('z', 0))
            except (KeyError, TypeError, ValueError):
                continue

            coordinates, map_type = _map_coordinates(x, y)
            legacy = palworld_coord.sav_to_map(x, y, new=False)
            worker_id = _normal_id(
                base_value.get('WorkerDirector', {})
                .get('value', {})
                .get('RawData', {})
                .get('value', {})
                .get('container_id')
            )
            bases.append(BaseMarkerData(
                base_id=base_id,
                guild_id=guild_id,
                guild_name=name,
                leader_name=leader_name,
                guild_level=guild_level,
                member_count=len(players),
                base_position=base_position,
                pal_count=worker_counts.get(worker_id, 0),
                coordinates=coordinates,
                legacy_coordinates=(legacy.x, legacy.y),
                save_coordinates=(x, y, z),
                map_type=map_type,
                radius=float(base_raw.get('area_range', 3500.0) or 3500.0),
            ))
            base_position += 1

    return tuple(guilds), tuple(bases), player_records


def _load_player_marker(
    player_file: Path,
    record: Mapping,
    levels: Mapping[str, int | str],
    tick: int | float,
    parser: Callable[[Path], Mapping],
) -> PlayerMarkerData | None:
    before = fingerprint_file(player_file)
    properties = parser(player_file)
    after = fingerprint_file(player_file)
    if before != after:
        raise WorldLoadError('A player save changed while it was being read.')
    try:
        save_data = properties['SaveData']['value']
        translation = save_data['LastTransform']['value']['Translation']['value']
        x = float(translation['x'])
        y = float(translation['y'])
        z = float(translation.get('z', 0))
    except (KeyError, TypeError, ValueError):
        return None

    coordinates, map_type = _map_coordinates(x, y)
    online = record.get('last_online')
    elapsed = None if online is None or not tick else (tick - online) / 10_000_000.0
    uid = str(record.get('uid', ''))
    return PlayerMarkerData(
        player_uid=uid.upper(),
        player_name=str(record.get('name') or 'Unknown'),
        level=levels.get(uid, '?'),
        guild_id=str(record.get('guild_id') or ''),
        guild_name=str(record.get('guild_name') or 'No Guild'),
        last_seen=_format_elapsed(elapsed),
        last_seen_seconds=elapsed,
        coordinates=coordinates,
        save_coordinates=(x, y, z),
        map_type=map_type,
    )


def load_read_only_world(
    path: str | Path,
    *,
    parser: Callable[[Path], Mapping] | None = None,
) -> ReadOnlyWorldData:
    source = Path(path).expanduser().resolve()
    if not source.is_file():
        raise WorldLoadError('Select an existing Level.sav file.')
    if source.name.lower() != 'level.sav':
        raise WorldLoadError('The selected file must be named Level.sav.')

    decode = parser or _decode_world_properties
    before = fingerprint_file(source)
    try:
        properties = decode(source)
        world = _world_save_data(properties)
        guilds, bases, player_records = _extract_world_markers(world)
        levels = _player_levels(world)
        tick = _unwrap(
            world.get('GameTimeSaveData', {})
            .get('value', {})
            .get('RealDateTimeTicks'),
            0,
        )
    except WorldLoadError:
        raise
    except (OSError, KeyError, TypeError, ValueError, EOFError) as exc:
        raise WorldLoadError(
            'The selected save could not be parsed. It may be incomplete or unsupported.'
        ) from exc

    after = fingerprint_file(source)
    if before != after:
        raise WorldLoadError('The world save changed while it was being read. Please try again.')

    warnings: list[str] = []
    players: list[PlayerMarkerData] = []
    players_dir = source.parent / 'Players'
    if not players_dir.is_dir():
        warnings.append('Players folder not found; player markers are unavailable.')
    else:
        skipped = 0
        for record in player_records:
            uid = str(record.get('uid') or '').upper()
            if not uid:
                continue
            player_file = players_dir / f'{uid}.sav'
            if not player_file.is_file():
                skipped += 1
                continue
            try:
                marker = _load_player_marker(player_file, record, levels, tick, decode)
            except (OSError, WorldLoadError, KeyError, TypeError, ValueError, EOFError):
                marker = None
            if marker is None:
                skipped += 1
            else:
                players.append(marker)
        if skipped:
            warnings.append(f'{skipped} player location(s) could not be displayed.')

    final_fingerprint = fingerprint_file(source)
    if before != final_fingerprint:
        raise WorldLoadError(
            'The world save changed while it was being read. Please try again.'
        )

    return ReadOnlyWorldData(
        source_path=source,
        fingerprint=before,
        guilds=guilds,
        bases=bases,
        players=tuple(players),
        warnings=tuple(warnings),
    )
