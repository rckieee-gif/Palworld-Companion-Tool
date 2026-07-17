from __future__ import annotations

import ast
from pathlib import Path


PROHIBITED_DIRECTORIES = (
    'palworld_aio/editor',
    'palworld_aio/inventory',
    'palworld_aio/managers',
    'palworld_toolsets',
    'palworld_xgp_import',
)
PROHIBITED_IMPORT_ROOTS = {
    'palworld_aio.editor',
    'palworld_aio.inventory',
    'palworld_aio.managers',
    'palworld_toolsets',
    'palworld_xgp_import',
}
PROHIBITED_UI_TEXT = (
    'save changes',
    'character transfer',
    'host swap',
    'slot injector',
    'convert saves',
    'player management',
    'guild management',
    'base camp tools',
)


def test_prohibited_feature_packages_are_deleted(src_dir: Path) -> None:
    for relative in PROHIBITED_DIRECTORIES:
        directory = src_dir / relative
        assert not directory.exists() or not list(directory.rglob('*.py')), relative
    commands = src_dir / 'palsav/palsav/commands'
    assert not commands.exists() or not list(commands.rglob('*.py'))
    assert not (src_dir / 'palsav/palsav/cli.py').exists()


def test_retained_application_has_no_prohibited_imports(src_dir: Path) -> None:
    problems: list[str] = []
    for path in (src_dir / 'palworld_aio').rglob('*.py'):
        tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
        for node in ast.walk(tree):
            module = ''
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                modules = [node.module or '']
            else:
                continue
            for module in modules:
                if any(
                    module == root or module.startswith(f'{root}.')
                    for root in PROHIBITED_IMPORT_ROOTS
                ):
                    problems.append(f'{path.relative_to(src_dir)}: {module}')
    assert problems == []


def test_no_application_save_serialization_calls_remain(src_dir: Path) -> None:
    prohibited_tokens = (
        'save_sav(',
        'compress_gvas_to_sav(',
        'write_gvas(',
        'write_sav(',
    )
    findings: list[str] = []
    for path in (src_dir / 'palworld_aio').rglob('*.py'):
        text = path.read_text(encoding='utf-8').lower()
        for token in prohibited_tokens:
            if token in text:
                findings.append(f'{path.relative_to(src_dir)}: {token}')
    assert findings == []


def test_prohibited_commands_are_not_registered_in_retained_ui(src_dir: Path) -> None:
    findings: list[str] = []
    for path in (src_dir / 'palworld_aio/ui').rglob('*.py'):
        text = path.read_text(encoding='utf-8').lower()
        for phrase in PROHIBITED_UI_TEXT:
            if phrase in text:
                findings.append(f'{path.relative_to(src_dir)}: {phrase}')
    assert findings == []
