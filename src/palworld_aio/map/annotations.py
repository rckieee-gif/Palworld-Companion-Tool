from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import uuid

from resource_resolver import get_user_config_dir


class AnnotationStore:
    """Persists map viewing annotations outside every Palworld save."""

    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path else Path(get_user_config_dir()) / 'map_annotations.json'
        self._annotations: list[dict] = []
        self.load()

    def load(self) -> tuple[dict, ...]:
        if not self.path.exists():
            self._annotations = []
            return ()
        try:
            payload = json.loads(self.path.read_text(encoding='utf-8'))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f'Could not load map annotations: {exc}') from exc
        annotations = payload.get('annotations', [])
        if not isinstance(annotations, list):
            raise ValueError('Map annotations file has an invalid format.')
        self._annotations = [self._normalize(item) for item in annotations]
        return self.items()

    def items(self) -> tuple[dict, ...]:
        return tuple(deepcopy(self._annotations))

    def add(self, annotation: dict) -> str:
        value = self._normalize(annotation)
        value.setdefault('id', str(uuid.uuid4()))
        value.setdefault('name', f'Annotation {len(self._annotations) + 1}')
        value.setdefault('enabled', True)
        self._annotations.append(value)
        self._save()
        return value['id']

    def update(self, annotation_id: str, changes: dict) -> bool:
        for index, annotation in enumerate(self._annotations):
            if annotation.get('id') != annotation_id:
                continue
            value = dict(annotation)
            value.update(changes)
            value['id'] = annotation_id
            self._annotations[index] = self._normalize(value)
            self._save()
            return True
        return False

    def remove(self, annotation_id: str) -> bool:
        original_count = len(self._annotations)
        self._annotations = [
            item for item in self._annotations if item.get('id') != annotation_id
        ]
        if len(self._annotations) == original_count:
            return False
        self._save()
        return True

    def clear(self) -> None:
        self._annotations = []
        self._save()

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {'version': 1, 'annotations': self._annotations}
        temporary = self.path.with_suffix(f'{self.path.suffix}.tmp')
        temporary.write_text(
            json.dumps(payload, ensure_ascii=True, indent=2),
            encoding='utf-8',
        )
        temporary.replace(self.path)

    @staticmethod
    def _normalize(annotation: dict) -> dict:
        if not isinstance(annotation, dict):
            raise ValueError('Each map annotation must be an object.')
        value = deepcopy(annotation)
        kind = value.get('type', 'rect')
        if kind == 'polygon':
            points = value.get('points', [])
            if len(points) < 3:
                raise ValueError('Polygon annotations require at least three points.')
            value['points'] = [
                {'x': float(point['x']), 'y': float(point['y'])}
                for point in points
            ]
        elif kind == 'rect':
            x1, x2 = sorted((float(value['x1']), float(value['x2'])))
            y1, y2 = sorted((float(value['y1']), float(value['y2'])))
            value.update({'x1': x1, 'x2': x2, 'y1': y1, 'y2': y2})
        else:
            raise ValueError(f'Unsupported map annotation type: {kind}')
        return value


def world_to_scene(
    world_x: float,
    world_y: float,
    map_width: int = 2048,
    map_height: int = 2048,
) -> tuple[float, float]:
    return (
        (world_x + 1000) / 2000 * map_width,
        (1000 - world_y) / 2000 * map_height,
    )


def scene_to_world(
    scene_x: float,
    scene_y: float,
    map_width: int = 2048,
    map_height: int = 2048,
) -> tuple[float, float]:
    return (
        scene_x / map_width * 2000 - 1000,
        1000 - scene_y / map_height * 2000,
    )
