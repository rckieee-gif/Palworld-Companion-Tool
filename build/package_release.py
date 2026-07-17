from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import sys
from zipfile import ZIP_DEFLATED, ZipFile


ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / 'src'
for import_root in (ROOT_DIR, SRC_DIR):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from app_info import PRODUCT_SLUG, PRODUCT_VERSION
from build.installer.build_installer import (
    installer_filename,
    windows_executable_filename,
)


DIST_DIR = ROOT_DIR / 'dist'
STANDALONE_DIR = DIST_DIR / 'main.dist'


def portable_archive_filename(version: str = PRODUCT_VERSION) -> str:
    return f'{PRODUCT_SLUG}-Portable-V{version}-win-x64.zip'


def create_portable_archive(
    source_dir: Path = STANDALONE_DIR,
    output_dir: Path = DIST_DIR,
    *,
    version: str = PRODUCT_VERSION,
) -> Path:
    if not source_dir.is_dir():
        raise FileNotFoundError(f'Standalone distribution was not found: {source_dir}')
    expected_executable = source_dir / windows_executable_filename(version)
    if not expected_executable.is_file():
        raise FileNotFoundError(
            f'Standalone executable was not found: {expected_executable}'
        )
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / portable_archive_filename(version)
    archive_root = f'{PRODUCT_SLUG}-V{version}-win-x64'
    with ZipFile(output, mode='w', compression=ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(source_dir.rglob('*')):
            if path.is_file():
                relative = path.relative_to(source_dir).as_posix()
                archive.write(path, f'{archive_root}/{relative}')
    return output


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def write_checksums(paths: list[Path], output: Path) -> Path:
    missing = [path for path in paths if not path.is_file()]
    if missing:
        raise FileNotFoundError(f'Release artifact was not found: {missing[0]}')
    lines = [f'{_sha256(path)}  {path.name}' for path in sorted(paths)]
    output.write_text('\n'.join(lines) + '\n', encoding='ascii')
    return output


def main() -> int:
    parser = argparse.ArgumentParser(
        description='Create the portable Windows archive and release checksums'
    )
    parser.parse_args()
    try:
        archive = create_portable_archive()
        installer = DIST_DIR / installer_filename()
        checksums = write_checksums(
            [installer, archive],
            DIST_DIR / 'SHA256SUMS.txt',
        )
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(f'Portable archive created: {archive}')
    print(f'Checksums created: {checksums}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
