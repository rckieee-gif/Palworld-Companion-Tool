from __future__ import annotations

from PySide6.QtCore import Qt

from palworld_aio.ui.pal_selector import PalSelectorDialog


PAL_INFO = {
    'Alpha_Internal': {'name': 'Alpha', 'combi_rank': 100},
    'Beta_Internal': {'name': 'Beta', 'combi_rank': 1500},
    'Gamma_Internal': {'name': 'Gamma', 'combi_rank': 500},
    'Mystery_Internal': {'name': 'Mystery'},
}


def _listed_species(dialog: PalSelectorDialog) -> list[str]:
    return [
        str(dialog.list_widget.item(index).data(Qt.UserRole))
        for index in range(dialog.list_widget.count())
    ]


def test_pal_selector_searches_exact_breeding_power(qapp) -> None:
    dialog = PalSelectorDialog(PAL_INFO)

    dialog.search.setText('1500')
    assert _listed_species(dialog) == ['Beta_Internal']

    dialog.search.setText('power:500')
    assert _listed_species(dialog) == ['Gamma_Internal']

    dialog.search.setText('breeding power 100')
    assert _listed_species(dialog) == ['Alpha_Internal']

    dialog.search.setText('50')
    assert _listed_species(dialog) == []
    dialog.close()


def test_pal_selector_keeps_name_and_internal_id_search(qapp) -> None:
    dialog = PalSelectorDialog(PAL_INFO)

    dialog.search.setText('beta')
    assert _listed_species(dialog) == ['Beta_Internal']

    dialog.search.setText('gamma_internal')
    assert _listed_species(dialog) == ['Gamma_Internal']
    dialog.close()


def test_pal_selector_sorts_by_breeding_power_in_both_directions(qapp) -> None:
    dialog = PalSelectorDialog(PAL_INFO)

    dialog.sort_order.setCurrentIndex(
        dialog.sort_order.findData('power_asc')
    )
    assert _listed_species(dialog) == [
        'Alpha_Internal',
        'Gamma_Internal',
        'Beta_Internal',
        'Mystery_Internal',
    ]

    dialog.sort_order.setCurrentIndex(
        dialog.sort_order.findData('power_desc')
    )
    assert _listed_species(dialog) == [
        'Beta_Internal',
        'Gamma_Internal',
        'Alpha_Internal',
        'Mystery_Internal',
    ]
    assert 'Breeding power 1500' in dialog.list_widget.item(0).text()
    dialog.close()
