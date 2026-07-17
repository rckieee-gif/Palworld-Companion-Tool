from __future__ import annotations

from palworld_aio.ui.pal_assets import pal_pixmap
from palworld_aio.ui.tabs.docs.wiki_tab import WikiTab


def test_all_wiki_categories_load_without_a_save(qapp) -> None:
    wiki = WikiTab()
    try:
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
            assert page._loaded is True
            assert page._all_data, category
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


def test_missing_pal_asset_fails_gracefully(qapp) -> None:
    placeholder = pal_pixmap('DefinitelyMissingPal', {}, 64)
    assert placeholder is not None
    assert placeholder.isNull() is False
