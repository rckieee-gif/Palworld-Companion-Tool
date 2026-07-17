from __future__ import annotations

from build.nuitka.build_nuitka import build_command, executable_filename
from build.verify_build import REQUIRED_RESOURCES, expected_standalone_executable


def test_build_uses_companion_identity_and_retained_resources() -> None:
    command = build_command(onefile=False)
    joined = '\n'.join(command)
    assert '--mode=standalone' in command
    assert executable_filename().startswith('PalworldCompanionTools-')
    assert '--product-name=Palworld Companion Tools' in command
    assert 'resources/game_data' in joined
    assert 'resources/assets/maps' in joined
    assert 'resources/i18n' in joined
    assert 'resources/ui/themes' in joined
    assert 'PySide6.QtNetwork' in joined
    assert 'resources/game_data/manifest.json' in REQUIRED_RESOURCES


def test_removed_feature_packages_are_not_bundled() -> None:
    joined = '\n'.join(build_command(onefile=False)).lower()
    for module in (
        'palworld_toolsets',
        'palworld_xgp_import',
        'palworld_aio.editor',
        'palworld_aio.inventory',
        'palworld_aio.managers',
        'palsav.commands',
    ):
        assert module not in joined


def test_build_verifier_targets_the_standalone_application() -> None:
    expected = expected_standalone_executable()
    assert expected.parent.name == 'main.dist'
    assert expected.name == executable_filename()
    assert 'Setup' not in expected.name
