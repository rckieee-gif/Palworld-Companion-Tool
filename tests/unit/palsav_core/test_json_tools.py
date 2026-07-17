from __future__ import annotations
import json
import uuid
import tempfile
import pytest
from tests.dynamic_importer import import_from

_json_tools = import_from('palsav.json_tools')
dump = _json_tools.dump
load = _json_tools.load
CustomEncoder = _json_tools.CustomEncoder
UUID = import_from('palsav.archive', 'UUID')


def test_json_dump_and_load_roundtrip():
    data = {'name': 'test', 'value': 42, 'nested': {'a': [1, 2, 3]}}
    with tempfile.NamedTemporaryFile(mode='wb', suffix='.json', delete=False) as f:
        path = f.name
    try:
        dump(data, path)
        result = load(path)
        assert result == data
    finally:
        import os
        os.unlink(path)


def test_json_dump_minify():
    data = {'key': 'value'}
    with tempfile.NamedTemporaryFile(mode='wb', suffix='.json', delete=False) as f:
        path = f.name
    try:
        dump(data, path, minify=True)
        with open(path, 'rb') as f:
            raw = f.read()
        assert b'\n' not in raw
    finally:
        import os
        os.unlink(path)


def test_custom_encoder_handles_uuid():
    u = UUID.from_str('00112233-4455-6677-8899-aabbccddeeff')
    encoded = json.dumps({'id': u}, cls=CustomEncoder)
    assert '00112233' in encoded


def test_custom_encoder_handles_bytes():
    encoded = json.dumps({'data': b'hello'}, cls=CustomEncoder)
    assert '"~b"' in encoded or 'aGVsbG8' in encoded


def test_json_tools_exports():
    json_tools = import_from('palsav.json_tools')
    assert hasattr(json_tools, 'dump')
    assert hasattr(json_tools, 'load')
    assert hasattr(json_tools, 'CustomEncoder')


def test_json_load_nonexistent():
    with pytest.raises((FileNotFoundError, OSError)):
        load('/nonexistent/path.json')
