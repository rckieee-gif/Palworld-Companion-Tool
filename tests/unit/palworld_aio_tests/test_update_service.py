from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json

import pytest

from palworld_aio.update_service import (
    UpdateCheckError,
    compare_versions,
    is_newer_version,
    normalize_version,
    parse_release_payload,
    should_check_automatically,
)


@pytest.mark.parametrize(
    ('left', 'right', 'expected'),
    (
        ('1.0.0', '0.9.9', 1),
        ('v1.0.0', '1.0', 0),
        ('1.0.0-rc.2', '1.0.0-rc.1', 1),
        ('1.0.0-RC.1', '1.0.0-rc.1', -1),
        ('1.0.0', '1.0.0-rc.9', 1),
        ('0.9.9', '1.0.0', -1),
    ),
)
def test_compare_versions(left: str, right: str, expected: int) -> None:
    assert compare_versions(left, right) == expected


def test_normalize_and_detect_newer_version() -> None:
    assert normalize_version('v01.000.000') == '1.0.0'
    assert is_newer_version('v1.1.0', current='1.0.0') is True
    assert is_newer_version('v1.0.0', current='1.0.0') is False


def test_invalid_version_is_rejected() -> None:
    with pytest.raises(UpdateCheckError, match='Invalid version'):
        normalize_version('release-latest')
    with pytest.raises(UpdateCheckError, match='Invalid version'):
        normalize_version('1.0.0-rc..1')


def _release_payload(**overrides) -> bytes:
    payload = {
        'tag_name': 'v1.1.0',
        'name': 'Palworld Companion Tools v1.1.0',
        'html_url': (
            'https://github.com/rckieee-gif/Palworld-Companion-Tool/'
            'releases/tag/v1.1.0'
        ),
        'body': 'Installer and data updates.',
        'draft': False,
        'prerelease': False,
    }
    payload.update(overrides)
    return json.dumps(payload).encode('utf-8')


def test_release_payload_is_parsed() -> None:
    release = parse_release_payload(_release_payload())
    assert release.version == '1.1.0'
    assert release.name == 'Palworld Companion Tools v1.1.0'
    assert release.url.endswith('/releases/tag/v1.1.0')
    assert release.notes == 'Installer and data updates.'


@pytest.mark.parametrize(
    'overrides',
    (
        {'draft': True},
        {'prerelease': True},
        {'tag_name': 'latest'},
        {'html_url': 'https://example.com/releases/tag/v1.1.0'},
        {'html_url': 'http://github.com/rckieee-gif/Palworld-Companion-Tool/releases/tag/v1.1.0'},
    ),
)
def test_untrusted_or_unstable_release_is_rejected(overrides: dict[str, object]) -> None:
    with pytest.raises(UpdateCheckError):
        parse_release_payload(_release_payload(**overrides))


def test_automatic_check_interval() -> None:
    now = datetime(2026, 7, 17, 12, 0, tzinfo=timezone.utc)
    assert should_check_automatically(None, now=now) is True
    assert should_check_automatically('not-a-date', now=now) is True
    assert should_check_automatically(
        (now - timedelta(hours=23)).isoformat(), now=now
    ) is False
    assert should_check_automatically(
        (now - timedelta(hours=25)).isoformat(), now=now
    ) is True
