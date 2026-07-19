from __future__ import annotations

import argparse
from collections import Counter
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any

from app_info import GAME_DATA_VERSION
from resource_resolver import get_resources_dir


MANIFEST_FILENAME = 'manifest.json'
MANIFEST_SCHEMA_VERSION = 1
REQUIRED_DATA_FILES = frozenset({
    'append_text.json',
    'boss_mapping.json',
    'breedingdata.json',
    'characters.json',
    'fast_travel_points.json',
    'friendship.json',
    'items.json',
    'pal_exp_table.json',
    'pals_learnset.json',
    'relic_data.json',
    'skills.json',
    'uidata.json',
    'work_suitability.json',
    'world.json',
    'world_map_areas.json',
})
VALID_ICON_EXTENSIONS = frozenset({'.png', '.webp'})

_SECTION_TYPES: dict[str, dict[str, type]] = {
    'boss_mapping.json': {'boss_defeat_flag_map': dict},
    'breedingdata.json': {
        'pal_info': dict,
        'unique_combos': list,
        'child_to_parents_formula': dict,
        'child_to_parents_unique': dict,
        'child_to_parents_ignore': dict,
        'parent_to_children_formula': dict,
    },
    'characters.json': {'pals': list, 'npcs': list, 'friendship': dict},
    'items.json': {'items': list, 'items_dynamic': dict},
    'pals_learnset.json': {'learnset': dict},
    'skills.json': {'passives': list, 'skills': list, 'elements': list},
    'uidata.json': {'ui_icons': dict},
    'work_suitability.json': {'work_types': list},
    'world.json': {'structures': list, 'technology': list, 'lab_research': dict},
    'world_map_areas.json': {'areas': list},
}

_ENTRY_FIELDS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ('characters.json', 'pals', ('name', 'asset', 'icon')),
    ('characters.json', 'npcs', ('name', 'asset', 'icon')),
    (
        'items.json',
        'items',
        ('name', 'asset', 'icon', 'rarity', 'type_a', 'type_b', 'description', 'sort_id'),
    ),
    (
        'skills.json',
        'passives',
        ('name', 'asset', 'rank', 'icon', 'description'),
    ),
    (
        'skills.json',
        'skills',
        ('name', 'asset', 'element', 'power', 'cooldown', 'description'),
    ),
    (
        'skills.json',
        'elements',
        ('name', 'display', 'index', 'color', 'icons'),
    ),
    ('world.json', 'structures', ('name', 'asset', 'icon')),
    (
        'world.json',
        'technology',
        ('name', 'asset', 'icon', 'type', 'description'),
    ),
    ('work_suitability.json', 'work_types', ('id', 'display_name', 'icon', 'index')),
)

_UNIQUE_FIELDS: tuple[tuple[str, str, str], ...] = (
    ('characters.json', 'pals', 'asset'),
    ('characters.json', 'npcs', 'asset'),
    ('items.json', 'items', 'asset'),
    ('skills.json', 'passives', 'asset'),
    ('skills.json', 'skills', 'asset'),
    ('skills.json', 'elements', 'index'),
    ('world.json', 'structures', 'asset'),
    ('world.json', 'technology', 'asset'),
    ('work_suitability.json', 'work_types', 'id'),
)


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    message: str
    location: str = ''
    severity: str = 'error'

    def to_dict(self) -> dict[str, str]:
        value = {
            'code': self.code,
            'message': self.message,
            'severity': self.severity,
        }
        if self.location:
            value['location'] = self.location
        return value


