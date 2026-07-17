from __future__ import annotations
import os
import sys
from tests.dynamic_importer import import_from

_path_setup = import_from('path_setup')
get_project_dir = _path_setup.get_project_dir
setup = _path_setup.setup


def test_get_project_dir_returns_path():
    d = get_project_dir()
    assert d is not None
    assert os.path.isdir(d)


def test_project_dir_has_src():
    d = get_project_dir()
    assert os.path.isdir(os.path.join(d, "src"))


def test_project_dir_has_pyproject():
    d = get_project_dir()
    assert os.path.isfile(os.path.join(d, "pyproject.toml"))


def test_setup_adds_src_to_path():
    src_str = os.path.join(get_project_dir(), "src")
    setup()
    assert src_str in sys.path
