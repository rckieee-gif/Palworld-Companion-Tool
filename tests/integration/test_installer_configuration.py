from __future__ import annotations

from pathlib import Path
import tomllib
from zipfile import ZipFile
import subprocess
import sys

from app_info import PRODUCT_SLUG, PRODUCT_VERSION
from build.installer.build_installer import (
    build_command,
    installer_filename,
    windows_executable_filename,
)
from build.package_release import (
    create_portable_archive,
    portable_archive_filename,
    write_checksums,
)


def test_product_versions_are_synchronized(project_dir: Path) -> None:
    metadata = tomllib.loads((project_dir / 'pyproject.toml').read_text('utf-8'))
    assert metadata['project']['version'] == PRODUCT_VERSION


def test_installer_is_per_user_and_points_to_project_releases(
    project_dir: Path,
) -> None:
    script = (
        project_dir / 'build/installer/PalworldCompanionTools.iss'
    ).read_text('utf-8')
    assert 'PrivilegesRequired=lowest' in script
    assert r'DefaultDirName={localappdata}\Programs\{#AppName}' in script
    assert 'AppUpdatesURL={#AppUrl}/releases' in script
    assert r'Source: "..\..\dist\main.dist\*"' in script
    assert 'recursesubdirs createallsubdirs' in script
    assert r'Name: "{app}\PalworldCompanionTools-V*-win.exe"' in script
    assert 'UninstallDisplayIcon=' in script
    assert r'Software\Classes\palworld-companion' in script
    assert 'URL Protocol' in script
    assert r'""%1""' in script
    assert 'PrivilegesRequired=admin' not in script


def test_installer_command_receives_the_central_version() -> None:
    compiler = Path(r'C:\Program Files (x86)\Inno Setup 6\ISCC.exe')
    command = build_command(compiler)
    assert command[0] == str(compiler)
    assert f'/DAppVersion={PRODUCT_VERSION}' in command
    assert installer_filename() == (
        f'PalworldCompanionTools-Setup-V{PRODUCT_VERSION}-win-x64.exe'
    )


def test_release_workflow_builds_installer_portable_zip_and_checksums(
    project_dir: Path,
) -> None:
    workflow = (
        project_dir / '.github/workflows/release-windows.yml'
    ).read_text('utf-8')
    assert 'runs-on: windows-2022' in workflow
    assert 'build_nuitka.py --standalone' in workflow
    assert 'build/installer/build_installer.py' in workflow
    assert 'build/package_release.py' in workflow
    assert 'PalworldCompanionTools-Setup-V*-win-x64.exe' in workflow
    assert 'PalworldCompanionTools-Portable-V*-win-x64.zip' in workflow
    assert 'SHA256SUMS.txt' in workflow
    assert 'does not match application version' in workflow


def test_packaging_entry_points_can_run_directly(project_dir: Path) -> None:
    result = subprocess.run(
        [sys.executable, 'build/installer/build_installer.py', '--help'],
        cwd=project_dir,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr

    result = subprocess.run(
        [sys.executable, 'build/package_release.py', '--help'],
        cwd=project_dir,
        capture_output=True,
        text=True,
        check=False,
    )
    assert 'ModuleNotFoundError' not in result.stderr


def test_portable_archive_has_a_named_root_and_checksums(tmp_path: Path) -> None:
    source = tmp_path / 'main.dist'
    source.mkdir()
    (source / windows_executable_filename()).write_bytes(b'executable')
    (source / 'resources').mkdir()
    (source / 'resources/game-data.txt').write_text('data', encoding='utf-8')

    output_dir = tmp_path / 'release'
    archive = create_portable_archive(source, output_dir)
    assert archive.name == portable_archive_filename()
    with ZipFile(archive) as bundle:
        names = set(bundle.namelist())
    root = f'{PRODUCT_SLUG}-V{PRODUCT_VERSION}-win-x64'
    assert f'{root}/{windows_executable_filename()}' in names
    assert f'{root}/resources/game-data.txt' in names

    installer = output_dir / installer_filename()
    installer.write_bytes(b'installer')
    checksum_file = write_checksums(
        [installer, archive],
        output_dir / 'SHA256SUMS.txt',
    )
    checksum_text = checksum_file.read_text('ascii')
    assert installer.name in checksum_text
    assert archive.name in checksum_text
