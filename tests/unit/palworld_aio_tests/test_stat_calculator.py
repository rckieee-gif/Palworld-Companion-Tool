from __future__ import annotations

from copy import deepcopy
import math

import pytest

from palworld_aio.stat_calculator import (
    AffineIvFormula,
    CalculationStatus,
    DEFAULT_FORMULA_PROFILE,
    FormulaProfile,
    ModifierApplication,
    PalBaseStats,
    PalStatInput,
    RoundingMode,
    StatFormulaSet,
    StatKind,
    StatModifiers,
    StatPercentages,
    calculate_iv_range,
    calculate_pal_stats,
    reverse_stat_modifiers,
    validate_stat_inputs,
)


EXACT_FORMULA = AffineIvFormula(
    flat_offset=0.0,
    base_multiplier=1.0,
    level_offset=0.0,
    level_multiplier=0.0,
    iv_level_offset=100.0,
    iv_level_multiplier=0.0,
    rounding=RoundingMode.FLOOR,
)
COMPLETE_PROFILE = FormulaProfile(
    profile_id='deterministic-test-profile',
    display_name='Deterministic test profile',
    formulas=StatFormulaSet(EXACT_FORMULA, EXACT_FORMULA, EXACT_FORMULA),
    modifier_application=ModifierApplication.SEQUENTIAL_MULTIPLICATIVE,
    condenser_bonus_by_rank=(
        StatPercentages(),
        StatPercentages(5, 5, 5),
        StatPercentages(10, 10, 10),
        StatPercentages(15, 15, 15),
        StatPercentages(20, 20, 20),
    ),
)
BASE_STATS = PalBaseStats(100, 100, 100)


def _displayed_stat(
    *,
    level: int,
    iv: int,
    soul: float = 0,
    condenser: float = 0,
    passive: float = 0,
    other: float = 0,
) -> int:
    raw = 100 + iv * level
    multiplier = math.prod(
        1 + percent / 100
        for percent in (soul, condenser, passive, other)
    )
    return math.floor(raw * multiplier)


def _input(
    *,
    level: object = 10,
    displayed: object = 600,
    modifiers: StatModifiers | None = None,
    manual_base: PalBaseStats | None = None,
) -> PalStatInput:
    return PalStatInput(
        pal_name='Test Pal',
        level=level,
        current_hp=displayed,
        current_attack=displayed,
        current_defense=displayed,
        modifiers=modifiers or StatModifiers(),
        manual_base_stats=manual_base,
    )


@pytest.mark.parametrize(
    ('iv', 'expected'),
    ((0, '0 IV'), (50, '50 IV'), (100, '100 IV')),
)
def test_minimum_middle_and_maximum_configured_iv(iv: int, expected: str) -> None:
    displayed = _displayed_stat(level=10, iv=iv)
    result = calculate_pal_stats(
        _input(displayed=displayed),
        automatic_base_stats=BASE_STATS,
        profile=COMPLETE_PROFILE,
    )

    assert result.hp.display_value == expected
    assert result.hp.min_iv == iv
    assert result.hp.max_iv == iv


def test_display_rounding_can_produce_an_iv_range() -> None:
    slow_formula = AffineIvFormula(
        flat_offset=0,
        base_multiplier=1,
        level_offset=0,
        level_multiplier=0,
        iv_level_offset=1,
        iv_level_multiplier=0,
        rounding=RoundingMode.FLOOR,
    )
    profile = FormulaProfile(
        profile_id='rounding-range',
        display_name='Rounding range',
        formulas=StatFormulaSet(slow_formula, slow_formula, slow_formula),
        modifier_application=ModifierApplication.SEQUENTIAL_MULTIPLICATIVE,
    )

    estimate = calculate_iv_range(
        stat=StatKind.HP,
        displayed_stat=100,
        level=1,
        base_stat=100,
        modifiers=StatModifiers(),
        profile=profile,
    )

    assert estimate.status is CalculationStatus.READY
    assert estimate.display_value == '0\u201399 IV'


