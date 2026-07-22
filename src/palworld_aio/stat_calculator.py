from __future__ import annotations

from dataclasses import dataclass, field
from decimal import (
    Decimal,
    DecimalException,
    ROUND_CEILING,
    ROUND_FLOOR,
    ROUND_HALF_UP,
)
from enum import Enum
import math
from typing import TypeAlias


NumericInput: TypeAlias = int | float | str | None


class StatKind(str, Enum):
    """Stats supported by the first calculator version."""

    HP = 'hp'
    ATTACK = 'attack'
    DEFENSE = 'defense'


class CalculationStatus(str, Enum):
    """User-facing state of one IV estimate."""

    READY = 'ready'
    INVALID = 'invalid'
    MISSING_BASE_STATS = 'missing_base_stats'
    FORMULA_INCOMPLETE = 'formula_incomplete'
    UNABLE = 'unable'


class RoundingMode(str, Enum):
    """Supported stat rounding rules."""

    FLOOR = 'floor'
    HALF_UP = 'half_up'
    CEILING = 'ceiling'


class ModifierApplication(str, Enum):
    """How configured percentage modifier categories combine."""

    SEQUENTIAL_MULTIPLICATIVE = 'sequential_multiplicative'
    ADDITIVE_PERCENT = 'additive_percent'


@dataclass(frozen=True)
class PalBaseStats:
    """HP, Attack, and Defense base values for a Pal species."""

    hp: NumericInput
    attack: NumericInput
    defense: NumericInput


@dataclass(frozen=True)
class StatModifiers:
    """Displayed-stat modifiers, kept separate by game mechanic."""

    hp_soul_enhancement: NumericInput = 0
    attack_soul_enhancement: NumericInput = 0
    defense_soul_enhancement: NumericInput = 0
    condenser_rank: NumericInput = 0
    hp_passive_percent: NumericInput = 0
    attack_passive_percent: NumericInput = 0
    defense_passive_percent: NumericInput = 0
    hp_other_percent: NumericInput = 0
    attack_other_percent: NumericInput = 0
    defense_other_percent: NumericInput = 0


@dataclass(frozen=True)
class PalStatInput:
    """Raw calculator input. Numeric fields may contain unparsed UI text."""

    pal_name: str
    level: NumericInput
    current_hp: NumericInput
    current_attack: NumericInput
    current_defense: NumericInput
    modifiers: StatModifiers = field(default_factory=StatModifiers)
    manual_base_stats: PalBaseStats | None = None


@dataclass(frozen=True)
class AffineIvFormula:
    """Configurable affine stat formula with a linear integer-IV term.

    The continuous, unmodified stat is calculated as::

        flat_offset
        + base_stat * base_multiplier
        + level * (level_offset + base_stat * level_multiplier)
        + iv_fraction * level * (iv_level_offset + base_stat * iv_level_multiplier)

    ``rounding`` is applied to this raw value before display modifiers. Palworld
    then applies the profile's final rounding rule after those modifiers.
    """

    flat_offset: float
    base_multiplier: float
    level_offset: float
    level_multiplier: float
    iv_level_offset: float
    iv_level_multiplier: float
    rounding: RoundingMode

    def predict_continuous(
        self,
        *,
        base_stat: float,
        level: int,
        iv: int,
        min_iv: int,
        max_iv: int,
    ) -> float:
        """Return the unrounded stat before user-entered modifiers."""

        iv_span = max_iv - min_iv
        iv_fraction = 0.0 if iv_span == 0 else (iv - min_iv) / iv_span
        return (
            self.flat_offset
            + base_stat * self.base_multiplier
            + level * (self.level_offset + base_stat * self.level_multiplier)
            + iv_fraction
            * level
            * (self.iv_level_offset + base_stat * self.iv_level_multiplier)
        )

    def predict_decimal(
        self,
        *,
        base_stat: float,
        level: int,
        iv: int,
        min_iv: int,
        max_iv: int,
    ) -> Decimal:
        """Return the raw stat using decimal arithmetic for exact flooring."""

        number = lambda value: Decimal(str(value))
        base = number(base_stat)
        level_value = Decimal(level)
        iv_span = max_iv - min_iv
        iv_fraction = (
            Decimal(0)
            if iv_span == 0
            else Decimal(iv - min_iv) / Decimal(iv_span)
        )
        return (
            number(self.flat_offset)
            + base * number(self.base_multiplier)
            + level_value * (
                number(self.level_offset) + base * number(self.level_multiplier)
            )
            + iv_fraction
            * level_value
            * (
                number(self.iv_level_offset)
                + base * number(self.iv_level_multiplier)
            )
        )


