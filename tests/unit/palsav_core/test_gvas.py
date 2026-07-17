from __future__ import annotations
import io
import pytest
from tests.dynamic_importer import import_from

FArchiveWriter = import_from('palsav.archive', 'FArchiveWriter')
_gvas = import_from('palsav.gvas')
GvasHeader = _gvas.GvasHeader
GvasFile = _gvas.GvasFile


def test_gvas_header_roundtrip():
    writer = FArchiveWriter()
    writer.u32(0x53415647)
    writer.u32(0)
    writer.u32(0)
    writer.u32(0)
    writer.u32(0)
    writer.i32(0)
    writer.fstring('GvasFile')
    header = GvasHeader()
    header.save_game_version = 0
    header.package_version_ue4 = 0
    header.package_version_ue5 = 0
    header.engine_version = 0
    header.custom_versions = []
    header.save_game_class_name = 'GvasFile'
    assert header.save_game_class_name == 'GvasFile'


def test_gvas_header_defaults():
    assert hasattr(GvasHeader, '__annotations__')
    ann = GvasHeader.__annotations__
    assert 'save_game_version' in ann
    assert 'package_file_version_ue4' in ann
    assert 'package_file_version_ue5' in ann
    assert 'engine_version_major' in ann
    assert 'custom_versions' in ann
    assert 'save_game_class_name' in ann


def test_gvas_file_has_expected_attrs():
    assert hasattr(GvasFile, 'read')
    assert hasattr(GvasFile, 'load')
    assert hasattr(GvasFile, 'dump')
    assert hasattr(GvasFile, 'write')


def test_gvas_file_from_minimal_dict():
    data = {
        'header': {
            'magic': 1396790855,
            'save_game_version': 3,
            'package_file_version_ue4': 0,
            'package_file_version_ue5': 0,
            'engine_version_major': 0,
            'engine_version_minor': 0,
            'engine_version_patch': 0,
            'engine_version_changelist': 0,
            'engine_version_branch': '',
            'custom_version_format': 3,
            'custom_versions': [],
            'save_game_class_name': 'GvasFile',
        },
        'properties': {},
        'trailer': b'',
    }
    gvas = GvasFile.load(data)
    assert gvas.header.save_game_class_name == 'GvasFile'
    assert gvas.properties == {}
    assert gvas.trailer == b''