@pytest.mark.parametrize(('level', 'iv'), ((1, 50), (100, 50)))
def test_level_one_and_maximum_configured_level(level: int, iv: int) -> None:
    displayed = _displayed_stat(level=level, iv=iv)
    result = calculate_pal_stats(
        _input(level=level, displayed=displayed),
        automatic_base_stats=BASE_STATS,
        profile=COMPLETE_PROFILE,
    )

    assert result.hp.min_iv == iv
    assert result.hp.status is CalculationStatus.READY


def test_no_modifiers() -> None:
    result = calculate_pal_stats(
        _input(displayed=_displayed_stat(level=10, iv=40)),
        automatic_base_stats=BASE_STATS,
        profile=COMPLETE_PROFILE,
    )

    assert result.hp.min_iv == 40


@pytest.mark.parametrize(
    ('modifier', 'displayed'),
    (
        (StatModifiers(hp_passive_percent=20), _displayed_stat(level=10, iv=50, passive=20)),
        (StatModifiers(hp_passive_percent=-20), _displayed_stat(level=10, iv=50, passive=-20)),
        (StatModifiers(hp_soul_enhancement=10), _displayed_stat(level=10, iv=50, soul=10)),
        (StatModifiers(condenser_rank=2), _displayed_stat(level=10, iv=50, condenser=10)),
    ),
)
def test_individual_positive_negative_soul_and_condenser_modifiers(
    modifier: StatModifiers,
    displayed: int,
) -> None:
    estimate = calculate_iv_range(
        stat=StatKind.HP,
        displayed_stat=displayed,
        level=10,
        base_stat=100,
        modifiers=modifier,
        profile=COMPLETE_PROFILE,
    )

    assert estimate.min_iv == 50
    assert estimate.max_iv == 50


def test_combined_modifiers_are_reversed_by_configured_stages() -> None:
    modifiers = StatModifiers(
        hp_soul_enhancement=10,
        condenser_rank=2,
        hp_passive_percent=20,
        hp_other_percent=-5,
    )
    displayed = _displayed_stat(
        level=10,
        iv=50,
        soul=10,
        condenser=10,
        passive=20,
        other=-5,
    )

    estimate = calculate_iv_range(
        stat=StatKind.HP,
        displayed_stat=displayed,
        level=10,
        base_stat=100,
        modifiers=modifiers,
        profile=COMPLETE_PROFILE,
    )
    interval = reverse_stat_modifiers(
        displayed,
        stat=StatKind.HP,
        modifiers=modifiers,
        formula=EXACT_FORMULA,
        profile=COMPLETE_PROFILE,
    )

    assert estimate.min_iv == estimate.max_iv == 50
    assert interval.contains(600)


def test_forward_enumeration_avoids_float_boundary_false_negative() -> None:
    formula = AffineIvFormula(
        flat_offset=15,
        base_multiplier=0,
        level_offset=0,
        level_multiplier=0,
        iv_level_offset=0,
        iv_level_multiplier=0,
        rounding=RoundingMode.FLOOR,
    )
    profile = FormulaProfile(
        profile_id='float-boundary',
        display_name='Float boundary',
        formulas=StatFormulaSet(formula, formula, formula),
        modifier_application=ModifierApplication.SEQUENTIAL_MULTIPLICATIVE,
    )

    estimate = calculate_iv_range(
        stat=StatKind.HP,
        displayed_stat=21,
        level=1,
        base_stat=1,
        modifiers=StatModifiers(hp_soul_enhancement=40),
        profile=profile,
    )
    interval = reverse_stat_modifiers(
        21,
        stat=StatKind.HP,
        modifiers=StatModifiers(hp_soul_enhancement=40),
        formula=formula,
        profile=profile,
    )

    assert estimate.status is CalculationStatus.READY
    assert estimate.display_value == '0\u2013100 IV'
    assert interval.contains(15)