@dataclass(frozen=True)
class StatFormulaSet:
    """Optional formula definition for each supported stat."""

    hp: AffineIvFormula | None = None
    attack: AffineIvFormula | None = None
    defense: AffineIvFormula | None = None

    def for_stat(self, stat: StatKind) -> AffineIvFormula | None:
        return getattr(self, stat.value)


@dataclass(frozen=True)
class StatPercentages:
    """Per-stat percentages used by one configured modifier stage."""

    hp: float = 0.0
    attack: float = 0.0
    defense: float = 0.0

    def for_stat(self, stat: StatKind) -> float:
        return float(getattr(self, stat.value))


@dataclass(frozen=True)
class RatingBoundary:
    """Minimum normalized score and its display label."""

    minimum_score: float
    label: str


DEFAULT_RATING_BOUNDARIES = (
    RatingBoundary(100.0, 'Perfect'),
    RatingBoundary(90.0, 'Excellent'),
    RatingBoundary(70.0, 'Very Good'),
    RatingBoundary(50.0, 'Average'),
    RatingBoundary(1.0, 'Low'),
    RatingBoundary(0.0, 'Minimum'),
)


@dataclass(frozen=True)
class FormulaProfile:
    """Patch-specific formula, modifier, range, and rating configuration."""

    profile_id: str
    display_name: str
    formulas: StatFormulaSet
    modifier_application: ModifierApplication | None
    final_rounding: RoundingMode = RoundingMode.FLOOR
    condenser_bonus_by_rank: tuple[StatPercentages, ...] | None = None
    min_iv: int = 0
    max_iv: int = 100
    min_level: int = 1
    max_level: int = 100
    max_displayed_stat: int = 2_147_483_647
    soul_enhancement_min_percent: float = 0.0
    soul_enhancement_max_percent: float = 60.0
    condenser_min_rank: int = 0
    condenser_max_rank: int = 4
    modifier_min_percent: float = -99.0
    modifier_max_percent: float = 1000.0
    rating_boundaries: tuple[RatingBoundary, ...] = DEFAULT_RATING_BOUNDARIES
    incomplete_reason: str = ''


# Palworld 1.0 formulas. Talent/IV is 0-100 and adds 0.3% per point to
# species-based level growth. The game floors the raw stat, applies modifier
# categories multiplicatively, then floors the displayed result again.
# Sources:
#   https://palworld.wiki.gg/wiki/Pal_Stats
#   https://www.palworld.tools/upgrades
PALWORLD_1_0_FORMULA_PROFILE = FormulaProfile(
    profile_id='palworld-1.0',
    display_name='Palworld 1.0',
    formulas=StatFormulaSet(
        hp=AffineIvFormula(
            flat_offset=500.0,
            base_multiplier=0.0,
            level_offset=5.0,
            level_multiplier=0.5,
            iv_level_offset=0.0,
            iv_level_multiplier=0.15,
            rounding=RoundingMode.FLOOR,
        ),
        attack=AffineIvFormula(
            flat_offset=100.0,
            base_multiplier=0.0,
            level_offset=0.0,
            level_multiplier=0.075,
            iv_level_offset=0.0,
            iv_level_multiplier=0.0225,
            rounding=RoundingMode.FLOOR,
        ),
        defense=AffineIvFormula(
            flat_offset=50.0,
            base_multiplier=0.0,
            level_offset=0.0,
            level_multiplier=0.075,
            iv_level_offset=0.0,
            iv_level_multiplier=0.0225,
            rounding=RoundingMode.FLOOR,
        ),
    ),
    modifier_application=ModifierApplication.SEQUENTIAL_MULTIPLICATIVE,
    final_rounding=RoundingMode.FLOOR,
    condenser_bonus_by_rank=(
        StatPercentages(),
        StatPercentages(5.0, 5.0, 5.0),
        StatPercentages(10.0, 10.0, 10.0),
        StatPercentages(15.0, 15.0, 15.0),
        StatPercentages(20.0, 20.0, 20.0),
    ),
)
DEFAULT_FORMULA_PROFILE = PALWORLD_1_0_FORMULA_PROFILE


