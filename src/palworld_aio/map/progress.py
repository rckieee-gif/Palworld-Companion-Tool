from __future__ import annotations

import json
from pathlib import Path

from resource_resolver import get_user_config_dir


class MapProgressStore:
    """Persists discovered map locations outside every Palworld save."""

    def __init__(self, path: str | Path | None = None):
        self.path = (
            Path(path)
            if path
            else Path(get_user_config_dir()) / 'map_progress.json'
        )
        self._found_location_ids: set[str] = set()
        self.load()

    def load(self) -> frozenset[str]:
        if not self.path.exists():
            self._found_location_ids = set()
            return frozenset()
        try:
            payload = json.loads(self.path.read_text(encoding='utf-8'))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f'Could not load map progress: {exc}') from exc

        if not isinstance(payload, dict):
            raise ValueError('Map progress file has an invalid format.')
        found_location_ids = payload.get('found_location_ids', [])
        if not isinstance(found_location_ids, list) or not all(
            isinstance(location_id, str) and location_id.strip()
            for location_id in found_location_ids
        ):
            raise ValueError('Map progress file has an invalid format.')
        self._found_location_ids = set(found_location_ids)
        return self.items()

    def items(self) -> frozenset[str]:
        return frozenset(self._found_location_ids)

    def is_found(self, location_id: str) -> bool:
        return location_id in self._found_location_ids

    def set_found(self, location_id: str, found: bool) -> None:
        location_id = str(location_id).strip()
        if not location_id:
            raise ValueError('A map location ID is required.')
        if found:
            self._found_location_ids.add(location_id)
        else:
            self._found_location_ids.discard(location_id)
        self._save()

    def clear(self) -> None:
        self._found_location_ids.clear()
        self._save()

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            'version': 1,
            'found_location_ids': sorted(self._found_location_ids),
        }
        temporary = self.path.with_suffix(f'{self.path.suffix}.tmp')
        temporary.write_text(
            json.dumps(payload, ensure_ascii=True, indent=2),
            encoding='utf-8',
        )
        temporary.replace(self.path)
