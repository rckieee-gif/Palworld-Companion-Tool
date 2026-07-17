from __future__ import annotations

from PySide6.QtCore import QUrl, Qt
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app_info import (
    LICENSE_NAME,
    PRODUCT_NAME,
    PRODUCT_VERSION,
    UPSTREAM_REPOSITORY,
)
from i18n import t


class AboutTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(14)

        self.title_label = QLabel(PRODUCT_NAME)
        self.title_label.setObjectName('pageTitle')
        root.addWidget(self.title_label)
        self.version_label = QLabel()
        self.version_label.setObjectName('pageSubtitle')
        root.addWidget(self.version_label)

        body = QFrame()
        body.setObjectName('aboutPanel')
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(18, 18, 18, 18)
        body_layout.setSpacing(12)

        self.description_label = QLabel()
        self.description_label.setWordWrap(True)
        body_layout.addWidget(self.description_label)

        self.safety_label = QLabel()
        self.safety_label.setWordWrap(True)
        self.safety_label.setTextFormat(Qt.RichText)
        body_layout.addWidget(self.safety_label)

        self.attribution_label = QLabel()
        self.attribution_label.setWordWrap(True)
        body_layout.addWidget(self.attribution_label)

        self.rights_label = QLabel()
        self.rights_label.setWordWrap(True)
        body_layout.addWidget(self.rights_label)

        actions = QHBoxLayout()
        self.upstream_button = QPushButton()
        self.upstream_button.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl(UPSTREAM_REPOSITORY))
        )
        actions.addWidget(self.upstream_button)
        self.license_label = QLabel()
        self.license_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        actions.addWidget(self.license_label)
        actions.addStretch()
        body_layout.addLayout(actions)
        root.addWidget(body)
        root.addStretch()
        self.refresh_labels()

    def refresh_labels(self) -> None:
        self.version_label.setText(
            t('companion.about.version', default='Version {version}', version=PRODUCT_VERSION)
        )
        self.description_label.setText(t(
            'companion.about.description',
            default=(
                'A focused Palworld companion for read-only world maps, breeding '
                'planning, and game reference data.'
            ),
        ))
        self.safety_label.setText(t(
            'companion.about.safety',
            default=(
                '<b>Read-only guarantee:</b> loaded Palworld saves are immutable '
                'inputs. This application has no command that can overwrite them.'
            ),
        ))
        self.attribution_label.setText(t(
            'companion.about.attribution',
            default=(
                'This project is a streamlined derivative of PalworldSaveTools. '
                'It retains the original MIT license and attribution. The '
                'save-editing and server-administration features have been removed.'
            ),
        ))
        self.rights_label.setText(t(
            'companion.about.rights',
            default=(
                'Palworld names and assets belong to their respective owners. '
                'This project is not endorsed by Pocketpair.'
            ),
        ))
        self.upstream_button.setText(
            t('companion.about.upstream', default='Upstream project')
        )
        self.license_label.setText(
            t('companion.about.license', default='License: {license}', license=LICENSE_NAME)
        )
