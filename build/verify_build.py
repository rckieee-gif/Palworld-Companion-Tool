from __future__ import annotations

from pathlib import Path
import sys


ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / 'src'
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from app_info import EXECUTABLE_NAME, PRODUCT_VERSION


REQUIRED_RESOURCES = (
    'resources/assets/maps/T_WorldMap.webp',
    'resources/assets/maps/T_TreeMap.webp',
    'resources/game_data/breedingdata.json',
    'resources/game_data/characters.json',
    'resources/game_data/items.json',
    'resources/game_data/manifest.json',
    'resources/game_data/pal_spawns.json',
    'resources/i18n/en_US.json',
    'resources/ui/themes/darkmode.qss',
    'resources/ui/themes/lightmode.qss',
)
PROHIBITED_MODULES = (
    'palworld_toolsets',
    'palworld_xgp_import',
    'palworld_aio.editor',
    'palworld_aio.inventory',
    'palworld_aio.managers',
    'palsav.commands',
)


def expected_standalone_executable() -> Path:
    platform_tag = {'win32': 'win', 'darwin': 'macos'}.get(sys.platform, 'linux')
    suffix = '.exe' if sys.platform == 'win32' else ''
    filename = f'{EXECUTABLE_NAME}-V{PRODUCT_VERSION}-{platform_tag}{suffix}'
    return ROOT_DIR / 'dist' / 'main.dist' / filename


def main() -> int:
    report_path = ROOT_DIR / 'build' / 'nuitka-report.xml'
    if not report_path.is_file():
        print(f'Missing build report: {report_path}')
        return 1
    report = report_path.read_text(encoding='utf-8', errors='replace')
    failures: list[str] = []
    for resource in REQUIRED_RESOURCES:
        if resource.replace('/', '\\') not in report and resource not in report:
            failures.append(f'missing resource: {resource}')
    for module in PROHIBITED_MODULES:
        if f'name="{module}"' in report:
            failures.append(f'prohibited module bundled: {module}')

    executable = expected_standalone_executable()
    if not executable.is_file():
        failures.append(f'companion standalone executable was not found: {executable}')

    if failures:
        print('\n'.join(f'FAIL: {failure}' for failure in failures))
        return 1
    print(f'Build verified: {executable}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
