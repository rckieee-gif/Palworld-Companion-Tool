from __future__ import annotations

from palworld_aio.breeding_analyzer import (
    BreedCombination,
    BreedingAnalyzer,
    BreedingPath,
    build_breeding_tree,
)
from palworld_aio.game_data import load_breeding_data


def _analyzer() -> BreedingAnalyzer:
    return BreedingAnalyzer({
        'pal_info': {
            name: {'name': name}
            for name in ('A', 'B', 'C', 'D', 'E', 'T')
        },
        'child_to_parents_formula': {
            'C': [{'parent_a': 'A', 'parent_b': 'B'}],
            'D': [{'parent_a': 'A', 'parent_b': 'C'}],
            'E': [{'parent_a': 'B', 'parent_b': 'D'}],
            'T': [
                {'parent_a': 'A', 'parent_b': 'E'},
                {'parent_a': 'C', 'parent_b': 'D'},
            ],
        },
    })


def test_bundled_formula_combination_resolves() -> None:
    analyzer = BreedingAnalyzer(load_breeding_data())
    assert analyzer.pair_to_child[
        analyzer.pair_key('SheepBall', 'ChickenPal')
    ] == 'Ganesha'


def test_bundled_special_combination_overrides_formula() -> None:
    analyzer = BreedingAnalyzer(load_breeding_data())
    assert analyzer.pair_to_child[
        analyzer.pair_key('LazyDragon', 'ElecCat')
    ] == 'LazyDragon_Electric'


def test_parent_search_contains_special_combination() -> None:
    analyzer = BreedingAnalyzer(load_breeding_data())
    assert ('ElecCat', 'LazyDragon') in analyzer.parents_by_child[
        'LazyDragon_Electric'
    ]


def test_find_chain_returns_shortest_route() -> None:
    path = _analyzer().find_chain('A', 'E', max_generations=3)
    assert path.reachable is True
    assert path.generation == 2
    assert path.steps == (
        BreedCombination('A', 'C', 'D', 1),
        BreedCombination('D', 'B', 'E', 2),
    )


def test_find_chain_respects_generation_limit() -> None:
    path = _analyzer().find_chain('A', 'E', max_generations=1)
    assert path.reachable is False
    assert path.steps == ()


def test_required_pal_forces_matching_route() -> None:
    path = _analyzer().find_chain(
        'A',
        'T',
        max_generations=3,
        required=('C',),
    )
    assert path.reachable is True
    assert path.generation == 2
    assert [step.child for step in path.steps] == ['C', 'T']
    tree = build_breeding_tree(path)
    assert tree is not None
    assert tree.species == 'T'


def test_unowned_partner_toggle_changes_reachability() -> None:
    analyzer = BreedingAnalyzer({
        'child_to_parents_formula': {
            'B': [{'parent_a': 'A', 'parent_b': 'X'}],
            'T': [{'parent_a': 'B', 'parent_b': 'Y'}],
        }
    })
    unrestricted = analyzer.find_chain(
        'A', 'T', max_generations=2, allow_unowned_partners=True
    )
    restricted = analyzer.find_chain(
        'A', 'T', max_generations=2, allow_unowned_partners=False
    )
    with_required = analyzer.find_chain(
        'A',
        'T',
        max_generations=2,
        required=('X', 'Y'),
        allow_unowned_partners=False,
    )
    assert unrestricted.reachable is True
    assert restricted.reachable is False
    assert with_required.reachable is True


def test_build_tree_rejects_unreachable_path() -> None:
    path = BreedingPath('T', False, False, None, ())
    assert build_breeding_tree(path) is None
