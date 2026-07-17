from __future__ import annotations

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QLabel

from app_info import PRODUCT_VERSION, RELEASES_URL
from palworld_aio.ui.main_window import MainWindow
from palworld_aio.update_service import ReleaseInfo


EXPECTED_NAVIGATION = ('map', 'breeding', 'wiki', 'settings', 'about')
MAP_EMPTY_MESSAGE = (
    'Load a Palworld world save to view its map. This app opens saves '
    'in read-only mode and will never modify them.'
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
        assert window.stack.count() == 5
        assert window.stack.currentWidget() is window.breeding_tab
    finally:
        window.close()


def test_only_allowed_navigation_entries_are_registered(qapp) -> None:
    window = MainWindow(schedule_update_check=False)
    try:
        labels = tuple(button.text().lower() for button in window._nav_buttons.values())
        assert labels == EXPECTED_NAVIGATION
        assert set(window._pages) == set(EXPECTED_NAVIGATION)
    finally:
        window.close()


def test_breeding_and_wiki_work_without_world_data(qapp) -> None:
    window = MainWindow(schedule_update_check=False)
    try:
        window.navigate('breeding')
        assert len(window.breeding_tab.pal_info) > 250
        assert window.breeding_tab.tabs.count() == 3

        window.navigate('wiki')
        wiki = window.wiki_tab.wiki_tab
        assert len(wiki._pages) == 8
        assert wiki._pages['pals']._loaded is True
        assert wiki._pages['pals']._all_data
    finally:
        window.close()


def test_map_shows_read_only_empty_state(qapp) -> None:
    window = MainWindow(schedule_update_check=False)
    try:
        window.navigate('map')
        assert window.map_tab.content_stack.currentWidget() is window.map_tab.empty_page
        texts = [label.text() for label in window.map_tab.findChildren(QLabel)]
        assert MAP_EMPTY_MESSAGE in texts
    finally:
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
