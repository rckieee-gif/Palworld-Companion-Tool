from __future__ import annotations

from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QLabel

from palworld_aio.ui.main_window import MainWindow


EXPECTED_NAVIGATION = ('map', 'breeding', 'wiki', 'settings', 'about')
MAP_EMPTY_MESSAGE = (
    'Load a Palworld world save to view its map. This app opens saves '
    'in read-only mode and will never modify them.'
)


def test_app_starts_without_a_save(qapp) -> None:
    window = MainWindow()
    try:
        assert window.loaded_world is None
        assert window.navigation_ids == EXPECTED_NAVIGATION
        assert window.stack.count() == 5
        assert window.stack.currentWidget() is window.breeding_tab
    finally:
        window.close()


def test_only_allowed_navigation_entries_are_registered(qapp) -> None:
    window = MainWindow()
    try:
        labels = tuple(button.text().lower() for button in window._nav_buttons.values())
        assert labels == EXPECTED_NAVIGATION
        assert set(window._pages) == set(EXPECTED_NAVIGATION)
    finally:
        window.close()


def test_breeding_and_wiki_work_without_world_data(qapp) -> None:
    window = MainWindow()
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
    window = MainWindow()
    try:
        window.navigate('map')
        assert window.map_tab.content_stack.currentWidget() is window.map_tab.empty_page
        texts = [label.text() for label in window.map_tab.findChildren(QLabel)]
        assert MAP_EMPTY_MESSAGE in texts
    finally:
        window.close()


def test_no_save_shortcut_or_prohibited_command_action(qapp) -> None:
    window = MainWindow()
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
