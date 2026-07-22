from __future__ import annotations

from palworld_aio.pal_stats_repository import (
    PalLookupStatus,
    PalStatsRecord,
    PalStatsRepository,
)
from palworld_aio.stat_calculator import PalBaseStats


def test_bundled_repository_loads_canonical_displayed_stat_scaling() -> None:
    repository = PalStatsRepository.from_game_data()

    assert len(repository.records) == 299
    melpaca = repository.resolve('Melpaca')
    assert melpaca.status is PalLookupStatus.FOUND
    assert melpaca.record is not None
    assert melpaca.record.pal_id == 'Alpaca'
    assert melpaca.record.base_stats == PalBaseStats(90, 75, 90)


def test_plain_name_prefers_canonical_pal_over_boss_variants() -> None:
    repository = PalStatsRepository.from_game_data()

    anubis = repository.resolve('Anubis')

    assert anubis.status is PalLookupStatus.FOUND
    assert anubis.record is not None
    assert anubis.record.pal_id == 'Anubis'
    assert repository.resolve('Boss_Anubis').status is PalLookupStatus.MISSING
    assert repository.resolve('ElecLion').status is PalLookupStatus.MISSING


def test_pal_name_and_internal_id_matching_is_case_insensitive() -> None:
    repository = PalStatsRepository.from_game_data()

    assert repository.resolve('mElPaCa').record == repository.resolve('ALPACA').record


def test_unknown_pal_name_is_missing() -> None:
    repository = PalStatsRepository.from_game_data()

    assert repository.resolve('Definitely Not A Pal').status is PalLookupStatus.MISSING


def test_duplicate_display_names_are_ambiguous_but_ids_are_resolvable() -> None:
    repository = PalStatsRepository((
        PalStatsRecord('Foo_A', 'Foo', PalBaseStats(1, 2, 3), 'Foo \u2014 Foo_A'),
        PalStatsRecord('Foo_B', 'Foo', PalBaseStats(4, 5, 6), 'Foo \u2014 Foo_B'),
    ))

    assert repository.resolve('foo').status is PalLookupStatus.AMBIGUOUS
    assert repository.resolve('foo_b').record.base_stats == PalBaseStats(4, 5, 6)
    assert repository.resolve('FOO \u2014 FOO_A').record.pal_id == 'Foo_A'
