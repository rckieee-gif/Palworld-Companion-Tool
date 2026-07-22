from __future__ import annotations

from palworld_aio.game_data import load_game_data
from palworld_aio.wiki_text import (
    contains_game_tokens,
    get_wiki_text_resolver,
    prepare_wiki_entries,
)


def test_charging_shell_uses_real_status_and_rank_values() -> None:
    pals = load_game_data("characters.json")["pals"]
    snock = next(pal for pal in pals if pal["asset"] == "ElecSnail")

    description = get_wiki_text_resolver().resolve_partner_skill(snock)

    assert description == (
        "While in party, the player's attacks inflict Electrify 2~6. "
        "(Does not stack)"
    )


def test_visible_passive_description_uses_effect_values() -> None:
    passives = prepare_wiki_entries(
        "passive_skills",
        load_game_data("skills.json")["passives"],
    )
    serenity = next(row for row in passives if row["name"] == "Serenity")
    easygoing = next(row for row in passives if row["name"] == "Easygoing")

    assert serenity["_display_description"] == (
        "Active skill cooldown reduction 30%\nAttack +10%"
    )
    assert easygoing["_display_description"] == (
        "Active skill cooldown extension 15%"
    )


def test_all_public_wiki_templates_resolve_from_current_game_data() -> None:
    pals = prepare_wiki_entries(
        "pals",
        load_game_data("characters.json")["pals"],
    )
    passives = prepare_wiki_entries(
        "passive_skills",
        load_game_data("skills.json")["passives"],
    )

    for row in [*pals, *passives]:
        description = str(row.get("_display_description") or "")
        assert not contains_game_tokens(description), row["asset"]
        assert "value unavailable" not in description, row["asset"]


def test_wiki_filters_internal_records_without_mutating_source_data() -> None:
    raw_passives = load_game_data("skills.json")["passives"]
    raw_items = load_game_data("items.json")["items"]
    raw_pals = load_game_data("characters.json")["pals"]

    passives = prepare_wiki_entries("passive_skills", raw_passives)
    items = prepare_wiki_entries("items", raw_items)
    pals = prepare_wiki_entries("pals", raw_pals)

    assert all(
        str(row["category"]).endswith("SortDisplayable")
        for row in passives
    )
    assert not any(row["asset"] == "BlueprintTest" for row in items)
    assert not any(
        row.get("name") == row.get("asset")
        and not str(row.get("description") or "").strip()
        for row in items
    )
    assert not any(row["asset"].startswith("BOSS_") for row in pals)
    assert "_display_description" not in next(
        row for row in raw_pals if row["asset"] == "ElecSnail"
    )
