from __future__ import annotations

import json

import pytest

from palworld_aio.team_builder import (
    EffectCategory,
    MAX_TEAM_SIZE,
    TeamHistory,
    analyze_team,
    build_team_share_url,
    filter_team_members,
    is_team_share_url,
    load_team_members,
    normalize_team_ids,
    parse_team_share_url,
    team_member_index,
)
from palworld_aio.team_presets import validate_team_presets
from palworld_aio.team_storage import SavedTeamStore, TeamStorageError


REFERENCE_TEAM = (
    "ThunderBird",
    "ElecLizard",
    "MonochromeQueen",
    "ElecSnail",
    "ElecSnail_Ground",
)


def test_team_members_reuse_public_game_data() -> None:
    members = load_team_members()
    index = team_member_index()

    assert len(members) == 289
    assert set(REFERENCE_TEAM).issubset(index)
    assert index["ElecSnail"].name == "Snock"
    assert index["ElecSnail"].partner_description.endswith(
        "Electrify 2~6. (Does not stack)"
    )
    assert not any(member.member_id.startswith("BOSS_") for member in members)


def test_search_and_filters_use_member_data() -> None:
    members = load_team_members()

    by_search = filter_team_members(members, query="charging shell")
    by_element = filter_team_members(members, element="Electric")
    by_effect = filter_team_members(members, category=EffectCategory.STATUS)
    by_work = filter_team_members(members, work="Mining")

    assert [member.member_id for member in by_search] == ["ElecSnail"]
    assert all("Electric" in member.elements for member in by_element)
    assert "ElecSnail" in {member.member_id for member in by_effect}
    assert "Anubis" in {member.member_id for member in by_work}


def test_share_url_preserves_order_and_duplicates() -> None:
    index = team_member_index()
    team = ("ElecSnail", "ThunderBird", "ElecSnail")

    url = build_team_share_url(team, index)
    parsed = parse_team_share_url(url, index)

    assert url == (
        "palworld-companion://team-builder?"
        "team=elecsnail,thunderbird,elecsnail"
    )
    assert parsed.member_ids == team
    assert parsed.invalid_identifiers == ()
    assert is_team_share_url(url) is True
    assert is_team_share_url("/team-builder?team=elecsnail") is True


def test_invalid_and_excess_url_members_are_ignored_safely() -> None:
    index = team_member_index()
    url = (
        "palworld-companion://team-builder?team="
        "elecsnail,missing,thunderbird,elecsnail,anubis,lilyqueen,catbat"
    )

    parsed = parse_team_share_url(url, index)

    assert parsed.member_ids == (
        "ElecSnail",
        "ThunderBird",
        "ElecSnail",
        "Anubis",
        "LilyQueen",
    )
    assert parsed.invalid_identifiers == ("missing",)
    assert parsed.truncated_count == 1


def test_team_size_normalization_enforces_five_slots() -> None:
    normalized = normalize_team_ids(
        (*REFERENCE_TEAM, "Anubis"),
        team_member_index(),
    )
    assert len(normalized) == MAX_TEAM_SIZE
    assert normalized == REFERENCE_TEAM


def test_analysis_updates_duplicates_elements_and_effect_groups() -> None:
    analysis = analyze_team(
        ("ElecSnail", "ElecSnail", "ElecLizard"),
        team_member_index(),
    )

    assert analysis.selected_count == 3
    assert analysis.unique_count == 2
    assert analysis.duplicate_counts == (("Snock", 2),)
    assert analysis.element_distribution == (("Electric", 3),)
    status = next(
        summary for summary in analysis.effects
        if summary.category == EffectCategory.STATUS
    )
    snock = next(
        contribution for contribution in status.contributions
        if contribution.member_id == "ElecSnail"
    )
    assert snock.quantity == 2
    assert snock.stacking == "Does not stack"
    assert any("not totaled" in note for note in analysis.coverage_notes)


def test_team_history_restores_back_and_forward_order() -> None:
    history = TeamHistory()
    history.push(("ElecSnail",))
    history.push(("ThunderBird", "ElecSnail"))

    assert history.back() == ("ElecSnail",)
    assert history.can_forward is True
    assert history.forward() == ("ThunderBird", "ElecSnail")


def test_presets_only_reference_current_members() -> None:
    presets = validate_team_presets(team_member_index())
    electric = next(preset for preset in presets if preset.preset_id == "electric-synergy")

    assert electric.member_ids == REFERENCE_TEAM
    assert all(0 < len(preset.member_ids) <= MAX_TEAM_SIZE for preset in presets)


def test_saved_team_round_trip_preserves_duplicates_and_order(tmp_path) -> None:
    path = tmp_path / "saved-teams.json"
    ids = iter(("team-1",))
    store = SavedTeamStore(
        team_member_index(),
        path,
        id_factory=lambda: next(ids),
        timestamp_factory=lambda: "2026-07-20T00:00:00+00:00",
    )

    saved = store.create("  Electric   Pair  ", ("ElecSnail", "ElecSnail"))
    reloaded = SavedTeamStore(team_member_index(), path)

    assert saved.name == "Electric Pair"
    assert reloaded.get("team-1").member_ids == ("ElecSnail", "ElecSnail")
    assert reloaded.rename("team-1", "Status Team").name == "Status Team"
    assert reloaded.overwrite("team-1", REFERENCE_TEAM).member_ids == REFERENCE_TEAM
    reloaded.delete("team-1")
    assert reloaded.teams == ()


def test_saved_team_validation_handles_bad_input_and_corruption(tmp_path) -> None:
    path = tmp_path / "saved-teams.json"
    path.write_text("not-json", encoding="utf-8")
    store = SavedTeamStore(team_member_index(), path)

    assert store.teams == ()
    with pytest.raises(TeamStorageError, match="cannot be empty"):
        store.create("   ", ("ElecSnail",))
    with pytest.raises(TeamStorageError, match="Unknown Pal ID"):
        store.create("Bad", ("NotARealPal",))
    with pytest.raises(TeamStorageError, match="at most"):
        store.create("Too many", (*REFERENCE_TEAM, "Anubis"))

    path.write_text(json.dumps({"version": 999, "teams": []}), encoding="utf-8")
    assert SavedTeamStore(team_member_index(), path).teams == ()
