from __future__ import annotations

from collections import defaultdict
from html import escape
from pathlib import Path

import palworld_coord
from PySide6.QtCore import QPointF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QCursor, QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QCompleter,
    QFrame,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QHeaderView,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QStyle,
    QTabWidget,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from common import get_base_directory
from palworld_aio.game_data import GameDataError
from palworld_aio.map import annotations
from palworld_aio.map.annotations import AnnotationStore
from palworld_aio.map.locations import (
    MapLocation,
    load_fast_travel_locations,
    location_from_annotation,
)
from palworld_aio.map.progress import MapProgressStore
from palworld_aio.map.spawns import (
    PalSpawnRepository,
    PalSpawnSpecies,
    SpawnTimeFilter,
)
from palworld_aio.read_only_world import (
    BaseMarkerData,
    PlayerMarkerData,
    ReadOnlyWorldData,
)
from palworld_aio.ui.map_view.map_items import (
    BaseRadiusRing,
    ExclusionZoneItem,
    PolygonExclusionZoneItem,
)
from palworld_aio.ui.map_view.location_popup import LocationPopup
from palworld_aio.ui.map_view.map_markers import (
    BaseMarker,
    LocationMarker,
    PlayerMarker,
    location_pin_pixmap,
)
from palworld_aio.ui.map_view.map_view import MapGraphicsView
from palworld_aio.ui.map_view.spawn_heatmap import (
    SpawnHeatmapItem,
    render_spawn_heatmap,
)
from resource_resolver import get_user_config_dir, resource_path


_MAP_CONFIG = {
    'marker': {
        'type': 'icon',
        'dot': {
            'size': 24,
            'color': [255, 0, 0],
            'border_width': 3,
            'border_color': [180, 0, 0],
            'size_min': 24,
            'size_max': 24,
            'dynamic_sizing': False,
            'dynamic_sizing_formula': 'sqrt',
        },
        'icon': {
            'size_min': 32,
            'size_max': 64,
            'base_size': 48,
            'dynamic_sizing': True,
            'dynamic_sizing_formula': 'sqrt',
        },
    },
    'glow': {
        'enabled': True,
        'color': [59, 142, 208],
        'selected_alpha_min': 80,
        'selected_alpha_max': 180,
        'animation_speed': 8,
        'hover_alpha': 80,
        'radius_multiplier': 1.5,
    },
    'zoom': {
        'factor': 1.15,
        'min': 1.0,
        'max': 30.0,
        'double_click_target': 12.0,
        'animation_speed': 0.2,
        'animation_fps': 60,
    },
}


