from __future__ import annotations

from collections import defaultdict
from html import escape
import os
from pathlib import Path

import palworld_coord
from PySide6.QtCore import QPointF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QCursor, QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QCheckBox,
    QFrame,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QStyle,
    QTabWidget,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from common import get_base_directory
from i18n import t
from palworld_aio.map import annotations
from palworld_aio.map.annotations import AnnotationStore
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
from palworld_aio.ui.map_view.map_markers import BaseMarker, PlayerMarker
from palworld_aio.ui.map_view.map_view import MapGraphicsView
from palworld_aio.ui.map_view.mapgenie_view import MapGenieView
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
        self._source = 'local'
        self._guild_filter: str | None = None
        self._base_markers: dict[str, BaseMarker] = {}
        self._player_markers: dict[str, PlayerMarker] = {}
        self._radius_items: list[BaseRadiusRing] = []
        self._annotation_items: list = []
        self._selected_mapgenie_pin = None
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
        self._setup_ui()
        self._connect_signals()
        self._load_map_image('world')
        self._update_source_page()

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
        self.source_group = QButtonGroup(self)
        self.source_group.setExclusive(True)
        self.local_source_button = self._segment_button('Local map', True)
        self.live_source_button = self._segment_button('Interactive map', False)
        self.source_group.addButton(self.local_source_button, 0)
        self.source_group.addButton(self.live_source_button, 1)
        primary_row.addWidget(self.local_source_button)
        primary_row.addWidget(self.live_source_button)

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

        self.show_bases = QCheckBox('Bases')
        self.show_bases.setChecked(True)
        self.show_players = QCheckBox('Players')
        self.show_players.setChecked(True)
        self.show_radii = QCheckBox('Rings')
        self.show_radii.setChecked(True)
        self.show_annotations = QCheckBox('Annotations')
        self.show_annotations.setChecked(True)
        for toggle in (
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
        self.warning_label.setVisible(bool(self._annotation_error))
        self.warning_label.setText(self._annotation_error)
        self.warning_label.setMaximumWidth(420)
        primary_row.addWidget(self.warning_label)

        self.read_only_label = QLabel('READ-ONLY')
        self.read_only_label.setObjectName('readOnlyBadge')
        self.read_only_label.setVisible(False)
        primary_row.addWidget(self.read_only_label)
        toolbar_layout.addLayout(primary_row)
        toolbar_layout.addWidget(self.local_controls)
        root.addWidget(toolbar)

        self.content_stack = QStackedWidget()
        self.empty_page = self._create_empty_page()
        self.local_page = self._create_local_page()
        self.mapgenie_view = MapGenieView(auto_load=False)
        self.content_stack.addWidget(self.empty_page)
        self.content_stack.addWidget(self.local_page)
        self.content_stack.addWidget(self.mapgenie_view)
        root.addWidget(self.content_stack, 1)

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

    def _create_empty_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignCenter)
        icon = QLabel()
        pixmap = QPixmap(resource_path(get_base_directory(), 'T_WorldMap.webp'))
        if not pixmap.isNull():
            icon.setPixmap(
                pixmap.scaled(220, 140, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )
        icon.setAlignment(Qt.AlignCenter)
        layout.addWidget(icon)
        title = QLabel('Map viewer')
        title.setObjectName('emptyStateTitle')
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        message = QLabel(
            'Load a Palworld world save to view its map. This app opens saves '
            'in read-only mode and will never modify them.'
        )
        message.setObjectName('emptyStateText')
        message.setAlignment(Qt.AlignCenter)
        message.setWordWrap(True)
        message.setMaximumWidth(560)
        layout.addWidget(message)
        buttons = QHBoxLayout()
        load = QPushButton('Load Level.sav')
        load.setIcon(self.style().standardIcon(QStyle.SP_DialogOpenButton))
        load.clicked.connect(self.load_requested.emit)
        buttons.addWidget(load)
        browse = QPushButton('Open interactive map')
        browse.clicked.connect(lambda: self.live_source_button.click())
        buttons.addWidget(browse)
        layout.addLayout(buttons)
        return page

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
        self.world_name_label = QLabel('No world loaded')
        self.world_name_label.setObjectName('mapWorldName')
        sidebar_layout.addWidget(self.world_name_label)

        self.search = QLineEdit()
        self.search.setPlaceholderText('Search names, IDs, or coordinates')
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
        self.base_tree = QTreeWidget()
        self.base_tree.setHeaderLabels(['Guild / Base', 'Location'])
        self.base_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.player_tree = QTreeWidget()
        self.player_tree.setHeaderLabels(['Player', 'Level', 'Location'])
        self.player_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list_tabs.addTab(self.base_tree, 'Bases')
        self.list_tabs.addTab(self.player_tree, 'Players')
        sidebar_layout.addWidget(self.list_tabs, 1)

        detail_title = QLabel('Marker details')
        detail_title.setObjectName('mapDetailTitle')
        sidebar_layout.addWidget(detail_title)
        self.detail_label = QLabel('Select a base or player marker.')
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
        splitter.addWidget(map_host)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([320, 1100])
        layout.addWidget(splitter)
        return page

    def _create_annotation_menu(self) -> QMenu:
        menu = QMenu(self)
        rectangle = menu.addAction('Draw rectangle')
        polygon = menu.addAction('Draw polygon')
        menu.addSeparator()
        stop = menu.addAction('Stop drawing')
        clear = menu.addAction('Clear annotations')
        rectangle.triggered.connect(lambda: self._start_annotation('rect'))
        polygon.triggered.connect(lambda: self._start_annotation('polygon'))
        stop.triggered.connect(self._stop_annotation)
        clear.triggered.connect(self._clear_annotations)
        return menu

    def _connect_signals(self) -> None:
        self.source_group.idClicked.connect(self._switch_source)
        self.map_type_group.idClicked.connect(
            lambda index: self._switch_map_type('tree' if index else 'world')
        )
        self.search.textChanged.connect(self._refresh_visible_data)
        self.clear_filter_button.clicked.connect(self._clear_guild_filter)
        self.show_bases.toggled.connect(self._refresh_markers)
        self.show_players.toggled.connect(self._refresh_markers)
        self.show_radii.toggled.connect(self._refresh_radius_rings)
        self.show_annotations.toggled.connect(self._refresh_annotations)
        self.reset_button.clicked.connect(self.view.reset_view)
        self.view.zoom_changed.connect(self._scale_markers)
        self.view.marker_clicked.connect(self._on_marker_selected)
        self.view.marker_double_clicked.connect(self._on_marker_selected)
        self.view.marker_right_clicked.connect(self._show_marker_menu)
        self.view.marker_hover_entered.connect(
            lambda data, _position: self._show_details(data)
        )
        self.view.zone_created.connect(self._on_rectangle_created)
        self.view.polygon_closed.connect(self._on_polygon_created)
        self.view.zone_drawing_cancelled.connect(self._stop_annotation)
        self.view.zone_right_clicked.connect(self._show_annotation_menu)
        self.base_tree.itemDoubleClicked.connect(self._on_tree_item_activated)
        self.player_tree.itemDoubleClicked.connect(self._on_tree_item_activated)
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
        self.warning_label.setVisible(bool(warnings))
        self.warning_label.setText(' | '.join(warnings))
        self.world_name_label.setText(world.display_name if world else 'No world loaded')
        self._guild_filter = None
        self.search.clear()
        self._update_filter_label()
        self._update_source_page()
        self._refresh_visible_data()
        if world:
            self.status_message.emit(
                f'Read-only world loaded: {len(world.bases)} bases, '
                f'{len(world.players)} player locations'
            )

    def refresh(self) -> None:
        self._refresh_visible_data()

    def refresh_labels(self) -> None:
        self.mapgenie_view.refresh_labels()

    def _switch_source(self, index: int) -> None:
        self._source = 'mapgenie' if index == 1 else 'local'
        self._update_source_page()

    def _update_source_page(self) -> None:
        is_local = self._source == 'local'
        self.local_controls.setVisible(is_local)
        if not is_local:
            self.content_stack.setCurrentWidget(self.mapgenie_view)
            self.mapgenie_view.ensure_loaded()
        elif self.world is None:
            self.content_stack.setCurrentWidget(self.empty_page)
        else:
            self.content_stack.setCurrentWidget(self.local_page)
            QTimer.singleShot(0, self.view.reset_view)

    def _switch_map_type(self, map_type: str) -> None:
        if map_type == self.current_map:
            return
        self.current_map = map_type
        self._load_map_image(map_type)
        self._refresh_markers()
        self._refresh_radius_rings()
        self._refresh_annotations()

    def _load_map_image(self, map_type: str) -> None:
        filename = 'T_TreeMap.webp' if map_type == 'tree' else 'T_WorldMap.webp'
        pixmap = QPixmap(resource_path(get_base_directory(), filename))
        self.scene.clear()
        self._base_markers.clear()
        self._player_markers.clear()
        self._radius_items.clear()
        self._annotation_items.clear()
        if pixmap.isNull():
            self.map_width = self.map_height = 2048
            self.scene.setSceneRect(0, 0, self.map_width, self.map_height)
            self.status_message.emit(f'Map image is missing: {filename}')
            return
        self.map_width = pixmap.width()
        self.map_height = pixmap.height()
        image_item = QGraphicsPixmapItem(pixmap)
        image_item.setZValue(0)
        self.scene.addItem(image_item)
        self.scene.setSceneRect(0, 0, self.map_width, self.map_height)
        coordinate_range = palworld_coord.get_treemap_coord_range() if map_type == 'tree' else 1000
        self.view.set_map_type(map_type, coordinate_range)
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
        for marker in (*self._base_markers.values(), *self._player_markers.values()):
            self.scene.removeItem(marker)
        self._base_markers.clear()
        self._player_markers.clear()
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
            if value.get('type') == 'polygon':
                item = PolygonExclusionZoneItem(value, self.map_width, self.map_height)
            else:
                item = ExclusionZoneItem(value, self.map_width, self.map_height)
            self.scene.addItem(item)
            self._annotation_items.append(item)

    def _scale_markers(self, zoom: float) -> None:
        for marker in (*self._base_markers.values(), *self._player_markers.values()):
            marker.scale_to_zoom(zoom)

    def _update_marker_animations(self) -> None:
        for marker in (*self._base_markers.values(), *self._player_markers.values()):
            marker.update_glow()

    def _on_marker_selected(self, data, _marker) -> None:
        self._show_details(data)
        self._select_mapgenie_pin(data)

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

    def _show_marker_menu(self, data, global_position: QPointF) -> None:
        menu = QMenu(self)
        center_action = menu.addAction('Center on marker')
        copy_coordinates = menu.addAction('Copy coordinates')
        copy_identifier = menu.addAction('Copy identifier')
        menu.addSeparator()
        filter_action = menu.addAction('Filter by this guild')
        mapgenie_action = menu.addAction('View on interactive map')
        action = menu.exec(global_position.toPoint())
        if action == center_action:
            self._navigate_to(data)
        elif action == copy_coordinates:
            QApplication.clipboard().setText(
                f'{data.coordinates[0]}, {data.coordinates[1]}'
            )
        elif action == copy_identifier:
            identifier = data.player_uid if isinstance(data, PlayerMarkerData) else data.base_id
            QApplication.clipboard().setText(identifier)
        elif action == filter_action:
            self._set_guild_filter(data.guild_id, data.guild_name)
        elif action == mapgenie_action:
            self._select_mapgenie_pin(data)
            self.live_source_button.click()

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
        if isinstance(data, (BaseMarkerData, PlayerMarkerData)):
            self._show_marker_menu(data, QPointF(QCursor.pos()))

    def _on_tree_item_activated(self, item: QTreeWidgetItem, _column: int) -> None:
        data = item.data(0, Qt.UserRole)
        if isinstance(data, (BaseMarkerData, PlayerMarkerData)):
            self._navigate_to(data)
            self._show_details(data)

    def _navigate_to(self, data) -> None:
        if data.map_type != self.current_map:
            if data.map_type == 'tree':
                self.tree_button.click()
            else:
                self.world_button.click()
        marker = (
            self._player_markers.get(data.player_uid)
            if isinstance(data, PlayerMarkerData)
            else self._base_markers.get(data.base_id)
        )
        if marker:
            self.view.animate_to_marker(marker, zoom_level=10.0)

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

    def _select_mapgenie_pin(self, data) -> None:
        if isinstance(data, PlayerMarkerData):
            name = f'Player: {data.player_name}'
        else:
            name = f'{data.guild_name} - Base {data.base_position}'
        self._selected_mapgenie_pin = (name, data.coordinates)
        self.mapgenie_view.set_selected_location(name, data.coordinates)

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
            self._refresh_annotations()
