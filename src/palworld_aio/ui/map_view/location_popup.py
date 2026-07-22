from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStyle,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from palworld_aio.map.locations import MapLocation
from palworld_aio.ui.map_view.map_markers import location_pin_pixmap


class LocationPopup(QFrame):
    found_toggled = Signal(str, bool)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._location: MapLocation | None = None
        self.setObjectName('mapLocationPopup')
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setFixedWidth(300)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(24)
        shadow.setOffset(0, 7)
        shadow.setColor(QColor(0, 0, 0, 105))
        self.setGraphicsEffect(shadow)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 14)
        layout.setSpacing(10)

        header = QHBoxLayout()
        header.setSpacing(6)
        self.category_label = QLabel()
        self.category_label.setObjectName('mapPopupBadge')
        header.addWidget(self.category_label, 0, Qt.AlignLeft)
        header.addStretch()
        self.close_button = QToolButton()
        self.close_button.setObjectName('mapPopupClose')
        self.close_button.setIcon(
            self.style().standardIcon(QStyle.SP_TitleBarCloseButton)
        )
        self.close_button.setToolTip('Close marker details')
        self.close_button.setFixedSize(24, 24)
        self.close_button.clicked.connect(self.hide)
        header.addWidget(self.close_button)
        layout.addLayout(header)

        identity = QHBoxLayout()
        identity.setSpacing(10)
        self.icon_label = QLabel()
        self.icon_label.setObjectName('mapPopupIcon')
        self.icon_label.setAlignment(Qt.AlignCenter)
        self.icon_label.setFixedSize(48, 48)
        identity.addWidget(self.icon_label)
        self.title_label = QLabel()
        self.title_label.setObjectName('mapPopupTitle')
        self.title_label.setWordWrap(True)
        identity.addWidget(self.title_label, 1)
        layout.addLayout(identity)

        divider = QFrame()
        divider.setObjectName('mapPopupDivider')
        divider.setFrameShape(QFrame.HLine)
        layout.addWidget(divider)

        self.description_label = QLabel()
        self.description_label.setObjectName('mapPopupDescription')
        self.description_label.setWordWrap(True)
        layout.addWidget(self.description_label)

        coordinates = QHBoxLayout()
        coordinates.setSpacing(6)
        coordinate_caption = QLabel('In-game')
        coordinate_caption.setObjectName('mapPopupCoordinateCaption')
        coordinates.addWidget(coordinate_caption)
        self.coordinates_label = QLabel()
        self.coordinates_label.setObjectName('mapPopupCoordinates')
        self.coordinates_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        coordinates.addWidget(self.coordinates_label)
        coordinates.addStretch()
        layout.addLayout(coordinates)

        self.found_button = QPushButton('Mark as found')
        self.found_button.setObjectName('mapFoundButton')
        self.found_button.setCheckable(True)
        self.found_button.clicked.connect(self._emit_found_state)
        layout.addWidget(self.found_button)
        self.hide()

    @property
    def location(self) -> MapLocation | None:
        return self._location

    def set_location(self, location: MapLocation, found: bool) -> None:
        self._location = location
        self.category_label.setText(location.category.upper())
        self.title_label.setText(location.name)
        self.description_label.setText(
            location.description or self._default_description(location)
        )
        self.coordinates_label.setText(
            f'{location.coordinates[0]}, {location.coordinates[1]}'
        )
        self.found_button.setVisible(location.source == 'bundled')
        self.set_found(found)
        self.adjustSize()

    def set_found(self, found: bool) -> None:
        source = self._location.source if self._location else 'bundled'
        self.icon_label.setPixmap(location_pin_pixmap(30, source, found))
        self.found_button.setChecked(found)
        self.found_button.setText(
            'Marked as found' if found else 'Mark as found'
        )
        self.found_button.setProperty('found', found)
        self.found_button.style().unpolish(self.found_button)
        self.found_button.style().polish(self.found_button)

    def _emit_found_state(self, found: bool) -> None:
        if self._location is None:
            return
        self.set_found(found)
        self.found_toggled.emit(self._location.location_id, found)

    @staticmethod
    def _default_description(location: MapLocation) -> str:
        if location.source == 'local':
            return 'Personal map pin stored on this device.'
        return (
            f'Fast-travel point at {location.name}. '
            'Coordinates come from bundled game data.'
        )
