from __future__ import annotations

import math
from typing import Iterable

import palworld_coord
from PySide6.QtCore import Qt
from PySide6.QtGui import (
    QColor,
    QImage,
    QPainter,
    QPixmap,
    QRadialGradient,
    QTransform,
)
from PySide6.QtWidgets import QGraphicsPixmapItem

from palworld_aio.map import annotations
from palworld_aio.map.spawns import MapType, PalSpawnPoint


DEFAULT_RENDER_SIZE = 1024
_OUTLINE_THRESHOLD = 96


def _point_to_pixel(
    point: PalSpawnPoint,
    map_type: MapType,
    width: int,
    height: int,
) -> tuple[float, float]:
    if map_type == 'tree':
        return palworld_coord.treemap_save_to_pixel(
            point.world_x,
            point.world_y,
            width,
            height,
        )
    map_point = palworld_coord.sav_to_map(
        point.world_x,
        point.world_y,
        new=True,
    )
    return annotations.world_to_scene(
        map_point.x,
        map_point.y,
        width,
        height,
    )


def _render_spawn_outline(
    points: tuple[PalSpawnPoint, ...],
    map_type: MapType,
    world_span: float,
    size: int,
) -> QImage:
    mask = QImage(size, size, QImage.Format_Grayscale8)
    mask.fill(0)
    mask_painter = QPainter(mask)
    mask_painter.setRenderHint(QPainter.Antialiasing)
    mask_painter.setPen(Qt.NoPen)
    mask_painter.setBrush(Qt.white)
    for point in points:
        x, y = _point_to_pixel(point, map_type, size, size)
        radius = max(4.0, point.radius / world_span * size)
        mask_painter.drawEllipse(
            x - radius,
            y - radius,
            radius * 2,
            radius * 2,
        )
    mask_painter.end()

    mask_data = bytes(mask.constBits())
    stride = mask.bytesPerLine()
    pixels = bytearray(size * size * 4)
    dark = (9, 16, 22, 245)
    bright = (255, 218, 78, 250)
    threshold = _OUTLINE_THRESHOLD
    for y in range(size):
        row = y * stride
        for x in range(size):
            inside = mask_data[row + x] > threshold
            left = x > 0 and mask_data[row + x - 1] > threshold
            right = x + 1 < size and mask_data[row + x + 1] > threshold
            above = y > 0 and mask_data[row - stride + x] > threshold
            below = y + 1 < size and mask_data[row + stride + x] > threshold
            if inside:
                color = bright if not (left and right and above and below) else None
            else:
                color = dark if left or right or above or below else None
            if color is None:
                continue
            index = (y * size + x) * 4
            pixels[index] = color[0]
            pixels[index + 1] = color[1]
            pixels[index + 2] = color[2]
            pixels[index + 3] = color[3]
    return QImage(
        pixels,
        size,
        size,
        size * 4,
        QImage.Format_RGBA8888,
    ).copy()


def render_spawn_heatmap(
    points: Iterable[PalSpawnPoint],
    map_type: MapType,
    bounds: tuple[float, float, float, float],
    *,
    render_size: int = DEFAULT_RENDER_SIZE,
    outline: bool = True,
) -> QPixmap:
    """Render spawn areas into a transparent, density-emphasizing pixmap."""

    size = max(128, int(render_size))
    image = QImage(size, size, QImage.Format_ARGB32_Premultiplied)
    image.fill(Qt.transparent)
    min_x, min_y, max_x, max_y = bounds
    world_span = max(max_x - min_x, max_y - min_y)
    spawn_points = tuple(points)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setCompositionMode(QPainter.CompositionMode_Plus)
    for point in spawn_points:
        x, y = _point_to_pixel(point, map_type, size, size)
        radius = max(4.0, point.radius / world_span * size)
        alpha = max(
            14,
            min(64, round(16 + 48 * math.sqrt(point.probability))),
        )
        gradient = QRadialGradient(x, y, radius)
        gradient.setColorAt(0.0, QColor(255, 60, 48, alpha))
        gradient.setColorAt(0.38, QColor(255, 154, 38, round(alpha * 0.65)))
        gradient.setColorAt(0.72, QColor(255, 221, 70, round(alpha * 0.22)))
        gradient.setColorAt(1.0, QColor(255, 221, 70, 0))
        painter.setBrush(gradient)
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(x - radius, y - radius, radius * 2, radius * 2)
    if outline:
        painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
        painter.drawImage(
            0,
            0,
            _render_spawn_outline(
                spawn_points,
                map_type,
                world_span,
                size,
            ),
        )
    painter.end()
    return QPixmap.fromImage(image)


class SpawnHeatmapItem(QGraphicsPixmapItem):
    def __init__(
        self,
        pixmap: QPixmap,
        map_width: int,
        map_height: int,
    ):
        super().__init__(pixmap)
        self.setTransform(QTransform.fromScale(
            map_width / max(1, pixmap.width()),
            map_height / max(1, pixmap.height()),
        ))
        self.setTransformationMode(Qt.SmoothTransformation)
        self.setAcceptedMouseButtons(Qt.NoButton)
        self.setZValue(4)
        self.setOpacity(0.72)


__all__ = ['SpawnHeatmapItem', 'render_spawn_heatmap']
