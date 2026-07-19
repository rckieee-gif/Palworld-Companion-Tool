from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QStyle,
    QTabWidget,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from palworld_aio.breeding_analyzer import (
    BreedCombination,
    BreedingAnalyzer,
    BreedingPath,
    BreedingTreeNode,
    breeding_steps_from_tree,
    breeding_tree_depth,
)
from palworld_aio.game_data import GameDataError, load_breeding_data
from palworld_aio.ui.pal_assets import pal_pixmap, pixmap_for_icon
from palworld_aio.ui.pal_selector import select_pal
from palworld_aio.ui.parent_pair_selector import (
    build_parent_pair_options,
    select_parent_pair,
)
from palworld_aio.widgets.breeding_tree import BreedingTreeWidget
from palworld_aio.widgets.required_pals import RequiredPalsEditor


class BreedingTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.breeding_data: dict = {}
        self.pal_info: dict = {}
        self.analyzer = BreedingAnalyzer({})
        self._data_error = ''
        self.parent_a: str | None = None
        self.parent_b: str | None = None
        self.desired_child: str | None = None
        self.path_start: str | None = None
        self.path_target: str | None = None
        self._path_tree: BreedingTreeWidget | None = None
        self._path_steps_label: QLabel | None = None
        self._unique_pairs: set[tuple[str, str]] = set()
        self._load_data()
        self._setup_ui()
        self._refresh_all()

    def _load_data(self) -> None:
        try:
            self.breeding_data = load_breeding_data()
            self.analyzer = BreedingAnalyzer(self.breeding_data)
            self.pal_info = self.analyzer.pal_info
            self._unique_pairs = set()
            for combo in self.breeding_data.get('unique_combos', []):
                parent_a = combo.get('parent_a')
                parent_b = combo.get('parent_b')
                child = combo.get('child')
                if not parent_a or not parent_b or not child:
                    continue
                pair = self.analyzer.pair_key(parent_a, parent_b)
                if self.analyzer.pair_to_child.get(pair) == child:
                    self._unique_pairs.add(pair)
        except GameDataError as exc:
            self._data_error = str(exc)

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(10)

        heading = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel('Breeding Calculator')
        title.setObjectName('pageTitle')
        title_box.addWidget(title)
        subtitle = QLabel('Calculate offspring, find parents, and plan multi-generation paths.')
        subtitle.setObjectName('pageSubtitle')
        title_box.addWidget(subtitle)
        heading.addLayout(title_box)
        heading.addStretch()
        clear_button = QPushButton('Clear all')
        clear_button.setIcon(self.style().standardIcon(QStyle.SP_DialogResetButton))
        clear_button.clicked.connect(self.clear)
        heading.addWidget(clear_button)
        root.addLayout(heading)

        self.error_label = QLabel(self._data_error)
        self.error_label.setObjectName('mapWarning')
        self.error_label.setWordWrap(True)
        self.error_label.setVisible(bool(self._data_error))
        root.addWidget(self.error_label)

        self.tabs = QTabWidget()
        self.pair_page = self._create_pair_page()
        self.parents_page = self._create_parent_search_page()
        self.path_page = self._create_path_page()
        self.tabs.addTab(self.pair_page, 'Pair calculator')
        self.tabs.addTab(self.parents_page, 'Find parents')
        self.tabs.addTab(self.path_page, 'Path planner')
        root.addWidget(self.tabs, 1)

    def _create_pair_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(12, 16, 12, 12)
        layout.setSpacing(16)

        picker_row = QHBoxLayout()
        picker_row.addStretch()
        self.parent_a_button = self._pal_button('Select parent A')
        self.parent_a_button.clicked.connect(lambda: self._select_for('parent_a'))
        picker_row.addWidget(self.parent_a_button)
        plus = QLabel('+')
        plus.setObjectName('breedingOperator')
        plus.setAlignment(Qt.AlignCenter)
        plus.setFixedWidth(34)
        picker_row.addWidget(plus)
        self.parent_b_button = self._pal_button('Select parent B')
        self.parent_b_button.clicked.connect(lambda: self._select_for('parent_b'))
        picker_row.addWidget(self.parent_b_button)
        swap = QToolButton()
        swap.setIcon(self.style().standardIcon(QStyle.SP_BrowserReload))
        swap.setToolTip('Swap parents')
        swap.setFixedSize(34, 34)
        swap.clicked.connect(self._swap_parents)
        picker_row.addWidget(swap)
        arrow = QLabel('=')
        arrow.setObjectName('breedingOperator')
        arrow.setAlignment(Qt.AlignCenter)
        arrow.setFixedWidth(34)
        picker_row.addWidget(arrow)
        self.child_button = self._pal_button('Offspring')
        self.child_button.setEnabled(False)
        picker_row.addWidget(self.child_button)
        picker_row.addStretch()
        layout.addLayout(picker_row)

        self.pair_status = QLabel('Select two parents to calculate their offspring.')
        self.pair_status.setAlignment(Qt.AlignCenter)
        self.pair_status.setWordWrap(True)
        self.pair_status.setObjectName('breedingEmptyState')
        layout.addWidget(self.pair_status)
        layout.addStretch()
        return page

    def _create_parent_search_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(12, 14, 12, 12)
        layout.setSpacing(10)

        controls = QHBoxLayout()
        self.desired_child_button = self._pal_button('Select desired child')
        self.desired_child_button.clicked.connect(lambda: self._select_for('desired_child'))
        controls.addWidget(self.desired_child_button)
        self.parent_filter = QLineEdit()
        self.parent_filter.setPlaceholderText('Filter parent names or IDs')
        self.parent_filter.setClearButtonEnabled(True)
        self.parent_filter.textChanged.connect(self._refresh_parent_results)
        controls.addWidget(self.parent_filter, 1)
        self.parent_sort = QComboBox()
        self.parent_sort.addItem('Sort by name', 'name')
        self.parent_sort.addItem('Sort by combined power', 'power')
        self.parent_sort.addItem('Special combinations first', 'special')
        self.parent_sort.currentIndexChanged.connect(self._refresh_parent_results)
        controls.addWidget(self.parent_sort)
        layout.addLayout(controls)

        self.parent_count = QLabel('Select a desired child.')
        self.parent_count.setObjectName('pageSubtitle')
        layout.addWidget(self.parent_count)
        self.parent_results = QTreeWidget()
        self.parent_results.setHeaderLabels([
            'Parent A',
            'Parent B',
            'Pair type',
            'Combined power',
        ])
        self.parent_results.setRootIsDecorated(False)
        self.parent_results.setUniformRowHeights(True)
        self.parent_results.itemDoubleClicked.connect(self._use_parent_pair)
        layout.addWidget(self.parent_results, 1)
        return page

    def _create_path_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(12, 14, 12, 12)
        layout.setSpacing(10)

        controls = QFrame()
        controls.setObjectName('breedingControls')
        controls_layout = QVBoxLayout(controls)
        controls_layout.setContentsMargins(12, 12, 12, 12)
        controls_layout.setSpacing(10)
        first_row = QHBoxLayout()
        self.path_start_button = self._pal_button('Select starting Pal')
        self.path_start_button.clicked.connect(lambda: self._select_for('path_start'))
        first_row.addWidget(self.path_start_button)
        to_label = QLabel('to')
        to_label.setAlignment(Qt.AlignCenter)
        first_row.addWidget(to_label)
        self.path_target_button = self._pal_button('Select target Pal')
        self.path_target_button.clicked.connect(lambda: self._select_for('path_target'))
        first_row.addWidget(self.path_target_button)
        first_row.addSpacing(10)
        first_row.addWidget(QLabel('Max generations'))
        self.max_generations = QSpinBox()
        self.max_generations.setRange(1, 10)
        self.max_generations.setValue(6)
        self.max_generations.setFixedWidth(72)
        first_row.addWidget(self.max_generations)
        self.allow_unowned = QCheckBox('Allow additional partner Pals')
        self.allow_unowned.setChecked(True)
        self.allow_unowned.setToolTip(
            'When disabled, partners must be the starting or required Pals, or a Pal bred earlier in the path.'
        )
        first_row.addWidget(self.allow_unowned)
        first_row.addStretch()
        calculate = QPushButton('Calculate path')
        calculate.setIcon(self.style().standardIcon(QStyle.SP_CommandLink))
        calculate.clicked.connect(self._calculate_path)
        first_row.addWidget(calculate)
        controls_layout.addLayout(first_row)

        self.required_editor = RequiredPalsEditor(pixmap_for_icon)
        self.required_editor.set_pal_info(self.pal_info)
        self.required_editor.addRequested.connect(self._add_required_pal)
        controls_layout.addWidget(self.required_editor)
        layout.addWidget(controls)

        self.path_status = QLabel('Choose a starting Pal and a target Pal.')
        self.path_status.setObjectName('breedingEmptyState')
        self.path_status.setAlignment(Qt.AlignCenter)
        self.path_status.setWordWrap(True)
        layout.addWidget(self.path_status)

        self.path_scroll = QScrollArea()
        self.path_scroll.setWidgetResizable(True)
        self.path_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.path_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.path_scroll.setFrameShape(QFrame.NoFrame)
        self.path_result_host = QWidget()
        self.path_result_layout = QVBoxLayout(self.path_result_host)
        self.path_result_layout.setContentsMargins(0, 0, 0, 0)
        self.path_result_layout.setAlignment(Qt.AlignTop)
        self.path_scroll.setWidget(self.path_result_host)
        layout.addWidget(self.path_scroll, 1)
        return page

    @staticmethod
    def _pal_button(placeholder: str) -> QPushButton:
        button = QPushButton(placeholder)
        button.setProperty('palPicker', True)
        button.setIconSize(QSize(48, 48))
        button.setMinimumSize(190, 66)
        button.setMaximumWidth(280)
        button.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        return button

    def _select_for(self, role: str) -> None:
        species = select_pal(self.pal_info, self)
        if not species:
            return
        setattr(self, role, species)
        self._refresh_all()

    def _set_pal_button(
        self,
        button: QPushButton,
        species: str | None,
        placeholder: str,
    ) -> None:
        if not species:
            button.setText(placeholder)
            button.setIcon(QIcon())
            button.setToolTip('')
            return
        info = self.pal_info.get(species, {})
        name = str(info.get('name') or species)
        power = info.get('combi_rank', '?')
        button.setText(f'{name}\nBreeding power: {power}')
        button.setToolTip(species)
        pixmap = pal_pixmap(species, self.pal_info, 48)
        button.setIcon(QIcon(pixmap) if pixmap else QIcon())

    def _refresh_all(self) -> None:
        self._set_pal_button(self.parent_a_button, self.parent_a, 'Select parent A')
        self._set_pal_button(self.parent_b_button, self.parent_b, 'Select parent B')
        self._set_pal_button(
            self.desired_child_button,
            self.desired_child,
            'Select desired child',
        )
        self._set_pal_button(
            self.path_start_button,
            self.path_start,
            'Select starting Pal',
        )
        self._set_pal_button(
            self.path_target_button,
            self.path_target,
            'Select target Pal',
        )
        self._update_pair_result()
        self._refresh_parent_results()

    def _update_pair_result(self) -> None:
        if not self.parent_a or not self.parent_b:
            self._set_pal_button(self.child_button, None, 'Offspring')
            self.pair_status.setText('Select two parents to calculate their offspring.')
            return
        child = self.analyzer.pair_to_child.get(
            self.analyzer.pair_key(self.parent_a, self.parent_b)
        )
        if not child:
            self._set_pal_button(self.child_button, None, 'No result')
            self.pair_status.setText(
                'No breeding result is available for this pair in the bundled game data.'
            )
            return
        self._set_pal_button(self.child_button, child, 'Offspring')
        child_name = self.pal_info.get(child, {}).get('name', child)
        pair_type = (
            'Special breeding combination'
            if self.analyzer.pair_key(self.parent_a, self.parent_b) in self._unique_pairs
            else 'Breeding-power result'
        )
        self.pair_status.setText(f'{child_name} | {pair_type}')

    def _swap_parents(self) -> None:
        self.parent_a, self.parent_b = self.parent_b, self.parent_a
        self._refresh_all()

    def _refresh_parent_results(self, *_args) -> None:
        self.parent_results.clear()
        if not self.desired_child:
            self.parent_count.setText('Select a desired child.')
            return
        needle = self.parent_filter.text().strip().lower()
        records = []
        for parent_a, parent_b in self.analyzer.parents_by_child.get(self.desired_child, []):
            name_a = str(self.pal_info.get(parent_a, {}).get('name', parent_a))
            name_b = str(self.pal_info.get(parent_b, {}).get('name', parent_b))
            haystack = f'{name_a} {name_b} {parent_a} {parent_b}'.lower()
            if needle and needle not in haystack:
                continue
            power_a = int(self.pal_info.get(parent_a, {}).get('combi_rank', 0) or 0)
            power_b = int(self.pal_info.get(parent_b, {}).get('combi_rank', 0) or 0)
            is_special = self.analyzer.pair_key(parent_a, parent_b) in self._unique_pairs
            records.append((parent_a, parent_b, name_a, name_b, power_a + power_b, is_special))
        mode = self.parent_sort.currentData()
        if mode == 'power':
            records.sort(key=lambda record: (record[4], record[2].lower(), record[3].lower()))
        elif mode == 'special':
            records.sort(key=lambda record: (not record[5], record[2].lower(), record[3].lower()))
        else:
            records.sort(key=lambda record: (record[2].lower(), record[3].lower()))
        for parent_a, parent_b, name_a, name_b, power, is_special in records:
            item = QTreeWidgetItem([
                name_a,
                name_b,
                'Special' if is_special else 'Power formula',
                str(power),
            ])
            item.setData(0, Qt.UserRole, (parent_a, parent_b))
            icon_a = pal_pixmap(parent_a, self.pal_info, 28)
            if icon_a:
                item.setIcon(0, QIcon(icon_a))
            icon_b = pal_pixmap(parent_b, self.pal_info, 28)
            if icon_b:
                item.setIcon(1, QIcon(icon_b))
            self.parent_results.addTopLevelItem(item)
        target_name = self.pal_info.get(self.desired_child, {}).get('name', self.desired_child)
        self.parent_count.setText(f'{len(records)} parent pairs for {target_name}')
        for column in range(4):
            self.parent_results.resizeColumnToContents(column)

    def _use_parent_pair(self, item: QTreeWidgetItem, _column: int) -> None:
        pair = item.data(0, Qt.UserRole)
        if not pair:
            return
        self.parent_a, self.parent_b = pair
        self.tabs.setCurrentWidget(self.pair_page)
        self._refresh_all()

    def _add_required_pal(self) -> None:
        species = select_pal(self.pal_info, self)
        if species:
            self.required_editor.add_species(species)

    def _calculate_path(self) -> None:
        self._clear_path_result()
        if not self.path_start or not self.path_target:
            self.path_status.setText('Choose both a starting Pal and a target Pal.')
            return
        required = self.required_editor.required_species()
        path = self.analyzer.find_chain(
            self.path_start,
            self.path_target,
            self.max_generations.value(),
            required,
            allow_unowned_partners=self.allow_unowned.isChecked(),
        )
        if not path.reachable:
            self.path_status.setText(
                'No path was found within the selected generation limit and constraints.'
            )
            return
        if path.already_owned:
            self.path_status.setText('The starting Pal already matches the target Pal.')
        else:
            self.path_status.setText(
                f'Path found: {path.generation} generations, {len(path.steps)} breeding steps.'
            )
        owned = {self.path_start, *required}
        tree = BreedingTreeWidget(
            path,
            self.pal_info,
            owned,
            pixmap_for_icon,
            expandable_species=set(self.analyzer.parents_by_child),
        )
        tree.expansion_requested.connect(
            lambda node, widget=tree: self._expand_path_leaf(widget, node)
        )
        tree.tree_changed.connect(self._path_tree_changed)
        self._path_tree = tree
        self.path_result_layout.addWidget(tree)
        steps = QLabel(self._format_steps(path.steps))
        steps.setObjectName('breedingSteps')
        steps.setTextInteractionFlags(Qt.TextSelectableByMouse)
        steps.setWordWrap(True)
        steps.setVisible(bool(path.steps))
        self._path_steps_label = steps
        self.path_result_layout.addWidget(steps)

    def _expand_path_leaf(
        self,
        tree: BreedingTreeWidget,
        node: BreedingTreeNode,
    ) -> None:
        if not node.is_leaf or node.species in tree.owned_species:
            return
        pairs = tuple(self.analyzer.parents_by_child.get(node.species, ()))
        options = build_parent_pair_options(
            pairs,
            self.pal_info,
            tree.owned_species,
            self._unique_pairs,
            tree.blocked_species_for(node),
        )
        if not options:
            name = str(
                self.pal_info.get(node.species, {}).get('name') or node.species
            )
            self_only = bool(pairs) and all(
                parent_a == node.species and parent_b == node.species
                for parent_a, parent_b in pairs
            )
            message = (
                f'{name} can only be bred from two {name} parents in the '
                'current game data, so it cannot be expanded into a path '
                f'for obtaining your first {name}.'
                if self_only
                else (
                    f'No cycle-safe parent combination is available for {name} '
                    'in this branch.'
                )
            )
            QMessageBox.information(self, 'No breeding path', message)
            return
        pair = select_parent_pair(
            child_species=node.species,
            pairs=pairs,
            pal_info=self.pal_info,
            owned_species=tree.owned_species,
            unique_pairs=self._unique_pairs,
            blocked_species=tree.blocked_species_for(node),
            parent=self,
            options=options,
        )
        if pair is None:
            return
        if self.analyzer.pair_to_child.get(
            self.analyzer.pair_key(*pair)
        ) != node.species:
            QMessageBox.warning(
                self,
                'Invalid breeding pair',
                'The selected pair no longer produces this Pal in the bundled data.',
            )
            return
        try:
            tree.expand_leaf(node, *pair)
        except ValueError as exc:
            QMessageBox.warning(self, 'Cannot add branch', str(exc))

    def _path_tree_changed(self, root: BreedingTreeNode) -> None:
        steps = breeding_steps_from_tree(root)
        generation = breeding_tree_depth(root)
        self.path_status.setText(
            f'Expanded path: {generation} generations, '
            f'{len(steps)} breeding steps.'
        )
        if self._path_steps_label is not None:
            self._path_steps_label.setText(self._format_steps(steps))
            self._path_steps_label.setVisible(bool(steps))

    def _format_steps(self, steps: tuple[BreedCombination, ...]) -> str:
        lines = []
        for index, step in enumerate(steps, start=1):
            parent_a = self.pal_info.get(step.parent_a, {}).get('name', step.parent_a)
            parent_b = self.pal_info.get(step.parent_b, {}).get('name', step.parent_b)
            child = self.pal_info.get(step.child, {}).get('name', step.child)
            lines.append(f'{index}. {parent_a} + {parent_b} = {child}')
        return '\n'.join(lines)

    def _clear_path_result(self) -> None:
        self._path_tree = None
        self._path_steps_label = None
        while self.path_result_layout.count():
            item = self.path_result_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def clear(self) -> None:
        self.parent_a = None
        self.parent_b = None
        self.desired_child = None
        self.path_start = None
        self.path_target = None
        self.parent_filter.clear()
        self.required_editor.clear()
        self._clear_path_result()
        self.path_status.setText('Choose a starting Pal and a target Pal.')
        self._refresh_all()

    def refresh(self) -> None:
        return

    def refresh_labels(self) -> None:
        self.required_editor.refresh_labels()
