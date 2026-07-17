from typing import Any
from palsav.archive import FArchiveReader, FArchiveWriter
def decode(reader: FArchiveReader, type_name: str, size: int, path: str) -> dict[str, Any]:
    array_type = reader.fstring()
    _id = reader.optional_guid()
    count = reader.u32()
    data = reader.read(count)
    return {'array_type': array_type, 'id': _id, 'value': {'values': data}}
def encode(writer: FArchiveWriter, type_name: str, property: dict[str, Any]) -> int:
    writer.fstring(property['array_type'])
    writer.optional_guid(property.get('id', None))
    from palsav.archive import coerce_bytes
    buf = coerce_bytes(property['value']['values'])
    writer.u32(len(buf))
    writer.write(buf)
    return 4 + len(buf)