@dataclass(frozen=True)
class GameDataValidationReport:
    game_data_version: str
    schema_version: int | None
    files_checked: int
    icons_checked: int
    known_icon_fallbacks: int
    issues: tuple[ValidationIssue, ...]

    @property
    def errors(self) -> tuple[ValidationIssue, ...]:
        return tuple(issue for issue in self.issues if issue.severity == 'error')

    @property
    def warnings(self) -> tuple[ValidationIssue, ...]:
        return tuple(issue for issue in self.issues if issue.severity == 'warning')

    @property
    def is_valid(self) -> bool:
        return not self.errors

    def summary(self) -> str:
        if self.is_valid:
            summary = (
                f'Game data {self.game_data_version} is valid: '
                f'{self.files_checked} JSON files and {self.icons_checked} icons checked.'
            )
            if self.warnings:
                noun = 'warning' if len(self.warnings) == 1 else 'warnings'
                summary += f' {len(self.warnings)} {noun} reported.'
            return summary
        noun = 'error' if len(self.errors) == 1 else 'errors'
        return (
            f'Game data {self.game_data_version} failed validation with '
            f'{len(self.errors)} {noun}.'
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            'valid': self.is_valid,
            'game_data_version': self.game_data_version,
            'schema_version': self.schema_version,
            'files_checked': self.files_checked,
            'icons_checked': self.icons_checked,
            'known_icon_fallbacks': self.known_icon_fallbacks,
            'issues': [issue.to_dict() for issue in self.issues],
        }


class _IssueCollector:
    def __init__(self) -> None:
        self.issues: list[ValidationIssue] = []

    def add(self, code: str, message: str, location: str = '') -> None:
        self.issues.append(ValidationIssue(code, message, location))

    def warn(self, code: str, message: str, location: str = '') -> None:
        self.issues.append(ValidationIssue(code, message, location, 'warning'))


def default_game_data_dir() -> Path:
    return Path(get_resources_dir()) / 'game_data'


def _read_json_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(value, dict):
        raise ValueError('top-level value must be an object')
    return value


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _section_counts(value: Mapping[str, Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for key, section in sorted(value.items()):
        counts[str(key)] = len(section) if isinstance(section, (dict, list)) else 1
    return counts


def _icon_files(data_dir: Path) -> list[Path]:
    icon_dir = data_dir / 'icons'
    if not icon_dir.is_dir():
        return []
    return sorted(
        (path for path in icon_dir.rglob('*') if path.is_file()),
        key=lambda path: path.relative_to(data_dir).as_posix(),
    )


def _icon_bundle_metadata(data_dir: Path) -> dict[str, int | str]:
    files = _icon_files(data_dir)
    digest = hashlib.sha256()
    total_bytes = 0
    for path in files:
        relative = path.relative_to(data_dir).as_posix()
        digest.update(relative.encode('utf-8'))
        digest.update(b'\0')
        with path.open('rb') as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                total_bytes += len(chunk)
                digest.update(chunk)
        digest.update(b'\0')
    return {
        'count': len(files),
        'bytes': total_bytes,
        'sha256': digest.hexdigest(),
    }


def _missing_icon_paths(
    data_dir: Path,
    parsed: Mapping[str, dict[str, Any]],
) -> list[str]:
    missing: set[str] = set()
    for data in parsed.values():
        for icon_path, _field_path in _iter_icon_references(data, location=''):
            normalized = '/' + icon_path.strip().lstrip('/')
            if (
                '\\' not in icon_path
                and normalized.startswith('/icons/')
                and '..' not in Path(normalized.lstrip('/')).parts
                and Path(normalized).suffix.lower() in VALID_ICON_EXTENSIONS
                and not (data_dir / normalized.lstrip('/')).is_file()
            ):
                missing.add(normalized)
    return sorted(missing)


def build_game_data_manifest(
    data_dir: Path,
    *,
    game_data_version: str = GAME_DATA_VERSION,
) -> dict[str, Any]:
    data_dir = Path(data_dir)
    file_entries: dict[str, dict[str, Any]] = {}
    parsed: dict[str, dict[str, Any]] = {}
    for path in sorted(data_dir.glob('*.json')):
        if path.name == MANIFEST_FILENAME:
            continue
        value = _read_json_object(path)
        parsed[path.name] = value
        file_entries[path.name] = {
            'bytes': path.stat().st_size,
            'sha256': _sha256_file(path),
            'sections': _section_counts(value),
        }

    pal_info = parsed.get('breedingdata.json', {}).get('pal_info', {})
    unavailable_pals = sorted(
        str(species)
        for species, info in pal_info.items()
        if isinstance(info, dict) and info.get('available') is False
    ) if isinstance(pal_info, dict) else []

    return {
        'schema_version': MANIFEST_SCHEMA_VERSION,
        'game_data_version': str(game_data_version),
        'source': {
            'kind': 'bundled-game-export',
            'updater': 'scripts/scrs/update_game_data.py',
        },
        'files': file_entries,
        'icons': _icon_bundle_metadata(data_dir),
        'known_missing_icons': _missing_icon_paths(data_dir, parsed),
        'unavailable_pals': unavailable_pals,
    }


def write_game_data_manifest(
    data_dir: Path,
    *,
    game_data_version: str = GAME_DATA_VERSION,
) -> Path:
    data_dir = Path(data_dir)
    manifest = build_game_data_manifest(
        data_dir,
        game_data_version=game_data_version,
    )
    output = data_dir / MANIFEST_FILENAME
    temporary = output.with_suffix('.json.tmp')
    temporary.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=True) + '\n',
        encoding='utf-8',
    )
    temporary.replace(output)
    return output


