from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Iterable


@dataclass
class SpeciesCount:
    total: int = 0
    male: int = 0
    female: int = 0
    unknown: int = 0

    def add(self, gender: str = '') -> None:
        self.total += 1
        gender_key = str(gender or '').lower()
        if gender_key.endswith('male') and not gender_key.endswith('female'):
            self.male += 1
        elif gender_key.endswith('female'):
            self.female += 1
        else:
            self.unknown += 1


@dataclass
class PlayerPalInventory:
    uid: str
    name: str
    species: dict[str, SpeciesCount] = field(default_factory=dict)

    @property
    def total_pals(self) -> int:
        return sum(entry.total for entry in self.species.values())


@dataclass(frozen=True)
class BreedCombination:
    parent_a: str
    parent_b: str
    child: str
    generation: int = 1


@dataclass(frozen=True)
class PathNode:
    generation: int
    steps: int
    parents: tuple[str, str] | None = None


@dataclass(frozen=True)
class BreedingPath:
    target: str
    reachable: bool
    already_owned: bool
    generation: int | None
    steps: tuple[BreedCombination, ...]
    tree: BreedingTreeNode | None = None


@dataclass(frozen=True)
class BreedingTreeNode:
    species: str
    parents: tuple[BreedingTreeNode, ...] = ()

    @property
    def is_leaf(self) -> bool:
        return not self.parents


@dataclass(frozen=True)
class _RequiredCandidate:
    generation: int
    steps: int
    tree: BreedingTreeNode


def build_breeding_tree(path: BreedingPath) -> BreedingTreeNode | None:
    if not path.reachable:
        return None
    if path.tree:
        return path.tree
    steps_by_child = {step.child: step for step in path.steps}

    def build(species: str, ancestors: frozenset[str]) -> BreedingTreeNode:
        step = steps_by_child.get(species)
        if not step or species in ancestors:
            return BreedingTreeNode(species)
        branch_ancestors = ancestors | {species}
        return BreedingTreeNode(
            species,
            (
                build(step.parent_a, branch_ancestors),
                build(step.parent_b, branch_ancestors),
            ),
        )

    return build(path.target, frozenset())


def _required_bit_map(required: Iterable[str]) -> dict[str, int]:
    ordered = tuple(dict.fromkeys(species for species in required if species))
    return {species: 1 << index for index, species in enumerate(ordered)}


def breeding_steps_from_tree(root: BreedingTreeNode) -> tuple[BreedCombination, ...]:
    steps: list[BreedCombination] = []

    def visit(node: BreedingTreeNode) -> int:
        if node.is_leaf:
            return 0
        parent_a, parent_b = node.parents
        generation = max(visit(parent_a), visit(parent_b)) + 1
        steps.append(BreedCombination(parent_a.species, parent_b.species, node.species, generation))
        return generation

    visit(root)
    return tuple(steps)


def breeding_tree_depth(root: BreedingTreeNode) -> int:
    if root.is_leaf:
        return 0
    return max(breeding_tree_depth(parent) for parent in root.parents) + 1


def breeding_tree_ancestors(
    root: BreedingTreeNode,
    target: BreedingTreeNode,
) -> frozenset[str]:
    def find(
        node: BreedingTreeNode,
        ancestors: frozenset[str],
    ) -> frozenset[str] | None:
        if node is target:
            return ancestors
        next_ancestors = ancestors | {node.species}
        for parent in node.parents:
            result = find(parent, next_ancestors)
            if result is not None:
                return result
        return None

    result = find(root, frozenset())
    if result is None:
        raise ValueError('The selected node is not part of this breeding tree.')
    return result


def expand_breeding_tree(
    root: BreedingTreeNode,
    target: BreedingTreeNode,
    parent_a: str,
    parent_b: str,
) -> BreedingTreeNode:
    if not target.is_leaf:
        raise ValueError('Only a leaf Pal can be expanded.')
    if not parent_a or not parent_b:
        raise ValueError('Both parent species are required.')

    blocked_species = breeding_tree_ancestors(root, target) | {target.species}
    if parent_a in blocked_species or parent_b in blocked_species:
        raise ValueError('That parent pair would create a circular breeding branch.')

    replacement = BreedingTreeNode(
        target.species,
        (BreedingTreeNode(parent_a), BreedingTreeNode(parent_b)),
    )

    def replace(node: BreedingTreeNode) -> BreedingTreeNode:
        if node is target:
            return replacement
        if node.is_leaf:
            return node
        parents = tuple(replace(parent) for parent in node.parents)
        if parents == node.parents:
            return node
        return BreedingTreeNode(node.species, parents)

    return replace(root)


