from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys


ROOT_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT_DIR / 'src'
for import_root in (ROOT_DIR, SRC_DIR):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from app_info import EXECUTABLE_NAME, PRODUCT_VERSION


SCRIPT_PATH = Path(__file__).with_name('PalworldCompanionTools.iss')
STANDALONE_DIR = ROOT_DIR / 'dist' / 'main.dist'
DIST_DIR = ROOT_DIR / 'dist'


def installer_filename(version: str = PRODUCT_VERSION) -> str:
    return f'PalworldCompanionTools-Setup-V{version}-win-x64.exe'


def windows_executable_filename(version: str = PRODUCT_VERSION) -> str:
    return f'{EXECUTABLE_NAME}-V{version}-win.exe'


def find_compiler(explicit: str | os.PathLike[str] | None = None) -> Path:
    candidates: list[Path] = []
    if explicit:
        candidates.append(Path(explicit))
    configured = os.environ.get('INNO_SETUP_COMPILER')
    if configured:
        candidates.append(Path(configured))
    on_path = shutil.which('ISCC.exe') or shutil.which('iscc')
    if on_path:
        candidates.append(Path(on_path))
    for variable in ('ProgramFiles(x86)', 'ProgramFiles'):
        base = os.environ.get(variable)
        if base:
            candidates.append(Path(base) / 'Inno Setup 6' / 'ISCC.exe')
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    raise FileNotFoundError(
        'Inno Setup 6 was not found. Install it or set INNO_SETUP_COMPILER.'
    )


def build_command(compiler: Path, version: str = PRODUCT_VERSION) -> list[str]:
    return [
        str(compiler),
        '/Qp',
        f'/DAppVersion={version}',
        str(SCRIPT_PATH),
    ]


def validate_standalone(source_dir: Path = STANDALONE_DIR) -> None:
    if not source_dir.is_dir():
        raise FileNotFoundError(f'Standalone distribution was not found: {source_dir}')
    executable = source_dir / windows_executable_filename()
    if not executable.is_file():
        raise FileNotFoundError(f'Standalone executable was not found: {executable}')


def build_installer(compiler: Path) -> Path:
    validate_standalone()
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    command = build_command(compiler)
    print(subprocess.list2cmdline(command))
    subprocess.run(command, cwd=ROOT_DIR, check=True)
    output = DIST_DIR / installer_filename()
    if not output.is_file():
        raise FileNotFoundError(f'Installer compiler did not create: {output}')
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description='Build the Windows setup package')
    parser.add_argument('--compiler', help='Path to Inno Setup ISCC.exe')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    try:
        compiler = find_compiler(args.compiler)
        if args.dry_run:
            print(subprocess.list2cmdline(build_command(compiler)))
            return 0
        output = build_installer(compiler)
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(f'Installer created: {output}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
