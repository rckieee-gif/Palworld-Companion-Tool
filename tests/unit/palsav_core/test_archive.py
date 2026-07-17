from __future__ import annotations
import uuid
import pytest
from tests.dynamic_importer import import_from

_archive = import_from('palsav.archive')
UUID = _archive.UUID
FArchiveReader = _archive.FArchiveReader
FArchiveWriter = _archive.FArchiveWriter
uuid_reader = _archive.uuid_reader
uuid_writer = _archive.uuid_writer


def test_uuid_from_str():
    u = UUID.from_str('00112233-4455-6677-8899-aabbccddeeff')
    assert isinstance(u, UUID)
    assert str(u) == '00112233-4455-6677-8899-aabbccddeeff'


def test_uuid_from_hex():
    raw = b'\x00\x11\x22\x33\x44\x55\x66\x77\x88\x99\xaa\xbb\xcc\xdd\xee\xff'
    u = UUID(raw)
    assert str(u) == '33221100-7766-5544-bbaa-9988ffeeddcc'


def test_uuid_bytes_roundtrip():
    raw = b'\x00\x11\x22\x33\x44\x55\x66\x77\x88\x99\xaa\xbb\xcc\xdd\xee\xff'
    u = UUID(raw)
    assert u.raw_bytes == raw
    assert len(u.raw_bytes) == 16


def test_uuid_equality():
    u1 = UUID.from_str('00112233-4455-6677-8899-aabbccddeeff')
    u2 = UUID.from_str('00112233-4455-6677-8899-aabbccddeeff')
    u3 = UUID.from_str('00112233-4455-6677-8899-aabbccddee00')
    assert u1 == u2
    assert u1 != u3


def test_uuid_hashable():
    u1 = UUID.from_str('00112233-4455-6677-8899-aabbccddeeff')
    u2 = UUID.from_str('00112233-4455-6677-8899-aabbccddeeff')
    s = {u1, u2}
    assert len(s) == 1


def test_uuid_compatible_with_stdlib():
    u = UUID.from_str('00112233-4455-6677-8899-aabbccddeeff')
    std_u = uuid.UUID('00112233-4455-6677-8899-aabbccddeeff')
    assert u.UUID() == std_u


def test_uuid_repr():
    u = UUID.from_str('00112233-4455-6677-8899-aabbccddeeff')
    r = repr(u)
    assert 'UUID' in r or '00112233' in r


def test_farchive_reader_basic():
    data = b'\x01\x00\x00\x00'
    reader = FArchiveReader(data)
    val = reader.u32()
    assert val == 1
    assert reader.eof()


def test_farchive_reader_u32():
    data = b'\xff\xff\xff\xff\x00\x00\x00\x80'
    reader = FArchiveReader(data)
    assert reader.u32() == 4294967295
    assert reader.i32() == -2147483648


def test_farchive_reader_fstring():
    data = b'\x06\x00\x00\x00Hello\x00'
    reader = FArchiveReader(data)
    assert reader.fstring() == 'Hello'


def test_farchive_reader_empty_string():
    data = b'\x00\x00\x00\x00'
    reader = FArchiveReader(data)
    assert reader.fstring() == ''


def test_farchive_writer_u32():
    writer = FArchiveWriter()
    writer.u32(42)
    result = writer.bytes()
    assert result == b'\x2a\x00\x00\x00'


def test_farchive_writer_fstring():
    writer = FArchiveWriter()
    writer.fstring('test')
    result = writer.bytes()
    assert result == b'\x05\x00\x00\x00test\x00'


def test_farchive_roundtrip():
    writer = FArchiveWriter()
    writer.u32(100)
    writer.fstring('roundtrip')
    writer.i32(-42)
    data = writer.bytes()
    reader = FArchiveReader(data)
    assert reader.u32() == 100
    assert reader.fstring() == 'roundtrip'
    assert reader.i32() == -42
    assert reader.eof()


def test_uuid_reader():
    raw_uuid = b'\x00\x11\x22\x33\x44\x55\x66\x77\x88\x99\xaa\xbb\xcc\xdd\xee\xff'
    reader = FArchiveReader(raw_uuid)
    result = uuid_reader(reader)
    assert isinstance(result, UUID)
    assert str(result) == '33221100-7766-5544-bbaa-9988ffeeddcc'


def test_uuid_writer():
    u = UUID.from_str('00112233-4455-6677-8899-aabbccddeeff')
    writer = FArchiveWriter()
    uuid_writer(writer, u)
    assert writer.bytes() == b'\x33\x22\x11\x00\x77\x66\x55\x44\xbb\xaa\x99\x88\xff\xee\xdd\xcc'
