from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtGui import QResizeEvent
from PySide6.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QStyle,
    QTabWidget,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from palworld_aio.team_builder import (
    MAX_TEAM_SIZE,
    TeamHistory,
    TeamMember,
    TeamParseResult,
    analyze_team,
    build_team_share_url,
    load_team_members,
    normalize_team_ids,
    parse_team_share_url,
)
from palworld_aio.team_presets import TeamPreset, validate_team_presets
from palworld_aio.team_storage import SavedTeam, SavedTeamStore, TeamStorageError
from palworld_aio.ui.team_builder_widgets import TeamOverview, TeamSlots
from palworld_aio.ui.team_selector import MemberSelectorDialog, TeamNameDialog


class TeamBuilderTab(QWidget):
    status_message = Signal(str)

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        members: tuple[TeamMember, ...] | None = None,
        store: SavedTeamStore | None = None,
    ) -> None:
        super().__init__(parent)
        self.members = members or load_team_members()
        self.members_by_id = {member.member_id: member for member in self.members}
        self.presets = validate_team_presets(self.members_by_id)
        self.store = store or SavedTeamStore(self.members_by_id)
        self._team_ids: tuple[str, ...] = ()
        self.history = TeamHistory()
        self._setup_ui()
        self._connect_signals()
        self._populate_presets()
        self._refresh_saved_teams()
        self._refresh_team()

    @property
    def team_ids(self) -> tuple[str, ...]:
        return self._team_ids

    @property
    def current_share_url(self) -> str:
        return build_team_share_url(self._team_ids, self.members_by_id)

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.scroll = QScrollArea()
        self.scroll.setObjectName("teamBuilderScroll")
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        root.addWidget(self.scroll)

        content = QWidget()
        content.setObjectName("teamBuilderContent")
        self.scroll.setWidget(content)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(20, 16, 20, 24)
        layout.setSpacing(16)

        header = QGridLayout()
        header.setHorizontalSpacing(8)
        header.setVerticalSpacing(4)
        self.title_label = QLabel("Team Builder")
        self.title_label.setObjectName("teamPageTitle")
        header.addWidget(self.title_label, 0, 0, 1, 3)
        self.counter_label = QLabel()
        self.counter_label.setObjectName("teamCounter")
        self.counter_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        header.addWidget(self.counter_label, 1, 0, 1, 3)
        self.subtitle_label = QLabel(
            "Build an ordered party of up to five Pals and compare their "
            "partner-skill coverage."
        )
        self.subtitle_label.setObjectName("pageSubtitle")
        self.subtitle_label.setWordWrap(True)
        header.addWidget(self.subtitle_label, 2, 0, 1, 3)

        history_actions = QHBoxLayout()
        self.back_button = QToolButton()
        self.back_button.setObjectName("teamHistoryButton")
        self.back_button.setIcon(self.style().standardIcon(QStyle.SP_ArrowBack))
        self.back_button.setToolTip("Previous team")
        self.back_button.setAccessibleName("Restore previous team")
        history_actions.addWidget(self.back_button)
        self.forward_button = QToolButton()
        self.forward_button.setObjectName("teamHistoryButton")
        self.forward_button.setIcon(self.style().standardIcon(QStyle.SP_ArrowForward))
        self.forward_button.setToolTip("Next team")
        self.forward_button.setAccessibleName("Restore next team")
        history_actions.addWidget(self.forward_button)
        history_actions.addStretch()
        header.addLayout(history_actions, 3, 0)

        self.primary_actions_widget = QWidget()
        self.primary_actions_widget.setObjectName("teamPrimaryActions")
        self._primary_actions_layout = QGridLayout(self.primary_actions_widget)
        self._primary_actions_layout.setContentsMargins(0, 0, 0, 0)
        self._primary_actions_layout.setHorizontalSpacing(4)
        self._primary_actions_layout.setVerticalSpacing(4)
        self._primary_action_columns = 0
        self.clear_button = QPushButton("Clear Team")
        self.clear_button.setIcon(self.style().standardIcon(QStyle.SP_DialogResetButton))
        self.save_button = QPushButton("Save Team")
        self.save_button.setIcon(self.style().standardIcon(QStyle.SP_DialogSaveButton))
        self.share_button = QPushButton("Share Team")
        self.share_button.setIcon(self.style().standardIcon(QStyle.SP_DialogOpenButton))
        self._primary_action_buttons = (
            self.clear_button,
            self.save_button,
            self.share_button,
        )
        self._reflow_primary_actions(2)
        header.addWidget(self.primary_actions_widget, 4, 0, 1, 3, Qt.AlignRight)
        layout.addLayout(header)

        self.notice_label = QLabel()
        self.notice_label.setObjectName("teamNotice")
        self.notice_label.setAccessibleName("Team Builder notifications")
        self.notice_label.setWordWrap(True)
        self.notice_label.setVisible(False)
        layout.addWidget(self.notice_label)

        self.team_slots = TeamSlots()
        layout.addWidget(self.team_slots)

        divider = QFrame()
        divider.setObjectName("teamDivider")
        divider.setFrameShape(QFrame.HLine)
        layout.addWidget(divider)

        self.overview = TeamOverview()
        layout.addWidget(self.overview)

        library_title = QLabel("Team Library")
        library_title.setObjectName("teamSectionTitle")
        layout.addWidget(library_title)
        self.library_tabs = QTabWidget()
        self.library_tabs.setObjectName("teamLibraryTabs")
        self.library_tabs.addTab(self._build_preset_page(), "Presets")
        self.library_tabs.addTab(self._build_saved_page(), "Saved Teams")
        layout.addWidget(self.library_tabs)

    def _build_preset_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("teamLibraryPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(10, 10, 10, 10)
        self.preset_tree = QTreeWidget()
        self.preset_tree.setObjectName("teamPresetTree")
        self.preset_tree.setHeaderLabels(["Preset", "Goal", "Pals"])
        self.preset_tree.setRootIsDecorated(False)
        self.preset_tree.setUniformRowHeights(True)
        self.preset_tree.setSelectionMode(QAbstractItemView.SingleSelection)
        self.preset_tree.setAccessibleName("System team presets")
        layout.addWidget(self.preset_tree)
        row = QHBoxLayout()
        row.addStretch()
        self.apply_preset_button = QPushButton("Load Preset")
        self.apply_preset_button.setEnabled(False)
        row.addWidget(self.apply_preset_button)
        layout.addLayout(row)
        return page

    def _build_saved_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("teamLibraryPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(10, 10, 10, 10)
        self.saved_tree = QTreeWidget()
        self.saved_tree.setObjectName("teamSavedTree")
        self.saved_tree.setHeaderLabels(["Name", "Pals", "Updated"])
        self.saved_tree.setRootIsDecorated(False)
        self.saved_tree.setUniformRowHeights(True)
        self.saved_tree.setSelectionMode(QAbstractItemView.SingleSelection)
        self.saved_tree.setAccessibleName("Saved custom teams")
        layout.addWidget(self.saved_tree)
        self.saved_empty_label = QLabel("No custom teams saved yet.")
        self.saved_empty_label.setObjectName("teamEmptyText")
        self.saved_empty_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.saved_empty_label)
        row = QHBoxLayout()
        self.load_saved_button = QPushButton("Load")
        self.rename_saved_button = QPushButton("Rename")
        self.overwrite_saved_button = QPushButton("Overwrite")
        self.delete_saved_button = QPushButton("Delete")
        for button in (
            self.load_saved_button,
            self.rename_saved_button,
            self.overwrite_saved_button,
            self.delete_saved_button,
        ):
            button.setEnabled(False)
            row.addWidget(button)
        row.addStretch()
        layout.addLayout(row)
        return page

    def _connect_signals(self) -> None:
        self.team_slots.select_requested.connect(self._open_selector)
        self.team_slots.remove_requested.connect(self.remove_member)
        self.team_slots.move_requested.connect(self.move_member)
        self.clear_button.clicked.connect(self.clear_team)
        self.save_button.clicked.connect(self.save_current_team)
        self.share_button.clicked.connect(self.copy_share_url)
        self.back_button.clicked.connect(self.go_back)
        self.forward_button.clicked.connect(self.go_forward)

        self.preset_tree.itemSelectionChanged.connect(
            lambda: self.apply_preset_button.setEnabled(
                self.preset_tree.currentItem() is not None
            )
        )
        self.preset_tree.itemDoubleClicked.connect(
            lambda _item, _column: self._load_selected_preset()
        )
        self.apply_preset_button.clicked.connect(self._load_selected_preset)
        self.saved_tree.itemSelectionChanged.connect(self._saved_selection_changed)
        self.saved_tree.itemDoubleClicked.connect(
            lambda _item, _column: self._load_selected_saved_team()
        )
        self.load_saved_button.clicked.connect(self._load_selected_saved_team)
        self.rename_saved_button.clicked.connect(self._rename_selected_saved_team)
        self.overwrite_saved_button.clicked.connect(
            self._overwrite_selected_saved_team
        )
        self.delete_saved_button.clicked.connect(self._delete_selected_saved_team)

    def set_team(
        self,
        member_ids: Sequence[str],
        *,
        push_history: bool = True,
        message: str | None = None,
    ) -> tuple[str, ...]:
        normalized = normalize_team_ids(member_ids, self.members_by_id)
        if normalized == self._team_ids:
            if message:
                self._announce(message)
            return normalized
        self._team_ids = normalized
        if push_history:
            self.history.push(normalized)
        self._refresh_team()
        if message:
            self._announce(message)
        return normalized

    def set_slot_member(self, slot_index: int, member_id: str) -> bool:
        if member_id not in self.members_by_id or not 0 <= slot_index < MAX_TEAM_SIZE:
            return False
        team = list(self._team_ids)
        if slot_index < len(team):
            team[slot_index] = member_id
        elif len(team) < MAX_TEAM_SIZE:
            team.append(member_id)
        else:
            return False
        self.set_team(team)
        return True

    def remove_member(self, slot_index: int) -> None:
        if not 0 <= slot_index < len(self._team_ids):
            return
        team = list(self._team_ids)
        removed = self.members_by_id[team.pop(slot_index)].name
        self.set_team(team, message=f"Removed {removed} from the team.")

    def move_member(self, slot_index: int, offset: int) -> None:
        destination = slot_index + offset
        if not (
            0 <= slot_index < len(self._team_ids)
            and 0 <= destination < len(self._team_ids)
        ):
            return
        team = list(self._team_ids)
        team[slot_index], team[destination] = team[destination], team[slot_index]
        self.set_team(team)

    def clear_team(self, *, confirm: bool = True) -> bool:
        if not self._team_ids:
            return True
        if confirm and QMessageBox.question(
            self,
            "Clear team",
            "Remove every Pal from the current team?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        ) != QMessageBox.Yes:
            return False
        self.set_team((), message="Team cleared.")
        return True

    def apply_preset(self, preset_id: str, *, confirm: bool = True) -> bool:
        preset = next(
            (entry for entry in self.presets if entry.preset_id == preset_id),
            None,
        )
        if preset is None:
            return False
        if self._team_ids and tuple(preset.member_ids) != self._team_ids and confirm:
            if QMessageBox.question(
                self,
                "Replace current team",
                f"Replace the current team with {preset.name}?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            ) != QMessageBox.Yes:
                return False
        self.set_team(
            preset.member_ids,
            message=f"Loaded preset: {preset.name}.",
        )
        return True

    def save_current_team(self, name: str | None = None) -> SavedTeam | None:
        if not self._team_ids:
            self._announce("Select at least one Pal before saving a team.")
            return None
        if name is None:
            dialog = TeamNameDialog("Save Team", parent=self)
            if dialog.exec() != QDialog.Accepted:
                return None
            name = dialog.team_name
        try:
            saved = self.store.create(name, self._team_ids)
        except TeamStorageError as exc:
            self._show_storage_error(str(exc))
            return None
        self._refresh_saved_teams(select_id=saved.team_id)
        self.library_tabs.setCurrentIndex(1)
        self._announce(f"Saved team: {saved.name}.")
        return saved

    def load_saved_team(self, team_id: str, *, confirm: bool = True) -> bool:
        saved = self.store.get(team_id)
        if saved is None:
            return False
        if self._team_ids and saved.member_ids != self._team_ids and confirm:
            if QMessageBox.question(
                self,
                "Replace current team",
                f"Replace the current team with {saved.name}?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            ) != QMessageBox.Yes:
                return False
        self.set_team(saved.member_ids, message=f"Loaded saved team: {saved.name}.")
        return True

    def rename_saved_team(self, team_id: str, name: str) -> SavedTeam | None:
        try:
            saved = self.store.rename(team_id, name)
        except TeamStorageError as exc:
            self._show_storage_error(str(exc))
            return None
        self._refresh_saved_teams(select_id=team_id)
        self._announce(f"Renamed saved team to {saved.name}.")
        return saved

    def overwrite_saved_team(
        self,
        team_id: str,
        *,
        confirm: bool = True,
    ) -> SavedTeam | None:
        saved = self.store.get(team_id)
        if saved is None or not self._team_ids:
            return None
        if confirm and QMessageBox.question(
            self,
            "Overwrite saved team",
            f"Replace the members in {saved.name} with the current team?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        ) != QMessageBox.Yes:
            return None
        try:
            updated = self.store.overwrite(team_id, self._team_ids)
        except TeamStorageError as exc:
            self._show_storage_error(str(exc))
            return None
        self._refresh_saved_teams(select_id=team_id)
        self._announce(f"Updated saved team: {updated.name}.")
        return updated

    def delete_saved_team(self, team_id: str, *, confirm: bool = True) -> bool:
        saved = self.store.get(team_id)
        if saved is None:
            return False
        if confirm and QMessageBox.question(
            self,
            "Delete saved team",
            f"Delete {saved.name}?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        ) != QMessageBox.Yes:
            return False
        try:
            self.store.delete(team_id)
        except TeamStorageError as exc:
            self._show_storage_error(str(exc))
            return False
        self._refresh_saved_teams()
        self._announce(f"Deleted saved team: {saved.name}.")
        return True

    def load_share_url(self, value: str) -> TeamParseResult:
        result = parse_team_share_url(value, self.members_by_id)
        parts = []
        if result.invalid_identifiers:
            parts.append(
                f"Ignored {len(result.invalid_identifiers)} unknown Pal "
                f"{'identifier' if len(result.invalid_identifiers) == 1 else 'identifiers'}."
            )
        if result.truncated_count:
            parts.append(
                f"Ignored {result.truncated_count} Pal "
                f"{'entry' if result.truncated_count == 1 else 'entries'} beyond the five-slot limit."
            )
        if result.member_ids:
            parts.insert(0, "Shared team loaded.")
        elif not parts:
            parts.append("The shared link contains an empty team.")
        self.set_team(result.member_ids, message=" ".join(parts))
        return result

    def copy_share_url(self) -> bool:
        url = self.current_share_url
        clipboard = QApplication.clipboard()
        if clipboard is None:
            QMessageBox.information(self, "Share Team", f"Copy this link:\n\n{url}")
            return False
        try:
            clipboard.setText(url)
        except RuntimeError:
            QMessageBox.information(self, "Share Team", f"Copy this link:\n\n{url}")
            return False
        self._announce("Team share link copied to the clipboard.")
        return True

    def go_back(self) -> None:
        if not self.history.can_back:
            return
        self.set_team(
            self.history.back(),
            push_history=False,
            message="Restored previous team.",
        )

    def go_forward(self) -> None:
        if not self.history.can_forward:
            return
        self.set_team(
            self.history.forward(),
            push_history=False,
            message="Restored next team.",
        )

    def refresh(self) -> None:
        self._refresh_saved_teams()
        self._refresh_team()

    def refresh_labels(self) -> None:
        self._refresh_team()

    def resizeEvent(self, event: QResizeEvent) -> None:
        width = event.size().width()
        columns = 3 if width >= 720 else 2 if width >= 400 else 1
        self._reflow_primary_actions(columns)
        super().resizeEvent(event)

    def _reflow_primary_actions(self, columns: int) -> None:
        if columns == self._primary_action_columns:
            return
        self._primary_action_columns = columns
        for button in self._primary_action_buttons:
            self._primary_actions_layout.removeWidget(button)
        for index, button in enumerate(self._primary_action_buttons):
            self._primary_actions_layout.addWidget(
                button,
                index // columns,
                index % columns,
            )
        self._primary_actions_layout.invalidate()
        self.primary_actions_widget.updateGeometry()

    def _open_selector(self, slot_index: int) -> None:
        dialog = MemberSelectorDialog(
            self.members,
            self._team_ids,
            slot_index=slot_index,
            parent=self,
        )
        if dialog.exec() == QDialog.Accepted and dialog.selected_member_id:
            self.set_slot_member(slot_index, dialog.selected_member_id)

    def _refresh_team(self) -> None:
        self.counter_label.setText(f"{len(self._team_ids)} / {MAX_TEAM_SIZE} selected")
        self.team_slots.set_team(self._team_ids, self.members_by_id)
        self.overview.set_analysis(analyze_team(self._team_ids, self.members_by_id))
        has_team = bool(self._team_ids)
        self.clear_button.setEnabled(has_team)
        self.save_button.setEnabled(has_team)
        self.share_button.setEnabled(has_team)
        self.back_button.setEnabled(self.history.can_back)
        self.forward_button.setEnabled(self.history.can_forward)
        self._saved_selection_changed()

    def _populate_presets(self) -> None:
        self.preset_tree.clear()
        for preset in self.presets:
            names = [self.members_by_id[member_id].name for member_id in preset.member_ids]
            item = QTreeWidgetItem([preset.name, preset.goal, ", ".join(names)])
            item.setData(0, Qt.UserRole, preset.preset_id)
            item.setToolTip(0, preset.description)
            self.preset_tree.addTopLevelItem(item)
        for column in range(3):
            self.preset_tree.resizeColumnToContents(column)

    def _refresh_saved_teams(self, *, select_id: str | None = None) -> None:
        self.saved_tree.clear()
        selected_item = None
        for saved in self.store.teams:
            names = [
                self.members_by_id[member_id].name
                for member_id in saved.member_ids
                if member_id in self.members_by_id
            ]
            item = QTreeWidgetItem([
                saved.name,
                ", ".join(names),
                saved.updated_at[:10],
            ])
            item.setData(0, Qt.UserRole, saved.team_id)
            self.saved_tree.addTopLevelItem(item)
            if saved.team_id == select_id:
                selected_item = item
        self.saved_empty_label.setVisible(not self.store.teams)
        self.saved_tree.setVisible(bool(self.store.teams))
        for column in range(3):
            self.saved_tree.resizeColumnToContents(column)
        if selected_item is not None:
            self.saved_tree.setCurrentItem(selected_item)
        self._saved_selection_changed()

    def _selected_preset(self) -> TeamPreset | None:
        item = self.preset_tree.currentItem()
        if item is None:
            return None
        preset_id = str(item.data(0, Qt.UserRole))
        return next(
            (preset for preset in self.presets if preset.preset_id == preset_id),
            None,
        )

    def _selected_saved_id(self) -> str | None:
        item = self.saved_tree.currentItem()
        return str(item.data(0, Qt.UserRole)) if item is not None else None

    def _load_selected_preset(self) -> None:
        preset = self._selected_preset()
        if preset is not None:
            self.apply_preset(preset.preset_id)

    def _saved_selection_changed(self) -> None:
        selected = self._selected_saved_id() is not None
        self.load_saved_button.setEnabled(selected)
        self.rename_saved_button.setEnabled(selected)
        self.overwrite_saved_button.setEnabled(selected and bool(self._team_ids))
        self.delete_saved_button.setEnabled(selected)

    def _load_selected_saved_team(self) -> None:
        team_id = self._selected_saved_id()
        if team_id:
            self.load_saved_team(team_id)

    def _rename_selected_saved_team(self) -> None:
        team_id = self._selected_saved_id()
        saved = self.store.get(team_id or "")
        if saved is None:
            return
        dialog = TeamNameDialog(
            "Rename Saved Team",
            initial_name=saved.name,
            parent=self,
        )
        if dialog.exec() == QDialog.Accepted:
            self.rename_saved_team(saved.team_id, dialog.team_name)

    def _overwrite_selected_saved_team(self) -> None:
        team_id = self._selected_saved_id()
        if team_id:
            self.overwrite_saved_team(team_id)

    def _delete_selected_saved_team(self) -> None:
        team_id = self._selected_saved_id()
        if team_id:
            self.delete_saved_team(team_id)

    def _announce(self, message: str) -> None:
        self.notice_label.setText(message)
        self.notice_label.setVisible(bool(message))
        self.status_message.emit(message)
        QTimer.singleShot(8_000, self._clear_notice)

    def _clear_notice(self) -> None:
        self.notice_label.clear()
        self.notice_label.setVisible(False)

    def _show_storage_error(self, message: str) -> None:
        self._announce(message)
        QMessageBox.warning(self, "Saved Teams", message)
