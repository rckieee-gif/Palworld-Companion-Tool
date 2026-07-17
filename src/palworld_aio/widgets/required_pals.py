from collections.abc import Callable

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QCursor, QFontMetrics, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QListView,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from i18n import t


class RequiredPalsEditor(QWidget):
    addRequested = Signal()
    changed = Signal()
    MAX_PALS = 5

    def __init__(
        self,
        icon_loader: Callable[[str, int], QPixmap | None],
        parent=None,
    ):
        super().__init__(parent)
        self._icon_loader = icon_loader
        self._pal_info = {}
        self._species: list[str] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(6)
        self._title_label = QLabel()
        self._title_label.setStyleSheet('color: palette(text); font-size: 12px; font-weight: 600;')
        header.addWidget(self._title_label)
        self._count_label = QLabel()
        self._count_label.setStyleSheet('color: #64748b; font-size: 10px;')
        header.addWidget(self._count_label)
        header.addStretch()
        self._add_button = QPushButton()
        self._add_button.setFixedHeight(27)
        self._add_button.setCursor(QCursor(Qt.PointingHandCursor))
        self._add_button.setStyleSheet(
            'QPushButton { background: rgba(125,211,252,0.08); color: palette(link); '
            'border: 1px solid rgba(125,211,252,0.2); border-radius: 5px; '
            'padding: 3px 9px; font-size: 11px; font-weight: 600; }'
            'QPushButton:hover { background: rgba(125,211,252,0.15); color: #fff; }'
            'QPushButton:disabled { color: #475569; border-color: rgba(255,255,255,0.06); }'
        )
        self._add_button.clicked.connect(self.addRequested.emit)
        header.addWidget(self._add_button)
        layout.addLayout(header)

        self._list = QListWidget()
        self._list.setFlow(QListView.LeftToRight)
        self._list.setWrapping(False)
        self._list.setResizeMode(QListView.Adjust)
        self._list.setMovement(QListView.Static)
        self._list.setSelectionMode(QAbstractItemView.NoSelection)
        self._list.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        self._list.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._list.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._list.setFixedHeight(52)
        self._list.setStyleSheet(
            'QListWidget { background: transparent; border: none; outline: none; }'
            'QListWidget::item { background: rgba(30,41,52,0.72); '
            'border: 1px solid rgba(125,211,252,0.14); border-radius: 5px; margin: 1px; }'
        )
        layout.addWidget(self._list)
        self.refresh_labels()
        self._render()

    def required_species(self) -> tuple[str, ...]:
        return tuple(self._species)

    def set_pal_info(self, pal_info: dict):
        self._pal_info = pal_info or {}
        self._render()

    def add_species(self, species: str) -> bool:
        if not species or species in self._species or len(self._species) >= self.MAX_PALS:
            return False
        self._species.append(species)
        self._render()
        self.changed.emit()
        return True

    def remove_species(self, species: str):
        if species not in self._species:
            return
        self._species.remove(species)
        self._render()
        self.changed.emit()

    def clear(self):
        if not self._species:
            return
        self._species.clear()
        self._render()
        self.changed.emit()

    def refresh_labels(self):
        self._title_label.setText(t('breeding.required.title', default='Required Pals'))
        self._add_button.setText(t('breeding.required.add', default='+ Add'))
        self._add_button.setToolTip(t(
            'breeding.required.add_tooltip',
            default='Add a Pal that must appear in the route',
        ))
        self._update_count()

    def _update_count(self):
        self._count_label.setText(f'{len(self._species)}/{self.MAX_PALS}')
        self._add_button.setEnabled(len(self._species) < self.MAX_PALS)

    def _render(self):
        self._list.clear()
        for species in self._species:
            info = self._pal_info.get(species, {})
            name = info.get('name', species)
            item = QListWidgetItem()
            item.setSizeHint(QSize(154, 42))
            chip = QWidget()
            row = QHBoxLayout(chip)
            row.setContentsMargins(5, 3, 3, 3)
            row.setSpacing(5)

            icon_label = QLabel()
            icon_label.setFixedSize(30, 30)
            icon_label.setAlignment(Qt.AlignCenter)
            pixmap = self._icon_loader(info.get('icon', ''), 28)
            if pixmap and not pixmap.isNull():
                icon_label.setPixmap(pixmap)
            row.addWidget(icon_label)

            name_label = QLabel()
            name_label.setStyleSheet('color: palette(text); font-size: 11px; font-weight: 600;')
            name_label.setToolTip(name)
            name_label.setText(QFontMetrics(name_label.font()).elidedText(name, Qt.ElideRight, 83))
            row.addWidget(name_label, 1)

            remove_button = QToolButton()
            remove_button.setText('\u00d7')
            remove_button.setFixedSize(22, 22)
            remove_button.setCursor(QCursor(Qt.PointingHandCursor))
            remove_button.setToolTip(t(
                'breeding.required.remove',
                default='Remove {name}',
                name=name,
            ))
            remove_button.setStyleSheet(
                'QToolButton { background: transparent; color: palette(mid); border: none; '
                'font-size: 17px; font-weight: 600; }'
                'QToolButton:hover { color: #f87171; background: rgba(248,113,113,0.08); '
                'border-radius: 4px; }'
            )
            remove_button.clicked.connect(
                lambda _checked=False, value=species: self.remove_species(value)
            )
            row.addWidget(remove_button)
            self._list.addItem(item)
            self._list.setItemWidget(item, chip)
        self._list.setVisible(bool(self._species))
        self._update_count()
