from collections import namedtuple
__transl_x_old = 123888
__transl_y_old = 158000
__scale_old = 459
__transl_x_new = 375247
__transl_y_new = -18
__scale_new = 725
__treemap_transl_x = 358540
__treemap_transl_y = -382365
__treemap_scale = 724
__treemap_pixel_offset_x = 1760
__treemap_pixel_offset_y = 2571
__treemap_cursor_offset_x = -1075
__treemap_cursor_offset_y = 1568
__treemap_coord_range = 2500
MAP_Z_THRESHOLD = 5000
Point = namedtuple('Point', ['x', 'y'])
def sav_to_map(x: float, y: float, new: bool=False) -> Point:
    if new:
        transl_x = __transl_x_new
        transl_y = __transl_y_new
        scale = __scale_new
    else:
        transl_x = __transl_x_old
        transl_y = __transl_y_old
        scale = __scale_old
    newX = x + transl_x
    newY = y - transl_y
    return Point(x=round(newY / scale), y=round(newX / scale))
def sav_to_treemap(x: float, y: float) -> Point:
    newX = x + __treemap_transl_x
    newY = y - __treemap_transl_y
    return Point(x=round(newY / __treemap_scale), y=round(newX / __treemap_scale))
def sav_to_map_by_z(x: float, y: float, z: float=0.0) -> Point:
    pt = sav_to_map(x, y, new=True)
    if abs(pt.x) > 1000 or abs(pt.y) > 1000:
        pt2 = sav_to_treemap(x, y)
        if abs(pt2.x) <= 2500 and abs(pt2.y) <= 2500:
            return pt2
    return pt
def treemap_to_sav(x: int, y: int) -> Point:
    newX = y * __treemap_scale
    newY = x * __treemap_scale
    return Point(x=newX - __treemap_transl_x, y=newY + __treemap_transl_y)
def treemap_to_pixel(x_world: int, y_world: int, width: int, height: int) -> tuple[int, int]:
    x_min, x_max = (-__treemap_coord_range, __treemap_coord_range)
    y_min, y_max = (-__treemap_coord_range, __treemap_coord_range)
    x_scale = width / (x_max - x_min)
    y_scale = height / (y_max - y_min)
    img_x = int((x_world - x_min) * x_scale) + __treemap_pixel_offset_x
    img_y = int((y_max - y_world) * y_scale) + __treemap_pixel_offset_y
    return (max(0, min(width - 1, img_x)), max(0, min(height - 1, img_y)))
def treemap_pixel_to_cursor(img_x: float, img_y: float, width: int, height: int) -> tuple[float, float]:
    coord_range = __treemap_coord_range
    x_world = img_x / width * (coord_range * 2) - coord_range + __treemap_cursor_offset_x
    y_world = coord_range - img_y / height * (coord_range * 2) + __treemap_cursor_offset_y
    return (x_world, y_world)
def get_treemap_coord_range() -> int:
    return __treemap_coord_range
def get_map_z_threshold() -> int:
    return MAP_Z_THRESHOLD
def map_to_sav(x: int, y: int, new: bool=False) -> Point:
    if new:
        transl_x = __transl_x_new
        transl_y = __transl_y_new
        scale = __scale_new
    else:
        transl_x = __transl_x_old
        transl_y = __transl_y_old
        scale = __scale_old
    newX = x * scale
    newY = y * scale
    return Point(x=newY - transl_x, y=newX + transl_y)