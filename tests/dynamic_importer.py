from __future__ import annotations

import importlib
import sys

from tests.test_registry import get_entry, _resolve_parent


def import_from(logical_path: str, name: str | None = None):
    root = logical_path.split('.')[0]
    rest = logical_path.split('.')[1:]
    entry = get_entry(root)

    if entry is None:
        module = importlib.import_module(logical_path)
        return getattr(module, name) if name else module

    if entry.get('installed'):
        actual_path = logical_path
    else:
        import_as = entry['import_as']
        actual_path = import_as + ('.' + '.'.join(rest) if rest else '')

        parent_alias = entry.get('parent')
        if parent_alias:
            parent_dir = str(_resolve_parent(parent_alias))
            if parent_dir not in sys.path:
                sys.path.insert(0, parent_dir)

    module = importlib.import_module(actual_path)

    if name is not None:
        return getattr(module, name)
    return module
