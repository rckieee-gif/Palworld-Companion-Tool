from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from palworld_aio.ui.pal_assets import pal_pixmap


class PalSelectorDialog(QDialog):
    def __init__(self, pal_info: dict, parent: QWidget | None = None):
        super().__init__(parent)
        self.pal_info = pal_info
        self.selected_species: str | None = None
        self.setWindowTitle('Select a Pal')
        self.setMinimumSize(480, 620)

        layout = QVBoxLayout(self)
        self.search = QLineEdit()
        self.search.setPlaceholderText('Search by Pal name or internal ID')
        self.search.setClearButtonEnabled(True)
        layout.addWidget(self.search)

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
        self.list_widget.itemSelectionChanged.connect(self._selection_changed)
        self.list_widget.itemDoubleClicked.connect(lambda _item: self._accept_selection())
        self._populate()

    def _populate(self, *_args) -> None:
        needle = self.search.text().strip().lower()
        self.list_widget.clear()
        records = []
        for species, info in self.pal_info.items():
            name = str(info.get('name') or species)
            if needle and needle not in name.lower() and needle not in species.lower():
                continue
            records.append((name, species, info))
        records.sort(key=lambda record: (record[0].lower(), record[1].lower()))
        for name, species, info in records:
            power = info.get('combi_rank', '?')
            item = QListWidgetItem(f'{name}   |   Power {power}')
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