@dataclass(frozen=True)
class ValidationIssue:
    """A field-level validation problem suitable for display in the UI."""

    field: str
    message: str
    code: str = 'invalid'


@dataclass(frozen=True)
class StatInterval:
    """Continuous interval represented by one rounded displayed stat."""

    minimum: float
    maximum: float
    minimum_inclusive: bool
    maximum_inclusive: bool

    def contains(self, value: float) -> bool:
        lower_ok = value >= self.minimum if self.minimum_inclusive else value > self.minimum
        upper_ok = value <= self.maximum if self.maximum_inclusive else value < self.maximum
        return lower_ok and upper_ok


@dataclass(frozen=True)
class PalStatEstimate:
    """Result for one stat, including uncertainty caused by rounding."""

    stat: StatKind
    status: CalculationStatus
    min_iv: int | None = None
    max_iv: int | None = None
    normalized_score: float | None = None
    rating: str = 'Unable to determine'
    note: str = ''
    unmodified_interval: StatInterval | None = None

    @property
    def display_value(self) -> str:
        if self.status is CalculationStatus.INVALID:
            return 'Invalid input'
        if self.status is CalculationStatus.MISSING_BASE_STATS:
            return 'Missing base-stat data'
        if self.status is CalculationStatus.FORMULA_INCOMPLETE:
            return 'Formula data incomplete'
        if self.status is not CalculationStatus.READY:
            return 'Unable to determine'
        if self.min_iv == self.max_iv:
            return f'{self.min_iv} IV'
        return f'{self.min_iv}\u2013{self.max_iv} IV'


@dataclass(frozen=True)
class PalStatResult:
    """Complete calculator result for HP, Attack, and Defense."""

    hp: PalStatEstimate
    attack: PalStatEstimate
    defense: PalStatEstimate
    validation_errors: tuple[ValidationIssue, ...] = ()
    average_iv: float | None = None
    perfect_stats: int = 0
    overall_rating: str = 'Unable to determine'
    base_stats_source: str = ''

    def for_stat(self, stat: StatKind) -> PalStatEstimate:
        return getattr(self, stat.value)


@dataclass(frozen=True)
class _NormalizedModifiers:
    hp_soul_enhancement: float
    attack_soul_enhancement: float
    defense_soul_enhancement: float
    condenser_rank: int
    hp_passive_percent: float
    attack_passive_percent: float
    defense_passive_percent: float
    hp_other_percent: float
    attack_other_percent: float
    defense_other_percent: float


@dataclass(frozen=True)
class _NormalizedInput:
    pal_name: str
    level: int
    current_hp: int
    current_attack: int
    current_defense: int
    modifiers: _NormalizedModifiers
    base_stats: tuple[float, float, float] | None
    base_stats_source: str


class FormulaDataIncompleteError(ValueError):
    """Raised when a requested calculation lacks authoritative configuration."""


def _coerce_int(
    value: NumericInput,
    *,
    field_name: str,
    label: str,
    issues: list[ValidationIssue],
    required: bool = True,
) -> int | None:
    if value is None or (isinstance(value, str) and not value.strip()):
        if required:
            issues.append(ValidationIssue(field_name, f'{label} is required.', 'required'))
        return None
    if isinstance(value, bool):
        parsed = None
    elif isinstance(value, int):
        parsed = value
    elif isinstance(value, float):
        parsed = int(value) if math.isfinite(value) and value.is_integer() else None
    else:
        try:
            parsed = int(str(value).strip())
        except (TypeError, ValueError):
            parsed = None
    if parsed is None:
        issues.append(ValidationIssue(field_name, f'{label} must be a whole number.'))
    return parsed


def _coerce_float(
    value: NumericInput,
    *,
    field_name: str,
    label: str,
    issues: list[ValidationIssue],
    required: bool,
    default: float = 0.0,
) -> float | None:
    if value is None or (isinstance(value, str) and not value.strip()):
        if required:
            issues.append(ValidationIssue(field_name, f'{label} is required.', 'required'))
            return None
        return default
    if isinstance(value, bool):
        parsed = None
    else:
        try:
            parsed = float(value)
        except (OverflowError, TypeError, ValueError):
            parsed = None
    if parsed is None or not math.isfinite(parsed):
        issues.append(ValidationIssue(field_name, f'{label} must be a finite number.'))
        return None
    return parsed


