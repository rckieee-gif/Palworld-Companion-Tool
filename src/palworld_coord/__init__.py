from __future__ import annotations

from collections import namedtuple
import math


__transl_x_old = 123888
__transl_y_old = 158000
__scale_old = 459
__transl_x_new = 375247
__transl_y_new = -18
__scale_new = 725

__treemap_transl_x = 358540
__treemap_transl_y = -382365
__treemap_scale = 724

# Pal/DataTable/WorldMapUIData/DT_WorldMapUIData, Tree row (Palworld 1.0).
# The texture is rotated relative to Unreal world axes: world Y maps left/right
# and world X maps bottom/top.
__treemap_world_x_min = 347351.5
__treemap_world_y_min = -818197.0
__treemap_world_x_max = 689148.5
__treemap_world_y_max = -476400.0

MAP_Z_THRESHOLD = 5000
Point = namedtuple('Point', ['x', 'y'])


def sav_to_map(x: float, y: float, new: bool = False) -> Point:
    if new:
        transl_x = __transl_x_new
        transl_y = __transl_y_new
        scale = __scale_new
    else:
        transl_x = __transl_x_old
        transl_y = __transl_y_old
        scale = __scale_old
    new_x = x + transl_x
    new_y = y - transl_y
    return Point(x=round(new_y / scale), y=round(new_x / scale))


def _sav_to_treemap_float(x: float, y: float) -> tuple[float, float]:
    new_x = x + __treemap_transl_x
    new_y = y - __treemap_transl_y
    return new_y / __treemap_scale, new_x / __treemap_scale


def sav_to_treemap(x: float, y: float) -> Point:
    map_x, map_y = _sav_to_treemap_float(x, y)
    return Point(x=round(map_x), y=round(map_y))


def is_treemap_save_position(
    x: float,
    y: float,
    *,
    margin: float = 0.0,
) -> bool:
    """Return whether Unreal world coordinates belong to the Tree map."""

    return (
        __treemap_world_x_min - margin
        <= x
        <= __treemap_world_x_max + margin
        and __treemap_world_y_min - margin
        <= y
        <= __treemap_world_y_max + margin
    )


def sav_to_map_by_z(x: float, y: float, z: float = 0.0) -> Point:
    del z
    point = sav_to_map(x, y, new=True)
    if (
        abs(point.x) > 1000 or abs(point.y) > 1000
    ) and is_treemap_save_position(x, y):
        return sav_to_treemap(x, y)
    return point


def treemap_to_sav(x: float, y: float) -> Point:
    new_x = y * __treemap_scale
    new_y = x * __treemap_scale
    return Point(
        x=new_x - __treemap_transl_x,
        y=new_y + __treemap_transl_y,
    )


def get_treemap_world_bounds() -> tuple[float, float, float, float]:
    """Return Tree world bounds as min X, min Y, max X, max Y."""

    return (
        __treemap_world_x_min,
        __treemap_world_y_min,
        __treemap_world_x_max,
        __treemap_world_y_max,
    )


def get_treemap_map_bounds() -> tuple[float, float, float, float]:
    """Return Tree display-coordinate bounds as min X, min Y, max X, max Y."""

    min_x, min_y = _sav_to_treemap_float(
        __treemap_world_x_min,
        __treemap_world_y_min,
    )
    max_x, max_y = _sav_to_treemap_float(
        __treemap_world_x_max,
        __treemap_world_y_max,
    )
    return min_x, min_y, max_x, max_y


def treemap_save_to_pixel(
    x: float,
    y: float,
    width: int,
    height: int,
) -> tuple[int, int]:
    """Convert raw Tree world coordinates directly to texture pixels."""

    horizontal_range = __treemap_world_y_max - __treemap_world_y_min
    vertical_range = __treemap_world_x_max - __treemap_world_x_min
    image_x = round((y - __treemap_world_y_min) / horizontal_range * width)
    image_y = round((__treemap_world_x_max - x) / vertical_range * height)
    return (
        max(0, min(width - 1, image_x)),
        max(0, min(height - 1, image_y)),
    )


def treemap_to_pixel(
    x_world: float,
    y_world: float,
    width: int,
    height: int,
) -> tuple[int, int]:
    save_point = treemap_to_sav(x_world, y_world)
    return treemap_save_to_pixel(save_point.x, save_point.y, width, height)


def treemap_pixel_to_map(
    image_x: float,
    image_y: float,
    width: int,
    height: int,
) -> tuple[float, float]:
    min_x, min_y, max_x, max_y = get_treemap_map_bounds()
    map_x = min_x + image_x / width * (max_x - min_x)
    map_y = max_y - image_y / height * (max_y - min_y)
    return map_x, map_y


def treemap_pixel_to_cursor(
    image_x: float,
    image_y: float,
    width: int,
    height: int,
) -> tuple[float, float]:
    return treemap_pixel_to_map(image_x, image_y, width, height)


def get_treemap_coord_range() -> int:
    return math.ceil(max(abs(value) for value in get_treemap_map_bounds()))


def get_map_z_threshold() -> int:
    return MAP_Z_THRESHOLD


def map_to_sav(x: float, y: float, new: bool = False) -> Point:
    if new:
        transl_x = __transl_x_new
        transl_y = __transl_y_new
        scale = __scale_new
    else:
        transl_x = __transl_x_old
        transl_y = __transl_y_old
        scale = __scale_old
    new_x = x * scale
    new_y = y * scale
    return Point(x=new_y - transl_x, y=new_x + transl_y)
