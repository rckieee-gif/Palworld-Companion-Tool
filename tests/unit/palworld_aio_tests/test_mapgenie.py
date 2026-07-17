from tests.dynamic_importer import import_from


_mapgenie = import_from('palworld_aio.map.mapgenie')
MAPGENIE_PALPAGOS_URL = _mapgenie.MAPGENIE_PALPAGOS_URL
format_map_coordinates = _mapgenie.format_map_coordinates
format_selected_pin = _mapgenie.format_selected_pin
is_allowed_map_url = _mapgenie.is_allowed_map_url


def test_mapgenie_url_targets_palpagos_islands():
    assert MAPGENIE_PALPAGOS_URL == (
        'https://mapgenie.io/palworld/maps/palpagos-islands'
    )


def test_format_map_coordinates_matches_map_viewer_precision():
    assert format_map_coordinates((123.9, -45.2)) == 'X:123, Y:-45'


def test_format_selected_pin_includes_name_and_coordinates():
    assert format_selected_pin('Player: Ada', (-7, 42)) == (
        'Player: Ada  |  X:-7, Y:42'
    )


def test_embedded_map_url_policy_allows_only_mapgenie_hosts():
    assert is_allowed_map_url(MAPGENIE_PALPAGOS_URL)
    assert is_allowed_map_url('https://media.mapgenie.io/example')
    assert not is_allowed_map_url('https://mapgenie.io.example.com/')
    assert not is_allowed_map_url('javascript:alert(1)')
