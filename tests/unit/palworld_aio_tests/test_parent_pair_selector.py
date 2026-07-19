from __future__ import annotations

from palworld_aio.ui.parent_pair_selector import build_parent_pair_options


def test_parent_pair_options_prioritize_available_and_filter_cycles() -> None:
    pal_info = {
        'A': {'name': 'Alpha', 'combi_rank': 10},
        'B': {'name': 'Beta', 'combi_rank': 20},
        'C': {'name': 'Charlie', 'combi_rank': 30},
        'D': {'name': 'Delta', 'combi_rank': 40},
        'T': {'name': 'Target', 'combi_rank': 50},
    }
    options = build_parent_pair_options(
        (('C', 'D'), ('A', 'B'), ('A', 'T')),
        pal_info,
        owned_species={'A', 'B'},
        unique_pairs={('C', 'D')},
        blocked_species={'T'},
    )

    assert [(option.parent_a, option.parent_b) for option in options] == [
        ('A', 'B'),
        ('C', 'D'),
    ]
    assert options[0].availability == 'Both available'
    assert options[1].is_special is True
    assert options[1].combined_power == 70
