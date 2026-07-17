"""Asynchronous, release-only update checks against the companion repository."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
import re
from typing import Any
from urllib.parse import urlparse

from PySide6.QtCore import QObject, QUrl, Signal
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest

from app_info import (
    LATEST_RELEASE_API_URL,
    PRODUCT_SLUG,
    PRODUCT_VERSION,
    REPOSITORY_SLUG,
)


AUTO_CHECK_INTERVAL = timedelta(hours=24)
_VERSION_PATTERN = re.compile(
    r'^[vV]?(?P<release>\d+(?:\.\d+)*)'
    r'(?:-(?P<prerelease>[0-9A-Za-z.-]+))?'
    r'(?:\+[0-9A-Za-z.-]+)?$'
)


class UpdateCheckError(ValueError):
    """Raised when update metadata is malformed or cannot be trusted."""


@dataclass(frozen=True)
class ReleaseInfo:
    version: str
    name: str
    url: str
    notes: str = ''


@dataclass(frozen=True)
class _ParsedVersion:
    release: tuple[int, ...]
    prerelease: tuple[str, ...] | None


def _parse_version(value: str) -> _ParsedVersion:
    match = _VERSION_PATTERN.fullmatch(value.strip())
    if match is None:
        raise UpdateCheckError(f'Invalid version: {value!r}')
    release = tuple(int(part) for part in match.group('release').split('.'))
    prerelease_text = match.group('prerelease')
    if prerelease_text is not None and any(
        not part for part in prerelease_text.split('.')
    ):
        raise UpdateCheckError(f'Invalid version: {value!r}')
    prerelease = (
        tuple(prerelease_text.split('.')) if prerelease_text is not None else None
    )
    return _ParsedVersion(release=release, prerelease=prerelease)


def normalize_version(value: str) -> str:
    parsed = _parse_version(value)
    release = '.'.join(str(part) for part in parsed.release)
    if parsed.prerelease is None:
        return release
    return f'{release}-{".".join(parsed.prerelease)}'


def _compare_prerelease(
    left: tuple[str, ...] | None,
    right: tuple[str, ...] | None,
) -> int:
    if left is None:
        return 0 if right is None else 1
    if right is None:
        return -1
    for left_part, right_part in zip(left, right):
        if left_part == right_part:
            continue
        left_numeric = left_part.isdigit()
        right_numeric = right_part.isdigit()
        if left_numeric and right_numeric:
            return 1 if int(left_part) > int(right_part) else -1
        if left_numeric != right_numeric:
            return -1 if left_numeric else 1
        return 1 if left_part > right_part else -1
    if len(left) == len(right):
        return 0
    return 1 if len(left) > len(right) else -1


def compare_versions(left: str, right: str) -> int:
    left_version = _parse_version(left)
    right_version = _parse_version(right)
    width = max(len(left_version.release), len(right_version.release))
    left_release = left_version.release + (0,) * (width - len(left_version.release))
    right_release = right_version.release + (0,) * (width - len(right_version.release))
    if left_release != right_release:
        return 1 if left_release > right_release else -1
    return _compare_prerelease(left_version.prerelease, right_version.prerelease)


def is_newer_version(candidate: str, current: str = PRODUCT_VERSION) -> bool:
    return compare_versions(candidate, current) > 0


def parse_release_payload(payload: bytes | str) -> ReleaseInfo:
    try:
        decoded = payload.decode('utf-8') if isinstance(payload, bytes) else payload
        value: Any = json.loads(decoded)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise UpdateCheckError('GitHub returned invalid release metadata.') from exc
    if not isinstance(value, Mapping):
        raise UpdateCheckError('GitHub release metadata was not an object.')
    if value.get('draft') is True or value.get('prerelease') is True:
        raise UpdateCheckError('The latest release is not a stable published release.')

    tag_name = value.get('tag_name')
    release_url = value.get('html_url')
    if not isinstance(tag_name, str) or not tag_name.strip():
        raise UpdateCheckError('The release did not include a version tag.')
    if not isinstance(release_url, str):
        raise UpdateCheckError('The release did not include a web address.')

    parsed_url = urlparse(release_url)
    expected_prefix = f'/{REPOSITORY_SLUG}/releases/'
    if (
        parsed_url.scheme != 'https'
        or parsed_url.hostname not in {'github.com', 'www.github.com'}
        or not parsed_url.path.startswith(expected_prefix)
    ):
        raise UpdateCheckError('GitHub returned an unexpected release address.')

    version = normalize_version(tag_name)
    name_value = value.get('name')
    name = str(name_value).strip() if name_value else f'Version {version}'
    notes_value = value.get('body')
    notes = str(notes_value).strip() if notes_value else ''
    return ReleaseInfo(version=version, name=name, url=release_url, notes=notes)


def should_check_automatically(
    last_checked: object,
    *,
    now: datetime | None = None,
    interval: timedelta = AUTO_CHECK_INTERVAL,
) -> bool:
    if not isinstance(last_checked, str) or not last_checked.strip():
        return True
    try:
        checked_at = datetime.fromisoformat(last_checked.replace('Z', '+00:00'))
    except ValueError:
        return True
    if checked_at.tzinfo is None:
        checked_at = checked_at.replace(tzinfo=timezone.utc)
    current = now or datetime.now(timezone.utc)
    checked_at = checked_at.astimezone(timezone.utc)
    current = current.astimezone(timezone.utc)
    if checked_at > current:
        return True
    return current - checked_at >= interval


def current_utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


class GitHubReleaseChecker(QObject):
    """Fetch the latest stable GitHub release without blocking the UI thread."""

    update_available = Signal(object)
    up_to_date = Signal(object)
    failed = Signal(str)
    finished = Signal()

    def __init__(
        self,
        parent: QObject | None = None,
        *,
        network_manager: QNetworkAccessManager | None = None,
    ):
        super().__init__(parent)
        self._network_manager = network_manager or QNetworkAccessManager(self)
        self._reply: QNetworkReply | None = None

    @property
    def is_checking(self) -> bool:
        return self._reply is not None

    def check(self) -> bool:
        if self._reply is not None:
            return False
        request = QNetworkRequest(QUrl(LATEST_RELEASE_API_URL))
        request.setHeader(
            QNetworkRequest.KnownHeaders.UserAgentHeader,
            f'{PRODUCT_SLUG}/{PRODUCT_VERSION}',
        )
        request.setRawHeader(b'Accept', b'application/vnd.github+json')
        request.setRawHeader(b'X-GitHub-Api-Version', b'2022-11-28')
        request.setTransferTimeout(10_000)
        self._reply = self._network_manager.get(request)
        self._reply.finished.connect(self._handle_reply)
        return True

    def _handle_reply(self) -> None:
        reply = self._reply
        self._reply = None
        if reply is None:
            return
        try:
            if reply.error() != QNetworkReply.NetworkError.NoError:
                self.failed.emit(f'GitHub update check failed: {reply.errorString()}')
                return
            status = reply.attribute(
                QNetworkRequest.Attribute.HttpStatusCodeAttribute
            )
            if status != 200:
                self.failed.emit(f'GitHub update check returned HTTP {status}.')
                return
            try:
                release = parse_release_payload(bytes(reply.readAll()))
            except UpdateCheckError as exc:
                self.failed.emit(str(exc))
                return
            if is_newer_version(release.version):
                self.update_available.emit(release)
            else:
                self.up_to_date.emit(release)
        finally:
            reply.deleteLater()
            self.finished.emit()


__all__ = [
    'AUTO_CHECK_INTERVAL',
    'GitHubReleaseChecker',
    'ReleaseInfo',
    'UpdateCheckError',
    'compare_versions',
    'current_utc_timestamp',
    'is_newer_version',
    'normalize_version',
    'parse_release_payload',
    'should_check_automatically',
]