def _validate_range(
    value: float | int | None,
    *,
    minimum: float | int,
    maximum: float | int,
    field_name: str,
    label: str,
    issues: list[ValidationIssue],
) -> None:
    if value is not None and not minimum <= value <= maximum:
        issues.append(ValidationIssue(
            field_name,
            f'{label} must be between {minimum:g} and {maximum:g}.',
            'out_of_range',
        ))


def _normalize_modifiers(
    values: StatModifiers,
    profile: FormulaProfile,
    issues: list[ValidationIssue],
) -> _NormalizedModifiers:
    soul_specs = (
        ('hp_soul_enhancement', 'HP Soul Enhancement'),
        ('attack_soul_enhancement', 'Attack Soul Enhancement'),
        ('defense_soul_enhancement', 'Defense Soul Enhancement'),
    )
    parsed: dict[str, float | int | None] = {}
    for field_name, label in soul_specs:
        parsed[field_name] = _coerce_float(
            getattr(values, field_name),
            field_name=field_name,
            label=label,
            issues=issues,
            required=False,
        )
        _validate_range(
            parsed[field_name],
            minimum=profile.soul_enhancement_min_percent,
            maximum=profile.soul_enhancement_max_percent,
            field_name=field_name,
            label=label,
            issues=issues,
        )

    rank = _coerce_int(
        values.condenser_rank,
        field_name='condenser_rank',
        label='Essence Condenser rank',
        issues=issues,
        required=False,
    )
    rank = profile.condenser_min_rank if rank is None else rank
    _validate_range(
        rank,
        minimum=profile.condenser_min_rank,
        maximum=profile.condenser_max_rank,
        field_name='condenser_rank',
        label='Essence Condenser rank',
        issues=issues,
    )

    percent_specs = (
        ('hp_passive_percent', 'HP passive modifier'),
        ('attack_passive_percent', 'Attack passive modifier'),
        ('defense_passive_percent', 'Defense passive modifier'),
        ('hp_other_percent', 'Other HP modifier'),
        ('attack_other_percent', 'Other Attack modifier'),
        ('defense_other_percent', 'Other Defense modifier'),
    )
    for field_name, label in percent_specs:
        parsed[field_name] = _coerce_float(
            getattr(values, field_name),
            field_name=field_name,
            label=label,
            issues=issues,
            required=False,
        )
        _validate_range(
            parsed[field_name],
            minimum=profile.modifier_min_percent,
            maximum=profile.modifier_max_percent,
            field_name=field_name,
            label=label,
            issues=issues,
        )

    return _NormalizedModifiers(
        hp_soul_enhancement=float(parsed['hp_soul_enhancement'] or 0.0),
        attack_soul_enhancement=float(parsed['attack_soul_enhancement'] or 0.0),
        defense_soul_enhancement=float(parsed['defense_soul_enhancement'] or 0.0),
        condenser_rank=rank,
        hp_passive_percent=float(parsed['hp_passive_percent'] or 0.0),
        attack_passive_percent=float(parsed['attack_passive_percent'] or 0.0),
        defense_passive_percent=float(parsed['defense_passive_percent'] or 0.0),
        hp_other_percent=float(parsed['hp_other_percent'] or 0.0),
        attack_other_percent=float(parsed['attack_other_percent'] or 0.0),
        defense_other_percent=float(parsed['defense_other_percent'] or 0.0),
    )


def _normalize_base_stats(
    base_stats: PalBaseStats,
    issues: list[ValidationIssue],
) -> tuple[float, float, float] | None:
    parsed: list[float | None] = []
    for field_name, label, value in (
        ('base_hp', 'Base HP', base_stats.hp),
        ('base_attack', 'Base Attack', base_stats.attack),
        ('base_defense', 'Base Defense', base_stats.defense),
    ):
        number = _coerce_float(
            value,
            field_name=field_name,
            label=label,
            issues=issues,
            required=True,
        )
        if number is not None and number <= 0:
            issues.append(ValidationIssue(
                field_name,
                f'{label} must be greater than zero.',
                'not_positive',
            ))
        parsed.append(number)
    if any(value is None or value <= 0 for value in parsed):
        return None
    return float(parsed[0]), float(parsed[1]), float(parsed[2])


