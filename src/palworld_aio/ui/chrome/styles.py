from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QWidget

from boot_paths import GUI_DIR


LOGGER = logging.getLogger(__name__)


class ThemeManager:
    _theme_content: dict[str, str] = {}

    @classmethod
    def load_qss_content(cls, theme: str = 'dark') -> str:
        selected = theme if theme in ('dark', 'light') else 'dark'
        if selected in cls._theme_content:
            return cls._theme_content[selected]
        path = Path(GUI_DIR) / f'{selected}mode.qss'
        try:
            content = path.read_text(encoding='utf-8')
        except OSError as exc:
            LOGGER.error('Could not load %s theme from %s: %s', selected, path, exc)
            content = ''
        cls._theme_content[selected] = content
        return content

    @classmethod
    def apply_global(cls, theme: str = 'dark') -> bool:
        app = QApplication.instance()
        if app is None:
            return False
        selected = theme if theme in ('dark', 'light') else 'dark'
        app.setPalette(cls._palette(selected))
        content = cls.load_qss_content(selected)
        app.setStyleSheet(content)
        app.setProperty('companionTheme', selected)
        return bool(content)

    @staticmethod
    def _palette(theme: str) -> QPalette:
        colors = (
            {
                QPalette.Window: '#181b1e',
                QPalette.WindowText: '#e8eaec',
                QPalette.Base: '#131619',
                QPalette.AlternateBase: '#202428',
                QPalette.ToolTipBase: '#f4f6f7',
                QPalette.ToolTipText: '#16191b',
                QPalette.Text: '#e8eaec',
                QPalette.Button: '#2a3035',
                QPalette.ButtonText: '#edf0f2',
                QPalette.BrightText: '#ffffff',
                QPalette.Link: '#64d3c1',
                QPalette.Highlight: '#24545d',
                QPalette.HighlightedText: '#ffffff',
                QPalette.Light: '#343b41',
                QPalette.Midlight: '#41484f',
                QPalette.Mid: '#9aa2aa',
                QPalette.Dark: '#111315',
                QPalette.PlaceholderText: '#7f8991',
            }
            if theme == 'dark'
            else {
                QPalette.Window: '#f3f5f6',
                QPalette.WindowText: '#252a2e',
                QPalette.Base: '#ffffff',
                QPalette.AlternateBase: '#edf1f2',
                QPalette.ToolTipBase: '#20262a',
                QPalette.ToolTipText: '#ffffff',
                QPalette.Text: '#252a2e',
                QPalette.Button: '#ffffff',
                QPalette.ButtonText: '#252a2e',
                QPalette.BrightText: '#000000',
                QPalette.Link: '#177e72',
                QPalette.Highlight: '#cde9ed',
                QPalette.HighlightedText: '#16363b',
                QPalette.Light: '#ffffff',
                QPalette.Midlight: '#d0d6da',
                QPalette.Mid: '#68727a',
                QPalette.Dark: '#aeb7bd',
                QPalette.PlaceholderText: '#7d878e',
            }
        )
        palette = QPalette()
        for role, color in colors.items():
            palette.setColor(role, QColor(color))
        return palette

    @classmethod
    def apply_to_widget(cls, widget: QWidget, theme: str = 'dark') -> bool:
        content = cls.load_qss_content(theme)
        widget.setStyleSheet(content)
        return bool(content)

    @classmethod
    def load_styles(cls, widget: QWidget) -> bool:
        return cls.apply_to_widget(widget)