class BreedingAnalyzer:
    def __init__(self, breeding_data: dict):
        self.breeding_data = breeding_data or {}
        raw_pal_info = self.breeding_data.get('pal_info', {})
        if not isinstance(raw_pal_info, dict):
            raw_pal_info = {}
        self.unavailable_species = frozenset(
            species
            for species, info in raw_pal_info.items()
            if isinstance(info, dict) and info.get('available') is False
        )
        self.pal_info = {
            species: info
            for species, info in raw_pal_info.items()
            if species not in self.unavailable_species
        }
        self.pair_to_child: dict[tuple[str, str], str] = {}
        self.children_by_parent: dict[str, list[tuple[str, str]]] = {}
        self.parents_by_child: dict[str, list[tuple[str, str]]] = {}
        self._build_pair_index()
        self._build_parent_index()

    @staticmethod
    def pair_key(parent_a: str, parent_b: str) -> tuple[str, str]:
        return tuple(sorted((parent_a, parent_b)))

    def _build_pair_index(self) -> None:
        # Later sources take priority, so explicit unique combinations win.
        for source in (
            'child_to_parents_formula',
            'child_to_parents_ignore',
            'child_to_parents_unique',
        ):
            for child, pairs in self.breeding_data.get(source, {}).items():
                if child in self.unavailable_species:
                    continue
                for pair in pairs:
                    parent_a = pair.get('parent_a')
                    parent_b = pair.get('parent_b')
                    if (
                        parent_a
                        and parent_b
                        and parent_a not in self.unavailable_species
                        and parent_b not in self.unavailable_species
                    ):
                        self.pair_to_child[self.pair_key(parent_a, parent_b)] = child
        for combo in self.breeding_data.get('unique_combos', []):
            parent_a = combo.get('parent_a')
            parent_b = combo.get('parent_b')
            child = combo.get('child')
            if (
                parent_a
                and parent_b
                and child
                and parent_a not in self.unavailable_species
                and parent_b not in self.unavailable_species
                and child not in self.unavailable_species
            ):
                self.pair_to_child[self.pair_key(parent_a, parent_b)] = child

    def _build_parent_index(self) -> None:
        for (parent_a, parent_b), child in self.pair_to_child.items():
            self.children_by_parent.setdefault(parent_a, []).append((parent_b, child))
            self.parents_by_child.setdefault(child, []).append((parent_a, parent_b))
            if parent_a != parent_b:
                self.children_by_parent.setdefault(parent_b, []).append((parent_a, child))
        for parent, children in self.children_by_parent.items():
            children.sort(key=lambda entry: (
                self.pal_info.get(entry[1], {}).get('name', entry[1]),
                self.pal_info.get(entry[0], {}).get('name', entry[0]),
            ))
        for child, parents in self.parents_by_child.items():
            parents.sort(key=lambda entry: (
                self.pal_info.get(entry[0], {}).get('name', entry[0]),
                self.pal_info.get(entry[1], {}).get('name', entry[1]),
            ))

    @staticmethod
    def can_breed(parent_a: str, parent_b: str, inventory: PlayerPalInventory) -> bool:
        count_a = inventory.species.get(parent_a)
        count_b = inventory.species.get(parent_b)
        if not count_a or not count_b:
            return False
        if parent_a == parent_b:
            if count_a.total < 2:
                return False
            return bool(
                (count_a.male and count_a.female)
                or count_a.unknown >= 2
                or (count_a.unknown and (count_a.male or count_a.female))
            )
        if count_a.unknown or count_b.unknown:
            return True
        return bool((count_a.male and count_b.female) or (count_a.female and count_b.male))

    def immediate_results(self, inventory: PlayerPalInventory) -> list[BreedCombination]:
        results = []
        for (parent_a, parent_b), child in self.pair_to_child.items():
            if self.can_breed(parent_a, parent_b, inventory):
                results.append(BreedCombination(parent_a, parent_b, child))
        return sorted(
            results,
            key=lambda item: (
                self.pal_info.get(item.child, {}).get('name', item.child),
                self.pal_info.get(item.parent_a, {}).get('name', item.parent_a),
                self.pal_info.get(item.parent_b, {}).get('name', item.parent_b),
            ),
        )

    def reachable_nodes(self, inventory: PlayerPalInventory, max_generations: int = 3) -> dict[str, PathNode]:
        max_generations = max(1, int(max_generations))
        nodes = {
            species: PathNode(generation=0, steps=0)
            for species, count in inventory.species.items()
            if count.total > 0 and species not in self.unavailable_species
        }
        ordered_pairs = sorted(self.pair_to_child.items())
        changed = True
        while changed:
            changed = False
            for (parent_a, parent_b), child in ordered_pairs:
                node_a = nodes.get(parent_a)
                node_b = nodes.get(parent_b)
                if node_a is None or node_b is None:
                    continue
                if node_a.generation == 0 and node_b.generation == 0:
                    if not self.can_breed(parent_a, parent_b, inventory):
                        continue
                elif parent_a == parent_b and node_a.generation == 0:
                    if not self.can_breed(parent_a, parent_b, inventory):
                        continue
                generation = max(node_a.generation, node_b.generation) + 1
                if generation > max_generations:
                    continue
                steps = node_a.steps + node_b.steps + 1
                candidate = PathNode(generation=generation, steps=steps, parents=(parent_a, parent_b))
                current = nodes.get(child)
                if current is None or (candidate.generation, candidate.steps, candidate.parents) < (
                    current.generation,
                    current.steps,
                    current.parents or ('', ''),
                ):
                    nodes[child] = candidate
                    changed = True
        return nodes

    def find_path(
        self,
        inventory: PlayerPalInventory,
        target: str,
        max_generations: int = 3,
        required: Iterable[str] = (),
    ) -> BreedingPath:
        required = tuple(required)
        if target in self.unavailable_species or any(
            species in self.unavailable_species for species in required
        ):
            return BreedingPath(target, False, False, None, ())
        required_bits = _required_bit_map(required)
        if required_bits:
            return self._find_path_with_required(
                inventory,
                target,
                max_generations,
                required_bits,
            )
        nodes = self.reachable_nodes(inventory, max_generations)
        target_node = nodes.get(target)
        if target_node is None:
            return BreedingPath(target, False, False, None, ())
        if target_node.generation == 0:
            return BreedingPath(target, True, True, 0, ())

        steps: list[BreedCombination] = []
        visited = set()

        def visit(species: str) -> None:
            node = nodes.get(species)
            if not node or not node.parents or species in visited:
                return
            parent_a, parent_b = node.parents
            visit(parent_a)
            visit(parent_b)
            visited.add(species)
            steps.append(BreedCombination(parent_a, parent_b, species, node.generation))

        visit(target)
        return BreedingPath(target, True, False, target_node.generation, tuple(steps))

    def _find_path_with_required(
        self,
        inventory: PlayerPalInventory,
        target: str,
        max_generations: int,
        required_bits: dict[str, int],
    ) -> BreedingPath:
        max_generations = max(1, int(max_generations))
        required_mask = (1 << len(required_bits)) - 1
        memo: dict[tuple[str, int], dict[int, _RequiredCandidate]] = {}

        def score(candidate: _RequiredCandidate) -> tuple[int, int]:
            return candidate.generation, candidate.steps

        def add_candidate(
            bucket: dict[int, _RequiredCandidate],
            mask: int,
            candidate: _RequiredCandidate,
        ) -> None:
            for existing_mask, existing in bucket.items():
                if existing_mask | mask == existing_mask and score(existing) <= score(candidate):
                    return
            dominated = [
                existing_mask
                for existing_mask, existing in bucket.items()
                if existing_mask | mask == mask and score(candidate) <= score(existing)
            ]
            for existing_mask in dominated:
                del bucket[existing_mask]
            bucket[mask] = candidate

        def solve(species: str, depth: int) -> dict[int, _RequiredCandidate]:
            key = species, depth
            cached = memo.get(key)
            if cached is not None:
                return cached
            candidates: dict[int, _RequiredCandidate] = {}
            count = inventory.species.get(species)
            if count and count.total > 0:
                add_candidate(candidates, required_bits.get(species, 0), _RequiredCandidate(
                    generation=0,
                    steps=0,
                    tree=BreedingTreeNode(species),
                ))
            if depth > 0:
                for parent_a, parent_b in self.parents_by_child.get(species, ()):
                    candidates_a = solve(parent_a, depth - 1)
                    if not candidates_a:
                        continue
                    candidates_b = solve(parent_b, depth - 1)
                    if not candidates_b:
                        continue
                    for mask_a, candidate_a in candidates_a.items():
                        for mask_b, candidate_b in candidates_b.items():
                            if candidate_a.generation == 0 and candidate_b.generation == 0:
                                if not self.can_breed(parent_a, parent_b, inventory):
                                    continue
                            generation = max(candidate_a.generation, candidate_b.generation) + 1
                            if generation > depth:
                                continue
                            mask = mask_a | mask_b | required_bits.get(species, 0)
                            add_candidate(candidates, mask, _RequiredCandidate(
                                generation=generation,
                                steps=candidate_a.steps + candidate_b.steps + 1,
                                tree=BreedingTreeNode(
                                    species,
                                    (candidate_a.tree, candidate_b.tree),
                                ),
                            ))
            memo[key] = candidates
            return candidates

        target_candidate = solve(target, max_generations).get(required_mask)
        if target_candidate is None:
            return BreedingPath(target, False, False, None, ())
        already_owned = target_candidate.generation == 0
        steps = breeding_steps_from_tree(target_candidate.tree)
        return BreedingPath(
            target,
            True,
            already_owned,
            target_candidate.generation,
            steps,
            target_candidate.tree,
        )

    def find_chain(
        self,
        start: str,
        target: str,
        max_generations: int = 3,
        required: Iterable[str] = (),
        allow_unowned_partners: bool = True,
    ) -> BreedingPath:
        return self.find_chain_from_any(
            (start,),
            target,
            max_generations,
            required,
            allow_unowned_partners,
        )

    def find_chain_from_any(
        self,
        starts: Iterable[str],
        target: str,
        max_generations: int = 3,
        required: Iterable[str] = (),
        allow_unowned_partners: bool = True,
    ) -> BreedingPath:
        max_generations = max(1, int(max_generations))
        required = tuple(required)
        if target in self.unavailable_species or any(
            species in self.unavailable_species for species in required
        ):
            return BreedingPath(target, False, False, None, ())
        start_set = {
            start
            for start in starts
            if start and start not in self.unavailable_species
        }
        if not start_set:
            return BreedingPath(target, False, False, None, ())
        required_bits = _required_bit_map(required)
        if required_bits:
            return self._find_chain_with_required(
                start_set,
                target,
                max_generations,
                required_bits,
                allow_unowned_partners,
            )
        if target in start_set:
            return BreedingPath(target, True, True, 0, ())

        ordered_starts = sorted(
            start_set,
            key=lambda species: self.pal_info.get(species, {}).get('name', species),
        )
        initial_available = frozenset(start_set)
        queue = deque((start, (), initial_available) for start in ordered_starts)
        visited_depth = {
            (start, initial_available) if not allow_unowned_partners else start: 0
            for start in ordered_starts
        }
        while queue:
            current, steps, available = queue.popleft()
            depth = len(steps)
            if depth >= max_generations:
                continue
            for partner, child in self.children_by_parent.get(current, []):
                if child == current or partner == target:
                    continue
                if not allow_unowned_partners and partner not in available:
                    continue
                generation = depth + 1
                next_steps = steps + (BreedCombination(current, partner, child, generation),)
                if child == target:
                    return BreedingPath(target, True, False, generation, next_steps)
                next_available = available | {child}
                state = (
                    (child, next_available)
                    if not allow_unowned_partners
                    else child
                )
                if generation < visited_depth.get(state, max_generations + 1):
                    visited_depth[state] = generation
                    queue.append((child, next_steps, next_available))
        return BreedingPath(target, False, False, None, ())

    def _find_chain_with_required(
        self,
        start_set: set[str],
        target: str,
        max_generations: int,
        required_bits: dict[str, int],
        allow_unowned_partners: bool,
    ) -> BreedingPath:
        required_mask = (1 << len(required_bits)) - 1
        ordered_starts = sorted(
            start_set,
            key=lambda species: self.pal_info.get(species, {}).get('name', species),
        )
        queue = deque()
        visited_depth = {}
        initial_available = frozenset(start_set | set(required_bits))
        for start in ordered_starts:
            mask = required_bits.get(start, 0)
            tree = BreedingTreeNode(start)
            if start == target and mask == required_mask:
                return BreedingPath(target, True, True, 0, (), tree)
            state = (
                (start, mask, initial_available)
                if not allow_unowned_partners
                else (start, mask)
            )
            visited_depth[state] = 0
            queue.append((start, mask, (), tree, initial_available))

        while queue:
            current, mask, steps, tree, available = queue.popleft()
            depth = len(steps)
            if depth >= max_generations:
                continue
            for partner, child in self.children_by_parent.get(current, ()):
                if child == current or partner == target:
                    continue
                if not allow_unowned_partners and partner not in available:
                    continue
                generation = depth + 1
                child_mask = mask | required_bits.get(partner, 0) | required_bits.get(child, 0)
                child_tree = BreedingTreeNode(
                    child,
                    (tree, BreedingTreeNode(partner)),
                )
                next_steps = steps + (BreedCombination(current, partner, child, generation),)
                if child == target and child_mask == required_mask:
                    return BreedingPath(
                        target,
                        True,
                        False,
                        generation,
                        next_steps,
                        child_tree,
                    )
                next_available = available | {child}
                state = (
                    (child, child_mask, next_available)
                    if not allow_unowned_partners
                    else (child, child_mask)
                )
                if generation < visited_depth.get(state, max_generations + 1):
                    visited_depth[state] = generation
                    queue.append((child, child_mask, next_steps, child_tree, next_available))
        return BreedingPath(target, False, False, None, ())
