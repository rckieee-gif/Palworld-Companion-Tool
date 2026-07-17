from urllib.parse import urlparse


MAPGENIE_PALPAGOS_URL = 'https://mapgenie.io/palworld/maps/palpagos-islands'


def is_allowed_map_url(url: str) -> bool:
    """Return whether an embedded main-frame URL belongs to MapGenie."""
    parsed = urlparse(url)
    hostname = (parsed.hostname or '').lower()
    return (
        parsed.scheme.lower() in {'http', 'https'}
        and (hostname == 'mapgenie.io' or hostname.endswith('.mapgenie.io'))
    )


def format_map_coordinates(coords):
    """Format Palworld map coordinates consistently for display and copying."""
    x, y = coords
    return f'X:{int(x)}, Y:{int(y)}'


def format_selected_pin(name, coords):
    return f'{name}  |  {format_map_coordinates(coords)}'
