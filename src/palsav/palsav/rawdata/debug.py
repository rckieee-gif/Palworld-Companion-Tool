from typing import Any
import logging
logger = logging.getLogger(__name__)
from palsav.archive import *
def decode(reader: FArchiveReader, type_name: str, size: int, path: str) -> dict[str, Any]:
    if type_name != 'ArrayProperty':
        raise Exception(f'Expected ArrayProperty, got {type_name}')
    value = reader.property(type_name, size, path, nested_caller_path=path)
    debug_bytes = value['value']['values']
    if len(debug_bytes) > 0:
        debug_str = ''.join((f'{b:02x}' for b in debug_bytes))
        logger.debug(debug_str)
    return value
def encode(writer: FArchiveWriter, property_type: str, properties: dict[str, Any]) -> int:
    if property_type != 'ArrayProperty':
        raise Exception(f'Expected ArrayProperty, got {property_type}')
    del properties['custom_type']
    return writer.property_inner(property_type, properties)