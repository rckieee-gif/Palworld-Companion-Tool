from __future__ import annotations

import logging

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QCompleter,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStyle,
    QVBoxLayout,
    QWidget,
)

from palworld_aio.game_data import GameDataError
from palworld_aio.pal_stats_repository import (
    PalLookupResult,
    PalLookupStatus,
    PalStatsRepository,
)
from palworld_aio.stat_calculator import (
    CalculationStatus,
    DEFAULT_FORMULA_PROFILE,
    FormulaProfile,
    PalBaseStats,
    PalStatEstimate,
    PalStatInput,
    PalStatResult,
    StatKind,
    StatModifiers,
    calculate_pal_stats,
)


LOGGER = logging.getLogger(__name__)


class StatsCalculatorTab(QWidget):
    """Manual Pal stat-quality calculator backed by bundled base stats."""

    status_message = Signal(str)

    _FIELD_DEFAULTS = {
        'level': '1',
        'current_hp': '',
        'current_attack': '',
        'current_defense': '',
        'hp_soul_enhancement': '0',
        'attack_soul_enhancement': '0',
        'defense_soul_enhancement': '0',
        'condenser_rank': '0',
        'hp_passive_percent': '0',
        'attack_passive_percent': '0',
        'defense_passive_percent': '0',
        'hp_other_percent': '0',
        'attack_other_percent': '0',
        'defense_other_percent': '0',
        'base_hp': '',
        'base_attack': '',
        'base_defense': '',
    }

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        repository: PalStatsRepository | None = None,
        profile: FormulaProfile = DEFAULT_FORMULA_PROFILE,
    ) -> None:
        super().__init__(parent)
        self.profile = profile
        self._data_error = ''
        try:
            self.repository = repository or PalStatsRepository.from_game_data()
        except GameDataError as exc:
            self.repository = PalStatsRepository(())
            self._data_error = str(exc)
        self._fields: dict[str, QLineEdit] = {}
        self._field_errors: dict[str, QLabel] = {}
        self._result_widgets: dict[StatKind, dict[str, QLabel]] = {}
        self._has_results = False
        self._resetting = False
        self._setup_ui()
        self._connect_inputs()
        self._update_pal_data_state()

    def _setup_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setObjectName('statsCalculatorScroll')
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        content = QWidget()
        content.setObjectName('statsCalculatorContent')
        root = QVBoxLayout(content)
        root.setContentsMargins(22, 18, 22, 22)
        root.setSpacing(14)

        heading = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel('Palworld Stats Calculator')
        title.setObjectName('statsPageTitle')
        title_box.addWidget(title)
        subtitle = QLabel(
            'Estimate HP, Attack, and Defense IV ranges from the stats shown in game.'
        )
        subtitle.setObjectName('pageSubtitle')
        subtitle.setWordWrap(True)
        title_box.addWidget(subtitle)
        heading.addLayout(title_box, 1)
        profile_label = QLabel(self.profile.display_name)
        profile_label.setObjectName('statsProfileBadge')
        profile_label.setToolTip('Formula profiles keep patch-specific constants outside the UI.')
        heading.addWidget(profile_label, 0, Qt.AlignTop)
        root.addLayout(heading)

        notice_text = self.profile.incomplete_reason
        if self._data_error:
            notice_text = f'{self._data_error} {notice_text}'.strip()
        self.formula_notice = QLabel(notice_text)
        self.formula_notice.setObjectName('statsFormulaNotice')
        self.formula_notice.setWordWrap(True)
        self.formula_notice.setVisible(bool(notice_text))
        root.addWidget(self.formula_notice)

        columns = QHBoxLayout()
        columns.setSpacing(14)
        inputs_column = QVBoxLayout()
        inputs_column.setSpacing(10)
        results_column = QVBoxLayout()
        results_column.setSpacing(10)

        inputs_column.addWidget(self._create_pal_information_section())
        inputs_column.addWidget(self._create_current_stats_section())
        inputs_column.addWidget(self._create_enhancements_section())
        inputs_column.addWidget(self._create_passive_section())
        inputs_column.addWidget(self._create_other_section())
        self.manual_base_section = self._create_manual_base_section()
        inputs_column.addWidget(self.manual_base_section)

        actions = QHBoxLayout()
        self.calculate_button = QPushButton('Calculate')
        self.calculate_button.setObjectName('statsCalculateButton')
        self.calculate_button.setIcon(self.style().standardIcon(QStyle.SP_CommandLink))
        self.calculate_button.clicked.connect(self._calculate)
        actions.addWidget(self.calculate_button)
        self.reset_button = QPushButton('Reset')
        self.reset_button.setIcon(self.style().standardIcon(QStyle.SP_DialogResetButton))
        self.reset_button.clicked.connect(self.reset)
        actions.addWidget(self.reset_button)
        actions.addStretch()
        inputs_column.addLayout(actions)
        inputs_column.addStretch()

        results_title = QLabel('Results')
        results_title.setObjectName('statsSectionHeading')
        results_column.addWidget(results_title)
        results_help = QLabel(
            'A range is shown when the same displayed integer can come from multiple IVs.'
        )
        results_help.setObjectName('pageSubtitle')
        results_help.setWordWrap(True)
        results_column.addWidget(results_help)

        self.stale_label = QLabel('Inputs changed. These results are out of date.')
        self.stale_label.setObjectName('statsStaleNotice')
        self.stale_label.setWordWrap(True)
        self.stale_label.setVisible(False)
        results_column.addWidget(self.stale_label)

        for stat, label in (
            (StatKind.HP, 'HP IV'),
            (StatKind.ATTACK, 'Attack IV'),
            (StatKind.DEFENSE, 'Defense IV'),
        ):
            results_column.addWidget(self._create_result_card(stat, label))

        self.overall_card = QFrame()
        self.overall_card.setObjectName('statsOverallCard')
        overall_layout = QVBoxLayout(self.overall_card)
        overall_layout.setContentsMargins(14, 12, 14, 12)
        overall_title = QLabel('Overall summary')
        overall_title.setObjectName('statsCardTitle')
        overall_layout.addWidget(overall_title)
        self.average_label = QLabel('Average IV: \u2014')
        self.average_label.setObjectName('statsOverallValue')
        overall_layout.addWidget(self.average_label)
        self.perfect_label = QLabel('Perfect stats: \u2014')
        self.perfect_label.setObjectName('statsCardMeta')
        overall_layout.addWidget(self.perfect_label)
        self.overall_rating_label = QLabel('Overall rating: Unable to determine')
        self.overall_rating_label.setObjectName('statsCardMeta')
        overall_layout.addWidget(self.overall_rating_label)
        self.overall_note = QLabel('Calculate all three stats to see a summary.')
        self.overall_note.setObjectName('statsCardNote')
        self.overall_note.setWordWrap(True)
        overall_layout.addWidget(self.overall_note)
        results_column.addWidget(self.overall_card)
        results_column.addStretch()

        inputs_host = QWidget()
        inputs_host.setLayout(inputs_column)
        inputs_host.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        results_host = QWidget()
        results_host.setLayout(results_column)
        results_host.setMinimumWidth(330)
        results_host.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        columns.addWidget(inputs_host, 3)
        columns.addWidget(results_host, 2)
        root.addLayout(columns)
        root.addStretch()

        scroll.setWidget(content)
        outer.addWidget(scroll)

    def _create_section(self, title: str, help_text: str = '') -> tuple[QFrame, QFormLayout]:
        section = QFrame()
        section.setObjectName('statsSection')
        layout = QVBoxLayout(section)
        layout.setContentsMargins(14, 12, 14, 13)
        layout.setSpacing(7)
        heading = QLabel(title)
        heading.setObjectName('statsSectionHeading')
        layout.addWidget(heading)
        if help_text:
            help_label = QLabel(help_text)
            help_label.setObjectName('statsSectionHelp')
            help_label.setWordWrap(True)
            layout.addWidget(help_label)
        form_host = QWidget()
        form_host.setObjectName('statsSectionBody')
        form = QFormLayout(form_host)
        form.setContentsMargins(0, 3, 0, 0)
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(8)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        layout.addWidget(form_host)
        return section, form

    def _field_widget(
        self,
        field_name: str,
        *,
        placeholder: str = '',
        tooltip: str = '',
    ) -> QWidget:
        host = QWidget()
        host.setObjectName('statsFieldHost')
        layout = QVBoxLayout(host)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        edit = QLineEdit(self._FIELD_DEFAULTS.get(field_name, ''))
        edit.setObjectName(f'stats_{field_name}')
        edit.setPlaceholderText(placeholder)
        edit.setClearButtonEnabled(False)
        edit.setAccessibleName(field_name.replace('_', ' ').title())
        if tooltip:
            edit.setToolTip(tooltip)
        error = QLabel()
        error.setObjectName('statsFieldError')
        error.setWordWrap(True)
        error.setVisible(False)
        layout.addWidget(edit)
        layout.addWidget(error)
        self._fields[field_name] = edit
        self._field_errors[field_name] = error
        return host

    def _create_pal_information_section(self) -> QFrame:
        section, form = self._create_section(
            '1. Pal Information',
            'Choose a bundled Pal or type any name. Duplicate names include their internal ID.',
        )
        pal_host = QWidget()
        pal_host.setObjectName('statsFieldHost')
        pal_layout = QVBoxLayout(pal_host)
        pal_layout.setContentsMargins(0, 0, 0, 0)
        pal_layout.setSpacing(3)
        self.pal_combo = QComboBox()
        self.pal_combo.setObjectName('statsPalName')
        self.pal_combo.setEditable(True)
        self.pal_combo.setInsertPolicy(QComboBox.NoInsert)
        self.pal_combo.setSizeAdjustPolicy(
            QComboBox.AdjustToMinimumContentsLengthWithIcon
        )
        self.pal_combo.setMinimumContentsLength(20)
        self.pal_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.pal_combo.setMaxVisibleItems(18)
        self.pal_combo.addItems(self.repository.labels())
        self.pal_combo.setCurrentIndex(-1)
        line_edit = self.pal_combo.lineEdit()
        if line_edit is not None:
            line_edit.setPlaceholderText('Search or type a Pal name')
            line_edit.setAccessibleName('Pal name')
        completer = QCompleter(self.repository.labels(), self.pal_combo)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        completer.setFilterMode(Qt.MatchContains)
        completer.setCompletionMode(QCompleter.PopupCompletion)
        self.pal_combo.setCompleter(completer)
        pal_error = QLabel()
        pal_error.setObjectName('statsFieldError')
        pal_error.setWordWrap(True)
        pal_error.setVisible(False)
        pal_layout.addWidget(self.pal_combo)
        pal_layout.addWidget(pal_error)
        self._field_errors['pal_name'] = pal_error
        form.addRow('Pal name', pal_host)
        form.addRow('Level', self._field_widget(
            'level',
            placeholder=f'{self.profile.min_level}\u2013{self.profile.max_level}',
            tooltip='Use the Pal level shown on its status screen.',
        ))
        self.pal_data_status = QLabel()
        self.pal_data_status.setObjectName('statsDataStatus')
        self.pal_data_status.setWordWrap(True)
        form.addRow('', self.pal_data_status)
        return section

    def _create_current_stats_section(self) -> QFrame:
        section, form = self._create_section(
            '2. Current Stats',
            'Enter the whole numbers currently displayed on the Pal status screen.',
        )
        form.addRow('HP', self._field_widget('current_hp', placeholder='Displayed HP'))
        form.addRow('Attack', self._field_widget('current_attack', placeholder='Displayed Attack'))
        form.addRow('Defense', self._field_widget('current_defense', placeholder='Displayed Defense'))
        return section

    def _create_enhancements_section(self) -> QFrame:
        soul_range = (
            f'{self.profile.soul_enhancement_min_percent:g}\u2013'
            f'{self.profile.soul_enhancement_max_percent:g}%'
        )
        condenser_range = (
            f'{self.profile.condenser_min_rank}\u2013'
            f'{self.profile.condenser_max_rank}'
        )
        section, form = self._create_section(
            '3. Enhancements',
            f'Soul fields are total percentages ({soul_range}). '
            f'Condenser rank is {condenser_range}.',
        )
        tooltip = (
            f'Enter the total Soul Enhancement percentage, not its level. '
            f'This profile accepts {soul_range}.'
        )
        form.addRow('HP Soul (%)', self._field_widget('hp_soul_enhancement', tooltip=tooltip))
        form.addRow('Attack Soul (%)', self._field_widget('attack_soul_enhancement', tooltip=tooltip))
        form.addRow('Defense Soul (%)', self._field_widget('defense_soul_enhancement', tooltip=tooltip))
        form.addRow('Condenser rank', self._field_widget(
            'condenser_rank',
            tooltip=(
                f'Use {self.profile.condenser_min_rank} for no condensation and '
                f'{condenser_range} for the current star rank.'
            ),
        ))
        return section

    def _create_passive_section(self) -> QFrame:
        section, form = self._create_section(
            '4. Passive Modifiers',
            'Combine only passives that change the displayed stat. Elemental damage is not Attack.',
        )
        form.addRow('HP modifier (%)', self._field_widget('hp_passive_percent'))
        form.addRow('Attack modifier (%)', self._field_widget('attack_passive_percent'))
        form.addRow('Defense modifier (%)', self._field_widget('defense_passive_percent'))
        return section

    def _create_other_section(self) -> QFrame:
        section, form = self._create_section(
            '5. Other Modifiers',
            'Use for Trust, mutations, or another displayed-stat modifier not represented above.',
        )
        form.addRow('Other HP (%)', self._field_widget('hp_other_percent'))
        form.addRow('Other Attack (%)', self._field_widget('attack_other_percent'))
        form.addRow('Other Defense (%)', self._field_widget('defense_other_percent'))
        return section

    def _create_manual_base_section(self) -> QFrame:
        section, form = self._create_section(
            '6. Manual Base Stats',
            'Required only when the typed Pal cannot be resolved to bundled scaling data.',
        )
        form.addRow('Base HP', self._field_widget('base_hp'))
        form.addRow('Base Attack', self._field_widget('base_attack'))
        form.addRow('Base Defense', self._field_widget('base_defense'))
        return section

    def _create_result_card(self, stat: StatKind, title: str) -> QFrame:
        card = QFrame()
        card.setObjectName('statsResultCard')
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(4)
        title_label = QLabel(title)
        title_label.setObjectName('statsCardTitle')
        layout.addWidget(title_label)
        value = QLabel('Not calculated')
        value.setObjectName('statsCardValue')
        value.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(value)
        score = QLabel('Normalized score: \u2014')
        score.setObjectName('statsCardMeta')
        layout.addWidget(score)
        rating = QLabel('Rating: \u2014')
        rating.setObjectName('statsCardRating')
        layout.addWidget(rating)
        note = QLabel('Enter the Pal data and select Calculate.')
        note.setObjectName('statsCardNote')
        note.setWordWrap(True)
        layout.addWidget(note)
        self._result_widgets[stat] = {
            'value': value,
            'score': score,
            'rating': rating,
            'note': note,
        }
        return card

    def _connect_inputs(self) -> None:
        self.pal_combo.currentTextChanged.connect(self._on_pal_name_changed)
        line_edit = self.pal_combo.lineEdit()
        if line_edit is not None:
            line_edit.returnPressed.connect(self._calculate)
        for field_name, edit in self._fields.items():
            edit.textChanged.connect(
                lambda _text, name=field_name: self._on_input_changed(name)
            )
            edit.returnPressed.connect(self._calculate)

    def _on_pal_name_changed(self, _text: str) -> None:
        self._clear_field_error('pal_name')
        self._mark_stale()
        self._update_pal_data_state()

    def _on_input_changed(self, field_name: str) -> None:
        if self._resetting:
            return
        self._clear_field_error(field_name)
        self._mark_stale()

    def _mark_stale(self) -> None:
        if self._has_results and not self._resetting:
            self.stale_label.setVisible(True)

    def _lookup(self) -> PalLookupResult:
        return self.repository.resolve(self.pal_combo.currentText())

    def _update_pal_data_state(self) -> None:
        lookup = self._lookup()
        if lookup.status is PalLookupStatus.FOUND and lookup.record is not None:
            base = lookup.record.base_stats
            self.pal_data_status.setText(
                f'Bundled base stats: HP {base.hp:g}, Attack {base.attack:g}, '
                f'Defense {base.defense:g} ({lookup.record.pal_id})'
            )
            self.pal_data_status.setProperty('dataState', 'found')
            self.manual_base_section.setVisible(False)
        elif lookup.status is PalLookupStatus.AMBIGUOUS:
            self.pal_data_status.setText(
                'Multiple bundled entries use this name. Choose a suggestion with an internal ID or enter base stats.'
            )
            self.pal_data_status.setProperty('dataState', 'warning')
            self.manual_base_section.setVisible(True)
        elif self.pal_combo.currentText().strip():
            self.pal_data_status.setText(
                'No exact bundled match. Manual base stats are required.'
            )
            self.pal_data_status.setProperty('dataState', 'warning')
            self.manual_base_section.setVisible(True)
        else:
            self.pal_data_status.setText(
                f'{len(self.repository.records)} calculator-ready Pal entries are available.'
            )
            self.pal_data_status.setProperty('dataState', 'neutral')
            self.manual_base_section.setVisible(True)
        self.pal_data_status.style().unpolish(self.pal_data_status)
        self.pal_data_status.style().polish(self.pal_data_status)

    def _build_input(self) -> tuple[PalStatInput, PalBaseStats | None]:
        lookup = self._lookup()
        automatic = (
            lookup.record.base_stats
            if lookup.status is PalLookupStatus.FOUND and lookup.record is not None
            else None
        )
        manual_text = tuple(
            self._fields[field].text()
            for field in ('base_hp', 'base_attack', 'base_defense')
        )
        manual = (
            PalBaseStats(*manual_text)
            if automatic is None and any(value.strip() for value in manual_text)
            else None
        )
        modifiers = StatModifiers(
            hp_soul_enhancement=self._fields['hp_soul_enhancement'].text(),
            attack_soul_enhancement=self._fields['attack_soul_enhancement'].text(),
            defense_soul_enhancement=self._fields['defense_soul_enhancement'].text(),
            condenser_rank=self._fields['condenser_rank'].text(),
            hp_passive_percent=self._fields['hp_passive_percent'].text(),
            attack_passive_percent=self._fields['attack_passive_percent'].text(),
            defense_passive_percent=self._fields['defense_passive_percent'].text(),
            hp_other_percent=self._fields['hp_other_percent'].text(),
            attack_other_percent=self._fields['attack_other_percent'].text(),
            defense_other_percent=self._fields['defense_other_percent'].text(),
        )
        values = PalStatInput(
            pal_name=self.pal_combo.currentText(),
            level=self._fields['level'].text(),
            current_hp=self._fields['current_hp'].text(),
            current_attack=self._fields['current_attack'].text(),
            current_defense=self._fields['current_defense'].text(),
            modifiers=modifiers,
            manual_base_stats=manual,
        )
        return values, automatic

    def _calculate(self) -> None:
        self._clear_errors()
        try:
            values, automatic = self._build_input()
            result = calculate_pal_stats(
                values,
                automatic_base_stats=automatic,
                profile=self.profile,
            )
        except Exception:
            LOGGER.exception('Unexpected Stats Calculator failure')
            QMessageBox.warning(
                self,
                'Could not calculate stats',
                'An unexpected calculation error occurred. Your entries were kept so you can correct or report them.',
            )
            self.status_message.emit('Stats calculation failed unexpectedly.')
            return

        for issue in result.validation_errors:
            error = self._field_errors.get(issue.field)
            if error is not None and not error.isVisible():
                error.setText(issue.message)
                error.setVisible(True)
        self._show_result(result)
        self._has_results = True
        self.stale_label.setVisible(False)
        if result.validation_errors:
            self.status_message.emit('Correct the highlighted calculator fields.')
        elif any(
            result.for_stat(stat).status is CalculationStatus.FORMULA_INCOMPLETE
            for stat in StatKind
        ):
            self.status_message.emit(
                f'Pal base stats loaded; {self.profile.display_name} formula data is incomplete.'
            )
        elif all(
            result.for_stat(stat).status is CalculationStatus.READY
            for stat in StatKind
        ):
            self.status_message.emit('Stat IV ranges calculated.')
        elif any(
            result.for_stat(stat).status is CalculationStatus.READY
            for stat in StatKind
        ):
            self.status_message.emit('Some stat IV ranges calculated; review unmatched stats.')
        else:
            self.status_message.emit('No IV range matched the entered stats and modifiers.')

    def _show_result(self, result: PalStatResult) -> None:
        for stat in StatKind:
            estimate = result.for_stat(stat)
            widgets = self._result_widgets[stat]
            widgets['value'].setText(estimate.display_value)
            widgets['score'].setText(
                'Normalized score: \u2014'
                if estimate.normalized_score is None
                else f'Normalized score: {estimate.normalized_score:.1f}%'
            )
            widgets['rating'].setText(f'Rating: {estimate.rating}')
            widgets['note'].setText(estimate.note or self._default_result_note(estimate))
            widgets['value'].setProperty('resultState', estimate.status.value)
            widgets['value'].style().unpolish(widgets['value'])
            widgets['value'].style().polish(widgets['value'])

        if result.average_iv is None:
            self.average_label.setText('Average IV: \u2014')
            self.perfect_label.setText('Perfect stats: \u2014')
            self.overall_rating_label.setText('Overall rating: Unable to determine')
            self.overall_note.setText(
                'Individual uncertainty remains visible above; all three results must be available for a summary.'
            )
        else:
            self.average_label.setText(f'Average IV: {result.average_iv:.1f}')
            self.perfect_label.setText(f'Perfect stats: {result.perfect_stats} of 3')
            self.overall_rating_label.setText(f'Overall rating: {result.overall_rating}')
            self.overall_note.setText(
                'The average uses each displayed range midpoint and does not replace the individual ranges.'
            )

    @staticmethod
    def _default_result_note(estimate: PalStatEstimate) -> str:
        if estimate.status is CalculationStatus.MISSING_BASE_STATS:
            return 'Choose a known Pal or provide manual base stats.'
        if estimate.status is CalculationStatus.INVALID:
            return 'Correct the highlighted input fields.'
        return 'No IV matched the configured formula and modifier profile.'

    def _clear_field_error(self, field_name: str) -> None:
        error = self._field_errors.get(field_name)
        if error is not None:
            error.clear()
            error.setVisible(False)

    def _clear_errors(self) -> None:
        for field_name in self._field_errors:
            self._clear_field_error(field_name)

    def _reset_result_cards(self) -> None:
        for widgets in self._result_widgets.values():
            widgets['value'].setText('Not calculated')
            widgets['value'].setProperty('resultState', 'empty')
            widgets['value'].style().unpolish(widgets['value'])
            widgets['value'].style().polish(widgets['value'])
            widgets['score'].setText('Normalized score: \u2014')
            widgets['rating'].setText('Rating: \u2014')
            widgets['note'].setText('Enter the Pal data and select Calculate.')
        self.average_label.setText('Average IV: \u2014')
        self.perfect_label.setText('Perfect stats: \u2014')
        self.overall_rating_label.setText('Overall rating: Unable to determine')
        self.overall_note.setText('Calculate all three stats to see a summary.')

    def reset(self) -> None:
        """Restore field defaults and clear calculator results."""

        self._resetting = True
        try:
            self.pal_combo.setCurrentIndex(-1)
            if self.pal_combo.lineEdit() is not None:
                self.pal_combo.lineEdit().clear()
            for field_name, edit in self._fields.items():
                edit.setText(self._FIELD_DEFAULTS[field_name])
            self._clear_errors()
            self._reset_result_cards()
            self._has_results = False
            self.stale_label.setVisible(False)
        finally:
            self._resetting = False
        self._update_pal_data_state()
        self.status_message.emit('Stats Calculator reset.')

    def refresh(self) -> None:
        """Refresh the selected Pal's data-status text when the page opens."""

        self._update_pal_data_state()


__all__ = ['StatsCalculatorTab']
