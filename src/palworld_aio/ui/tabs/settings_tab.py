from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
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
    check_updates_requested = Signal()

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

        updates_widget = QWidget()
        updates_layout = QVBoxLayout(updates_widget)
        updates_layout.setContentsMargins(0, 0, 0, 0)
        updates_layout.setSpacing(8)
        self.auto_updates_checkbox = QCheckBox()
        self.auto_updates_checkbox.setChecked(
            bool(get_config_value('check_updates_automatically', True))
        )
        updates_layout.addWidget(self.auto_updates_checkbox)
        update_actions = QHBoxLayout()
        update_actions.setContentsMargins(0, 0, 0, 0)
        self.check_updates_button = QPushButton()
        self.check_updates_button.setObjectName('checkUpdatesButton')
        update_actions.addWidget(self.check_updates_button)
        update_actions.addStretch()
        updates_layout.addLayout(update_actions)
        self.update_status_label = QLabel()
        self.update_status_label.setObjectName('pageSubtitle')
        self.update_status_label.setWordWrap(True)
        updates_layout.addWidget(self.update_status_label)
        self.updates_label = QLabel()
        form.addRow(self.updates_label, updates_widget)
        root.addWidget(form_host)
        root.addStretch()

        self.theme_combo.currentIndexChanged.connect(self._on_theme_changed)
        self.language_combo.currentIndexChanged.connect(self._on_language_changed)
        self.auto_updates_checkbox.toggled.connect(self._on_auto_updates_changed)
        self.check_updates_button.clicked.connect(self.check_updates_requested.emit)
        self.refresh_labels()

    def _on_theme_changed(self, _index: int) -> None:
        theme = str(self.theme_combo.currentData())
        set_config_value('theme', theme)
        self.theme_changed.emit(theme)

    def _on_language_changed(self, _index: int) -> None:
        language = str(self.language_combo.currentData())
        self.language_changed.emit(language)

    def _on_auto_updates_changed(self, checked: bool) -> None:
        set_config_value('check_updates_automatically', checked)

    def set_update_status(self, text: str, *, checking: bool = False) -> None:
        self.update_status_label.setText(text)
        self.check_updates_button.setEnabled(not checking)

    def refresh_labels(self) -> None:
        self.title_label.setText(t('companion.nav.settings', default='Settings'))
        self.subtitle_label.setText(t(
            'companion.settings.subtitle',
            default='Appearance, language, and update preferences are stored locally.',
        ))
        self.theme_label.setText(t('companion.settings.theme', default='Theme'))
        self.language_label.setText(t('companion.settings.language', default='Language'))
        self.updates_label.setText(t(
            'companion.settings.updates',
            default='Updates',
        ))
        self.auto_updates_checkbox.setText(t(
            'companion.settings.updates_auto',
            default='Check automatically at startup',
        ))
        self.check_updates_button.setText(t(
            'companion.settings.updates_check',
            default='Check now',
        ))
        if not self.update_status_label.text():
            self.update_status_label.setText(t(
                'companion.settings.updates_help',
                default='Checks the latest stable release on GitHub once per day.',
            ))
        self.theme_combo.setItemText(
            self.theme_combo.findData('dark'),
            t('companion.settings.dark', default='Dark'),
        )
        self.theme_combo.setItemText(
            self.theme_combo.findData('light'),
            t('companion.settings.light', default='Light'),
        )
