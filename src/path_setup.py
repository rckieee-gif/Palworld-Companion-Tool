import os
import sys

SRC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)))


def setup():
    if SRC_DIR not in sys.path:
        sys.path.insert(0, SRC_DIR)


def get_src_dir():
    return SRC_DIR


def get_project_dir():
    return os.path.dirname(SRC_DIR)