def _normalize_inputs(
    values: PalStatInput,
    profile: FormulaProfile,
    automatic_base_stats: PalBaseStats | None,
) -> tuple[_NormalizedInput, tuple[ValidationIssue, ...]]:
    issues: list[ValidationIssue] = []
    pal_name = str(values.pal_name).strip()
    if not pal_name:
        issues.append(ValidationIssue('pal_name', 'Pal name is required.', 'required'))

    level = _coerce_int(
        values.level,
        field_name='level',
        label='Level',
        issues=issues,
    )
    _validate_range(
        level,
        minimum=profile.min_level,
        maximum=profile.max_level,
        field_name='level',
        label='Level',
        issues=issues,
    )

    current_values: dict[str, int | None] = {}
    for field_name, label in (
        ('current_hp', 'Current HP'),
        ('current_attack', 'Current Attack'),
        ('current_defense', 'Current Defense'),
    ):
        current = _coerce_int(
            getattr(values, field_name),
            field_name=field_name,
            label=label,
            issues=issues,
        )
        _validate_range(
            current,
            minimum=1,
            maximum=profile.max_displayed_stat,
            field_name=field_name,
            label=label,
            issues=issues,
        )
        current_values[field_name] = current

    modifiers = _normalize_modifiers(values.modifiers, profile, issues)
    selected_base = automatic_base_stats or values.manual_base_stats
    base_source = 'dataset' if automatic_base_stats is not None else 'manual'
    if selected_base is None:
        for field_name, label in (
            ('base_hp', 'Base HP'),
            ('base_attack', 'Base Attack'),
            ('base_defense', 'Base Defense'),
        ):
            issues.append(ValidationIssue(
                field_name,
                f'{label} is required when the Pal is not in the dataset.',
                'missing_base',
            ))
        base_stats = None
        base_source = ''
    else:
        base_stats = _normalize_base_stats(selected_base, issues)

    normalized = _NormalizedInput(
        pal_name=pal_name,
        level=level or profile.min_level,
        current_hp=current_values['current_hp'] or 0,
        current_attack=current_values['current_attack'] or 0,
        current_defense=current_values['current_defense'] or 0,
        modifiers=modifiers,
        base_stats=base_stats,
        base_stats_source=base_source,
    )
    return normalized, tuple(issues)


def validate_stat_inputs(
    values: PalStatInput,
    *,
    automatic_base_stats: PalBaseStats | None = None,
    profile: FormulaProfile = DEFAULT_FORMULA_PROFILE,
) -> tuple[ValidationIssue, ...]:
    """Validate raw calculator values without mutating the input models."""

    _normalized, issues = _normalize_inputs(values, profile, automatic_base_stats)
    return issues


def _modifier_percentages(
    stat: StatKind,
    modifiers: _NormalizedModifiers,
    profile: FormulaProfile,
) -> tuple[float, float, float, float]:
    if profile.modifier_application is None:
        raise FormulaDataIncompleteError('Modifier application order is not configured.')
    soul = float(getattr(modifiers, f'{stat.value}_soul_enhancement'))
    passive = float(getattr(modifiers, f'{stat.value}_passive_percent'))
    other = float(getattr(modifiers, f'{stat.value}_other_percent'))
    if modifiers.condenser_rank == 0:
        condenser = 0.0
    elif (
        profile.condenser_bonus_by_rank is None
        or modifiers.condenser_rank >= len(profile.condenser_bonus_by_rank)
    ):
        raise FormulaDataIncompleteError(
            f'Condenser rank {modifiers.condenser_rank} has no configured stat bonus.'
        )
    else:
        condenser = profile.condenser_bonus_by_rank[
            modifiers.condenser_rank
        ].for_stat(stat)
    return soul, condenser, passive, other


