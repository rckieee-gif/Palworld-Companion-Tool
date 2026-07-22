from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from palworld_aio.team_builder import MAX_TEAM_SIZE


@dataclass(frozen=True, slots=True)
class TeamPreset:
    preset_id: str
    name: str
    description: str
    member_ids: tuple[str, ...]
    goal: str


TEAM_PRESETS = (
    TeamPreset(
        preset_id="electric-synergy",
        name="Electric Synergy",
        description=(
            "Applies Electrify, rewards the status, adds party offense, and "
            "covers Water damage."
        ),
        member_ids=(
            "ThunderBird",
            "ElecLizard",
            "MonochromeQueen",
            "ElecSnail",
            "ElecSnail_Ground",
        ),
        goal="Status damage",
    ),
    TeamPreset(
        preset_id="balanced-expedition",
        name="Balanced Expedition",
        description=(
            "Combines offense, healing, defense, detection, and mixed element "
            "coverage."
        ),
        member_ids=(
            "Anubis",
            "LilyQueen",
            "FlowerDinosaur",
            "ThunderDragonMan",
            "CatBat",
        ),
        goal="Balanced",
    ),
    TeamPreset(
        preset_id="beginner-utility",
        name="Beginner Utility",
        description=(
            "Early-game shields, carrying capacity, ranch supplies, and two "
            "active combat partners."
        ),
        member_ids=(
            "SheepBall",
            "PinkCat",
            "ChickenPal",
            "Kitsunebi",
            "Carbunclo",
        ),
        goal="Beginner-friendly",
    ),
    TeamPreset(
        preset_id="rapid-travel",
        name="Rapid Travel",
        description=(
            "A selection of flying and ground mounts with varied combat and "
            "movement benefits."
        ),
        member_ids=(
            "JetDragon",
            "HawkBird",
            "FengyunDeeper",
            "ThunderBird",
            "KingAlpaca",
        ),
        goal="Mobility",
    ),
)


def validate_team_presets(valid_member_ids: Iterable[str]) -> tuple[TeamPreset, ...]:
    valid = set(valid_member_ids)
    for preset in TEAM_PRESETS:
        if not preset.member_ids or len(preset.member_ids) > MAX_TEAM_SIZE:
            raise ValueError(f"Invalid team size in preset: {preset.preset_id}")
        unknown = [member_id for member_id in preset.member_ids if member_id not in valid]
        if unknown:
            raise ValueError(
                f"Unknown Pal IDs in preset {preset.preset_id}: {', '.join(unknown)}"
            )
    return TEAM_PRESETS
