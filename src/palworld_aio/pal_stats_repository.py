from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math
from typing import Any

from palworld_aio.game_data import GameDataError, load_game_data
from palworld_aio.stat_calculator import PalBaseStats


@dataclass(frozen=True)
class PalStatsRecord:
    """One calculator-ready Pal species row from bundled game data."""

    pal_id: str
    name: str
    base_stats: PalBaseStats
    label: str


class PalLookupStatus(str, Enum):
    """Outcome of an exact, case-insensitive Pal lookup."""

    FOUND = 'found'
    AMBIGUOUS = 'ambiguous'
    MISSING = 'missing'


@dataclass(frozen=True)
class PalLookupResult:
    """Resolved Pal record or candidates for a duplicate display name."""

    status: PalLookupStatus
    record: PalStatsRecord | None = None
    matches: tuple[PalStatsRecord, ...] = ()


class PalStatsRepository:
    """Read-only loader and search service for Pal base-stat scaling."""

    def __init__(self, records: tuple[PalStatsRecord, ...]):
        self._records = records
        self._by_id = {record.pal_id.casefold(): record for record in records}
        self._by_label = {record.label.casefold(): record for record in records}
        by_name: dict[str, list[PalStatsRecord]] = {}
        for record in records:
            by_name.setdefault(record.name.casefold(), []).append(record)
        self._by_name = {
            name: tuple(items)
            for name, items in by_name.items()
        }

    @classmethod
    def from_game_data(cls) -> 'PalStatsRepository':
        """Load canonical calculator-ready rows from bundled game data."""

        data = load_game_data('characters.json')
        rows = data.get('pals')
        if not isinstance(rows, list):
            raise GameDataError('Character data does not contain a Pal list.')
        breeding_data = load_game_data('breedingdata.json')
        pal_info = breeding_data.get('pal_info')
        if not isinstance(pal_info, dict):
            raise GameDataError('Breeding data does not contain canonical Pal information.')
        canonical_ids = {
            str(pal_id).casefold()
            for pal_id, info in pal_info.items()
            if isinstance(info, dict) and info.get('available') is not False
        }

        candidates: list[tuple[str, str, PalBaseStats]] = []
        name_counts: dict[str, int] = {}
        for row in rows:
            if (
                not isinstance(row, dict)
                or str(row.get('asset') or '').casefold() not in canonical_ids
            ):
                continue
            parsed = cls._parse_row(row)
            if parsed is None:
                continue
            pal_id, name, base_stats = parsed
            candidates.append(parsed)
            name_counts[name.casefold()] = name_counts.get(name.casefold(), 0) + 1

        records = tuple(
            PalStatsRecord(
                pal_id=pal_id,
                name=name,
                base_stats=base_stats,
                label=(
                    f'{name} \u2014 {pal_id}'
                    if name_counts[name.casefold()] > 1
                    else name
                ),
            )
            for pal_id, name, base_stats in candidates
        )
        return cls(tuple(sorted(records, key=lambda item: (item.name.casefold(), item.pal_id.casefold()))))

    @staticmethod
    def _parse_row(row: Any) -> tuple[str, str, PalBaseStats] | None:
        if not isinstance(row, dict):
            return None
        pal_id = str(row.get('asset') or '').strip()
        name = str(row.get('name') or '').strip()
        scaling = row.get('scaling')
        if not pal_id or not name or not isinstance(scaling, dict):
            return None
        values: list[float] = []
        for key in ('hp', 'attack', 'defense'):
            try:
                value = float(scaling[key])
            except (KeyError, TypeError, ValueError):
                return None
            if not math.isfinite(value) or value <= 0:
                return None
            values.append(value)
        return pal_id, name, PalBaseStats(*values)

    @property
    def records(self) -> tuple[PalStatsRecord, ...]:
        return self._records

    def labels(self) -> tuple[str, ...]:
        """Return sorted editable-combo labels, disambiguated by internal ID."""

        return tuple(record.label for record in self._records)

    def resolve(self, query: str) -> PalLookupResult:
        """Resolve a label, internal ID, or display name case-insensitively."""

        key = query.strip().casefold()
        if not key:
            return PalLookupResult(PalLookupStatus.MISSING)
        by_label = self._by_label.get(key)
        if by_label is not None:
            return PalLookupResult(PalLookupStatus.FOUND, by_label, (by_label,))
        by_id = self._by_id.get(key)
        if by_id is not None:
            return PalLookupResult(PalLookupStatus.FOUND, by_id, (by_id,))
        by_name = self._by_name.get(key, ())
        if len(by_name) == 1:
            return PalLookupResult(PalLookupStatus.FOUND, by_name[0], by_name)
        if by_name:
            return PalLookupResult(PalLookupStatus.AMBIGUOUS, matches=by_name)
        return PalLookupResult(PalLookupStatus.MISSING)

    def search(self, query: str, *, limit: int = 50) -> tuple[PalStatsRecord, ...]:
        """Search display names and internal IDs for future picker UIs."""

        key = query.strip().casefold()
        if not key:
            return self._records[:limit]
        return tuple(
            record
            for record in self._records
            if key in record.name.casefold() or key in record.pal_id.casefold()
        )[:limit]


__all__ = [
    'PalLookupResult',
    'PalLookupStatus',
    'PalStatsRecord',
    'PalStatsRepository',
]
