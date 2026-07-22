from __future__ import annotations

import palworld_coord

from palworld_aio.map.spawns import PalSpawnRepository
from palworld_aio.ui.map_view.spawn_heatmap import render_spawn_heatmap


def test_spawn_repository_loads_bundled_game_tables() -> None:
    repository = PalSpawnRepository.from_game_data()

    assert len(repository.records) == 286
    assert len(repository.records_for_map('world')) == 262
    assert len(repository.records_for_map('tree')) == 100
    assert repository.resolve('DomeArmorDragon').name == 'Aegidron'
    assert repository.resolve('Aegidron').pal_id == 'DomeArmorDragon'
    assert repository.resolve('RowName') is None


def test_spawn_points_are_within_their_game_map_bounds() -> None:
    repository = PalSpawnRepository.from_game_data()

    for map_type in ('world', 'tree'):
        min_x, min_y, max_x, max_y = repository.bounds_for(map_type)
        for record in repository.records_for_map(map_type):
            for point in record.points_for(map_type):
                assert min_x <= point.world_x <= max_x
                assert min_y <= point.world_y <= max_y


def test_day_and_night_filters_follow_spawn_time_codes() -> None:
    repository = PalSpawnRepository.from_game_data()
    bakemi = repository.resolve('Bakemi')

    assert bakemi is not None
    assert len(bakemi.points_for('world', 'all')) == 116
    assert len(bakemi.points_for('world', 'day')) == 38
    assert len(bakemi.points_for('world', 'night')) == 116


def test_tree_spawn_maps_to_a_visible_texture_pixel() -> None:
    repository = PalSpawnRepository.from_game_data()
    aegidron = repository.resolve('Aegidron')

    assert aegidron is not None
    point = aegidron.tree[0]
    pixel = palworld_coord.treemap_save_to_pixel(
        point.world_x,
        point.world_y,
        8192,
        8192,
    )
    assert 0 <= pixel[0] < 8192
    assert 0 <= pixel[1] < 8192


def test_heatmap_renderer_produces_a_transparent_overlay(qapp) -> None:
    repository = PalSpawnRepository.from_game_data()
    aegidron = repository.resolve('Aegidron')

    assert aegidron is not None
    pixmap = render_spawn_heatmap(
        aegidron.tree,
        'tree',
        repository.bounds_for('tree'),
        render_size=256,
    )
    image = pixmap.toImage()

    assert not pixmap.isNull()
    assert any(
        image.pixelColor(x, y).alpha() > 0
        for x in range(0, image.width(), 8)
        for y in range(0, image.height(), 8)
    )


def test_heatmap_outline_extends_the_visible_spawn_boundary(qapp) -> None:
    repository = PalSpawnRepository.from_game_data()
    aegidron = repository.resolve('Aegidron')

    assert aegidron is not None
    without_outline = render_spawn_heatmap(
        aegidron.tree,
        'tree',
        repository.bounds_for('tree'),
        render_size=256,
        outline=False,
    ).toImage()
    with_outline = render_spawn_heatmap(
        aegidron.tree,
        'tree',
        repository.bounds_for('tree'),
        render_size=256,
        outline=True,
    ).toImage()

    def visible_pixels(image) -> int:
        return sum(
            image.pixelColor(x, y).alpha() > 0
            for x in range(image.width())
            for y in range(image.height())
        )

    assert visible_pixels(with_outline) > visible_pixels(without_outline)
