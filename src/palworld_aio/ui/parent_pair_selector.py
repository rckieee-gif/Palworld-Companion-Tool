from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QLineEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from palworld_aio.ui.pal_assets import pal_pixmap


@dataclass(frozen=True, slots=True)
class ParentPairOption:
    parent_a: str
    parent_b: str
    name_a: str
    name_b: str
    combined_power: int
    is_special: bool
    owned_count: int

    @property
    def availability(self) -> str:
        if self.owned_count == 2:
            return 'Both available'
        if self.owned_count == 1:
            return '1 available'
        return 'Need both'


def build_parent_pair_options(
    pairs: Iterable[tuple[str, str]],
    pal_info: dict,
    owned_species: set[str],
    unique_pairs: set[tuple[str, str]],
    blocked_species: set[str] | frozenset[str] = frozenset(),
) -> tuple[ParentPairOption, ...]:
    options: list[ParentPairOption] = []
    for parent_a, parent_b in pairs:
        if parent_a in blocked_species or parent_b in blocked_species:
            continue
        name_a = str(pal_info.get(parent_a, {}).get('name') or parent_a)
        name_b = str(pal_info.get(parent_b, {}).get('name') or parent_b)
        power_a = int(pal_info.get(parent_a, {}).get('combi_rank', 0) or 0)
        power_b = int(pal_info.get(parent_b, {}).get('combi_rank', 0) or 0)
        options.append(ParentPairOption(
            parent_a=parent_a,
            parent_b=parent_b,
            name_a=name_a,
            name_b=name_b,
            combined_power=power_a + power_b,
            is_special=tuple(sorted((parent_a, parent_b))) in unique_pairs,
            owned_count=int(parent_a in owned_species) + int(parent_b in owned_species),
        ))
    return tuple(sorted(
        options,
        key=lambda option: (
            -option.owned_count,
            not option.is_special,
            option.name_a.casefold(),
            option.name_b.casefold(),
        ),
    ))


class ParentPairSelectorDialog(QDialog):
    def __init__(
        self,
        child_species: str,
        options: tuple[ParentPairOption, ...],
        pal_info: dict,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.child_species = child_species
        self.options = options
        self.pal_info = pal_info
        self.selected_pair: tuple[str, str] | None = None
        child_name = str(
            pal_info.get(child_species, {}).get('name') or child_species
        )
        self.setWindowTitle(f'Choose parents for {child_name}')
        self.setMinimumSize(760, 520)

        layout = QVBoxLayout(self)
        prompt = QLabel(
            f'Select a breeding pair to expand the {child_name} branch.'
        )
        prompt.setWordWrap(True)
        layout.addWidget(prompt)

        self.search = QLineEdit()
        self.search.setPlaceholderText('Filter parent names or internal IDs')
        self.search.setClearButtonEnabled(True)
        layout.addWidget(self.search)

        self.count_label = QLabel()
        self.count_label.setObjectName('pageSubtitle')
        layout.addWidget(self.count_label)

        self.results = QTreeWidget()
        self.results.setHeaderLabels([
            'Parent A',
            'Parent B',
            'Pair type',
            'Availability',
            'Combined power',
        ])
        self.results.setRootIsDecorated(False)
        self.results.setUniformRowHeights(True)
        self.results.setIconSize(QSize(32, 32))
        layout.addWidget(self.results, 1)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.Cancel | QDialogButtonBox.Ok
        )
        add_button = self.buttons.button(QDialogButtonBox.Ok)
        add_button.setText('Add branch')
        add_button.setEnabled(False)
        self.buttons.accepted.connect(self._accept_selection)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

        self.search.textChanged.connect(self._populate)
        self.results.itemSelectionChanged.connect(self._selection_changed)
        self.results.itemDoubleClicked.connect(
            lambda _item, _column: self._accept_selection()
        )
        self._populate()

    def _populate(self, *_args) -> None:
        needle = self.search.text().strip().casefold()
        self.results.clear()
        visible = []
        for option in self.options:
            haystack = ' '.join((
                option.name_a,
                option.name_b,
                option.parent_a,
                option.parent_b,
                'special' if option.is_special else 'power formula',
            )).casefold()
            if needle and needle not in haystack:
                continue
            visible.append(option)

        for option in visible:
            item = QTreeWidgetItem([
                option.name_a,
                option.name_b,
                'Special' if option.is_special else 'Power formula',
                option.availability,
                str(option.combined_power),
            ])
            item.setData(0, Qt.UserRole, (option.parent_a, option.parent_b))
            icon_a = pal_pixmap(option.parent_a, self.pal_info, 32)
            if icon_a:
                item.setIcon(0, QIcon(icon_a))
            icon_b = pal_pixmap(option.parent_b, self.pal_info, 32)
            if icon_b:
                item.setIcon(1, QIcon(icon_b))
            self.results.addTopLevelItem(item)

        self.count_label.setText(
            f'{len(visible)} parent pairs'
            if visible
            else 'No cycle-safe parent pairs match this search.'
        )
        for column in range(5):
            self.results.resizeColumnToContents(column)
        self._selection_changed()

    def _selection_changed(self) -> None:
        self.buttons.button(QDialogButtonBox.Ok).setEnabled(
            self.results.currentItem() is not None
        )

    def _accept_selection(self) -> None:
        item = self.results.currentItem()
        if item is None:
            return
        parent_a, parent_b = item.data(0, Qt.UserRole)
        self.selected_pair = str(parent_a), str(parent_b)
        self.accept()


def select_parent_pair(
    child_species: str,
    pairs: Iterable[tuple[str, str]],
    pal_info: dict,
    owned_species: set[str],
    unique_pairs: set[tuple[str, str]],
    blocked_species: set[str] | frozenset[str],
    parent: QWidget | None = None,
    options: tuple[ParentPairOption, ...] | None = None,
) -> tuple[str, str] | None:
    if options is None:
        options = build_parent_pair_options(
            pairs,
            pal_info,
            owned_species,
            unique_pairs,
            blocked_species,
        )
    dialog = ParentPairSelectorDialog(child_species, options, pal_info, parent)
    if dialog.exec() == QDialog.Accepted:
        return dialog.selected_pair
    return None