def test_raw_stat_is_floored_before_modifiers_and_again_afterward() -> None:
    formula = AffineIvFormula(
        flat_offset=15.9,
        base_multiplier=0,
        level_offset=0,
        level_multiplier=0,
        iv_level_offset=0,
        iv_level_multiplier=0,
        rounding=RoundingMode.FLOOR,
    )
    profile = FormulaProfile(
        profile_id='two-stage-rounding',
        display_name='Two-stage rounding',
        formulas=StatFormulaSet(formula, formula, formula),
        modifier_application=ModifierApplication.SEQUENTIAL_MULTIPLICATIVE,
    )

    estimate = calculate_iv_range(
        stat=StatKind.HP,
        displayed_stat=16,
        level=1,
        base_stat=1,
        modifiers=StatModifiers(hp_soul_enhancement=10),
        profile=profile,
    )
    interval = reverse_stat_modifiers(
        16,
        stat=StatKind.HP,
        modifiers=StatModifiers(hp_soul_enhancement=10),
        formula=formula,
        profile=profile,
    )

    assert estimate.status is CalculationStatus.READY
    assert interval.contains(15.9)


def test_decimal_math_preserves_exact_raw_and_modifier_boundaries() -> None:
    raw_boundary = calculate_iv_range(
        stat=StatKind.HP,
        displayed_stat=1943,
        level=40,
        base_stat=50,
        modifiers=StatModifiers(),
        profile=DEFAULT_FORMULA_PROFILE,
    )
    modifier_formula = AffineIvFormula(
        flat_offset=50,
        base_multiplier=0,
        level_offset=0,
        level_multiplier=0,
        iv_level_offset=0,
        iv_level_multiplier=0,
        rounding=RoundingMode.FLOOR,
    )
    modifier_profile = FormulaProfile(
        profile_id='decimal-modifier-boundary',
        display_name='Decimal modifier boundary',
        formulas=StatFormulaSet(modifier_formula, modifier_formula, modifier_formula),
        modifier_application=ModifierApplication.SEQUENTIAL_MULTIPLICATIVE,
    )
    modifier_boundary = calculate_iv_range(
        stat=StatKind.HP,
        displayed_stat=57,
        level=1,
        base_stat=1,
        modifiers=StatModifiers(hp_soul_enhancement=14),
        profile=modifier_profile,
    )

    assert raw_boundary.min_iv == raw_boundary.max_iv == 81
    assert modifier_boundary.status is CalculationStatus.READY


def test_missing_pal_base_stats_has_explicit_result() -> None:
    result = calculate_pal_stats(_input(), profile=COMPLETE_PROFILE)

    assert result.hp.status is CalculationStatus.MISSING_BASE_STATS
    assert result.hp.display_value == 'Missing base-stat data'
    assert {issue.field for issue in result.validation_errors} == {
        'base_hp',
        'base_attack',
        'base_defense',
    }


def test_manual_base_stats_are_used() -> None:
    result = calculate_pal_stats(
        _input(manual_base=BASE_STATS),
        profile=COMPLETE_PROFILE,
    )

    assert result.hp.min_iv == 50
    assert result.base_stats_source == 'manual'


@pytest.mark.parametrize(
    ('field_value', 'expected_field'),
    (
        ('not a level', 'level'),
        (float('nan'), 'level'),
        (float('inf'), 'level'),
    ),
)
def test_invalid_and_non_finite_text_input(field_value: object, expected_field: str) -> None:
    result = calculate_pal_stats(
        _input(level=field_value),
        automatic_base_stats=BASE_STATS,
        profile=COMPLETE_PROFILE,
    )

    assert result.hp.status is CalculationStatus.INVALID
    assert expected_field in {issue.field for issue in result.validation_errors}


@pytest.mark.parametrize('displayed', (0, -1))
def test_zero_and_negative_current_stats_are_invalid(displayed: int) -> None:
    issues = validate_stat_inputs(
        _input(displayed=displayed),
        automatic_base_stats=BASE_STATS,
        profile=COMPLETE_PROFILE,
    )

    assert {'current_hp', 'current_attack', 'current_defense'} <= {
        issue.field for issue in issues
    }


