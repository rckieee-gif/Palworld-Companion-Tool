from __future__ import annotations

from collections import Counter
from collections.abc import Mapping

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QIcon, QResizeEvent
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QStyle,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from palworld_aio.team_builder import MAX_TEAM_SIZE, TeamAnalysis, TeamMember
from palworld_aio.ui.pal_assets import pixmap_for_icon


class TeamSlot(QFrame):
    select_requested = Signal(int)
    remove_requested = Signal(int)
    move_requested = Signal(int, int)

    def __init__(self, index: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.index = index
        self.member: TeamMember | None = None
        self.setObjectName("teamSlot")
        self.setProperty("slotState", "empty")
        self.setMinimumWidth(148)
        self.setMinimumHeight(218)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(5)

        top = QHBoxLayout()
        self.slot_label = QLabel(f"Slot {index + 1}")
        self.slot_label.setObjectName("teamSlotNumber")
        top.addWidget(self.slot_label)
        top.addStretch()
        self.quantity_label = QLabel()
        self.quantity_label.setObjectName("teamQuantityBadge")
        self.quantity_label.setVisible(False)
        top.addWidget(self.quantity_label)
        self.remove_button = QToolButton()
        self.remove_button.setObjectName("teamSlotAction")
        self.remove_button.setIcon(self.style().standardIcon(QStyle.SP_DialogCloseButton))
        self.remove_button.setToolTip("Remove this Pal")
        self.remove_button.setAccessibleName(f"Remove Pal from slot {index + 1}")
        self.remove_button.clicked.connect(lambda: self.remove_requested.emit(self.index))
        self.remove_button.setVisible(False)
        top.addWidget(self.remove_button)
        layout.addLayout(top)

        self.member_button = QToolButton()
        self.member_button.setObjectName("teamMemberButton")
        self.member_button.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        self.member_button.setIconSize(QSize(76, 76))
        self.member_button.setMinimumHeight(116)
        self.member_button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.member_button.clicked.connect(lambda: self.select_requested.emit(self.index))
        layout.addWidget(self.member_button)

        self.elements_label = QLabel()
        self.elements_label.setObjectName("teamSlotMeta")
        self.elements_label.setAlignment(Qt.AlignCenter)
        self.elements_label.setWordWrap(True)
        layout.addWidget(self.elements_label)

        self.skill_label = QLabel()
        self.skill_label.setObjectName("teamSlotSkill")
        self.skill_label.setAlignment(Qt.AlignCenter)
        self.skill_label.setWordWrap(True)
        layout.addWidget(self.skill_label)

        movement = QHBoxLayout()
        movement.addStretch()
        self.left_button = QToolButton()
        self.left_button.setObjectName("teamSlotAction")
        self.left_button.setIcon(self.style().standardIcon(QStyle.SP_ArrowLeft))
        self.left_button.setToolTip("Move Pal left")
        self.left_button.setAccessibleName(f"Move slot {index + 1} left")
        self.left_button.clicked.connect(lambda: self.move_requested.emit(self.index, -1))
        movement.addWidget(self.left_button)
        self.right_button = QToolButton()
        self.right_button.setObjectName("teamSlotAction")
        self.right_button.setIcon(self.style().standardIcon(QStyle.SP_ArrowRight))
        self.right_button.setToolTip("Move Pal right")
        self.right_button.setAccessibleName(f"Move slot {index + 1} right")
        self.right_button.clicked.connect(lambda: self.move_requested.emit(self.index, 1))
        movement.addWidget(self.right_button)
        movement.addStretch()
        layout.addLayout(movement)
        self.set_member(None, 0, 0)

    def set_member(
        self,
        member: TeamMember | None,
        quantity: int,
        selected_count: int,
    ) -> None:
        self.member = member
        self.setProperty("slotState", "filled" if member else "empty")
        self.style().unpolish(self)
        self.style().polish(self)
        if member is None:
            self.member_button.setText("Select Pal")
            self.member_button.setIcon(
                self.style().standardIcon(QStyle.SP_FileDialogNewFolder)
            )
            self.member_button.setToolTip(f"Select a Pal for slot {self.index + 1}")
            self.member_button.setAccessibleName(
                f"Select a Pal for empty team slot {self.index + 1}"
            )
            self.elements_label.setText("Empty slot")
            self.skill_label.clear()
            self.quantity_label.setVisible(False)
            self.remove_button.setVisible(False)
            self.left_button.setVisible(False)
            self.right_button.setVisible(False)
            return

        pixmap = pixmap_for_icon(member.icon, 76)
        self.member_button.setIcon(QIcon(pixmap) if pixmap else QIcon())
        self.member_button.setText(member.name)
        self.member_button.setToolTip(f"Replace {member.name}")
        self.member_button.setAccessibleName(
            f"Replace {member.name} in team slot {self.index + 1}"
        )
        self.elements_label.setText(" / ".join(member.elements) or "Unknown element")
        self.skill_label.setText(member.partner_skill or "No partner skill listed")
        self.skill_label.setToolTip(member.partner_description)
        self.quantity_label.setText(f"x{quantity}")
        self.quantity_label.setVisible(quantity > 1)
        self.remove_button.setVisible(True)
        self.left_button.setVisible(True)
        self.right_button.setVisible(True)
        self.left_button.setEnabled(self.index > 0)
        self.right_button.setEnabled(self.index + 1 < selected_count)


class TeamSlots(QWidget):
    select_requested = Signal(int)
    remove_requested = Signal(int)
    move_requested = Signal(int, int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("teamSlots")
        self._columns = 0
        self._layout = QGridLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setHorizontalSpacing(8)
        self._layout.setVerticalSpacing(8)
        self.slots = [TeamSlot(index, self) for index in range(MAX_TEAM_SIZE)]
        for slot in self.slots:
            slot.select_requested.connect(self.select_requested)
            slot.remove_requested.connect(self.remove_requested)
            slot.move_requested.connect(self.move_requested)
        self._reflow(5)

    @property
    def columns(self) -> int:
        return self._columns

    def set_team(
        self,
        member_ids: tuple[str, ...],
        members_by_id: Mapping[str, TeamMember],
    ) -> None:
        counts = Counter(member_ids)
        for position, slot in enumerate(self.slots):
            member_id = member_ids[position] if position < len(member_ids) else None
            member = members_by_id.get(member_id) if member_id is not None else None
            quantity = counts[member_id] if member_id is not None else 0
            slot.set_member(member, quantity, len(member_ids))

    def resizeEvent(self, event: QResizeEvent) -> None:
        width = event.size().width()
        columns = 5 if width >= 860 else 3 if width >= 620 else 2 if width >= 350 else 1
        self._reflow(columns)
        super().resizeEvent(event)

    def _reflow(self, columns: int) -> None:
        if columns == self._columns and self._layout.count() == MAX_TEAM_SIZE:
            return
        self._columns = columns
        for slot in self.slots:
            self._layout.removeWidget(slot)
        for index, slot in enumerate(self.slots):
            self._layout.addWidget(slot, index // columns, index % columns)
        self._layout.invalidate()
        self.updateGeometry()


class TeamOverview(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("teamOverview")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        title = QLabel("Team Overview")
        title.setObjectName("teamSectionTitle")
        layout.addWidget(title)

        self._summary_layout = QGridLayout()
        self._summary_layout.setContentsMargins(0, 0, 0, 0)
        self._summary_layout.setHorizontalSpacing(8)
        self._summary_layout.setVerticalSpacing(6)
        self.selected_label = QLabel()
        self.selected_label.setObjectName("teamMetric")
        self.element_label = QLabel()
        self.element_label.setObjectName("teamMetric")
        self.element_label.setWordWrap(True)
        self.duplicate_label = QLabel()
        self.duplicate_label.setObjectName("teamMetric")
        self.duplicate_label.setWordWrap(True)
        self._summary_columns = 0
        self._reflow_summary(1)
        layout.addLayout(self._summary_layout)

        self.work_label = QLabel()
        self.work_label.setObjectName("teamOverviewText")
        self.work_label.setWordWrap(True)
        layout.addWidget(self.work_label)

        self.effects = QTreeWidget()
        self.effects.setObjectName("teamEffects")
        self.effects.setHeaderLabels(["Category / Pal", "Partner Skill", "Effect", "Stacking"])
        self.effects.setRootIsDecorated(True)
        self.effects.setUniformRowHeights(False)
        self.effects.setAlternatingRowColors(True)
        self.effects.setMinimumHeight(210)
        layout.addWidget(self.effects)

        self.empty_label = QLabel()
        self.empty_label.setObjectName("teamEmptyText")
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.empty_label.setWordWrap(True)
        layout.addWidget(self.empty_label)

        self.notes_label = QLabel()
        self.notes_label.setObjectName("teamOverviewText")
        self.notes_label.setWordWrap(True)
        layout.addWidget(self.notes_label)

    def set_analysis(self, analysis: TeamAnalysis) -> None:
        self.selected_label.setText(
            f"{analysis.selected_count} selected | {analysis.unique_count} unique"
        )
        elements = ", ".join(
            f"{name} x{count}" for name, count in analysis.element_distribution
        ) or "None"
        self.element_label.setText(f"Elements: {elements}")
        duplicates = ", ".join(
            f"{name} x{count}" for name, count in analysis.duplicate_counts
        ) or "None"
        self.duplicate_label.setText(f"Duplicates: {duplicates}")
        work = ", ".join(
            f"{name} ({count})" for name, count in analysis.work_distribution
        ) or "None"
        self.work_label.setText(f"Work coverage: {work}")

        self.effects.clear()
        for summary in analysis.effects:
            category_item = QTreeWidgetItem([
                summary.category.value,
                f"{len(summary.contributions)} partner skills",
                "",
                "",
            ])
            category_item.setExpanded(True)
            self.effects.addTopLevelItem(category_item)
            for contribution in summary.contributions:
                quantity = f" x{contribution.quantity}" if contribution.quantity > 1 else ""
                child = QTreeWidgetItem([
                    f"{contribution.member_name}{quantity}",
                    contribution.partner_skill,
                    contribution.description,
                    contribution.stacking,
                ])
                category_item.addChild(child)
        self.effects.setVisible(bool(analysis.effects))
        self.empty_label.setVisible(not analysis.effects)
        self.empty_label.setText(
            "Add Pals to see grouped partner skills and coverage."
            if not analysis.effects else ""
        )
        self.effects.resizeColumnToContents(0)
        self.effects.resizeColumnToContents(1)
        self.effects.resizeColumnToContents(3)
        self.notes_label.setText("\n".join(
            f"- {note}" for note in analysis.coverage_notes
        ))

    def resizeEvent(self, event: QResizeEvent) -> None:
        self._reflow_summary(3 if event.size().width() >= 680 else 1)
        super().resizeEvent(event)

    def _reflow_summary(self, columns: int) -> None:
        if columns == self._summary_columns:
            return
        self._summary_columns = columns
        labels = (self.selected_label, self.element_label, self.duplicate_label)
        for label in labels:
            self._summary_layout.removeWidget(label)
        for index, label in enumerate(labels):
            self._summary_layout.addWidget(label, index // columns, index % columns)
        self._summary_layout.invalidate()
        self.updateGeometry()
