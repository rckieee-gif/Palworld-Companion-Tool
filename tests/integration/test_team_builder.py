from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QDialog

from palworld_aio.team_builder import EffectCategory, load_team_members, team_member_index
from palworld_aio.team_storage import SavedTeamStore
from palworld_aio.ui.team_selector import MemberSelectorDialog
from palworld_aio.ui.tabs.team_builder_tab import TeamBuilderTab


def _tab(tmp_path) -> TeamBuilderTab:
    store = SavedTeamStore(team_member_index(), tmp_path / "saved-teams.json")
    return TeamBuilderTab(store=store)


def test_select_replace_remove_and_duplicate_slots(qapp, tmp_path) -> None:
    tab = _tab(tmp_path)
    try:
        assert tab.set_slot_member(0, "ElecSnail") is True
        assert tab.set_slot_member(1, "ElecSnail") is True
        assert tab.team_ids == ("ElecSnail", "ElecSnail")
        assert tab.team_slots.slots[0].quantity_label.text() == "x2"
        assert tab.team_slots.slots[0].quantity_label.isHidden() is False

        assert tab.set_slot_member(0, "ThunderBird") is True
        assert tab.team_ids == ("ThunderBird", "ElecSnail")
        tab.remove_member(0)
        assert tab.team_ids == ("ElecSnail",)
        assert tab.counter_label.text() == "1 / 5 selected"
    finally:
        tab.close()


def test_maximum_five_members_and_reordering(qapp, tmp_path) -> None:
    tab = _tab(tmp_path)
    try:
        tab.set_team((
            "ThunderBird",
            "ElecLizard",
            "MonochromeQueen",
            "ElecSnail",
            "ElecSnail_Ground",
        ))
        assert tab.set_slot_member(4, "Anubis") is True
        assert tab.set_slot_member(5, "LilyQueen") is False
        assert len(tab.team_ids) == 5

        before = tab.team_ids
        tab.move_member(1, -1)
        assert tab.team_ids[:2] == (before[1], before[0])
    finally:
        tab.close()


def test_selector_search_filters_incremental_results_and_keyboard(qapp) -> None:
    dialog = MemberSelectorDialog(
        load_team_members(),
        ("ElecSnail",),
        slot_index=1,
    )
    try:
        assert dialog.results.count() == dialog.PAGE_SIZE
        assert dialog.load_more_button.isHidden() is False

        dialog.search.setText("Charging Shell")
        assert [member.member_id for member in dialog.visible_members] == ["ElecSnail"]
        dialog.results.setCurrentRow(0)
        QTest.keyClick(dialog.results, Qt.Key_Return)

        assert dialog.result() == QDialog.Accepted
        assert dialog.selected_member_id == "ElecSnail"
    finally:
        dialog.close()


def test_selector_element_effect_and_work_filters(qapp) -> None:
    dialog = MemberSelectorDialog(load_team_members(), (), slot_index=0)
    try:
        dialog.element_filter.setCurrentText("Electric")
        assert dialog.visible_members
        assert all("Electric" in member.elements for member in dialog.visible_members)

        dialog.clear_filters()
        dialog.effect_filter.setCurrentText(EffectCategory.STATUS.value)
        assert "ElecSnail" in {member.member_id for member in dialog.visible_members}

        dialog.clear_filters()
        dialog.work_filter.setCurrentText("Mining")
        assert "Anubis" in {member.member_id for member in dialog.visible_members}
    finally:
        dialog.close()


def test_shared_url_invalid_ids_and_history_restore(qapp, tmp_path) -> None:
    tab = _tab(tmp_path)
    try:
        result = tab.load_share_url(
            "palworld-companion://team-builder?team="
            "elecsnail,missing,thunderbird,elecsnail"
        )
        assert result.invalid_identifiers == ("missing",)
        assert tab.team_ids == ("ElecSnail", "ThunderBird", "ElecSnail")
        assert "Ignored 1 unknown" in tab.notice_label.text()

        tab.set_slot_member(0, "Anubis")
        changed = tab.team_ids
        tab.go_back()
        assert tab.team_ids == ("ElecSnail", "ThunderBird", "ElecSnail")
        tab.go_forward()
        assert tab.team_ids == changed
    finally:
        tab.close()


def test_saved_team_create_load_rename_overwrite_and_delete(qapp, tmp_path) -> None:
    tab = _tab(tmp_path)
    try:
        tab.set_team(("ElecSnail", "ElecSnail", "ThunderBird"))
        saved = tab.save_current_team("Status Pair")
        assert saved is not None
        assert saved.member_ids == tab.team_ids

        tab.set_team(("Anubis",))
        assert tab.load_saved_team(saved.team_id, confirm=False) is True
        assert tab.team_ids == ("ElecSnail", "ElecSnail", "ThunderBird")
        assert tab.rename_saved_team(saved.team_id, "Electric Core").name == "Electric Core"

        tab.set_team(("LilyQueen", "Anubis"))
        assert tab.overwrite_saved_team(saved.team_id, confirm=False).member_ids == tab.team_ids
        assert tab.delete_saved_team(saved.team_id, confirm=False) is True
        assert tab.store.teams == ()
    finally:
        tab.close()


def test_team_overview_and_compact_layout_update_without_overflow(qapp, tmp_path) -> None:
    tab = _tab(tmp_path)
    try:
        tab.resize(520, 760)
        tab.show()
        tab.set_team(("ElecSnail", "ElecSnail", "ElecLizard"))
        qapp.processEvents()

        assert tab.team_slots.columns == 2
        assert tab.scroll.horizontalScrollBar().maximum() == 0
        assert "3 selected" in tab.overview.selected_label.text()
        assert "Snock x2" in tab.overview.duplicate_label.text()
        assert tab.overview.effects.topLevelItemCount() > 0
    finally:
        tab.close()


def test_share_button_copies_canonical_url(qapp, tmp_path) -> None:
    tab = _tab(tmp_path)
    try:
        tab.set_team(("ElecSnail", "ElecSnail"))
        assert tab.copy_share_url() is True
        assert qapp.clipboard().text() == (
            "palworld-companion://team-builder?team=elecsnail,elecsnail"
        )
        assert "copied" in tab.notice_label.text().casefold()
    finally:
        tab.close()
