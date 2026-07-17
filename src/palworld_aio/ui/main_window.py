from __future__ import annotations

from collections.abc import Callable
import os
from pathlib import Path

from PySide6.QtCore import QObject, QThread, QTimer, QUrl, Qt, Signal, Slot
from PySide6.QtGui import (
    QAction,
    QCloseEvent,
    QDesktopServices,
    QDragEnterEvent,
    QDropEvent,
    QIcon,
    QKeySequence,
)
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QStatusBar,
    QStyle,
    QVBoxLayout,
    QWidget,
)

from app_info import PRODUCT_NAME, PRODUCT_VERSION, RELEASES_URL
from common import ICON_PATH, get_preferred_save_path, set_last_save_path
from i18n import get_config_value, set_config_value, set_language, t
from palworld_aio.read_only_world import (
    ReadOnlyWorldData,
    WorldLoadError,
    load_read_only_world,
)
from palworld_aio.update_service import (
    GitHubReleaseChecker,
    ReleaseInfo,
    current_utc_timestamp,
    should_check_automatically,
)
from palworld_aio.ui.chrome.styles import ThemeManager
from palworld_aio.ui.tabs.about_tab import AboutTab
from palworld_aio.ui.tabs.breeding_tab import BreedingTab
from palworld_aio.ui.tabs.docs_tab import DocsTab
from palworld_aio.ui.tabs.map_tab import MapTab
from palworld_aio.ui.tabs.settings_tab import SettingsTab


class _WorldLoadWorker(QObject):
    loaded = Signal(object)
    failed = Signal(str)
    finished = Signal()

    def __init__(
        self,
        path: str,
        loader: Callable[[str], ReadOnlyWorldData],
    ):
        super().__init__()
        self.path = path
        self.loader = loader

    @Slot()
    def run(self) -> None:
        try:
            self.loaded.emit(self.loader(self.path))
        except (WorldLoadError, OSError) as exc:
            self.failed.emit(str(exc))
        except Exception as exc:
            self.failed.emit(f'The world could not be loaded: {exc}')
        finally:
            self.finished.emit()


