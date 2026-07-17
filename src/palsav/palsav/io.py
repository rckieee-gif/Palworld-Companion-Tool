import os
import mmap
import logging
logger = logging.getLogger(__name__)
from palsav.core import decompress_sav_to_gvas, compress_gvas_to_sav
from palsav.gvas import GvasFile
from palsav.paltypes import PALWORLD_TYPE_HINTS, PALWORLD_CUSTOM_PROPERTIES


def load_sav(
    path,
    type_hints=None,
    custom_properties=None,
    allow_nan=True,
    mmap_threshold_mb=100,
) -> 'GvasFile':
    if type_hints is None:
        type_hints = PALWORLD_TYPE_HINTS
    if custom_properties is None:
        custom_properties = PALWORLD_CUSTOM_PROPERTIES

    file_size = os.path.getsize(path)
    if file_size > mmap_threshold_mb * 1024 * 1024:
        logger.info(f'Large file ({file_size / (1024 * 1024):.1f} MB), using mmap...')
        with open(path, 'rb') as f:
            with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mm:
                raw_gvas, _ = decompress_sav_to_gvas(mm.read())
    else:
        with open(path, 'rb') as f:
            data = f.read()
        raw_gvas, _ = decompress_sav_to_gvas(data)

    return GvasFile.read(raw_gvas, type_hints, custom_properties, allow_nan=allow_nan)


def save_sav(gvas_file: GvasFile, path, custom_properties=None, save_type=None) -> None:
    if custom_properties is None:
        custom_properties = PALWORLD_CUSTOM_PROPERTIES
    if save_type is None:
        save_type = 49
    data = gvas_file.write(custom_properties)
    compressed = compress_gvas_to_sav(data, save_type)
    with open(path, 'wb') as f:
        f.write(compressed)