def _modifier_multiplier_decimal(
    stat: StatKind,
    modifiers: _NormalizedModifiers,
    profile: FormulaProfile,
) -> Decimal:
    percentages = _modifier_percentages(stat, modifiers, profile)
    decimal_percentages = tuple(Decimal(str(value)) for value in percentages)
    if profile.modifier_application is ModifierApplication.ADDITIVE_PERCENT:
        multiplier = Decimal(1) + sum(
            decimal_percentages,
            start=Decimal(0),
        ) / Decimal(100)
    else:
        multiplier = Decimal(1)
        for percent in decimal_percentages:
            multiplier *= Decimal(1) + percent / Decimal(100)
    if not multiplier.is_finite() or multiplier <= 0:
        raise ValueError('Applied stat modifiers produce an invalid multiplier.')
    return multiplier


def _round_decimal_stat(value: Decimal, rounding: RoundingMode) -> int:
    """Apply a configured game rounding rule without binary-float drift."""

    if not value.is_finite():
        raise ValueError('Stat calculation produced a non-finite value.')
    decimal_rounding = {
        RoundingMode.FLOOR: ROUND_FLOOR,
        RoundingMode.CEILING: ROUND_CEILING,
        RoundingMode.HALF_UP: ROUND_HALF_UP,
    }[rounding]
    return int(value.to_integral_value(rounding=decimal_rounding))


def _reverse_two_stage_rounding(
    displayed_stat: int,
    *,
    multiplier: Decimal,
    raw_rounding: RoundingMode,
    final_rounding: RoundingMode,
) -> StatInterval:
    """Return raw continuous values surviving both configured rounding stages."""

    displayed = Decimal(displayed_stat)
    half = Decimal('0.5')
    if final_rounding is RoundingMode.FLOOR:
        lower = displayed / multiplier
        upper = (displayed + 1) / multiplier
        minimum_integer = int(lower.to_integral_value(rounding=ROUND_CEILING))
        maximum_integer = int(upper.to_integral_value(rounding=ROUND_CEILING)) - 1
    elif final_rounding is RoundingMode.CEILING:
        lower = (displayed - 1) / multiplier
        upper = displayed / multiplier
        minimum_integer = int(lower.to_integral_value(rounding=ROUND_FLOOR)) + 1
        maximum_integer = int(upper.to_integral_value(rounding=ROUND_FLOOR))
    else:
        lower = (displayed - half) / multiplier
        upper = (displayed + half) / multiplier
        minimum_integer = int(lower.to_integral_value(rounding=ROUND_CEILING))
        maximum_integer = int(upper.to_integral_value(rounding=ROUND_CEILING)) - 1

    if minimum_integer > maximum_integer:
        return StatInterval(1.0, 0.0, False, False)
    if raw_rounding is RoundingMode.FLOOR:
        return StatInterval(
            float(minimum_integer),
            float(maximum_integer + 1),
            True,
            False,
        )
    if raw_rounding is RoundingMode.CEILING:
        return StatInterval(
            float(minimum_integer - 1),
            float(maximum_integer),
            False,
            True,
        )
    return StatInterval(
        float(Decimal(minimum_integer) - half),
        float(Decimal(maximum_integer) + half),
        True,
        False,
    )


def reverse_stat_modifiers(
    displayed_stat: int,
    *,
    stat: StatKind,
    modifiers: StatModifiers,
    formula: AffineIvFormula,
    profile: FormulaProfile = DEFAULT_FORMULA_PROFILE,
) -> StatInterval:
    """Reverse modifiers and rounding into an unmodified continuous interval.

    Sequential profiles apply Soul Enhancement, Condenser, passive, and other
    percentages in that order. They are reversed in the opposite order. Additive
    profiles combine the four categories once, as explicitly selected by the
    formula profile.
    """

    if not 1 <= displayed_stat <= profile.max_displayed_stat:
        raise ValueError(
            f'Displayed stat must be between 1 and {profile.max_displayed_stat}.'
        )

    issues: list[ValidationIssue] = []
    normalized = _normalize_modifiers(modifiers, profile, issues)
    if issues:
        raise ValueError(issues[0].message)
    multiplier = _modifier_multiplier_decimal(stat, normalized, profile)
    return _reverse_two_stage_rounding(
        displayed_stat,
        multiplier=multiplier,
        raw_rounding=formula.rounding,
        final_rounding=profile.final_rounding,
    )


def _reverse_normalized_modifiers(
    displayed_stat: int,
    *,
    stat: StatKind,
    modifiers: _NormalizedModifiers,
    formula: AffineIvFormula,
    profile: FormulaProfile,
) -> StatInterval:
    multiplier = _modifier_multiplier_decimal(stat, modifiers, profile)
    return _reverse_two_stage_rounding(
        displayed_stat,
        multiplier=multiplier,
        raw_rounding=formula.rounding,
        final_rounding=profile.final_rounding,
    )