def test_oversized_current_stat_is_invalid_instead_of_raising() -> None:
    result = calculate_pal_stats(
        _input(displayed=10**400),
        automatic_base_stats=BASE_STATS,
        profile=COMPLETE_PROFILE,
    )

    assert result.hp.status is CalculationStatus.INVALID
    assert {'current_hp', 'current_attack', 'current_defense'} <= {
        issue.field for issue in result.validation_errors
    }


def test_extreme_manual_base_stat_does_not_overflow() -> None:
    result = calculate_pal_stats(
        _input(
            displayed=100,
            manual_base=PalBaseStats(1e308, 100, 100),
            modifiers=StatModifiers(
                hp_soul_enhancement=60,
                hp_passive_percent=1000,
                hp_other_percent=1000,
                condenser_rank=4,
            ),
        ),
        profile=COMPLETE_PROFILE,
    )

    assert result.hp.status is CalculationStatus.UNABLE


def test_out_of_range_enhancement_is_invalid() -> None:
    values = _input(modifiers=StatModifiers(hp_soul_enhancement=1001))

    issues = validate_stat_inputs(
        values,
        automatic_base_stats=BASE_STATS,
        profile=COMPLETE_PROFILE,
    )

    assert any(issue.field == 'hp_soul_enhancement' for issue in issues)


def test_out_of_range_condenser_rank_is_invalid() -> None:
    values = _input(modifiers=StatModifiers(condenser_rank=5))

    issues = validate_stat_inputs(
        values,
        automatic_base_stats=BASE_STATS,
        profile=COMPLETE_PROFILE,
    )

    assert any(issue.field == 'condenser_rank' for issue in issues)


@pytest.mark.parametrize('percent', (-100, 1001))
def test_extreme_modifier_percentages_are_invalid(percent: int) -> None:
    values = _input(modifiers=StatModifiers(hp_other_percent=percent))

    issues = validate_stat_inputs(
        values,
        automatic_base_stats=BASE_STATS,
        profile=COMPLETE_PROFILE,
    )

    assert any(issue.field == 'hp_other_percent' for issue in issues)


def test_default_palworld_profile_calculates_known_unmodified_stats() -> None:
    result = calculate_pal_stats(
        PalStatInput('Melpaca', 50, 3337, 423, 438),
        automatic_base_stats=PalBaseStats(90, 75, 90),
        profile=DEFAULT_FORMULA_PROFILE,
    )

    assert result.hp.display_value == '50 IV'
    assert result.attack.display_value == '50 IV'
    assert result.defense.display_value == '50 IV'
    assert result.average_iv == 50


def test_explicitly_incomplete_profile_never_fabricates_an_iv() -> None:
    incomplete_profile = FormulaProfile(
        profile_id='incomplete-test',
        display_name='Incomplete test profile',
        formulas=StatFormulaSet(),
        modifier_application=None,
        incomplete_reason='Test formula is unavailable.',
    )

    result = calculate_pal_stats(
        _input(),
        automatic_base_stats=BASE_STATS,
        profile=incomplete_profile,
    )

    assert result.hp.status is CalculationStatus.FORMULA_INCOMPLETE
    assert result.hp.min_iv is None
    assert result.hp.display_value == 'Formula data incomplete'


def test_calculation_does_not_mutate_input_models() -> None:
    values = _input(
        modifiers=StatModifiers(hp_passive_percent=20),
        manual_base=PalBaseStats('100', '100', '100'),
    )
    before = deepcopy(values)

    calculate_pal_stats(values, profile=COMPLETE_PROFILE)

    assert values == before


def test_overall_summary_keeps_ranges_and_counts_only_exact_perfect_stats() -> None:
    result = calculate_pal_stats(
        PalStatInput('Test Pal', 10, 1100, 600, 100, manual_base_stats=BASE_STATS),
        profile=COMPLETE_PROFILE,
    )

    assert result.average_iv == pytest.approx(50)
    assert result.perfect_stats == 1
    assert result.overall_rating == 'Average'