def _validate_manifest_files(
    data_dir: Path,
    manifest: Mapping[str, Any],
    parsed: dict[str, dict[str, Any]],
    collector: _IssueCollector,
) -> int:
    manifest_files = manifest.get('files')
    if not isinstance(manifest_files, dict):
        collector.add('manifest.files', 'Manifest files must be an object.', MANIFEST_FILENAME)
        manifest_files = {}

    actual_names = {
        path.name for path in data_dir.glob('*.json') if path.name != MANIFEST_FILENAME
    }
    missing_required = sorted(REQUIRED_DATA_FILES - actual_names)
    for filename in missing_required:
        collector.add('file.missing', 'Required game-data file is missing.', filename)

    for filename in sorted(actual_names - set(manifest_files)):
        collector.add(
            'manifest.file_untracked',
            'JSON file is not recorded in the manifest.',
            filename,
        )
    for filename in sorted(set(manifest_files) - actual_names):
        collector.add(
            'manifest.file_missing',
            'Manifest references a JSON file that is missing.',
            filename,
        )

    files_checked = 0
    for filename in sorted(actual_names):
        path = data_dir / filename
        try:
            value = _read_json_object(path)
        except FileNotFoundError:
            collector.add('file.missing', 'Game-data file is missing.', filename)
            continue
        except OSError as exc:
            collector.add('file.read', f'Could not read file: {exc}', filename)
            continue
        except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as exc:
            collector.add('file.json', f'Invalid JSON object: {exc}', filename)
            continue

        parsed[filename] = value
        files_checked += 1
        expected = manifest_files.get(filename)
        if not isinstance(expected, dict):
            continue

        try:
            actual_size = path.stat().st_size
            actual_hash = _sha256_file(path)
        except OSError as exc:
            collector.add('file.read', f'Could not inspect file: {exc}', filename)
            continue
        if expected.get('bytes') != actual_size:
            collector.add(
                'file.size',
                f'Expected {expected.get("bytes")} bytes, found {actual_size}.',
                filename,
            )
        if expected.get('sha256') != actual_hash:
            collector.add('file.checksum', 'SHA-256 does not match the manifest.', filename)
        if expected.get('sections') != _section_counts(value):
            collector.add(
                'file.sections',
                'Top-level record counts do not match the manifest.',
                filename,
            )
    return files_checked


