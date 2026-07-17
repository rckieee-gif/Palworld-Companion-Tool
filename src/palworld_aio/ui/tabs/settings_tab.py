from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QFrame,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from i18n import get_config_value, get_language, set_config_value, t


LANGUAGES = {
    'English': 'en_US',
    'Chinese (Simplified)': 'zh_CN',
    'Russian': 'ru_RU',
    'French': 'fr_FR',
    'Spanish': 'es_ES',
    'German': 'de_DE',
    'Japanese': 'ja_JP',
    'Korean': 'ko_KR',
}


class SettingsTab(QWidget):
    theme_changed = Signal(str)
    language_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(14)

        self.title_label = QLabel()
        self.title_label.setObjectName('pageTitle')
        root.addWidget(self.title_label)
        self.subtitle_label = QLabel()
        self.subtitle_label.setObjectName('pageSubtitle')
        root.addWidget(self.subtitle_label)

        form_host = QFrame()
        form_host.setObjectName('settingsPanel')
        form = QFormLayout(form_host)
        form.setContentsMargins(18, 18, 18, 18)
        form.setHorizontalSpacing(24)
        form.setVerticalSpacing(14)

        self.theme_combo = QComboBox()
        self.theme_combo.addItem('Dark', 'dark')
        self.theme_combo.addItem('Light', 'light')
        current_theme = str(get_config_value('theme', 'dark'))
        self.theme_combo.setCurrentIndex(max(0, self.theme_combo.findData(current_theme)))
        self.theme_label = QLabel()
        form.addRow(self.theme_label, self.theme_combo)

        self.language_combo = QComboBox()
        for label, code in LANGUAGES.items():
            self.language_combo.addItem(label, code)
        current_language = get_language()
        self.language_combo.setCurrentIndex(
            max(0, self.language_combo.findData(current_language))
        )
        self.language_label = QLabel()
        form.addRow(self.language_label, self.language_combo)
        root.addWidget(form_host)
        root.addStretch()

        self.theme_combo.currentIndexChanged.connect(self._on_theme_changed)
        self.language_combo.currentIndexChanged.connect(self._on_language_changed)
        self.refresh_labels()

    def _on_theme_changed(self, _index: int) -> None:
        theme = str(self.theme_combo.currentData())
        set_config_value('theme', theme)
        self.theme_changed.emit(theme)

    def _on_language_changed(self, _index: int) -> None:
        language = str(self.language_combo.currentData())
        self.language_changed.emit(language)

    def refresh_labels(self) -> None:
        self.title_label.setText(t('companion.nav.settings', default='Settings'))
        self.subtitle_label.setText(t(
            'companion.settings.subtitle',
            default='Appearance and language preferences are stored locally.',
        ))
        self.theme_label.setText(t('companion.settings.theme', default='Theme'))
        self.language_label.setText(t('companion.settings.language', default='Language'))
        self.theme_combo.setItemText(
            self.theme_combo.findData('dark'),
            t('companion.settings.dark', default='Dark'),
        )
        self.theme_combo.setItemText(
            self.theme_combo.findData('light'),
            t('companion.settings.light', default='Light'),
        )
