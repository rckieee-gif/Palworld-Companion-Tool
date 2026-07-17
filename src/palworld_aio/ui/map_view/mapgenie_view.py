from PySide6.QtCore import QUrl, Qt
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QStyle,
    QVBoxLayout,
    QWidget,
)

from i18n import t
from palworld_aio.map.mapgenie import (
    MAPGENIE_PALPAGOS_URL,
    format_map_coordinates,
    format_selected_pin,
    is_allowed_map_url,
)

try:
    from PySide6.QtWebEngineCore import QWebEnginePage
    from PySide6.QtWebEngineWidgets import QWebEngineView
except ImportError:
    QWebEnginePage = None
    QWebEngineView = None


if QWebEnginePage is not None:
    class _MapGeniePage(QWebEnginePage):
        """Keep the embedded main frame on MapGenie-owned pages."""

        def acceptNavigationRequest(self, url, navigation_type, is_main_frame):
            if not is_main_frame or is_allowed_map_url(url.toString()):
                return True
            QDesktopServices.openUrl(url)
            return False
else:
    _MapGeniePage = None


class MapGenieView(QWidget):
    """Live MapGenie browser with a local save-pin coordinate bridge."""

    def __init__(self, parent=None, auto_load=False):
        super().__init__(parent)
        self._selected_name = None
        self._selected_coords = None
        self._load_requested = False
        self.web_view = None
        self._setup_ui()
        if auto_load:
            self.ensure_loaded()

    @property
    def web_engine_available(self):
        return QWebEngineView is not None

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        toolbar = QFrame()
        toolbar.setObjectName('mapGenieToolbar')
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(8, 6, 8, 6)
        toolbar_layout.setSpacing(5)

        self.back_button = self._icon_button(
            QStyle.SP_ArrowBack,
            t('mapgenie.back', default='Back'),
        )
        self.forward_button = self._icon_button(
            QStyle.SP_ArrowForward,
            t('mapgenie.forward', default='Forward'),
        )
        self.reload_button = self._icon_button(
            QStyle.SP_BrowserReload,
            t('mapgenie.reload', default='Reload'),
        )
        toolbar_layout.addWidget(self.back_button)
        toolbar_layout.addWidget(self.forward_button)
        toolbar_layout.addWidget(self.reload_button)

        self.pin_label = QLabel(t('mapgenie.no_pin', default='No save pin selected'))
        self.pin_label.setObjectName('mapGeniePin')
        self.pin_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.pin_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.pin_label.setMinimumWidth(80)
        toolbar_layout.addWidget(self.pin_label, 1)

        self.copy_button = self._icon_button(
            QStyle.SP_FileDialogDetailedView,
            t('mapgenie.copy_coords', default='Copy Coordinates'),
        )
        self.copy_button.setEnabled(False)
        self.copy_button.clicked.connect(self.copy_selected_coordinates)
        toolbar_layout.addWidget(self.copy_button)

        self.external_button = self._icon_button(
            QStyle.SP_DirLinkIcon,
            t('mapgenie.open_browser', default='Open in Browser'),
        )
        self.external_button.clicked.connect(self.open_in_browser)
        toolbar_layout.addWidget(self.external_button)
        layout.addWidget(toolbar)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setObjectName('mapGenieProgress')
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(2)
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        if QWebEngineView is not None:
            self.web_view = QWebEngineView(self)
            self.web_view.setPage(_MapGeniePage(self.web_view))
            self.web_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            self.web_view.loadStarted.connect(self._on_load_started)
            self.web_view.loadProgress.connect(self._on_load_progress)
            self.web_view.loadFinished.connect(self._on_load_finished)
            self.web_view.urlChanged.connect(self._update_navigation)
            self.back_button.clicked.connect(self.web_view.back)
            self.forward_button.clicked.connect(self.web_view.forward)
            self.reload_button.clicked.connect(self.web_view.reload)
            layout.addWidget(self.web_view, 1)
            self._update_navigation()
        else:
            self.back_button.setEnabled(False)
            self.forward_button.setEnabled(False)
            self.reload_button.setEnabled(False)
            layout.addWidget(self._build_fallback(), 1)

    def _icon_button(self, standard_icon, tooltip):
        button = QPushButton()
        button.setIcon(self.style().standardIcon(standard_icon))
        button.setToolTip(tooltip)
        button.setFixedSize(34, 30)
        return button

    def _build_fallback(self):
        panel = QWidget()
        panel.setObjectName('mapGenieFallback')
        panel_layout = QVBoxLayout(panel)
        panel_layout.setAlignment(Qt.AlignCenter)
        self.fallback_status = QLabel(t(
            'mapgenie.webview_unavailable',
            default='The embedded map is unavailable in this source environment.',
        ))
        self.fallback_status.setObjectName('mapGenieFallbackStatus')
        self.fallback_status.setAlignment(Qt.AlignCenter)
        self.fallback_status.setWordWrap(True)
        panel_layout.addWidget(self.fallback_status)
        self.fallback_open_button = QPushButton(t('mapgenie.open_browser', default='Open in Browser'))
        self.fallback_open_button.setFixedWidth(160)
        self.fallback_open_button.clicked.connect(self.open_in_browser)
        panel_layout.addWidget(self.fallback_open_button, alignment=Qt.AlignCenter)
        return panel

    def ensure_loaded(self):
        if self.web_view is None or self._load_requested:
            return
        self._load_requested = True
        self.web_view.setUrl(QUrl(MAPGENIE_PALPAGOS_URL))

    def set_selected_location(self, name, coords):
        self._selected_name = str(name)
        self._selected_coords = (coords[0], coords[1])
        self.pin_label.setText(format_selected_pin(self._selected_name, self._selected_coords))
        self.pin_label.setToolTip(self.pin_label.text())
        self.copy_button.setEnabled(True)

    def clear_selected_location(self):
        self._selected_name = None
        self._selected_coords = None
        self.pin_label.setText(t('mapgenie.no_pin', default='No save pin selected'))
        self.pin_label.setToolTip('')
        self.copy_button.setEnabled(False)

    def copy_selected_coordinates(self):
        if self._selected_coords is None:
            return
        QApplication.clipboard().setText(format_map_coordinates(self._selected_coords))

    def open_in_browser(self):
        QDesktopServices.openUrl(QUrl(MAPGENIE_PALPAGOS_URL))

    def refresh_labels(self):
        self.back_button.setToolTip(t('mapgenie.back', default='Back'))
        self.forward_button.setToolTip(t('mapgenie.forward', default='Forward'))
        self.reload_button.setToolTip(t('mapgenie.reload', default='Reload'))
        self.copy_button.setToolTip(t('mapgenie.copy_coords', default='Copy Coordinates'))
        self.external_button.setToolTip(t('mapgenie.open_browser', default='Open in Browser'))
        if hasattr(self, 'fallback_status'):
            self.fallback_status.setText(t(
                'mapgenie.webview_unavailable',
                default='The embedded map is unavailable in this source environment.',
            ))
            self.fallback_open_button.setText(t('mapgenie.open_browser', default='Open in Browser'))
        if self._selected_coords is None:
            self.pin_label.setText(t('mapgenie.no_pin', default='No save pin selected'))
        else:
            self.pin_label.setText(format_selected_pin(self._selected_name, self._selected_coords))

    def _on_load_started(self):
        self.progress.setValue(0)
        self.progress.setVisible(True)

    def _on_load_progress(self, progress):
        self.progress.setValue(progress)

    def _on_load_finished(self, _ok):
        self.progress.setVisible(False)
        self._update_navigation()

    def _update_navigation(self, _url=None):
        if self.web_view is None:
            return
        history = self.web_view.history()
        self.back_button.setEnabled(history.canGoBack())
        self.forward_button.setEnabled(history.canGoForward())
