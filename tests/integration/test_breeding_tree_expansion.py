from __future__ import annotations

from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QLabel
from PySide6.QtTest import QTest

from palworld_aio.breeding_analyzer import (
    BreedingAnalyzer,
    BreedingPath,
    BreedingTreeNode,
)
from palworld_aio.ui.tabs import breeding_tab as breeding_tab_module
from palworld_aio.ui.tabs.breeding_tab import BreedingTab
from palworld_aio.widgets.breeding_tree import BreedingTreeWidget


def _tree_widget() -> tuple[BreedingTreeWidget, BreedingTreeNode]:
    expandable_leaf = BreedingTreeNode('E')
    root = BreedingTreeNode(
        'T',
        (BreedingTreeNode('A'), expandable_leaf),
    )
    path = BreedingPath('T', True, False, 1, (), root)
    widget = BreedingTreeWidget(
        path,
        {
            species: {'name': species, 'icon': ''}
            for species in ('A', 'B', 'D', 'E', 'T')
        },
        {'A'},
        lambda _path, _size: None,
        expandable_species={'E'},
    )
    return widget, expandable_leaf


def test_orange_plus_badge_requests_only_its_leaf(qapp) -> None:
    widget, expandable_leaf = _tree_widget()
    widget.resize(widget.sizeHint())
    widget.show()
    qapp.processEvents()
    requested = []
    widget.expansion_requested.connect(requested.append)

    leaf_rect = widget._rects_by_node[id(expandable_leaf)]
    QTest.mouseClick(
        widget,
        Qt.LeftButton,
        pos=QPoint(round(leaf_rect.center().x()), round(leaf_rect.bottom())),
    )

    assert requested == [expandable_leaf]
    widget.close()


def test_selected_parent_pair_expands_tree_and_updates_steps(qapp, monkeypatch) -> None:
    tab = BreedingTab()
    tab.analyzer = BreedingAnalyzer({
        'pal_info': {
            species: {'name': species}
            for species in ('A', 'B', 'D', 'E', 'T')
        },
        'child_to_parents_formula': {
            'E': [{'parent_a': 'B', 'parent_b': 'D'}],
            'T': [{'parent_a': 'A', 'parent_b': 'E'}],
        },
    })
    tab.pal_info = tab.analyzer.pal_info
    tab._unique_pairs = set()
    widget, expandable_leaf = _tree_widget()
    widget.tree_changed.connect(tab._path_tree_changed)
    tab._path_steps_label = QLabel()
    monkeypatch.setattr(
        breeding_tab_module,
        'select_parent_pair',
        lambda **_kwargs: ('B', 'D'),
    )

    tab._expand_path_leaf(widget, expandable_leaf)

    assert widget.root is not None
    assert widget.root.parents[1].parents == (
        BreedingTreeNode('B'),
        BreedingTreeNode('D'),
    )
    assert tab.path_status.text() == 'Expanded path: 2 generations, 2 breeding steps.'
    assert tab._path_steps_label.text() == '1. B + D = E\n2. A + E = T'
    tab.close()


def test_self_only_leaf_explains_why_it_cannot_expand(qapp, monkeypatch) -> None:
    tab = BreedingTab()
    tab.analyzer = BreedingAnalyzer({
        'pal_info': {
            'A': {'name': 'Alpha'},
            'B': {'name': 'Bastigor'},
            'T': {'name': 'Target'},
        },
        'unique_combos': [
            {'parent_a': 'B', 'parent_b': 'B', 'child': 'B'},
        ],
    })
    tab.pal_info = tab.analyzer.pal_info
    tab._unique_pairs = {tab.analyzer.pair_key('B', 'B')}
    leaf = BreedingTreeNode('B')
    path = BreedingPath(
        'T',
        True,
        False,
        1,
        (),
        BreedingTreeNode('T', (BreedingTreeNode('A'), leaf)),
    )
    widget = BreedingTreeWidget(
        path,
        tab.pal_info,
        {'A'},
        lambda _path, _size: None,
        expandable_species={'B'},
    )
    messages = []
    monkeypatch.setattr(
        breeding_tab_module.QMessageBox,
        'information',
        lambda _parent, title, message: messages.append((title, message)),
    )

    tab._expand_path_leaf(widget, leaf)

    assert messages[0][0] == 'No breeding path'
    assert 'can only be bred from two Bastigor parents' in messages[0][1]
    assert widget.root.parents[1].is_leaf is True
    tab.close()