def _normalized_score(min_iv: int, max_iv: int, profile: FormulaProfile) -> float:
    midpoint = (min_iv + max_iv) / 2.0
    span = profile.max_iv - profile.min_iv
    if span <= 0:
        return 100.0
    return max(0.0, min(100.0, (midpoint - profile.min_iv) / span * 100.0))


def rating_for_score(score: float, profile: FormulaProfile = DEFAULT_FORMULA_PROFILE) -> str:
    """Return the configured label for a normalized 0-100 score."""

    for boundary in sorted(
        profile.rating_boundaries,
        key=lambda item: item.minimum_score,
        reverse=True,
    ):
        if score >= boundary.minimum_score:
            return boundary.label
    return 'Unable to determine'


def calculate_iv_range(
    *,
    stat: StatKind,
    displayed_stat: int,
    level: int,
    base_stat: float,
    modifiers: StatModifiers | _NormalizedModifiers,
    profile: FormulaProfile = DEFAULT_FORMULA_PROFILE,
) -> PalStatEstimate:
    """Enumerate configured integer IVs and return all values matching display rounding."""

    if (
        isinstance(displayed_stat, bool)
        or not isinstance(displayed_stat, int)
        or not 1 <= displayed_stat <= profile.max_displayed_stat
    ):
        return PalStatEstimate(
            stat,
            CalculationStatus.INVALID,
            note=(
                f'Displayed stat must be a whole number between 1 and '
                f'{profile.max_displayed_stat}.'
            ),
        )

    if isinstance(modifiers, StatModifiers):
        modifier_issues: list[ValidationIssue] = []
        normalized_modifiers = _normalize_modifiers(modifiers, profile, modifier_issues)
        if modifier_issues:
            return PalStatEstimate(
                stat,
                CalculationStatus.INVALID,
                note=modifier_issues[0].message,
            )
    else:
        normalized_modifiers = modifiers

    formula = profile.formulas.for_stat(stat)
    if formula is None:
        return PalStatEstimate(
            stat,
            CalculationStatus.FORMULA_INCOMPLETE,
            note=profile.incomplete_reason or f'{stat.value.title()} formula is not configured.',
        )
    try:
        interval = _reverse_normalized_modifiers(
            displayed_stat,
            stat=stat,
            modifiers=normalized_modifiers,
            formula=formula,
            profile=profile,
        )
    except FormulaDataIncompleteError as exc:
        return PalStatEstimate(
            stat,
            CalculationStatus.FORMULA_INCOMPLETE,
            note=str(exc),
        )
    except ValueError as exc:
        return PalStatEstimate(stat, CalculationStatus.INVALID, note=str(exc))

    try:
        multiplier = _modifier_multiplier_decimal(stat, normalized_modifiers, profile)
    except FormulaDataIncompleteError as exc:
        return PalStatEstimate(
            stat,
            CalculationStatus.FORMULA_INCOMPLETE,
            note=str(exc),
        )
    except ValueError as exc:
        return PalStatEstimate(stat, CalculationStatus.INVALID, note=str(exc))

    matches: list[int] = []
    for iv in range(profile.min_iv, profile.max_iv + 1):
        try:
            predicted = formula.predict_decimal(
                base_stat=base_stat,
                level=level,
                iv=iv,
                min_iv=profile.min_iv,
                max_iv=profile.max_iv,
            )
            raw_stat = _round_decimal_stat(predicted, formula.rounding)
            displayed_prediction = _round_decimal_stat(
                Decimal(raw_stat) * multiplier,
                profile.final_rounding,
            )
        except (DecimalException, OverflowError, ValueError):
            continue
        if displayed_prediction == displayed_stat:
            matches.append(iv)

    if not matches:
        return PalStatEstimate(
            stat,
            CalculationStatus.UNABLE,
            note='The displayed stat does not match any IV in the configured range.',
            unmodified_interval=interval,
        )

    minimum = max(profile.min_iv, matches[0])
    maximum = min(profile.max_iv, matches[-1])
    score = _normalized_score(minimum, maximum, profile)
    note = (
        'Exact within the configured integer IV scale.'
        if minimum == maximum
        else f'Displayed-stat rounding allows IVs {minimum}\u2013{maximum}.'
    )
    return PalStatEstimate(
        stat,
        CalculationStatus.READY,
        min_iv=minimum,
        max_iv=maximum,
        normalized_score=score,
        rating=rating_for_score(score, profile),
        note=note,
        unmodified_interval=interval,
    )