class MapTab(QWidget):
    load_requested = Signal()
    close_requested = Signal()
    status_message = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.world: ReadOnlyWorldData | None = None
        self.current_map = 'world'
        self._guild_filter: str | None = None
        self._location_markers: dict[str, LocationMarker] = {}
        self._base_markers: dict[str, BaseMarker] = {}
        self._player_markers: dict[str, PlayerMarker] = {}
        self._radius_items: list[BaseRadiusRing] = []
        self._annotation_items: list = []
        self._heatmap_item: SpawnHeatmapItem | None = None
        self._map_image_loaded = False
        self._popup_marker: LocationMarker | None = None
        try:
            self.annotation_store = AnnotationStore()
            self._annotation_error = ''
        except ValueError as exc:
            self.annotation_store = AnnotationStore.__new__(AnnotationStore)
            self.annotation_store.path = (
                Path(get_user_config_dir()) / 'map_annotations.json'
            )
            self.annotation_store._annotations = []
            self._annotation_error = str(exc)
        try:
            self.progress_store = MapProgressStore()
            self._progress_error = ''
        except ValueError as exc:
            self.progress_store = MapProgressStore.__new__(MapProgressStore)
            self.progress_store.path = (
                Path(get_user_config_dir()) / 'map_progress.json'
            )
            self.progress_store._found_location_ids = set()
            self._progress_error = str(exc)
        try:
            self._bundled_locations = load_fast_travel_locations()
            self._location_error = ''
        except GameDataError as exc:
            self._bundled_locations = ()
            self._location_error = str(exc)
        try:
            self._spawn_repository = PalSpawnRepository.from_game_data()
            self._spawn_error = ''
        except GameDataError as exc:
            self._spawn_repository = None
            self._spawn_error = str(exc)
        self._setup_ui()
        self._connect_signals()
        self._load_map_image('world')
        self._refresh_visible_data()

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        toolbar = QFrame()
        toolbar.setObjectName('mapToolbar')
        toolbar_layout = QVBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(10, 7, 10, 7)
        toolbar_layout.setSpacing(6)
        primary_row = QHBoxLayout()
        primary_row.setContentsMargins(0, 0, 0, 0)
        primary_row.setSpacing(8)

        self.load_button = QPushButton('Load world')
        self.load_button.setIcon(self.style().standardIcon(QStyle.SP_DialogOpenButton))
        self.load_button.clicked.connect(self.load_requested.emit)
        primary_row.addWidget(self.load_button)

        self.close_button = QToolButton()
        self.close_button.setIcon(self.style().standardIcon(QStyle.SP_DialogCloseButton))
        self.close_button.setToolTip('Close world')
        self.close_button.setFixedSize(34, 30)
        self.close_button.setEnabled(False)
        self.close_button.clicked.connect(self.close_requested.emit)
        primary_row.addWidget(self.close_button)

        primary_row.addSpacing(8)
        native_label = QLabel('Native map')
        native_label.setObjectName('mapSourceLabel')
        primary_row.addWidget(native_label)

        self.local_controls = QWidget()
        local_controls_layout = QHBoxLayout(self.local_controls)
        local_controls_layout.setContentsMargins(8, 0, 0, 0)
        local_controls_layout.setSpacing(7)
        self.map_type_group = QButtonGroup(self)
        self.map_type_group.setExclusive(True)
        self.world_button = self._segment_button('World', True)
        self.tree_button = self._segment_button('Tree', False)
        self.map_type_group.addButton(self.world_button, 0)
        self.map_type_group.addButton(self.tree_button, 1)
        local_controls_layout.addWidget(self.world_button)
        local_controls_layout.addWidget(self.tree_button)

        self.show_locations = QCheckBox('Locations')
        self.show_locations.setChecked(True)
        self.show_bases = QCheckBox('Bases')
        self.show_bases.setChecked(True)
        self.show_players = QCheckBox('Players')
        self.show_players.setChecked(True)
        self.show_radii = QCheckBox('Rings')
        self.show_radii.setChecked(True)
        self.show_annotations = QCheckBox('Annotations')
        self.show_annotations.setChecked(True)
        for toggle in (
            self.show_locations,
            self.show_bases,
            self.show_players,
            self.show_radii,
            self.show_annotations,
        ):
            local_controls_layout.addWidget(toggle)

        self.annotation_button = QToolButton()
        self.annotation_button.setIcon(
            QIcon(resource_path(get_base_directory(), 'zones.webp'))
        )
        self.annotation_button.setIconSize(QSize(20, 20))
        self.annotation_button.setToolTip('Map annotations')
        self.annotation_button.setPopupMode(QToolButton.InstantPopup)
        self.annotation_button.setMenu(self._create_annotation_menu())
        if self._annotation_error:
            self.annotation_button.setToolTip(self._annotation_error)
        local_controls_layout.addWidget(self.annotation_button)

        self.reset_button = QToolButton()
        self.reset_button.setIcon(self.style().standardIcon(QStyle.SP_BrowserReload))
        self.reset_button.setToolTip('Reset map view')
        self.reset_button.setFixedSize(34, 30)
        local_controls_layout.addWidget(self.reset_button)
        local_controls_layout.addStretch()
        primary_row.addStretch()

        self.warning_label = QLabel()
        self.warning_label.setObjectName('mapWarning')
        initial_warning = ' | '.join(filter(None, (
            self._annotation_error,
            self._progress_error,
            self._location_error,
            self._spawn_error,
        )))
        self.warning_label.setVisible(bool(initial_warning))
        self.warning_label.setText(initial_warning)
        self.warning_label.setMaximumWidth(420)
        primary_row.addWidget(self.warning_label)

        self.read_only_label = QLabel('READ-ONLY')
        self.read_only_label.setObjectName('readOnlyBadge')
        self.read_only_label.setVisible(False)
        primary_row.addWidget(self.read_only_label)
        toolbar_layout.addLayout(primary_row)
        toolbar_layout.addWidget(self.local_controls)

        self.heatmap_controls = QFrame()
        self.heatmap_controls.setObjectName('mapHeatmapBar')
        heatmap_layout = QHBoxLayout(self.heatmap_controls)
        heatmap_layout.setContentsMargins(8, 0, 0, 0)
        heatmap_layout.setSpacing(8)
        self.show_heatmap = QCheckBox('Pal heatmap')
        self.show_heatmap.setObjectName('mapHeatmapToggle')
        self.show_heatmap.setEnabled(self._spawn_repository is not None)
        heatmap_layout.addWidget(self.show_heatmap)
        heatmap_label = QLabel('Pal')
        heatmap_label.setObjectName('mapHeatmapLabel')
        heatmap_layout.addWidget(heatmap_label)
        self.heatmap_pal_combo = QComboBox()
        self.heatmap_pal_combo.setObjectName('mapHeatmapPal')
        self.heatmap_pal_combo.setEditable(True)
        self.heatmap_pal_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.heatmap_pal_combo.setMaxVisibleItems(18)
        self.heatmap_pal_combo.setMinimumWidth(220)
        self.heatmap_pal_combo.lineEdit().setClearButtonEnabled(True)
        self.heatmap_pal_combo.lineEdit().setPlaceholderText('Search Pals')
        heatmap_layout.addWidget(self.heatmap_pal_combo)
        self.heatmap_time_combo = QComboBox()
        self.heatmap_time_combo.setObjectName('mapHeatmapTime')
        self.heatmap_time_combo.addItem('All times', 'all')
        self.heatmap_time_combo.addItem('Day', 'day')
        self.heatmap_time_combo.addItem('Night', 'night')
        heatmap_layout.addWidget(self.heatmap_time_combo)
        self.show_heatmap_outline = QCheckBox('Outline')
        self.show_heatmap_outline.setObjectName('mapHeatmapOutline')
        self.show_heatmap_outline.setChecked(True)
        heatmap_layout.addWidget(self.show_heatmap_outline)
        self.heatmap_status_label = QLabel()
        self.heatmap_status_label.setObjectName('mapHeatmapStatus')
        heatmap_layout.addWidget(self.heatmap_status_label, 1)
        self._populate_heatmap_pals()
        self.heatmap_completer = QCompleter(
            self.heatmap_pal_combo.model(),
            self,
        )
        self.heatmap_completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.heatmap_completer.setFilterMode(Qt.MatchContains)
        self.heatmap_completer.setCompletionMode(
            QCompleter.CompletionMode.PopupCompletion
        )
        self.heatmap_pal_combo.setCompleter(self.heatmap_completer)
        self._set_heatmap_controls_enabled(False)
        toolbar_layout.addWidget(self.heatmap_controls)
        root.addWidget(toolbar)

        self.local_page = self._create_local_page()
        root.addWidget(self.local_page, 1)

        self.animation_timer = QTimer(self)
        self.animation_timer.setInterval(30)
        self.animation_timer.timeout.connect(self._update_marker_animations)
        self.animation_timer.start()

    @staticmethod
    def _segment_button(text: str, checked: bool) -> QPushButton:
        button = QPushButton(text)
        button.setCheckable(True)
        button.setChecked(checked)
        button.setProperty('segmentButton', True)
        button.setMinimumWidth(72)
        return button

    def _populate_heatmap_pals(self) -> None:
        selected_id = self.heatmap_pal_combo.currentData()
        self.heatmap_pal_combo.blockSignals(True)
        self.heatmap_pal_combo.clear()
        if self._spawn_repository is not None:
            for record in self._spawn_repository.records_for_map(self.current_map):
                self.heatmap_pal_combo.addItem(record.name, record.pal_id)
        selected_index = self.heatmap_pal_combo.findData(selected_id)
        self.heatmap_pal_combo.setCurrentIndex(selected_index)
        if selected_index < 0:
            self.heatmap_pal_combo.setEditText('')
        self.heatmap_pal_combo.blockSignals(False)

    def _set_heatmap_controls_enabled(self, enabled: bool) -> None:
        available = self._spawn_repository is not None
        self.heatmap_pal_combo.setEnabled(available and enabled)
        self.heatmap_time_combo.setEnabled(available and enabled)
        self.show_heatmap_outline.setEnabled(available and enabled)
        if not available:
            self.heatmap_status_label.setText(
                self._spawn_error or 'Pal spawn data is unavailable.'
            )
        elif not enabled:
            self.heatmap_status_label.setText('Heatmap off')
        elif self.heatmap_pal_combo.currentIndex() < 0:
            count = self.heatmap_pal_combo.count()
            self.heatmap_status_label.setText(
                f'{count} Pals available on the {self.current_map.title()} map.'
            )

    def _selected_heatmap_pal(self) -> PalSpawnSpecies | None:
        if self._spawn_repository is None:
            return None
        index = self.heatmap_pal_combo.currentIndex()
        displayed_text = self.heatmap_pal_combo.currentText().strip()
        selected_id = self.heatmap_pal_combo.currentData()
        query = (
            str(selected_id)
            if index >= 0 and displayed_text == self.heatmap_pal_combo.itemText(index)
            else displayed_text
        )
        record = self._spawn_repository.resolve(query)
        if record is None:
            return None
        resolved_index = self.heatmap_pal_combo.findData(record.pal_id)
        if resolved_index >= 0 and resolved_index != index:
            self.heatmap_pal_combo.blockSignals(True)
            self.heatmap_pal_combo.setCurrentIndex(resolved_index)
            self.heatmap_pal_combo.blockSignals(False)
        return record

    def _on_heatmap_toggled(self, checked: bool) -> None:
        self._set_heatmap_controls_enabled(checked)
        self._refresh_heatmap()

    def _refresh_heatmap(self, *_args) -> None:
        if self._heatmap_item is not None:
            try:
                if self._heatmap_item.scene() is self.scene:
                    self.scene.removeItem(self._heatmap_item)
            except RuntimeError:
                pass
            self._heatmap_item = None
        if not self.show_heatmap.isChecked():
            self._set_heatmap_controls_enabled(False)
            return
        if self._spawn_repository is None:
            self._set_heatmap_controls_enabled(True)
            return
        if not self._map_image_loaded:
            self.heatmap_status_label.setText('Map image is unavailable.')
            return
        record = self._selected_heatmap_pal()
        if record is None:
            self.heatmap_status_label.setText('Select a Pal to show its spawn areas.')
            return
        time_value = str(self.heatmap_time_combo.currentData() or 'all')
        time_filter: SpawnTimeFilter = (
            time_value if time_value in ('all', 'day', 'night') else 'all'
        )
        points = record.points_for(self.current_map, time_filter)
        if not points:
            self.heatmap_status_label.setText(
                f'No {time_filter} spawn areas are recorded for {record.name}.'
            )
            return
        pixmap = render_spawn_heatmap(
            points,
            self.current_map,
            self._spawn_repository.bounds_for(self.current_map),
            outline=self.show_heatmap_outline.isChecked(),
        )
        if pixmap.isNull():
            self.heatmap_status_label.setText('The heatmap could not be rendered.')
            return
        self._heatmap_item = SpawnHeatmapItem(
            pixmap,
            self.map_width,
            self.map_height,
        )
        self.scene.addItem(self._heatmap_item)
        period = {
            'all': 'all times',
            'day': 'daytime',
            'night': 'nighttime',
        }[time_filter]
        self.heatmap_status_label.setText(
            f'{len(points):,} recorded spawn areas for {record.name} ({period}).'
        )

    def _create_local_page(self) -> QWidget:
        page = QWidget()
        layout = QHBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)

        sidebar = QWidget()
        sidebar.setMinimumWidth(270)
        sidebar.setMaximumWidth(390)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(10, 10, 8, 10)
        sidebar_layout.setSpacing(8)
        self.world_name_label = QLabel('Palworld map')
        self.world_name_label.setObjectName('mapWorldName')
        sidebar_layout.addWidget(self.world_name_label)
        self.world_status_label = QLabel(
            'Explore bundled locations. Load Level.sav to add read-only '
            'base and player overlays.'
        )
        self.world_status_label.setObjectName('mapWorldStatus')
        self.world_status_label.setWordWrap(True)
        sidebar_layout.addWidget(self.world_status_label)

        self.search = QLineEdit()
        self.search.setPlaceholderText('Search places, names, IDs, or coordinates')
        self.search.setClearButtonEnabled(True)
        sidebar_layout.addWidget(self.search)

        filter_row = QHBoxLayout()
        self.filter_label = QLabel()
        self.filter_label.setObjectName('mapFilterLabel')
        self.filter_label.setVisible(False)
        filter_row.addWidget(self.filter_label, 1)
        self.clear_filter_button = QToolButton()
        self.clear_filter_button.setText('x')
        self.clear_filter_button.setToolTip('Clear guild filter')
        self.clear_filter_button.setVisible(False)
        filter_row.addWidget(self.clear_filter_button)
        sidebar_layout.addLayout(filter_row)

        self.list_tabs = QTabWidget()
        self.location_tree = QTreeWidget()
        self.location_tree.setHeaderLabels(['Place', 'Location'])
        self.location_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.location_tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.location_tree.header().setSectionResizeMode(
            1,
            QHeaderView.ResizeToContents,
        )
        self.base_tree = QTreeWidget()
        self.base_tree.setHeaderLabels(['Guild / Base', 'Location'])
        self.base_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.player_tree = QTreeWidget()
        self.player_tree.setHeaderLabels(['Player', 'Level', 'Location'])
        self.player_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list_tabs.addTab(self.location_tree, 'Places')
        self.list_tabs.addTab(self.base_tree, 'Bases')
        self.list_tabs.addTab(self.player_tree, 'Players')
        self.list_tabs.tabBar().setExpanding(True)
        self.list_tabs.tabBar().setUsesScrollButtons(False)
        sidebar_layout.addWidget(self.list_tabs, 1)

        detail_title = QLabel('Marker details')
        detail_title.setObjectName('mapDetailTitle')
        sidebar_layout.addWidget(detail_title)
        self.detail_label = QLabel('Select a place, base, or player marker.')
        self.detail_label.setObjectName('mapDetail')
        self.detail_label.setWordWrap(True)
        self.detail_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.detail_label.setMinimumHeight(118)
        self.detail_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        sidebar_layout.addWidget(self.detail_label)
        splitter.addWidget(sidebar)

        map_host = QWidget()
        map_layout = QVBoxLayout(map_host)
        map_layout.setContentsMargins(0, 0, 0, 0)
        self.scene = QGraphicsScene(self)
        self.view = MapGraphicsView(_MAP_CONFIG)
        self.view.setScene(self.scene)
        self.view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        map_layout.addWidget(self.view)
        self.location_popup = LocationPopup(self.view.viewport())
        self.view.overlay_position_callback = self._position_location_popup
        splitter.addWidget(map_host)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([320, 1100])
        layout.addWidget(splitter)
        return page

    def _create_annotation_menu(self) -> QMenu:
        menu = QMenu(self)
        add_pin = menu.addAction('Add pin at coordinates')
        menu.addSeparator()
        rectangle = menu.addAction('Draw rectangle')
        polygon = menu.addAction('Draw polygon')
        menu.addSeparator()
        stop = menu.addAction('Stop drawing')
        clear = menu.addAction('Clear annotations')
        add_pin.triggered.connect(self._add_pin_at_coordinates)
        rectangle.triggered.connect(lambda: self._start_annotation('rect'))
        polygon.triggered.connect(lambda: self._start_annotation('polygon'))
        stop.triggered.connect(self._stop_annotation)
        clear.triggered.connect(self._clear_annotations)
        return menu

    def _connect_signals(self) -> None:
        self.map_type_group.idClicked.connect(
            lambda index: self._switch_map_type('tree' if index else 'world')
        )
        self.search.textChanged.connect(self._refresh_visible_data)
        self.clear_filter_button.clicked.connect(self._clear_guild_filter)
        self.show_locations.toggled.connect(self._refresh_markers)
        self.show_bases.toggled.connect(self._refresh_markers)
        self.show_players.toggled.connect(self._refresh_markers)
        self.show_radii.toggled.connect(self._refresh_radius_rings)
        self.show_annotations.toggled.connect(self._refresh_annotations)
        self.show_heatmap.toggled.connect(self._on_heatmap_toggled)
        self.heatmap_pal_combo.currentIndexChanged.connect(self._refresh_heatmap)
        self.heatmap_pal_combo.lineEdit().returnPressed.connect(
            self._refresh_heatmap
        )
        self.heatmap_time_combo.currentIndexChanged.connect(self._refresh_heatmap)
        self.show_heatmap_outline.toggled.connect(self._refresh_heatmap)
        self.reset_button.clicked.connect(self.view.reset_view)
        self.view.zoom_changed.connect(self._scale_markers)
        self.view.marker_clicked.connect(self._on_marker_selected)
        self.view.marker_double_clicked.connect(self._on_marker_selected)
        self.view.marker_right_clicked.connect(self._show_marker_menu)
        self.view.marker_hover_entered.connect(
            lambda data, _position: self._show_details(data)
        )
        self.view.empty_space_clicked.connect(self._hide_location_popup)
        self.view.zone_created.connect(self._on_rectangle_created)
        self.view.polygon_closed.connect(self._on_polygon_created)
        self.view.zone_drawing_cancelled.connect(self._stop_annotation)
        self.view.zone_right_clicked.connect(self._show_annotation_menu)
        self.view.empty_space_right_clicked.connect(self._show_empty_map_menu)
        self.view.horizontalScrollBar().valueChanged.connect(
            self._position_location_popup
        )
        self.view.verticalScrollBar().valueChanged.connect(
            self._position_location_popup
        )
        self.location_popup.found_toggled.connect(self._set_location_found)
        self.location_tree.itemDoubleClicked.connect(self._on_tree_item_activated)
        self.base_tree.itemDoubleClicked.connect(self._on_tree_item_activated)
        self.player_tree.itemDoubleClicked.connect(self._on_tree_item_activated)
        self.location_tree.customContextMenuRequested.connect(
            lambda point: self._show_tree_menu(self.location_tree, point)
        )
        self.base_tree.customContextMenuRequested.connect(
            lambda point: self._show_tree_menu(self.base_tree, point)
        )
        self.player_tree.customContextMenuRequested.connect(
            lambda point: self._show_tree_menu(self.player_tree, point)
        )

    def set_world(self, world: ReadOnlyWorldData | None) -> None:
        self.world = world
        self.close_button.setEnabled(world is not None)
        self.read_only_label.setVisible(world is not None)
        warnings = list(world.warnings) if world else []
        if self._annotation_error:
            warnings.append(self._annotation_error)
        if self._progress_error:
            warnings.append(self._progress_error)
        if self._location_error:
            warnings.append(self._location_error)
        if self._spawn_error:
            warnings.append(self._spawn_error)
        self.warning_label.setVisible(bool(warnings))
        self.warning_label.setText(' | '.join(warnings))
        self.world_name_label.setText(world.display_name if world else 'Palworld map')
        self.world_status_label.setText(
            'Save overlay loaded in read-only mode.'
            if world
            else (
                'Explore bundled locations. Load Level.sav to add read-only '
                'base and player overlays.'
            )
        )
        self._guild_filter = None
        self.search.clear()
        self._update_filter_label()
        self._refresh_visible_data()
        if world:
            self.status_message.emit(
                f'Read-only world loaded: {len(world.bases)} bases, '
                f'{len(world.players)} player locations'
            )

    def refresh(self) -> None:
        self._refresh_visible_data()

    def refresh_labels(self) -> None:
        pass

    def _switch_map_type(self, map_type: str) -> None:
        if map_type == self.current_map:
            return
        self.current_map = map_type
        self._populate_heatmap_pals()
        self._load_map_image(map_type)
        self._refresh_trees()
        self._refresh_markers()
        self._refresh_radius_rings()
        self._refresh_annotations()

    def _load_map_image(self, map_type: str) -> None:
        self._hide_location_popup()
        filename = 'T_TreeMap.webp' if map_type == 'tree' else 'T_WorldMap.webp'
        pixmap = QPixmap(resource_path(get_base_directory(), filename))
        self._heatmap_item = None
        self._map_image_loaded = False
        self.scene.clear()
        self._location_markers.clear()
        self._base_markers.clear()
        self._player_markers.clear()
        self._radius_items.clear()
        self._annotation_items.clear()
        if pixmap.isNull():
            self.map_width = self.map_height = 2048
            self.scene.setSceneRect(0, 0, self.map_width, self.map_height)
            self.status_message.emit(f'Map image is missing: {filename}')
            self._refresh_heatmap()
            return
        self.map_width = pixmap.width()
        self.map_height = pixmap.height()
        image_item = QGraphicsPixmapItem(pixmap)
        image_item.setZValue(0)
        self.scene.addItem(image_item)
        self.scene.setSceneRect(0, 0, self.map_width, self.map_height)
        self._map_image_loaded = True
        coordinate_range = palworld_coord.get_treemap_coord_range() if map_type == 'tree' else 1000
        self.view.set_map_type(map_type, coordinate_range)
        self._refresh_heatmap()
        QTimer.singleShot(0, self.view.reset_view)

    def _scene_coordinates(self, coordinates: tuple[int, int], map_type: str) -> tuple[float, float]:
        if map_type == 'tree':
            return palworld_coord.treemap_to_pixel(
                coordinates[0], coordinates[1], self.map_width, self.map_height
            )
        return annotations.world_to_scene(
            coordinates[0], coordinates[1], self.map_width, self.map_height
        )

    def _filtered_bases(self) -> list[BaseMarkerData]:
        if not self.world:
            return []
        needle = self.search.text().strip().lower()
        result = []
        for base in self.world.bases:
            if self._guild_filter and base.guild_id != self._guild_filter:
                continue
            haystack = ' '.join((
                base.guild_name,
                base.leader_name,
                base.base_id,
                str(base.coordinates[0]),
                str(base.coordinates[1]),
            )).lower()
            if needle and needle not in haystack:
                continue
            result.append(base)
        return result

    def _local_pin_locations(self) -> list[MapLocation]:
        return [
            location_from_annotation(value)
            for value in self.annotation_store.items()
            if value.get('type') == 'point' and value.get('enabled', True)
        ]

    def _filtered_locations(self) -> list[MapLocation]:
        needle = self.search.text().strip().casefold()
        result = []
        for location in (*self._bundled_locations, *self._local_pin_locations()):
            haystack = ' '.join((
                location.name,
                location.internal_id,
                location.location_id,
                location.category,
                location.description,
                str(location.coordinates[0]),
                str(location.coordinates[1]),
            )).casefold()
            if needle and needle not in haystack:
                continue
            result.append(location)
        return result

    def _filtered_players(self) -> list[PlayerMarkerData]:
        if not self.world:
            return []
        needle = self.search.text().strip().lower()
        result = []
        for player in self.world.players:
            if self._guild_filter and player.guild_id != self._guild_filter:
                continue
            haystack = ' '.join((
                player.player_name,
                player.player_uid,
                player.guild_name,
                str(player.coordinates[0]),
                str(player.coordinates[1]),
            )).lower()
            if needle and needle not in haystack:
                continue
            result.append(player)
        return result

    def _refresh_visible_data(self, *_args) -> None:
        self._refresh_trees()
        self._refresh_markers()
        self._refresh_radius_rings()
        self._refresh_annotations()

    def _refresh_trees(self) -> None:
        self.location_tree.clear()
        location_groups: dict[str, list[MapLocation]] = defaultdict(list)
        for location in self._filtered_locations():
            if location.map_type == self.current_map:
                location_groups[location.category].append(location)
        for category in ('Fast Travel', 'My Pins'):
            locations = location_groups.get(category, [])
            if not locations:
                continue
            found_count = sum(
                self.progress_store.is_found(location.location_id)
                for location in locations
                if location.source == 'bundled'
            )
            summary = (
                f'{found_count}/{len(locations)} found'
                if category == 'Fast Travel'
                else f'{len(locations)} places'
            )
            category_item = QTreeWidgetItem([
                category,
                summary,
            ])
            category_item.setData(0, Qt.UserRole, ('location-category', category))
            for location in sorted(locations, key=lambda item: item.name.casefold()):
                child = QTreeWidgetItem([
                    location.name,
                    f'{location.coordinates[0]}, {location.coordinates[1]}',
                ])
                child.setData(0, Qt.UserRole, location)
                child.setToolTip(0, location.name)
                found = self.progress_store.is_found(location.location_id)
                child.setIcon(
                    0,
                    QIcon(location_pin_pixmap(
                        15,
                        location.source,
                        found,
                    )),
                )
                child.setForeground(
                    0,
                    QColor(
                        '#E77A20'
                        if location.source == 'local'
                        else '#27A875' if found else '#2F80ED'
                    ),
                )
                category_item.addChild(child)
            self.location_tree.addTopLevelItem(category_item)
            category_item.setExpanded(True)
        self.base_tree.clear()
        grouped: dict[str, list[BaseMarkerData]] = defaultdict(list)
        for base in self._filtered_bases():
            grouped[base.guild_id].append(base)
        for guild_id, bases in sorted(grouped.items(), key=lambda item: item[1][0].guild_name.lower()):
            guild_item = QTreeWidgetItem([bases[0].guild_name, f'{len(bases)} bases'])
            guild_item.setData(0, Qt.UserRole, ('guild', guild_id))
            for base in bases:
                child = QTreeWidgetItem([
                    f'Base {base.base_position}',
                    f'{base.coordinates[0]}, {base.coordinates[1]}',
                ])
                child.setData(0, Qt.UserRole, base)
                child.setForeground(0, QColor('#4FC3F7'))
                guild_item.addChild(child)
            self.base_tree.addTopLevelItem(guild_item)
            guild_item.setExpanded(True)
        self.base_tree.resizeColumnToContents(0)

        self.player_tree.clear()
        for player in sorted(self._filtered_players(), key=lambda item: item.player_name.lower()):
            item = QTreeWidgetItem([
                player.player_name,
                str(player.level),
                f'{player.coordinates[0]}, {player.coordinates[1]}',
            ])
            item.setData(0, Qt.UserRole, player)
            self.player_tree.addTopLevelItem(item)
        self.player_tree.resizeColumnToContents(0)

    def _refresh_markers(self, *_args) -> None:
        self._hide_location_popup()
        for marker in (
            *self._location_markers.values(),
            *self._base_markers.values(),
            *self._player_markers.values(),
        ):
            self.scene.removeItem(marker)
        self._location_markers.clear()
        self._base_markers.clear()
        self._player_markers.clear()

        if self.show_locations.isChecked():
            for location in self._filtered_locations():
                if location.map_type != self.current_map:
                    continue
                x, y = self._scene_coordinates(location.coordinates, location.map_type)
                marker = LocationMarker(
                    location,
                    x,
                    y,
                    self.progress_store.is_found(location.location_id),
                )
                marker.scale_to_zoom(self.view.current_zoom)
                marker.setZValue(12 if location.source == 'local' else 9)
                self.scene.addItem(marker)
                self._location_markers[location.location_id] = marker

        if not self.world:
            return
        base_icon = QPixmap(resource_path(get_base_directory(), 'baseicon.webp'))
        player_icon = QPixmap(resource_path(get_base_directory(), 'playericon.webp'))
        if self.show_bases.isChecked() and not base_icon.isNull():
            for base in self._filtered_bases():
                if base.map_type != self.current_map:
                    continue
                x, y = self._scene_coordinates(base.coordinates, base.map_type)
                marker = BaseMarker(base, x, y, base_icon, _MAP_CONFIG)
                marker.scale_to_zoom(self.view.current_zoom)
                marker.setZValue(10)
                self.scene.addItem(marker)
                self._base_markers[base.base_id] = marker
        if self.show_players.isChecked() and not player_icon.isNull():
            for player in self._filtered_players():
                if player.map_type != self.current_map:
                    continue
                x, y = self._scene_coordinates(player.coordinates, player.map_type)
                marker = PlayerMarker(player, x, y, player_icon)
                marker.scale_to_zoom(self.view.current_zoom)
                marker.setZValue(11)
                self.scene.addItem(marker)
                self._player_markers[player.player_uid] = marker

    def _refresh_radius_rings(self, *_args) -> None:
        for item in self._radius_items:
            self.scene.removeItem(item)
        self._radius_items.clear()
        if (
            not self.world
            or self.current_map != 'world'
            or not self.show_radii.isChecked()
        ):
            return
        for base in self._filtered_bases():
            if base.map_type != 'world':
                continue
            x, y = self._scene_coordinates(base.coordinates, 'world')
            ring = BaseRadiusRing(x, y, base.radius)
            self.scene.addItem(ring)
            self._radius_items.append(ring)

    def _refresh_annotations(self, *_args) -> None:
        for item in self._annotation_items:
            self.scene.removeItem(item)
        self._annotation_items.clear()
        if self.current_map != 'world' or not self.show_annotations.isChecked():
            return
        for value in self.annotation_store.items():
            if not value.get('enabled', True):
                continue
            if value.get('type') == 'point':
                continue
            if value.get('type') == 'polygon':
                item = PolygonExclusionZoneItem(value, self.map_width, self.map_height)
            else:
                item = ExclusionZoneItem(value, self.map_width, self.map_height)
            self.scene.addItem(item)
            self._annotation_items.append(item)

    def _scale_markers(self, zoom: float) -> None:
        for marker in (
            *self._location_markers.values(),
            *self._base_markers.values(),
            *self._player_markers.values(),
        ):
            marker.scale_to_zoom(zoom)
        self._position_location_popup()

    def _update_marker_animations(self) -> None:
        for marker in (
            *self._location_markers.values(),
            *self._base_markers.values(),
            *self._player_markers.values(),
        ):
            if marker.isSelected() or marker.is_hovered or marker.glow_alpha > 0:
                marker.update_glow()

    def _on_marker_selected(self, data, marker) -> None:
        self._show_details(data)
        if isinstance(data, MapLocation):
            self._show_location_popup(data, marker)
        else:
            self._hide_location_popup()

    def _show_location_popup(
        self,
        location: MapLocation,
        marker: LocationMarker,
    ) -> None:
        self._popup_marker = marker
        self.location_popup.set_location(
            location,
            self.progress_store.is_found(location.location_id),
        )
        self.location_popup.show()
        self.location_popup.raise_()
        self._position_location_popup()

    def _hide_location_popup(self, *_args) -> None:
        if hasattr(self, 'location_popup'):
            self.location_popup.hide()
        self._popup_marker = None

    def _position_location_popup(self, *_args) -> None:
        if (
            not hasattr(self, 'location_popup')
            or self.location_popup.isHidden()
            or self._popup_marker is None
            or self._popup_marker.scene() is None
        ):
            return
        anchor = self.view.mapFromScene(self._popup_marker.scenePos())
        popup = self.location_popup
        popup.adjustSize()
        margin = 12
        gap = 18
        x = anchor.x() - popup.width() // 2
        y = anchor.y() - popup.height() - gap
        if y < margin:
            y = anchor.y() + gap
        x = max(margin, min(x, self.view.viewport().width() - popup.width() - margin))
        y = max(margin, min(y, self.view.viewport().height() - popup.height() - margin))
        popup.move(x, y)
        popup.raise_()

    def _set_location_found(self, location_id: str, found: bool) -> None:
        try:
            self.progress_store.set_found(location_id, found)
        except (OSError, ValueError) as exc:
            if self.location_popup.location is not None:
                self.location_popup.set_found(not found)
            QMessageBox.warning(
                self,
                'Map progress',
                f'Could not store map progress: {exc}',
            )
            return
        marker = self._location_markers.get(location_id)
        if marker is not None:
            marker.set_found(found)
        if (
            self.location_popup.location is not None
            and self.location_popup.location.location_id == location_id
        ):
            self.location_popup.set_found(found)
        self._refresh_trees()
        state = 'found' if found else 'not found'
        self.status_message.emit(f'Map location marked as {state}.')

    def _show_details(self, data) -> None:
        if isinstance(data, PlayerMarkerData):
            self.detail_label.setText(
                f'<b>{escape(data.player_name)}</b><br>'
                f'Guild: {escape(data.guild_name)}<br>'
                f'Level: {escape(str(data.level))}<br>'
                f'Last seen: {escape(data.last_seen)}<br>'
                f'Coordinates: {data.coordinates[0]}, {data.coordinates[1]}<br>'
                f'Player ID: {escape(data.player_uid)}'
            )
        elif isinstance(data, BaseMarkerData):
            self.detail_label.setText(
                f'<b>{escape(data.guild_name)} - Base {data.base_position}</b><br>'
                f'Leader: {escape(data.leader_name)}<br>'
                f'Guild level: {data.guild_level}<br>'
                f'Members: {data.member_count} | Assigned Pals: {data.pal_count}<br>'
                f'Coordinates: {data.coordinates[0]}, {data.coordinates[1]}<br>'
                f'Base ID: {escape(data.base_id)}'
            )
        elif isinstance(data, MapLocation):
            source = 'Local pin' if data.source == 'local' else 'Bundled game data'
            description = (
                f'<br>{escape(data.description)}'
                if data.description
                else ''
            )
            self.detail_label.setText(
                f'<b>{escape(data.name)}</b><br>'
                f'{escape(data.category)} | {source}<br>'
                f'Map: {escape(data.map_type.title())}<br>'
                f'Coordinates: {data.coordinates[0]}, {data.coordinates[1]}<br>'
                f'Location ID: {escape(data.internal_id)}'
                f'{description}'
            )

    def _show_marker_menu(self, data, global_position: QPointF) -> None:
        menu = QMenu(self)
        center_action = menu.addAction('Center on marker')
        copy_coordinates = menu.addAction('Copy coordinates')
        copy_identifier = menu.addAction('Copy identifier')
        filter_action = None
        found_action = None
        rename_action = None
        delete_action = None
        if isinstance(data, (BaseMarkerData, PlayerMarkerData)):
            menu.addSeparator()
            filter_action = menu.addAction('Filter by this guild')
        elif isinstance(data, MapLocation) and data.source == 'bundled':
            menu.addSeparator()
            is_found = self.progress_store.is_found(data.location_id)
            found_action = menu.addAction(
                'Mark as not found' if is_found else 'Mark as found'
            )
        elif isinstance(data, MapLocation) and data.source == 'local':
            menu.addSeparator()
            rename_action = menu.addAction('Rename pin')
            delete_action = menu.addAction('Delete pin')
        action = menu.exec(global_position.toPoint())
        if action == center_action:
            self._navigate_to(data)
        elif action == copy_coordinates:
            QApplication.clipboard().setText(
                f'{data.coordinates[0]}, {data.coordinates[1]}'
            )
        elif action == copy_identifier:
            if isinstance(data, PlayerMarkerData):
                identifier = data.player_uid
            elif isinstance(data, BaseMarkerData):
                identifier = data.base_id
            else:
                identifier = data.internal_id
            QApplication.clipboard().setText(identifier)
        elif filter_action is not None and action == filter_action:
            self._set_guild_filter(data.guild_id, data.guild_name)
        elif found_action is not None and action == found_action:
            self._set_location_found(data.location_id, not is_found)
        elif rename_action is not None and action == rename_action:
            self._rename_pin(data)
        elif delete_action is not None and action == delete_action:
            self._delete_pin(data)

    def _show_tree_menu(self, tree: QTreeWidget, point) -> None:
        item = tree.itemAt(point)
        if item is None:
            return
        data = item.data(0, Qt.UserRole)
        if isinstance(data, tuple) and data[0] == 'guild':
            guild_id = data[1]
            guild_name = item.text(0)
            menu = QMenu(self)
            filter_action = menu.addAction('Filter by this guild')
            copy_action = menu.addAction('Copy guild identifier')
            action = menu.exec(tree.viewport().mapToGlobal(point))
            if action == filter_action:
                self._set_guild_filter(guild_id, guild_name)
            elif action == copy_action:
                QApplication.clipboard().setText(guild_id)
            return
        if isinstance(data, tuple) and data[0] == 'location-category':
            return
        if isinstance(data, (MapLocation, BaseMarkerData, PlayerMarkerData)):
            self._show_marker_menu(data, QPointF(QCursor.pos()))

    def _on_tree_item_activated(self, item: QTreeWidgetItem, _column: int) -> None:
        data = item.data(0, Qt.UserRole)
        if isinstance(data, (MapLocation, BaseMarkerData, PlayerMarkerData)):
            marker = self._navigate_to(data)
            self._show_details(data)
            if isinstance(data, MapLocation) and isinstance(marker, LocationMarker):
                self._show_location_popup(data, marker)
            else:
                self._hide_location_popup()

    def _navigate_to(self, data):
        if data.map_type != self.current_map:
            if data.map_type == 'tree':
                self.tree_button.click()
            else:
                self.world_button.click()
        if isinstance(data, PlayerMarkerData):
            marker = self._player_markers.get(data.player_uid)
        elif isinstance(data, BaseMarkerData):
            marker = self._base_markers.get(data.base_id)
        else:
            marker = self._location_markers.get(data.location_id)
        if marker:
            self.view.animate_to_marker(marker, zoom_level=10.0)
        return marker

    def _set_guild_filter(self, guild_id: str, guild_name: str) -> None:
        self._guild_filter = guild_id
        self.filter_label.setText(f'Guild: {guild_name}')
        self._update_filter_label()
        self._refresh_visible_data()

    def _clear_guild_filter(self) -> None:
        self._guild_filter = None
        self._update_filter_label()
        self._refresh_visible_data()

    def _update_filter_label(self) -> None:
        visible = bool(self._guild_filter)
        self.filter_label.setVisible(visible)
        self.clear_filter_button.setVisible(visible)

    def _coordinates_at_global_position(
        self,
        global_position: QPointF,
    ) -> tuple[tuple[int, int], QPointF] | None:
        viewport_position = self.view.viewport().mapFromGlobal(
            global_position.toPoint()
        )
        scene_position = self.view.mapToScene(viewport_position)
        if not self.scene.sceneRect().contains(scene_position):
            return None
        if self.current_map == 'tree':
            x, y = palworld_coord.treemap_pixel_to_map(
                scene_position.x(),
                scene_position.y(),
                self.map_width,
                self.map_height,
            )
        else:
            x, y = annotations.scene_to_world(
                scene_position.x(),
                scene_position.y(),
                self.map_width,
                self.map_height,
            )
        return (round(x), round(y)), scene_position

    def _show_empty_map_menu(self, global_position: QPointF) -> None:
        location = self._coordinates_at_global_position(global_position)
        if location is None:
            return
        coordinates, scene_position = location
        menu = QMenu(self)
        add_pin = menu.addAction('Add pin here')
        copy_coordinates = menu.addAction('Copy coordinates')
        center_here = menu.addAction('Center map here')
        action = menu.exec(global_position.toPoint())
        if action == add_pin:
            self._create_pin(coordinates)
        elif action == copy_coordinates:
            QApplication.clipboard().setText(
                f'{coordinates[0]}, {coordinates[1]}'
            )
        elif action == center_here:
            self.view.animate_to_coords(
                scene_position.x(),
                scene_position.y(),
                zoom_level=max(4.0, self.view.current_zoom),
            )

    def _add_pin_at_coordinates(self) -> None:
        if self.current_map == 'tree':
            min_x, min_y, max_x, max_y = palworld_coord.get_treemap_map_bounds()
            coordinate_hint = (
                f'x {min_x:.0f} to {max_x:.0f}; '
                f'y {min_y:.0f} to {max_y:.0f}'
            )
        else:
            coordinate_hint = 'x and y -1000 to 1000'
        value, accepted = QInputDialog.getText(
            self,
            'Add map pin',
            f'Coordinates (x, y; {coordinate_hint}):',
        )
        if not accepted:
            return
        try:
            parts = [part.strip() for part in value.split(',')]
            if len(parts) != 2:
                raise ValueError
            coordinates = (round(float(parts[0])), round(float(parts[1])))
        except ValueError:
            QMessageBox.warning(
                self,
                'Invalid coordinates',
                'Enter two numbers separated by a comma, for example: 125, -340.',
            )
            return
        self._create_pin(coordinates)

    def _create_pin(self, coordinates: tuple[int, int]) -> None:
        name, accepted = QInputDialog.getText(self, 'Add map pin', 'Name:')
        if not accepted:
            return
        try:
            self.annotation_store.add({
                'type': 'point',
                'name': name.strip() or 'Map pin',
                'map_type': self.current_map,
                'x': coordinates[0],
                'y': coordinates[1],
            })
        except ValueError as exc:
            QMessageBox.warning(self, 'Invalid map pin', str(exc))
            return
        self._refresh_visible_data()
        self.status_message.emit(
            f'Local pin added at {coordinates[0]}, {coordinates[1]}.'
        )

    def _rename_pin(self, location: MapLocation) -> None:
        value, accepted = QInputDialog.getText(
            self,
            'Rename pin',
            'Name:',
            text=location.name,
        )
        if accepted and value.strip():
            self.annotation_store.update(
                location.location_id,
                {'name': value.strip()},
            )
            self._refresh_visible_data()

    def _delete_pin(self, location: MapLocation) -> None:
        answer = QMessageBox.question(
            self,
            'Delete pin',
            f'Delete the local pin "{location.name}"?',
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer == QMessageBox.Yes:
            self.annotation_store.remove(location.location_id)
            self.detail_label.setText('Select a place, base, or player marker.')
            self._refresh_visible_data()

    def _start_annotation(self, kind: str) -> None:
        if self.current_map != 'world':
            self.world_button.click()
        self.view.set_zone_shape_type(kind)
        self.view.set_zone_drawing_mode(True)
        self.status_message.emit('Map annotation drawing is active. Press Escape to stop.')

    def _stop_annotation(self) -> None:
        self.view.set_zone_drawing_mode(False)
        self.status_message.emit('Map annotation drawing stopped.')

    def _annotation_name(self) -> str | None:
        value, accepted = QInputDialog.getText(self, 'Map annotation', 'Name:')
        if not accepted:
            return None
        return value.strip() or 'Map annotation'

    def _on_rectangle_created(self, point_a: QPointF, point_b: QPointF) -> None:
        name = self._annotation_name()
        if name is None:
            return
        x1, y1 = annotations.scene_to_world(
            point_a.x(), point_a.y(), self.map_width, self.map_height
        )
        x2, y2 = annotations.scene_to_world(
            point_b.x(), point_b.y(), self.map_width, self.map_height
        )
        self.annotation_store.add({
            'type': 'rect',
            'name': name,
            'x1': x1,
            'y1': y1,
            'x2': x2,
            'y2': y2,
        })
        self._refresh_annotations()

    def _on_polygon_created(self, scene_points: list[QPointF]) -> None:
        name = self._annotation_name()
        if name is None:
            return
        points = []
        for point in scene_points:
            x, y = annotations.scene_to_world(
                point.x(), point.y(), self.map_width, self.map_height
            )
            points.append({'x': x, 'y': y})
        self.annotation_store.add({'type': 'polygon', 'name': name, 'points': points})
        self._refresh_annotations()

    def _show_annotation_menu(self, item, global_position: QPointF) -> None:
        annotation = item.zone_data
        menu = QMenu(self)
        rename = menu.addAction('Rename annotation')
        delete = menu.addAction('Delete annotation')
        action = menu.exec(global_position.toPoint())
        if action == rename:
            value, accepted = QInputDialog.getText(
                self,
                'Rename annotation',
                'Name:',
                text=annotation.get('name', ''),
            )
            if accepted and value.strip():
                self.annotation_store.update(annotation['id'], {'name': value.strip()})
                self._refresh_annotations()
        elif action == delete:
            self.annotation_store.remove(annotation['id'])
            self._refresh_annotations()

    def _clear_annotations(self) -> None:
        answer = QMessageBox.question(
            self,
            'Clear annotations',
            'Remove all local map annotations?',
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer == QMessageBox.Yes:
            self.annotation_store.clear()
            self._refresh_visible_data()
