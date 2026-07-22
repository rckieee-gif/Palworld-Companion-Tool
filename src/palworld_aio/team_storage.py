from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, replace
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
from typing import Any
from uuid import uuid4

from palworld_aio.team_builder import MAX_TEAM_SIZE
from resource_resolver import get_user_config_dir


LOGGER = logging.getLogger(__name__)
STORAGE_VERSION = 1
MAX_TEAM_NAME_LENGTH = 60


class TeamStorageError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class SavedTeam:
    team_id: str
    name: str
    member_ids: tuple[str, ...]
    created_at: str
    updated_at: str

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.team_id,
            "name": self.name,
            "member_ids": list(self.member_ids),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _clean_name(name: str) -> str:
    cleaned = " ".join(str(name).split())
    if not cleaned:
        raise TeamStorageError("Team name cannot be empty.")
    if len(cleaned) > MAX_TEAM_NAME_LENGTH:
        raise TeamStorageError(
            f"Team name must be {MAX_TEAM_NAME_LENGTH} characters or fewer."
        )
    return cleaned


class SavedTeamStore:
    def __init__(
        self,
        valid_member_ids: Iterable[str],
        path: Path | None = None,
        *,
        id_factory: Callable[[], str] | None = None,
        timestamp_factory: Callable[[], str] | None = None,
    ) -> None:
        self.path = path or Path(get_user_config_dir()) / "saved_teams.json"
        self._valid_member_ids = frozenset(valid_member_ids)
        self._id_factory = id_factory or (lambda: str(uuid4()))
        self._timestamp_factory = timestamp_factory or _timestamp
        self._teams = self._read()

    @property
    def teams(self) -> tuple[SavedTeam, ...]:
        return tuple(sorted(
            self._teams,
            key=lambda team: (team.name.casefold(), team.created_at),
        ))

    def get(self, team_id: str) -> SavedTeam | None:
        return next((team for team in self._teams if team.team_id == team_id), None)

    def create(self, name: str, member_ids: Iterable[str]) -> SavedTeam:
        members = self._validate_members(member_ids)
        now = self._timestamp_factory()
        team = SavedTeam(
            team_id=self._id_factory(),
            name=_clean_name(name),
            member_ids=members,
            created_at=now,
            updated_at=now,
        )
        self._teams.append(team)
        self._write()
        return team

    def overwrite(self, team_id: str, member_ids: Iterable[str]) -> SavedTeam:
        team = self._require(team_id)
        updated = replace(
            team,
            member_ids=self._validate_members(member_ids),
            updated_at=self._timestamp_factory(),
        )
        self._replace(updated)
        return updated

    def rename(self, team_id: str, name: str) -> SavedTeam:
        team = self._require(team_id)
        updated = replace(
            team,
            name=_clean_name(name),
            updated_at=self._timestamp_factory(),
        )
        self._replace(updated)
        return updated

    def delete(self, team_id: str) -> None:
        self._require(team_id)
        self._teams = [team for team in self._teams if team.team_id != team_id]
        self._write()

    def _validate_members(self, member_ids: Iterable[str]) -> tuple[str, ...]:
        members = tuple(str(member_id) for member_id in member_ids)
        if not members:
            raise TeamStorageError("Select at least one Pal before saving a team.")
        if len(members) > MAX_TEAM_SIZE:
            raise TeamStorageError(f"A team can contain at most {MAX_TEAM_SIZE} Pals.")
        unknown = [member_id for member_id in members if member_id not in self._valid_member_ids]
        if unknown:
            raise TeamStorageError(f"Unknown Pal ID: {unknown[0]}")
        return members

    def _require(self, team_id: str) -> SavedTeam:
        team = self.get(team_id)
        if team is None:
            raise TeamStorageError("Saved team was not found.")
        return team

    def _replace(self, updated: SavedTeam) -> None:
        self._teams = [
            updated if team.team_id == updated.team_id else team
            for team in self._teams
        ]
        self._write()

    def _read(self) -> list[SavedTeam]:
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return []
        except (OSError, json.JSONDecodeError) as exc:
            LOGGER.warning("Could not read saved teams from %s: %s", self.path, exc)
            return []
        if not isinstance(value, Mapping) or value.get("version") != STORAGE_VERSION:
            LOGGER.warning("Ignoring unsupported saved-team data in %s", self.path)
            return []
        raw_teams = value.get("teams")
        if not isinstance(raw_teams, list):
            return []
        teams = []
        for raw_team in raw_teams:
            parsed = self._parse_team(raw_team)
            if parsed is not None:
                teams.append(parsed)
        return teams

    def _parse_team(self, value: Any) -> SavedTeam | None:
        if not isinstance(value, Mapping):
            return None
        raw_members = value.get("member_ids")
        if not isinstance(raw_members, list):
            return None
        members = tuple(
            member_id
            for member_id in raw_members[:MAX_TEAM_SIZE]
            if isinstance(member_id, str) and member_id in self._valid_member_ids
        )
        try:
            name = _clean_name(str(value.get("name") or ""))
        except TeamStorageError:
            return None
        team_id = value.get("id")
        created_at = value.get("created_at")
        updated_at = value.get("updated_at")
        if not all(isinstance(field, str) and field for field in (
            team_id,
            created_at,
            updated_at,
        )) or not members:
            return None
        return SavedTeam(
            team_id=team_id,
            name=name,
            member_ids=members,
            created_at=created_at,
            updated_at=updated_at,
        )

    def _write(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        value = {
            "version": STORAGE_VERSION,
            "teams": [team.to_dict() for team in self._teams],
        }
        try:
            temporary.write_text(
                json.dumps(value, ensure_ascii=True, indent=2) + "\n",
                encoding="utf-8",
            )
            temporary.replace(self.path)
        except OSError as exc:
            LOGGER.warning("Could not save teams to %s: %s", self.path, exc)
            raise TeamStorageError("The saved-team file could not be updated.") from exc
