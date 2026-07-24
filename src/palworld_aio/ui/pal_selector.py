from __future__ import annotations

import re

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from palworld_aio.ui.pal_assets import pal_pixmap


_POWER_QUERY = re.compile(
    r'(?:(?:breeding\s+)?power\s*[:=]?\s*)?(\d+)',
    re.IGNORECASE,
)


def _breeding_power(info: dict) -> int | None:
    value = info.get('combi_rank')
    if isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _matches_query(
    query: str,
    name: str,
    species: str,
    power: int | None,
) -> bool:
    if not query:
        return True
    power_match = _POWER_QUERY.fullmatch(query)
    if power_match is not None:
        return power == int(power_match.group(1))
    normalized = query.casefold()
    return normalized in name.casefold() or normalized in species.casefold()


class PalSelectorDialog(QDialog):
    def __init__(self, pal_info: dict, parent: QWidget | None = None):
        super().__init__(parent)
        self.pal_info = pal_info
        self.selected_species: str | None = None
        self.setWindowTitle('Select a Pal')
        self.setMinimumSize(480, 620)

        layout = QVBoxLayout(self)
        search_row = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText('Search by name, ID, or breeding power')
        self.search.setClearButtonEnabled(True)
        search_row.addWidget(self.search, 1)
        self.sort_order = QComboBox()
        self.sort_order.setObjectName('palSelectorSort')
        self.sort_order.setAccessibleName('Sort Pals')
        self.sort_order.addItem('Name (A-Z)', 'name')
        self.sort_order.addItem('Breeding power (low-high)', 'power_asc')
        self.sort_order.addItem('Breeding power (high-low)', 'power_desc')
        search_row.addWidget(self.sort_order)
        layout.addLayout(search_row)

        self.count_label = QLabel()
        self.count_label.setObjectName('pageSubtitle')
        layout.addWidget(self.count_label)

        self.list_widget = QListWidget()
        self.list_widget.setIconSize(QSize(38, 38))
        self.list_widget.setUniformItemSizes(True)
        layout.addWidget(self.list_widget, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.Cancel | QDialogButtonBox.Ok)
        buttons.button(QDialogButtonBox.Ok).setEnabled(False)
        buttons.accepted.connect(self._accept_selection)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.buttons = buttons

        self.search.textChanged.connect(self._populate)
        self.sort_order.currentIndexChanged.connect(self._populate)
        self.list_widget.itemSelectionChanged.connect(self._selection_changed)
        self.list_widget.itemDoubleClicked.connect(lambda _item: self._accept_selection())
        self._populate()

    def _populate(self, *_args) -> None:
        query = self.search.text().strip()
        self.list_widget.clear()
        records = []
        for species, info in self.pal_info.items():
            name = str(info.get('name') or species)
            power = _breeding_power(info)
            if not _matches_query(query, name, species, power):
                continue
            records.append((name, species, power))
        sort_mode = self.sort_order.currentData()
        if sort_mode == 'power_asc':
            records.sort(key=lambda record: (
                record[2] is None,
                record[2] if record[2] is not None else 0,
                record[0].casefold(),
                record[1].casefold(),
            ))
        elif sort_mode == 'power_desc':
            records.sort(key=lambda record: (
                record[2] is None,
                -(record[2] if record[2] is not None else 0),
                record[0].casefold(),
                record[1].casefold(),
            ))
        else:
            records.sort(key=lambda record: (
                record[0].casefold(),
                record[1].casefold(),
            ))
        for name, species, power in records:
            power_label = str(power) if power is not None else '?'
            item = QListWidgetItem(
                f'{name}   |   Breeding power {power_label}'
            )
            item.setData(Qt.UserRole, species)
            item.setToolTip(species)
            pixmap = pal_pixmap(species, self.pal_info, 38)
            if pixmap and not pixmap.isNull():
                item.setIcon(QIcon(pixmap))
            self.list_widget.addItem(item)
        self.count_label.setText(f'{len(records)} Pals')
        self._selection_changed()

    def _selection_changed(self) -> None:
        self.buttons.button(QDialogButtonBox.Ok).setEnabled(
            self.list_widget.currentItem() is not None
        )

    def _accept_selection(self) -> None:
        item = self.list_widget.currentItem()
        if item is None:
            return
        self.selected_species = str(item.data(Qt.UserRole))
        self.accept()


def select_pal(pal_info: dict, parent: QWidget | None = None) -> str | None:
    dialog = PalSelectorDialog(pal_info, parent)
    if dialog.exec() == QDialog.Accepted:
        return dialog.selected_species
    return None
