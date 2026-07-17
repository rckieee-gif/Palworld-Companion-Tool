from __future__ import annotations

import atexit
import os
from pathlib import Path
import shutil
import sys
import tempfile

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / 'src'
PALSAV_SRC_DIR = SRC_DIR / 'palsav'
for path in (str(SRC_DIR), str(PALSAV_SRC_DIR), str(PROJECT_ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
_TEST_CONFIG_DIR = tempfile.mkdtemp(prefix='palworld-companion-tests-')
os.environ['PALWORLD_COMPANION_CONFIG_DIR'] = _TEST_CONFIG_DIR
atexit.register(shutil.rmtree, _TEST_CONFIG_DIR, True)


@pytest.fixture(scope='session')
def qapp():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def project_dir() -> Path:
    return PROJECT_ROOT


@pytest.fixture
def src_dir() -> Path:
    return SRC_DIR
