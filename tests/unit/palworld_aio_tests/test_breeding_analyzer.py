from __future__ import annotations

from palworld_aio.breeding_analyzer import (
    BreedCombination,
    BreedingAnalyzer,
    BreedingPath,
    BreedingTreeNode,
    breeding_steps_from_tree,
    breeding_tree_ancestors,
    breeding_tree_depth,
    build_breeding_tree,
    expand_breeding_tree,
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


def test_unavailable_species_are_removed_from_breeding_graph() -> None:
    analyzer = BreedingAnalyzer({
        'pal_info': {
            'A': {'name': 'A'},
            'Hidden': {'name': 'Hidden', 'available': False},
            'T': {'name': 'T'},
        },
        'child_to_parents_ignore': {
            'T': [{'parent_a': 'A', 'parent_b': 'Hidden'}],
        },
        'unique_combos': [
            {'parent_a': 'Hidden', 'parent_b': 'Hidden', 'child': 'Hidden'},
        ],
    })

    assert 'Hidden' not in analyzer.pal_info
    assert analyzer.pair_key('A', 'Hidden') not in analyzer.pair_to_child
    assert analyzer.find_chain('A', 'T').reachable is False


def test_bundled_paths_exclude_development_only_pals() -> None:
    analyzer = BreedingAnalyzer(load_breeding_data())
    unavailable = {
        'BlackFurDragon',
        'CandleWitch',
        'ElecLion',
        'Strawhatcat',
        'VolcanicTurtle',
    }

    assert unavailable.isdisjoint(analyzer.pal_info)
    assert analyzer.pair_key(
        'LazyCatfish_Gold', 'ElecLion'
    ) not in analyzer.pair_to_child
    assert 'ElecPanda' in analyzer.pal_info
    assert analyzer.children_by_parent['ElecPanda']

    path = analyzer.find_chain(
        'LazyCatfish_Gold', 'ChickenPal', max_generations=6
    )
    assert path.reachable is True
    assert path.generation == 6
    assert all(
        step.parent_a not in unavailable
        and step.parent_b not in unavailable
        and step.child not in unavailable
        for step in path.steps
    )
    assert all(
        'ChickenPal' not in (step.parent_a, step.parent_b)
        for step in path.steps
    )


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


def test_target_is_not_used_as_an_unowned_partner() -> None:
    analyzer = BreedingAnalyzer({
        'pal_info': {
            name: {'name': name}
            for name in ('A', 'B', 'T', 'X')
        },
        'child_to_parents_formula': {
            'B': [{'parent_a': 'A', 'parent_b': 'T'}],
            'T': [{'parent_a': 'B', 'parent_b': 'X'}],
        },
    })

    path = analyzer.find_chain(
        'A', 'T', max_generations=2, allow_unowned_partners=True
    )
    assert path.reachable is False


def test_build_tree_rejects_unreachable_path() -> None:
    path = BreedingPath('T', False, False, None, ())
    assert build_breeding_tree(path) is None


def test_leaf_can_be_expanded_into_a_parent_pair() -> None:
    leaf = BreedingTreeNode('E')
    root = BreedingTreeNode('T', (BreedingTreeNode('A'), leaf))

    expanded = expand_breeding_tree(root, leaf, 'B', 'D')

    assert expanded.parents[1] == BreedingTreeNode(
        'E',
        (BreedingTreeNode('B'), BreedingTreeNode('D')),
    )
    assert breeding_tree_depth(expanded) == 2
    assert breeding_steps_from_tree(expanded) == (
        BreedCombination('B', 'D', 'E', 1),
        BreedCombination('A', 'E', 'T', 2),
    )


def test_expansion_rejects_a_circular_parent_branch() -> None:
    leaf = BreedingTreeNode('E')
    root = BreedingTreeNode('T', (BreedingTreeNode('A'), leaf))

    assert breeding_tree_ancestors(root, leaf) == frozenset({'T'})
    try:
        expand_breeding_tree(root, leaf, 'B', 'T')
    except ValueError as exc:
        assert 'circular' in str(exc)
    else:
        raise AssertionError('Circular expansion should be rejected.')