def _validate_sections(
    parsed: Mapping[str, dict[str, Any]],
    collector: _IssueCollector,
) -> None:
    for filename, sections in _SECTION_TYPES.items():
        data = parsed.get(filename)
        if data is None:
            continue
        for section_name, expected_type in sections.items():
            section = data.get(section_name)
            if not isinstance(section, expected_type):
                collector.add(
                    'schema.section',
                    f'Expected {section_name} to be {expected_type.__name__}.',
                    filename,
                )

    for filename, section_name, fields in _ENTRY_FIELDS:
        section = parsed.get(filename, {}).get(section_name)
        if not isinstance(section, list):
            continue
        for index, entry in enumerate(section):
            location = f'{filename}:{section_name}[{index}]'
            if not isinstance(entry, dict):
                collector.add('schema.entry', 'Expected an object.', location)
                continue
            missing = [field for field in fields if field not in entry]
            if missing:
                collector.add(
                    'schema.fields',
                    f'Missing required fields: {", ".join(missing)}.',
                    location,
                )

    for filename, section_name, field in _UNIQUE_FIELDS:
        section = parsed.get(filename, {}).get(section_name)
        if not isinstance(section, list):
            continue
        values: list[Any] = []
        for index, entry in enumerate(section):
            if not isinstance(entry, dict) or entry.get(field) is None:
                continue
            value = entry[field]
            try:
                hash(value)
            except TypeError:
                collector.add(
                    'schema.field_type',
                    f'{field} must be a scalar value.',
                    f'{filename}:{section_name}[{index}]',
                )
                continue
            values.append(value)
        duplicates = sorted(
            (value for value, count in Counter(values).items() if count > 1),
            key=str,
        )
        if duplicates:
            collector.add(
                'schema.duplicate',
                f'Duplicate {field} values: {", ".join(map(str, duplicates[:20]))}.',
                f'{filename}:{section_name}',
            )


def _validate_breeding_data(
    data: Mapping[str, Any],
    manifest: Mapping[str, Any],
    collector: _IssueCollector,
) -> None:
    pal_info = data.get('pal_info')
    if not isinstance(pal_info, dict):
        return
    known_species = set(pal_info)
    if not known_species:
        collector.add('breeding.empty', 'Breeding Pal information is empty.', 'breedingdata.json')
        return

    for species, info in pal_info.items():
        location = f'breedingdata.json:pal_info.{species}'
        if not isinstance(info, dict):
            collector.add('breeding.pal', 'Pal information must be an object.', location)
            continue
        for field in ('name', 'combi_rank', 'rarity', 'ignore_combi', 'icon'):
            if field not in info:
                collector.add('breeding.pal_field', f'Missing required field: {field}.', location)
        if 'available' in info and not isinstance(info['available'], bool):
            collector.add('breeding.availability', 'available must be a boolean.', location)

    def check_species(species: Any, location: str) -> None:
        if not isinstance(species, str) or species not in known_species:
            collector.add(
                'breeding.reference',
                f'Unknown Pal reference: {species!r}.',
                location,
            )

    for section_name in (
        'child_to_parents_formula',
        'child_to_parents_unique',
        'child_to_parents_ignore',
    ):
        section = data.get(section_name)
        if not isinstance(section, dict):
            continue
        for child, pairs in section.items():
            location = f'breedingdata.json:{section_name}.{child}'
            check_species(child, location)
            if not isinstance(pairs, list):
                collector.add('breeding.pairs', 'Parent combinations must be a list.', location)
                continue
            for index, pair in enumerate(pairs):
                pair_location = f'{location}[{index}]'
                if not isinstance(pair, dict):
                    collector.add(
                        'breeding.pair',
                        'Parent combination must be an object.',
                        pair_location,
                    )
                    continue
                parent_a = pair.get('parent_a')
                parent_b = pair.get('parent_b')
                check_species(parent_a, pair_location)
                check_species(parent_b, pair_location)

    unique_combos = data.get('unique_combos')
    if isinstance(unique_combos, list):
        for index, combo in enumerate(unique_combos):
            location = f'breedingdata.json:unique_combos[{index}]'
            if not isinstance(combo, dict):
                collector.add('breeding.combo', 'Special combination must be an object.', location)
                continue
            for field in ('parent_a', 'parent_b', 'child'):
                check_species(combo.get(field), location)

    parent_map = data.get('parent_to_children_formula')
    if isinstance(parent_map, dict):
        for parent, entries in parent_map.items():
            location = f'breedingdata.json:parent_to_children_formula.{parent}'
            check_species(parent, location)
            if not isinstance(entries, list):
                collector.add('breeding.children', 'Child combinations must be a list.', location)
                continue
            for index, entry in enumerate(entries):
                entry_location = f'{location}[{index}]'
                if not isinstance(entry, dict):
                    collector.add(
                        'breeding.child',
                        'Child combination must be an object.',
                        entry_location,
                    )
                    continue
                check_species(entry.get('partner'), entry_location)
                check_species(entry.get('child'), entry_location)

    actual_unavailable = sorted(
        species
        for species, info in pal_info.items()
        if isinstance(info, dict) and info.get('available') is False
    )
    manifest_unavailable = manifest.get('unavailable_pals')
    if manifest_unavailable != actual_unavailable:
        collector.add(
            'breeding.unavailable_manifest',
            'Unavailable Pal list does not match breeding data.',
            MANIFEST_FILENAME,
        )


