from __future__ import annotations

from collections import Counter

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListView,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QStackedWidget,
    QStyle,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from palworld_aio.team_builder import (
    EffectCategory,
    TeamMember,
    filter_team_members,
)
from palworld_aio.ui.pal_assets import pixmap_for_icon
from palworld_aio.team_storage import MAX_TEAM_NAME_LENGTH


class MemberSelectorDialog(QDialog):
    PAGE_SIZE = 60

    def __init__(
        self,
        members: tuple[TeamMember, ...],
        team_ids: tuple[str, ...],
        *,
        slot_index: int,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.members = members
        self.team_counts = Counter(team_ids)
        self.slot_index = slot_index
        self.selected_member_id: str | None = None
        self._render_limit = self.PAGE_SIZE
        self._visible_members: tuple[TeamMember, ...] = ()
        self.setObjectName("teamMemberSelector")
        self.setWindowTitle(f"Select a Pal for slot {slot_index + 1}")
        self.resize(920, 700)
        self.setMinimumSize(680, 540)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(8)

        self.search = QLineEdit()
        self.search.setObjectName("teamMemberSearch")
        self.search.setPlaceholderText("Search Pal name, partner skill, or effect")
        self.search.setClearButtonEnabled(True)
        self.search.setAccessibleName("Search available Pals")
        layout.addWidget(self.search)

        filters = QHBoxLayout()
        self.element_filter = QComboBox()
        self.element_filter.setAccessibleName("Filter by element")
        self.element_filter.addItem("All elements", None)
        for element in sorted({value for member in members for value in member.elements}):
            self.element_filter.addItem(element, element)
        filters.addWidget(self.element_filter)

        self.effect_filter = QComboBox()
        self.effect_filter.setAccessibleName("Filter by partner effect")
        self.effect_filter.addItem("All effects", None)
        available_categories = {
            category for member in members for category in member.effect_categories
        }
        for category in EffectCategory:
            if category in available_categories:
                self.effect_filter.addItem(category.value, category)
        filters.addWidget(self.effect_filter)

        self.work_filter = QComboBox()
        self.work_filter.setAccessibleName("Filter by work suitability")
        self.work_filter.addItem("All work", None)
        for work in sorted({
            capability.name
            for member in members
            for capability in member.work_capabilities
        }):
            self.work_filter.addItem(work, work)
        filters.addWidget(self.work_filter)

        self.clear_filters_button = QToolButton()
        self.clear_filters_button.setIcon(
            self.style().standardIcon(QStyle.SP_DialogResetButton)
        )
        self.clear_filters_button.setToolTip("Clear search and filters")
        self.clear_filters_button.setAccessibleName("Clear member search and filters")
        self.clear_filters_button.clicked.connect(self.clear_filters)
        filters.addWidget(self.clear_filters_button)
        layout.addLayout(filters)

        self.count_label = QLabel()
        self.count_label.setObjectName("teamSelectorCount")
        layout.addWidget(self.count_label)

        self.results = QListWidget()
        self.results.setObjectName("teamMemberResults")
        self.results.setViewMode(QListView.IconMode)
        self.results.setResizeMode(QListView.Adjust)
        self.results.setMovement(QListView.Static)
        self.results.setWrapping(True)
        self.results.setWordWrap(True)
        self.results.setUniformItemSizes(True)
        self.results.setIconSize(QSize(64, 64))
        self.results.setGridSize(QSize(172, 184))
        self.results.setAccessibleName("Available Pals")

        empty = QLabel("No Pals match this search and filter combination.")
        empty.setObjectName("teamEmptyText")
        empty.setAlignment(Qt.AlignCenter)
        empty.setWordWrap(True)
        self.results_stack = QStackedWidget()
        self.results_stack.addWidget(self.results)
        self.results_stack.addWidget(empty)
        layout.addWidget(self.results_stack, 1)

        self.load_more_button = QPushButton("Load more")
        self.load_more_button.setObjectName("teamLoadMoreButton")
        self.load_more_button.clicked.connect(self._load_more)
        layout.addWidget(self.load_more_button, 0, Qt.AlignHCenter)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.Cancel | QDialogButtonBox.Ok
        )
        self.buttons.button(QDialogButtonBox.Ok).setText("Select")
        self.buttons.button(QDialogButtonBox.Ok).setEnabled(False)
        self.buttons.accepted.connect(self._accept_selection)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

        self.search.textChanged.connect(self._filters_changed)
        self.element_filter.currentIndexChanged.connect(self._filters_changed)
        self.effect_filter.currentIndexChanged.connect(self._filters_changed)
        self.work_filter.currentIndexChanged.connect(self._filters_changed)
        self.results.itemSelectionChanged.connect(self._selection_changed)
        self.results.itemActivated.connect(lambda _item: self._accept_selection())
        self._populate()
        self.search.setFocus()

    @property
    def visible_members(self) -> tuple[TeamMember, ...]:
        return self._visible_members

    def clear_filters(self) -> None:
        self.search.clear()
        self.element_filter.setCurrentIndex(0)
        self.effect_filter.setCurrentIndex(0)
        self.work_filter.setCurrentIndex(0)

    def _filters_changed(self, *_args) -> None:
        self._render_limit = self.PAGE_SIZE
        self._populate()

    def _populate(self) -> None:
        category = self.effect_filter.currentData()
        self._visible_members = filter_team_members(
            self.members,
            query=self.search.text().strip(),
            element=self.element_filter.currentData(),
            category=category if isinstance(category, EffectCategory) else None,
            work=self.work_filter.currentData(),
        )
        visible = self._visible_members[:self._render_limit]
        self.results.clear()
        for member in visible:
            quantity = self.team_counts.get(member.member_id, 0)
            team_state = f"\nIn team x{quantity}" if quantity else ""
            item = QListWidgetItem(
                f"{member.name}\n{' / '.join(member.elements) or 'Unknown'}"
                f" | Rarity {member.rarity}\n{member.partner_skill}{team_state}"
            )
            item.setData(Qt.UserRole, member.member_id)
            item.setToolTip(member.partner_description)
            item.setStatusTip(member.partner_description)
            pixmap = pixmap_for_icon(member.icon, 64)
            if pixmap:
                item.setIcon(QIcon(pixmap))
            if quantity:
                font = QFont(item.font())
                font.setBold(True)
                item.setFont(font)
            self.results.addItem(item)
        self.count_label.setText(
            f"Showing {len(visible)} of {len(self._visible_members)} Pals"
        )
        self.results_stack.setCurrentIndex(0 if visible else 1)
        self.load_more_button.setVisible(len(visible) < len(self._visible_members))
        self._selection_changed()

    def _load_more(self) -> None:
        self._render_limit += self.PAGE_SIZE
        self._populate()

    def _selection_changed(self) -> None:
        self.buttons.button(QDialogButtonBox.Ok).setEnabled(
            self.results.currentItem() is not None
        )

    def _accept_selection(self) -> None:
        item = self.results.currentItem()
        if item is None:
            return
        self.selected_member_id = str(item.data(Qt.UserRole))
        self.accept()


class TeamNameDialog(QDialog):
    def __init__(
        self,
        title: str,
        *,
        initial_name: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(420)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.name_edit = QLineEdit(initial_name)
        self.name_edit.setMaxLength(MAX_TEAM_NAME_LENGTH)
        self.name_edit.setPlaceholderText("Team name")
        self.name_edit.setAccessibleName("Team name")
        form.addRow("Name", self.name_edit)
        layout.addLayout(form)
        self.error_label = QLabel()
        self.error_label.setObjectName("teamFormError")
        self.error_label.setWordWrap(True)
        layout.addWidget(self.error_label)
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.Cancel | QDialogButtonBox.Save
        )
        self.buttons.button(QDialogButtonBox.Save).setEnabled(bool(initial_name.strip()))
        self.buttons.accepted.connect(self._validate)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
        self.name_edit.textChanged.connect(
            lambda text: self.buttons.button(QDialogButtonBox.Save).setEnabled(
                bool(text.strip())
            )
        )
        self.name_edit.selectAll()
        self.name_edit.setFocus()

    @property
    def team_name(self) -> str:
        return " ".join(self.name_edit.text().split())

    def _validate(self) -> None:
        if not self.team_name:
            self.error_label.setText("Enter a team name.")
            return
        self.accept()
