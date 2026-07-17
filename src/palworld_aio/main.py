from __future__ import annotations

import os
import sys
import traceback

os.environ.setdefault('QT_LOGGING_RULES', '*=false')
os.environ.setdefault('QT_DEBUG_PLUGINS', '0')

from PySide6.QtCore import QTimer
from PySide6.QtGui import QFont, QFontDatabase, QIcon
from PySide6.QtWidgets import QApplication, QMessageBox

from app_info import PRODUCT_NAME, PRODUCT_VERSION
from common import ICON_PATH, get_base_directory
from i18n import init_language
from resource_resolver import resource_path

from palworld_aio.ui.main_window import MainWindow


def _install_font() -> None:
    font_path = resource_path(get_base_directory(), 'HackNerdFont-Regular.ttf')
    if os.path.exists(font_path):
        had_system_fonts = bool(QFontDatabase.families())
        font_id = QFontDatabase.addApplicationFont(font_path)
        if not had_system_fonts and font_id >= 0:
            families = QFontDatabase.applicationFontFamilies(font_id)
            app = QApplication.instance()
            if families and app is not None:
                app.setFont(QFont(families[0], 10))


def _show_unhandled_error(exc_type, exc_value, exc_traceback) -> None:
    details = ''.join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    box = QMessageBox()
    box.setIcon(QMessageBox.Critical)
    box.setWindowTitle(f'{PRODUCT_NAME} - Error')
    box.setText('The application encountered an unexpected error.')
    box.setDetailedText(details)
    box.exec()


def run_aio(argv: list[str] | None = None) -> int:
    args = list(sys.argv if argv is None else argv)
    init_language('en_US')

    app = QApplication.instance() or QApplication(args)
    app.setApplicationName(PRODUCT_NAME)
    app.setApplicationVersion(PRODUCT_VERSION)
    app.setOrganizationName('Palworld Companion Tools')
    app.setStyle('Fusion')
    _install_font()

    if os.path.exists(ICON_PATH):
        app.setWindowIcon(QIcon(ICON_PATH))

    sys.excepthook = _show_unhandled_error
    window = MainWindow()
    window.show()

    file_arg = next(
        (arg for arg in args[1:] if not arg.startswith('-')),
        None,
    )
    if file_arg:
        QTimer.singleShot(0, lambda: window.load_world_path(file_arg))

    return app.exec()


if __name__ == '__main__':
    raise SystemExit(run_aio())