def _iter_icon_references(
    value: Any,
    *,
    location: str,
) -> Iterator[tuple[str, str]]:
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.startswith('/icons/') or stripped.startswith('icons/'):
            yield stripped, location
        return
    if isinstance(value, dict):
        for key, child in value.items():
            child_location = f'{location}.{key}' if location else str(key)
            yield from _iter_icon_references(child, location=child_location)
        return
    if isinstance(value, list):
        for index, child in enumerate(value):
            yield from _iter_icon_references(child, location=f'{location}[{index}]')


def _validate_icon_references(
    data_dir: Path,
    parsed: Mapping[str, dict[str, Any]],
    manifest: Mapping[str, Any],
    collector: _IssueCollector,
) -> int:
    missing_paths: set[str] = set()
    for filename, data in parsed.items():
        for icon_path, field_path in _iter_icon_references(data, location=''):
            location = f'{filename}:{field_path}'
            if '\\' in icon_path:
                collector.add('icon.separator', 'Icon path must use forward slashes.', location)
                continue
            normalized = '/' + icon_path.lstrip('/')
            parts = Path(normalized.lstrip('/')).parts
            if '..' in parts or not normalized.startswith('/icons/'):
                collector.add('icon.path', f'Invalid icon path: {icon_path}.', location)
                continue
            if Path(normalized).suffix.lower() not in VALID_ICON_EXTENSIONS:
                collector.add(
                    'icon.extension',
                    f'Unsupported icon extension: {icon_path}.',
                    location,
                )
                continue
            if not (data_dir / normalized.lstrip('/')).is_file():
                missing_paths.add(normalized)

    known_missing = manifest.get('known_missing_icons')
    if not isinstance(known_missing, list) or any(
        not isinstance(path, str) for path in known_missing
    ):
        collector.add(
            'manifest.missing_icons',
            'Manifest known_missing_icons must be a list of paths.',
            MANIFEST_FILENAME,
        )
        known_missing_set: set[str] = set()
    else:
        known_missing_set = set(known_missing)

    if missing_paths != known_missing_set:
        added = sorted(missing_paths - known_missing_set)
        resolved = sorted(known_missing_set - missing_paths)
        details: list[str] = []
        if added:
            details.append(f'{len(added)} new missing')
        if resolved:
            details.append(f'{len(resolved)} resolved')
        collector.add(
            'icon.missing_manifest',
            f'Missing-icon baseline changed ({", ".join(details)}).',
            MANIFEST_FILENAME,
        )
    if missing_paths:
        examples = ', '.join(sorted(missing_paths)[:3])
        collector.warn(
            'icon.fallbacks',
            f'{len(missing_paths)} known icon paths use the unknown-icon fallback. '
            f'Examples: {examples}.',
            'icons',
        )
    return len(missing_paths)


