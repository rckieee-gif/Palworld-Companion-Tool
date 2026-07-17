from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys


ROOT_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT_DIR / 'src'
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from app_info import (
    EXECUTABLE_NAME,
    PRODUCT_DESCRIPTION,
    PRODUCT_NAME,
    PRODUCT_VERSION,
)


MAIN_SCRIPT = SRC_DIR / 'palworld_aio' / 'main.py'
DIST_DIR = ROOT_DIR / 'dist'
REPORT_PATH = ROOT_DIR / 'build' / 'nuitka-report.xml'
ICON_PATH = ROOT_DIR / 'resources' / 'assets' / 'icons' / 'app' / 'icon.ico'
RESOURCE_DIRECTORIES = (
    'resources/assets/fonts',
    'resources/assets/icons/app',
    'resources/assets/icons/game',
    'resources/assets/maps',
    'resources/game_data',
    'resources/i18n',
    'resources/ui/themes',
)
INCLUDED_PACKAGES = (
    'i18n',
    'palsav',
    'palworld_aio',
    'palworld_coord',
)
INCLUDED_MODULES = (
    'orjson',
    'palooz',
    'PySide6.QtNetwork',
    'PySide6.QtWebEngineCore',
    'PySide6.QtWebEngineWidgets',
)


def platform_tag() -> str:
    return {'win32': 'win', 'darwin': 'macos'}.get(sys.platform, 'linux')


def executable_filename() -> str:
    suffix = '.exe' if sys.platform == 'win32' else ''
    return f'{EXECUTABLE_NAME}-V{PRODUCT_VERSION}-{platform_tag()}{suffix}'


def resolve_python() -> Path:
    relative = Path('Scripts/python.exe') if sys.platform == 'win32' else Path('bin/python')
    candidate = ROOT_DIR / '.venv' / relative
    return candidate if candidate.is_file() else Path(sys.executable)


def build_command(*, onefile: bool = False) -> list[str]:
    command = [
        str(resolve_python()),
        '-m',
        'nuitka',
        '--mode=onefile' if onefile else '--mode=standalone',
        '--enable-plugin=pyside6',
        '--prefer-source-code',
        f'--output-dir={DIST_DIR}',
        f'--output-filename={executable_filename()}',
        f'--report={REPORT_PATH}',
        f'--product-name={PRODUCT_NAME}',
        f'--file-description={PRODUCT_DESCRIPTION}',
        f'--file-version={PRODUCT_VERSION}',
        f'--product-version={PRODUCT_VERSION}',
        '--company-name=Pylar',
        '--copyright=Copyright (c) 2026 Pylar',
        '--assume-yes-for-downloads',
    ]

    for relative in RESOURCE_DIRECTORIES:
        source = ROOT_DIR / relative
        if not source.is_dir():
            raise FileNotFoundError(f'Required build resource is missing: {source}')
        command.append(f'--include-data-dir={source}={relative}')
    command.extend((
        f'--include-data-files={ROOT_DIR / "README.md"}=README.md',
        f'--include-data-files={ROOT_DIR / "license"}=license',
    ))
    command.extend(f'--include-package={name}' for name in INCLUDED_PACKAGES)
    command.extend(f'--include-module={name}' for name in INCLUDED_MODULES)

    if sys.platform == 'win32':
        command.append('--windows-console-mode=disable')
        if ICON_PATH.is_file():
            command.append(f'--windows-icon-from-ico={ICON_PATH}')
    elif sys.platform == 'darwin':
        command.extend((
            '--macos-create-app-bundle',
            f'--macos-app-name={PRODUCT_NAME}',
        ))
        if ICON_PATH.is_file():
            command.append(f'--macos-app-icon={ICON_PATH}')

    command.append(str(MAIN_SCRIPT))
    return command


def build(*, onefile: bool = False) -> int:
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env['PYTHONPATH'] = os.pathsep.join(
        filter(None, (str(SRC_DIR), str(SRC_DIR / 'palsav'), env.get('PYTHONPATH', '')))
    )
    env.setdefault('NUITKA_CACHE_DIR', str(ROOT_DIR / 'build' / 'nuitka-cache'))
    command = build_command(onefile=onefile)
    print('Building', PRODUCT_NAME)
    print(subprocess.list2cmdline(command))
    return subprocess.run(command, cwd=ROOT_DIR, env=env, check=False).returncode


def main() -> int:
    parser = argparse.ArgumentParser(description=f'Build {PRODUCT_NAME} with Nuitka')
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--onefile', action='store_true', help='Build one executable file')
    mode.add_argument('--standalone', action='store_true', help='Build a directory distribution')
    parser.add_argument('--dry-run', action='store_true', help='Print the build command only')
    args = parser.parse_args()

    command = build_command(onefile=args.onefile)
    if args.dry_run:
        print(subprocess.list2cmdline(command))
        return 0
    return build(onefile=args.onefile)


if __name__ == '__main__':
    raise SystemExit(main())
