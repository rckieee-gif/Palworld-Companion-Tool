from __future__ import annotations

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QLabel

from app_info import GAME_DATA_VERSION, PRODUCT_VERSION, RELEASES_URL
from palworld_aio.ui.main_window import MainWindow
from palworld_aio.update_service import ReleaseInfo


EXPECTED_NAVIGATION = (
    'map',
    'breeding',
    'stats_calculator',
    'team_builder',
    'wiki',
    'settings',
    'about',
)
MAP_NO_SAVE_MESSAGE = (
    'Explore bundled locations. Load Level.sav to add read-only '
    'base and player overlays.'
)


class _FakeUpdateChecker(QObject):
    update_available = Signal(object)
    up_to_date = Signal(object)
    failed = Signal(str)
    finished = Signal()

    def __init__(self):
        super().__init__()
        self.is_checking = False
        self.check_calls = 0

    def check(self) -> bool:
        self.check_calls += 1
        self.is_checking = True
        return True


def test_app_starts_without_a_save(qapp) -> None:
    window = MainWindow(schedule_update_check=False)
    try:
        assert window.loaded_world is None
        assert window.navigation_ids == EXPECTED_NAVIGATION
        assert window.stack.count() == 7
        assert window.stack.currentWidget() is window.breeding_tab
    finally:
        window.close()


def test_only_allowed_navigation_entries_are_registered(qapp) -> None:
    window = MainWindow(schedule_update_check=False)
    try:
        labels = tuple(button.text().lower() for button in window._nav_buttons.values())
        assert labels == (
            'map',
            'breeding',
            'stats calculator',
            'team builder',
            'wiki',
            'settings',
            'about',
        )
        assert set(window._pages) == set(EXPECTED_NAVIGATION)
    finally:
        window.close()


def test_stats_calculator_uses_bundled_data_and_calculates_iv(qapp) -> None:
    window = MainWindow(schedule_update_check=False)
    try:
        window.navigate('stats_calculator')
        calculator = window.stats_calculator_tab
        calculator.pal_combo.setCurrentText('mElPaCa')
        calculator._fields['level'].setText('50')
        calculator._fields['current_hp'].setText('3337')
        calculator._fields['current_attack'].setText('423')
        calculator._fields['current_defense'].setText('438')
        calculator.calculate_button.click()

        assert window.stack.currentWidget() is calculator
        assert window.page_title.text() == 'Stats Calculator'
        assert calculator._lookup().record.pal_id == 'Alpaca'
        assert calculator.manual_base_section.isHidden() is True
        assert all(
            widgets['value'].text() == '50 IV'
            for widgets in calculator._result_widgets.values()
        )
        assert calculator.formula_notice.isHidden() is True

        for field_name in ('current_hp', 'current_attack', 'current_defense'):
            calculator._fields[field_name].setText('1')
        calculator.calculate_button.click()
        assert all(
            widgets['value'].text() == 'Unable to determine'
            for widgets in calculator._result_widgets.values()
        )
        assert window.status_bar.currentMessage() == (
            'No IV range matched the entered stats and modifiers.'
        )

        calculator._fields['level'].setText('51')
        assert calculator.stale_label.isHidden() is False

        calculator.reset_button.click()
        assert all(
            widgets['value'].property('resultState') == 'empty'
            for widgets in calculator._result_widgets.values()
        )

        calculator.pal_combo.setCurrentText('Unknown manual Pal')
        assert calculator.manual_base_section.isHidden() is False
    finally:
        window.close()


def test_breeding_and_wiki_work_without_world_data(qapp) -> None:
    window = MainWindow(schedule_update_check=False)
    try:
        window.navigate('breeding')
        assert len(window.breeding_tab.pal_info) > 250
        assert 'ElecLion' not in window.breeding_tab.pal_info
        assert window.breeding_tab.max_generations.value() == 6
        assert window.breeding_tab.tabs.count() == 3

        window.navigate('wiki')
        wiki = window.wiki_tab.wiki_tab
        assert len(wiki._pages) == 8
        assert wiki._pages['pals']._loaded is True
        assert wiki._pages['pals']._all_data
    finally:
        window.close()


def test_team_builder_works_without_world_data_and_restores_share_url(qapp) -> None:
    window = MainWindow(schedule_update_check=False)
    try:
        window.open_team_url(
            'palworld-companion://team-builder?team=elecsnail,elecsnail,anubis'
        )

        assert window.stack.currentWidget() is window.team_builder_tab
        assert window.team_builder_tab.team_ids == (
            'ElecSnail',
            'ElecSnail',
            'Anubis',
        )
        assert window.page_title.text() == 'Team Builder'
    finally:
        window.close()


def test_native_map_is_available_without_a_save(qapp) -> None:
    window = MainWindow(schedule_update_check=False)
    try:
        window.navigate('map')
        assert window.map_tab.local_page is not None
        assert len(window.map_tab._bundled_locations) == 174
        assert len(window.map_tab._location_markers) == 157
        assert window.map_tab.location_tree.topLevelItemCount() == 1
        assert window.map_tab.read_only_label.isHidden() is True
        texts = [label.text() for label in window.map_tab.findChildren(QLabel)]
        assert MAP_NO_SAVE_MESSAGE in texts
    finally:
        window.close()