def _validate_icon_bundle(
    data_dir: Path,
    manifest: Mapping[str, Any],
    collector: _IssueCollector,
) -> int:
    expected = manifest.get('icons')
    if not isinstance(expected, dict):
        collector.add('manifest.icons', 'Manifest icons must be an object.', MANIFEST_FILENAME)
        expected = {}
    try:
        actual = _icon_bundle_metadata(data_dir)
    except OSError as exc:
        collector.add('icon.read', f'Could not inspect icon bundle: {exc}', 'icons')
        return 0
    if expected.get('count') != actual['count']:
        collector.add('icon.count', 'Icon count does not match the manifest.', 'icons')
    if expected.get('bytes') != actual['bytes']:
        collector.add('icon.size', 'Icon bundle size does not match the manifest.', 'icons')
    if expected.get('sha256') != actual['sha256']:
        collector.add('icon.checksum', 'Icon bundle SHA-256 does not match the manifest.', 'icons')
    if not (data_dir / 'icons' / 'T_icon_unknown.webp').is_file():
        collector.add('icon.fallback', 'Unknown-icon fallback is missing.', 'icons')
    return int(actual['count'])


def validate_game_data(
    data_dir: Path | None = None,
    *,
    expected_version: str | None = GAME_DATA_VERSION,
) -> GameDataValidationReport:
    data_dir = Path(data_dir) if data_dir is not None else default_game_data_dir()
    collector = _IssueCollector()
    manifest_path = data_dir / MANIFEST_FILENAME
    try:
        manifest = _read_json_object(manifest_path)
    except FileNotFoundError:
        collector.add('manifest.missing', 'Game-data manifest is missing.', MANIFEST_FILENAME)
        manifest = {}
    except OSError as exc:
        collector.add('manifest.read', f'Could not read manifest: {exc}', MANIFEST_FILENAME)
        manifest = {}
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as exc:
        collector.add('manifest.json', f'Invalid manifest: {exc}', MANIFEST_FILENAME)
        manifest = {}

    schema_version = manifest.get('schema_version')
    if schema_version != MANIFEST_SCHEMA_VERSION:
        collector.add(
            'manifest.schema_version',
            f'Expected schema {MANIFEST_SCHEMA_VERSION}, found {schema_version!r}.',
            MANIFEST_FILENAME,
        )
    game_data_version = str(manifest.get('game_data_version', 'unknown'))
    if expected_version is not None and game_data_version != str(expected_version):
        collector.add(
            'manifest.game_version',
            f'Expected game data {expected_version}, found {game_data_version}.',
            MANIFEST_FILENAME,
        )

    parsed: dict[str, dict[str, Any]] = {}
    files_checked = _validate_manifest_files(data_dir, manifest, parsed, collector)
    _validate_sections(parsed, collector)
    breeding_data = parsed.get('breedingdata.json')
    if breeding_data is not None:
        _validate_breeding_data(breeding_data, manifest, collector)
    known_icon_fallbacks = _validate_icon_references(
        data_dir,
        parsed,
        manifest,
        collector,
    )
    icons_checked = _validate_icon_bundle(data_dir, manifest, collector)

    return GameDataValidationReport(
        game_data_version=game_data_version,
        schema_version=schema_version if isinstance(schema_version, int) else None,
        files_checked=files_checked,
        icons_checked=icons_checked,
        known_icon_fallbacks=known_icon_fallbacks,
        issues=tuple(collector.issues),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Validate bundled Palworld game data')
    parser.add_argument('--data-dir', type=Path, default=default_game_data_dir())
    parser.add_argument('--expected-version', default=GAME_DATA_VERSION)
    parser.add_argument('--json', action='store_true', dest='as_json')
    args = parser.parse_args(argv)

    report = validate_game_data(
        args.data_dir,
        expected_version=args.expected_version,
    )
    if args.as_json:
        print(json.dumps(report.to_dict(), indent=2, ensure_ascii=True))
    else:
        print(report.summary())
        for issue in report.issues:
            location = f' [{issue.location}]' if issue.location else ''
            print(f'- {issue.severity}: {issue.code}{location}: {issue.message}')
    return 0 if report.is_valid else 1


if __name__ == '__main__':
    raise SystemExit(main())