class MainWindow(QMainWindow):
    NAVIGATION = ('map', 'breeding', 'wiki', 'settings', 'about')

    def __init__(
        self,
        *,
        world_loader: Callable[[str], ReadOnlyWorldData] = load_read_only_world,
        update_checker: GitHubReleaseChecker | None = None,
        schedule_update_check: bool = True,
    ):
        super().__init__()
        self._world_loader = world_loader
        self._update_checker = update_checker or GitHubReleaseChecker(self)
        self._world: ReadOnlyWorldData | None = None
        self._latest_release: ReleaseInfo | None = None
        self._manual_update_check = False
        self._load_thread: QThread | None = None
        self._load_worker: _WorldLoadWorker | None = None
        self._nav_buttons: dict[str, QPushButton] = {}
        self._pages: dict[str, QWidget] = {}
        self._setup_ui()
        self._setup_shortcuts()
        self._connect_signals()
        self._apply_theme(str(get_config_value('theme', 'dark')))
        self.navigate('breeding')
        self.setAcceptDrops(True)
        if schedule_update_check:
            QTimer.singleShot(1_500, self._check_updates_at_startup)

    @property
    def navigation_ids(self) -> tuple[str, ...]:
        return tuple(self._nav_buttons)

    @property
    def loaded_world(self) -> ReadOnlyWorldData | None:
        return self._world

    def _setup_ui(self) -> None:
        self.setObjectName('companionMainWindow')
        self.setWindowTitle(f'{PRODUCT_NAME} {PRODUCT_VERSION}')
        self.setMinimumSize(1100, 720)
        self.resize(1460, 860)
        if os.path.exists(ICON_PATH):
            self.setWindowIcon(QIcon(ICON_PATH))

        central = QWidget()
        central.setObjectName('central')
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        sidebar = QFrame()
        sidebar.setObjectName('companionSidebar')
        sidebar.setFixedWidth(190)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(12, 18, 12, 12)
        sidebar_layout.setSpacing(5)
        self.brand_label = QLabel(PRODUCT_NAME)
        self.brand_label.setObjectName('brandName')
        self.brand_label.setWordWrap(True)
        sidebar_layout.addWidget(self.brand_label)
        self.tagline_label = QLabel()
        self.tagline_label.setObjectName('brandTagline')
        sidebar_layout.addWidget(self.tagline_label)
        sidebar_layout.addSpacing(18)

        nav_specs = (
            ('map', QStyle.SP_DriveNetIcon),
            ('breeding', QStyle.SP_FileDialogContentsView),
            ('wiki', QStyle.SP_DialogHelpButton),
            ('settings', QStyle.SP_FileDialogDetailedView),
            ('about', QStyle.SP_MessageBoxInformation),
        )
        for page_id, icon_id in nav_specs:
            button = QPushButton()
            button.setObjectName(f'nav_{page_id}')
            button.setProperty('navButton', True)
            button.setCheckable(True)
            button.setAutoExclusive(True)
            button.setIcon(self.style().standardIcon(icon_id))
            button.setMinimumHeight(42)
            button.clicked.connect(lambda _checked=False, key=page_id: self.navigate(key))
            sidebar_layout.addWidget(button)
            self._nav_buttons[page_id] = button
        sidebar_layout.addStretch()
        self.privacy_label = QLabel()
        self.privacy_label.setObjectName('brandTagline')
        self.privacy_label.setWordWrap(True)
        sidebar_layout.addWidget(self.privacy_label)
        root.addWidget(sidebar)

        workspace = QWidget()
        workspace_layout = QVBoxLayout(workspace)
        workspace_layout.setContentsMargins(0, 0, 0, 0)
        workspace_layout.setSpacing(0)
        header = QFrame()
        header.setObjectName('companionHeader')
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(18, 10, 18, 10)
        self.page_title = QLabel()
        self.page_title.setObjectName('pageTitle')
        header_layout.addWidget(self.page_title)
        header_layout.addStretch()
        self.update_button = QPushButton()
        self.update_button.setObjectName('availableUpdateButton')
        self.update_button.setToolTip('Open the latest GitHub release')
        self.update_button.setVisible(False)
        self.update_button.clicked.connect(self._open_latest_release)
        header_layout.addWidget(self.update_button)
        self.world_status = QLabel('No world loaded')
        self.world_status.setObjectName('brandTagline')
        self.world_status.setTextInteractionFlags(Qt.TextSelectableByMouse)
        header_layout.addWidget(self.world_status)
        workspace_layout.addWidget(header)

        self.stack = QStackedWidget()
        self.map_tab = MapTab()
        self.breeding_tab = BreedingTab()
        self.wiki_tab = DocsTab()
        self.settings_tab = SettingsTab()
        self.about_tab = AboutTab()
        for page_id, page in (
            ('map', self.map_tab),
            ('breeding', self.breeding_tab),
            ('wiki', self.wiki_tab),
            ('settings', self.settings_tab),
            ('about', self.about_tab),
        ):
            self._pages[page_id] = page
            self.stack.addWidget(page)
        workspace_layout.addWidget(self.stack, 1)
        root.addWidget(workspace, 1)

        self.status_bar = QStatusBar()
        self.status_bar.setSizeGripEnabled(False)
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage('Ready')
        self.refresh_labels()

    def _setup_shortcuts(self) -> None:
        open_action = QAction(self)
        open_action.setShortcut(QKeySequence.Open)
        open_action.triggered.connect(self.choose_world)
        self.addAction(open_action)
        for index, page_id in enumerate(self.NAVIGATION, start=1):
            action = QAction(self)
            action.setShortcut(QKeySequence(f'Ctrl+{index}'))
            action.triggered.connect(lambda _checked=False, key=page_id: self.navigate(key))
            self.addAction(action)

    def _connect_signals(self) -> None:
        self.map_tab.load_requested.connect(self.choose_world)
        self.map_tab.close_requested.connect(self.close_world)
        self.map_tab.status_message.connect(self.status_bar.showMessage)
        self.settings_tab.theme_changed.connect(self._apply_theme)
        self.settings_tab.language_changed.connect(self._change_language)
        self.settings_tab.check_updates_requested.connect(
            lambda: self.check_for_updates(manual=True)
        )
        self.about_tab.check_updates_requested.connect(
            lambda: self.check_for_updates(manual=True)
        )
        self._update_checker.update_available.connect(self._on_update_available)
        self._update_checker.up_to_date.connect(self._on_up_to_date)
        self._update_checker.failed.connect(self._on_update_check_failed)
        self._update_checker.finished.connect(self._on_update_check_finished)

    def navigate(self, page_id: str) -> None:
        page = self._pages.get(page_id)
        if page is None:
            return
        self.stack.setCurrentWidget(page)
        self._nav_buttons[page_id].setChecked(True)
        titles = {
            'map': t('companion.nav.map', default='Map'),
            'breeding': t('companion.title.breeding', default='Breeding Calculator'),
            'wiki': t('companion.title.wiki', default='Palworld Wiki'),
            'settings': t('companion.nav.settings', default='Settings'),
            'about': t('companion.nav.about', default='About'),
        }
        self.page_title.setText(titles[page_id])
        refresh = getattr(page, 'refresh', None)
        if callable(refresh):
            refresh()

    def choose_world(self) -> None:
        initial_path = get_preferred_save_path()
        path, _selected_filter = QFileDialog.getOpenFileName(
            self,
            'Open Palworld world (read-only)',
            initial_path,
            'Palworld world (Level.sav);;Save files (*.sav)',
        )
        if path:
            self.load_world_path(path)

    def load_world_path(self, path: str) -> None:
        if self._load_thread is not None and self._load_thread.isRunning():
            self.status_bar.showMessage('A world is already being loaded.')
            return
        source = Path(path).expanduser()
        if source.name.lower() != 'level.sav':
            self._show_load_error('The selected file must be named Level.sav.')
            return

        self.status_bar.showMessage('Opening world in read-only mode...')
        self.map_tab.load_button.setEnabled(False)
        self._load_thread = QThread(self)
        self._load_worker = _WorldLoadWorker(str(source), self._world_loader)
        self._load_worker.moveToThread(self._load_thread)
        self._load_thread.started.connect(self._load_worker.run)
        self._load_worker.loaded.connect(self._on_world_loaded)
        self._load_worker.failed.connect(self._show_load_error)
        self._load_worker.finished.connect(self._load_thread.quit)
        self._load_worker.finished.connect(self._load_worker.deleteLater)
        self._load_thread.finished.connect(self._on_load_finished)
        self._load_thread.finished.connect(self._load_thread.deleteLater)
        self._load_thread.start()

    def _on_world_loaded(self, world: ReadOnlyWorldData) -> None:
        self._world = world
        self.map_tab.set_world(world)
        self.world_status.setText(f'{world.display_name} | READ-ONLY')
        set_last_save_path(str(world.source_path.parent))
        self.navigate('map')

    def _show_load_error(self, message: str) -> None:
        self.status_bar.showMessage('World load failed.')
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Critical)
        box.setWindowTitle('Could not open world')
        box.setText(message)
        box.exec()

    def _on_load_finished(self) -> None:
        self.map_tab.load_button.setEnabled(True)
        self._load_worker = None
        self._load_thread = None

    def close_world(self) -> None:
        self._world = None
        self.map_tab.set_world(None)
        self.world_status.setText('No world loaded')
        self.status_bar.showMessage('World closed. No save data was changed.')

    def _check_updates_at_startup(self) -> None:
        if not bool(get_config_value('check_updates_automatically', True)):
            return
        last_checked = get_config_value('last_update_check_utc')
        if should_check_automatically(last_checked):
            self.check_for_updates(manual=False)

    def check_for_updates(self, *, manual: bool) -> None:
        if self._update_checker.is_checking:
            self._manual_update_check = self._manual_update_check or manual
            if manual:
                self.status_bar.showMessage(
                    t('companion.update.checking', default='Checking for updates...')
                )
            return
        self._manual_update_check = manual
        if not self._update_checker.check():
            return
        message = t('companion.update.checking', default='Checking for updates...')
        self.settings_tab.set_update_status(message, checking=True)
        self.about_tab.set_update_status(message, checking=True)
        self.status_bar.showMessage(message)

    def _record_successful_update_check(self) -> None:
        set_config_value('last_update_check_utc', current_utc_timestamp())

    def _on_update_available(self, release: ReleaseInfo) -> None:
        self._latest_release = release
        self._record_successful_update_check()
        message = t(
            'companion.update.available',
            default='Version {version} is available.',
            version=release.version,
        )
        self.settings_tab.set_update_status(message)
        self.about_tab.set_update_status(message)
        self.update_button.setText(t(
            'companion.update.header',
            default='Update v{version}',
            version=release.version,
        ))
        self.update_button.setVisible(True)
        self.status_bar.showMessage(message)

        last_notified = str(get_config_value('last_notified_version', ''))
        if self._manual_update_check or last_notified != release.version:
            set_config_value('last_notified_version', release.version)
            self._show_update_dialog(release)

    def _on_up_to_date(self, release: ReleaseInfo) -> None:
        self._record_successful_update_check()
        self.update_button.setVisible(False)
        message = t(
            'companion.update.current',
            default='Version {version} is up to date.',
            version=PRODUCT_VERSION,
        )
        self.settings_tab.set_update_status(message)
        self.about_tab.set_update_status(message)
        self.status_bar.showMessage(message, 5_000)
        if self._manual_update_check:
            QMessageBox.information(
                self,
                t('companion.update.title', default='Software update'),
                message,
            )

    def _on_update_check_failed(self, message: str) -> None:
        friendly = t(
            'companion.update.failed',
            default='Could not check for updates. Check your internet connection and try again.',
        )
        self.settings_tab.set_update_status(friendly)
        self.about_tab.set_update_status(friendly)
        self.status_bar.showMessage(friendly, 7_000)
        if self._manual_update_check:
            QMessageBox.warning(
                self,
                t('companion.update.title', default='Software update'),
                f'{friendly}\n\n{message}',
            )

    def _on_update_check_finished(self) -> None:
        self.settings_tab.check_updates_button.setEnabled(True)
        self.about_tab.check_updates_button.setEnabled(True)
        self._manual_update_check = False

    def _show_update_dialog(self, release: ReleaseInfo) -> None:
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Information)
        box.setWindowTitle(t('companion.update.title', default='Software update'))
        box.setText(t(
            'companion.update.dialog',
            default='Palworld Companion Tools {version} is available.',
            version=release.version,
        ))
        box.setInformativeText(t(
            'companion.update.dialog_help',
            default=(
                'Open the GitHub release page to view the notes and download the '
                'new Windows installer. The app never sends or uploads save data.'
            ),
        ))
        open_button = box.addButton(
            t('companion.update.open', default='Open release'),
            QMessageBox.ButtonRole.AcceptRole,
        )
        box.addButton(
            t('companion.update.later', default='Later'),
            QMessageBox.ButtonRole.RejectRole,
        )
        box.exec()
        if box.clickedButton() is open_button:
            QDesktopServices.openUrl(QUrl(release.url))

    def _open_latest_release(self) -> None:
        url = self._latest_release.url if self._latest_release else RELEASES_URL
        QDesktopServices.openUrl(QUrl(url))

    def _apply_theme(self, theme: str) -> None:
        ThemeManager.apply_global(theme)

    def _change_language(self, language: str) -> None:
        set_language(language)
        self.refresh_labels()
        for page in self._pages.values():
            refresh_labels = getattr(page, 'refresh_labels', None)
            if callable(refresh_labels):
                refresh_labels()
        self.status_bar.showMessage('Language preference updated.')

    def refresh_labels(self) -> None:
        labels = {
            'map': t('companion.nav.map', default='Map'),
            'breeding': t('companion.nav.breeding', default='Breeding'),
            'wiki': t('companion.nav.wiki', default='Wiki'),
            'settings': t('companion.nav.settings', default='Settings'),
            'about': t('companion.nav.about', default='About'),
        }
        for page_id, label in labels.items():
            button = self._nav_buttons.get(page_id)
            if button is not None:
                button.setText(label)
        self.tagline_label.setText(
            t('companion.tagline', default='Map, breed, discover')
        )
        self.privacy_label.setText(
            t(
                'companion.privacy_short',
                default='Saves stay on this device.\nWorld loading is read-only.',
            )
        )
        if self._latest_release is not None:
            self.update_button.setText(t(
                'companion.update.header',
                default='Update v{version}',
                version=self._latest_release.version,
            ))
        current = next(
            (key for key, page in self._pages.items() if page is self.stack.currentWidget()),
            'breeding',
        )
        self.navigate(current)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        urls = event.mimeData().urls()
        if len(urls) == 1 and Path(urls[0].toLocalFile()).name.lower() == 'level.sav':
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        urls = event.mimeData().urls()
        if len(urls) == 1:
            self.load_world_path(urls[0].toLocalFile())
            event.acceptProposedAction()

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._load_thread is not None and self._load_thread.isRunning():
            QMessageBox.information(
                self,
                'World is loading',
                'Please wait for the read-only world load to finish before closing.',
            )
            event.ignore()
            return
        event.accept()