def test_native_map_searches_both_maps_and_renders_personal_pins(qapp) -> None:
    window = MainWindow(schedule_update_check=False)
    try:
        map_tab = window.map_tab
        map_tab.annotation_store.clear()

        map_tab.search.setText('Deserted Islet')
        assert len(map_tab._location_markers) == 1
        location = next(iter(map_tab._location_markers.values())).location_data
        assert location.name == 'Deserted Islet'

        map_tab.search.clear()
        map_tab.tree_button.click()
        assert len(map_tab._location_markers) == 17

        map_tab.world_button.click()
        pin_id = map_tab.annotation_store.add({
            'type': 'point',
            'name': 'Ore route',
            'map_type': 'world',
            'x': 125,
            'y': -340,
        })
        map_tab.refresh()
        assert pin_id in map_tab._location_markers
        assert map_tab._location_markers[pin_id].location_data.source == 'local'
        assert map_tab.world is None
    finally:
        window.map_tab.annotation_store.clear()
        window.close()


def test_native_map_renders_pal_heatmap_on_both_maps(qapp) -> None:
    window = MainWindow(schedule_update_check=False)
    try:
        map_tab = window.map_tab
        map_tab.tree_button.click()
        map_tab.show_heatmap.click()
        assert map_tab.show_heatmap_outline.isChecked() is True
        index = map_tab.heatmap_pal_combo.findText('Aegidron')
        assert index >= 0
        map_tab.heatmap_pal_combo.setCurrentIndex(index)
        qapp.processEvents()

        assert map_tab._heatmap_item is not None
        assert map_tab._heatmap_item.scene() is map_tab.scene
        assert 'Aegidron' in map_tab.heatmap_status_label.text()
        assert 'spawn areas' in map_tab.heatmap_status_label.text()

        map_tab.world_button.click()
        assert map_tab.current_map == 'world'
        index = map_tab.heatmap_pal_combo.findText('Blazehowl')
        assert index >= 0
        map_tab.heatmap_pal_combo.setCurrentIndex(index)
        qapp.processEvents()

        assert map_tab._heatmap_item is not None
        assert map_tab._heatmap_item.scene() is map_tab.scene
        assert 'Blazehowl' in map_tab.heatmap_status_label.text()
        assert 'spawn areas' in map_tab.heatmap_status_label.text()
    finally:
        window.close()


def test_native_map_pin_popup_tracks_found_progress(qapp) -> None:
    window = MainWindow(schedule_update_check=False)
    try:
        map_tab = window.map_tab
        map_tab.progress_store.clear()
        location_id, marker = next(iter(map_tab._location_markers.items()))

        map_tab._on_marker_selected(marker.location_data, marker)

        assert map_tab.location_popup.isHidden() is False
        assert map_tab.location_popup.location is marker.location_data
        assert map_tab.location_popup.found_button.text() == 'Mark as found'

        map_tab.location_popup.found_button.click()

        assert map_tab.progress_store.is_found(location_id) is True
        assert marker.found is True
        assert map_tab.location_popup.found_button.text() == 'Marked as found'

        map_tab.location_popup.found_button.click()

        assert map_tab.progress_store.is_found(location_id) is False
        assert marker.found is False
    finally:
        window.map_tab.progress_store.clear()
        window.close()


def test_no_save_shortcut_or_prohibited_command_action(qapp) -> None:
    window = MainWindow(schedule_update_check=False)
    try:
        prohibited = {
            'save changes',
            'character transfer',
            'host swap',
            'slot injector',
            'convert saves',
            'cleanup',
        }
        actions = window.findChildren(QAction)
        action_text = {action.text().strip().lower() for action in actions if action.text()}
        assert not prohibited.intersection(action_text)
        assert all(action.shortcut() != QKeySequence.Save for action in actions)
    finally:
        window.close()


def test_update_controls_are_wired_without_loading_a_save(qapp) -> None:
    checker = _FakeUpdateChecker()
    window = MainWindow(
        update_checker=checker,
        schedule_update_check=False,
    )
    try:
        assert window.settings_tab.auto_updates_checkbox.isChecked() is True
        window.settings_tab.check_updates_button.click()
        assert checker.check_calls == 1
        assert window.settings_tab.check_updates_button.isEnabled() is False

        checker.is_checking = False
        checker.finished.emit()
        assert window.settings_tab.check_updates_button.isEnabled() is True

        window._manual_update_check = False
        checker.up_to_date.emit(ReleaseInfo(
            version=PRODUCT_VERSION,
            name=f'Version {PRODUCT_VERSION}',
            url=f'{RELEASES_URL}/tag/v{PRODUCT_VERSION}',
        ))
        assert 'up to date' in window.settings_tab.update_status_label.text().lower()
        assert window.update_button.isHidden() is True
    finally:
        window.close()


def test_game_data_validation_is_available_without_a_save(qapp) -> None:
    window = MainWindow(schedule_update_check=False)
    try:
        window.navigate('settings')
        assert GAME_DATA_VERSION in window.settings_tab.game_data_status_label.text()
        window.settings_tab.validate_data_button.click()
        assert window.settings_tab._data_validation_report is not None
        assert window.settings_tab._data_validation_report.is_valid is True
        assert 'is valid' in window.settings_tab.game_data_status_label.text().lower()
        assert '58 known icon paths' in window.settings_tab.game_data_status_label.text()
        assert window.settings_tab.validate_data_button.isEnabled() is True

        window.navigate('about')
        assert GAME_DATA_VERSION in window.about_tab.data_version_label.text()
    finally:
        window.close()