def _uniform_result(
    status: CalculationStatus,
    *,
    note: str,
    errors: tuple[ValidationIssue, ...] = (),
) -> PalStatResult:
    estimates = tuple(
        PalStatEstimate(stat, status, note=note)
        for stat in StatKind
    )
    return PalStatResult(
        hp=estimates[0],
        attack=estimates[1],
        defense=estimates[2],
        validation_errors=errors,
    )


def calculate_pal_stats(
    values: PalStatInput,
    *,
    automatic_base_stats: PalBaseStats | None = None,
    profile: FormulaProfile = DEFAULT_FORMULA_PROFILE,
) -> PalStatResult:
    """Validate input and estimate HP, Attack, and Defense IV ranges."""

    normalized, issues = _normalize_inputs(values, profile, automatic_base_stats)
    blocking_issues = tuple(issue for issue in issues if issue.code != 'missing_base')
    if blocking_issues:
        return _uniform_result(
            CalculationStatus.INVALID,
            note='Correct the highlighted fields and calculate again.',
            errors=issues,
        )
    if normalized.base_stats is None:
        return _uniform_result(
            CalculationStatus.MISSING_BASE_STATS,
            note='Select a known Pal or enter all three manual base stats.',
            errors=issues,
        )

    estimates = (
        calculate_iv_range(
            stat=StatKind.HP,
            displayed_stat=normalized.current_hp,
            level=normalized.level,
            base_stat=normalized.base_stats[0],
            modifiers=normalized.modifiers,
            profile=profile,
        ),
        calculate_iv_range(
            stat=StatKind.ATTACK,
            displayed_stat=normalized.current_attack,
            level=normalized.level,
            base_stat=normalized.base_stats[1],
            modifiers=normalized.modifiers,
            profile=profile,
        ),
        calculate_iv_range(
            stat=StatKind.DEFENSE,
            displayed_stat=normalized.current_defense,
            level=normalized.level,
            base_stat=normalized.base_stats[2],
            modifiers=normalized.modifiers,
            profile=profile,
        ),
    )
    ready = [item for item in estimates if item.status is CalculationStatus.READY]
    average = None
    perfect = 0
    overall = 'Unable to determine'
    if len(ready) == 3:
        midpoints = [
            (float(item.min_iv) + float(item.max_iv)) / 2.0
            for item in ready
        ]
        average = sum(midpoints) / len(midpoints)
        iv_span = profile.max_iv - profile.min_iv
        normalized_average = (
            100.0
            if iv_span <= 0
            else max(
                0.0,
                min(100.0, (average - profile.min_iv) / iv_span * 100.0),
            )
        )
        perfect = sum(
            item.min_iv == profile.max_iv and item.max_iv == profile.max_iv
            for item in ready
        )
        overall = rating_for_score(normalized_average, profile)
    return PalStatResult(
        hp=estimates[0],
        attack=estimates[1],
        defense=estimates[2],
        validation_errors=issues,
        average_iv=average,
        perfect_stats=perfect,
        overall_rating=overall,
        base_stats_source=normalized.base_stats_source,
    )


__all__ = [
    'AffineIvFormula',
    'CalculationStatus',
    'DEFAULT_FORMULA_PROFILE',
    'FormulaDataIncompleteError',
    'FormulaProfile',
    'ModifierApplication',
    'PALWORLD_1_0_FORMULA_PROFILE',
    'PalBaseStats',
    'PalStatEstimate',
    'PalStatInput',
    'PalStatResult',
    'RatingBoundary',
    'RoundingMode',
    'StatFormulaSet',
    'StatInterval',
    'StatKind',
    'StatModifiers',
    'StatPercentages',
    'ValidationIssue',
    'calculate_iv_range',
    'calculate_pal_stats',
    'rating_for_score',
    'reverse_stat_modifiers',
    'validate_stat_inputs',
]
