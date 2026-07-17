from __future__ import annotations
import pytest
from tests.dynamic_importer import import_from

_coord = import_from('palworld_coord')
sav_to_map = _coord.sav_to_map
map_to_sav = _coord.map_to_sav
sav_to_treemap = _coord.sav_to_treemap
treemap_to_sav = _coord.treemap_to_sav
sav_to_map_by_z = _coord.sav_to_map_by_z
MAP_Z_THRESHOLD = _coord.MAP_Z_THRESHOLD
get_treemap_coord_range = _coord.get_treemap_coord_range
get_map_z_threshold = _coord.get_map_z_threshold
Point = _coord.Point


def test_sav_to_map_basic():
    result = sav_to_map(0, 0)
    assert isinstance(result, tuple)
    assert len(result) == 2
    assert all(isinstance(v, int) for v in result)


def test_sav_to_map_returns_int_values():
    result = sav_to_map(100000, 200000)
    x, y = result
    assert isinstance(x, int)
    assert isinstance(y, int)


def test_map_to_sav_basic():
    result = map_to_sav(0, 0)
    assert isinstance(result, tuple)
    assert len(result) == 2


def test_sav_to_map_symmetry():
    sav_x, sav_y = 50000, 75000
    map_x, map_y = sav_to_map(sav_x, sav_y)
    sav_x2, sav_y2 = map_to_sav(map_x, map_y)
    assert abs(sav_x2 - sav_x) < 100
    assert abs(sav_y2 - sav_y) < 100


def test_sav_to_map_new_flag():
    result_old = sav_to_map(1000, 2000, new=False)
    result_new = sav_to_map(1000, 2000, new=True)
    assert result_old != result_new


def test_sav_to_treemap():
    result = sav_to_treemap(0, 0)
    assert isinstance(result, tuple)
    assert len(result) == 2


def test_sav_to_map_by_z_below_threshold():
    result = sav_to_map_by_z(1000, 2000, z=MAP_Z_THRESHOLD - 1)
    assert isinstance(result, tuple)
    assert len(result) == 2


def test_sav_to_map_by_z_above_threshold():
    result = sav_to_map_by_z(1000, 2000, z=MAP_Z_THRESHOLD + 1)
    assert isinstance(result, tuple)
    assert len(result) == 2


def test_treemap_to_sav():
    result = treemap_to_sav(0, 0)
    assert isinstance(result, tuple)
    assert len(result) == 2


def test_get_treemap_coord_range():
    result = get_treemap_coord_range()
    assert isinstance(result, (int, float))
    assert result > 0


def test_get_map_z_threshold():
    assert get_map_z_threshold() == MAP_Z_THRESHOLD


def test_point_type():
    p = Point(1, 2)
    assert p.x == 1
    assert p.y == 2
    assert isinstance(p, tuple)
