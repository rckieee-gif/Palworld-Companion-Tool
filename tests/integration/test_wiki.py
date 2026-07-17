from __future__ import annotations

from PySide6.QtWidgets import QFrame

from palworld_aio.ui.pal_assets import pal_pixmap
from palworld_aio.ui.tabs.docs.wiki_tab import WikiTab


def test_all_wiki_categories_load_without_a_save(qapp) -> None:
    wiki = WikiTab()
    try:
        wiki.resize(900, 650)
        wiki.show()
        expected = {
            'pals',
            'items',
            'buildings',
            'active_skills',
            'passive_skills',
            'technologies',
            'elements',
            'work_suitability',
        }
        assert set(wiki._pages) == expected
        for category, page in wiki._pages.items():
            wiki._switch_category(category)
            qapp.processEvents()
            assert page._loaded is True
            assert page._all_data, category
            assert page._detail.horizontalScrollBar().maximum() == 0
            assert page._detail.widget().width() <= page._detail.viewport().width()
    finally:
        wiki.close()


def test_wiki_search_filters_pal_names(qapp) -> None:
    wiki = WikiTab()
    try:
        page = wiki._pages['pals']
        page._search.setText('Lamball')
        assert page._filtered_indices
        assert all(
            'lamball' in str(page._all_data[index].get('name', '')).lower()
            for index in page._filtered_indices
        )
    finally:
        wiki.close()


def test_wiki_empty_state_and_reset_controls(qapp) -> None:
    wiki = WikiTab()
    try:
        page = wiki._pages['pals']
        total = len(page._all_data)

        page._search.setText('no-pal-has-this-name')
        assert page._filtered_indices == []
        assert page._results_stack.currentIndex() == 1
        assert page._result_count.text() == '0 results'
        assert page._reset_button.isEnabled() is True

        page.reset_controls()
        assert page._search.text() == ''
        assert len(page._filtered_indices) == total
        assert page._results_stack.currentIndex() == 0
        assert page._reset_button.isEnabled() is False
    finally:
        wiki.close()


def test_pal_detail_includes_melee_attack(qapp) -> None:
    wiki = WikiTab()
    try:
        page = wiki._pages['pals']
        lamball = next(
            pal
            for pal in page._all_data
            if pal.get('asset') == 'SheepBall'
        )
        page._detail.show_item(lamball)

        stat_labels = {
            card.property('wikiStatLabel')
            for card in page._detail.findChildren(QFrame)
            if card.objectName() == 'wikiStatCard'
        }
        assert 'Melee Atk' in stat_labels
        assert lamball['stats']['melee_attack'] == 70
    finally:
        wiki.close()


def test_missing_pal_asset_fails_gracefully(qapp) -> None:
    placeholder = pal_pixmap('DefinitelyMissingPal', {}, 64)
    assert placeholder is not None
    assert placeholder.isNull() is False
