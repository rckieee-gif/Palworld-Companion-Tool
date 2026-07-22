from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from enum import StrEnum
from functools import lru_cache
from types import MappingProxyType
from typing import Iterable, Mapping, Sequence
from urllib.parse import parse_qs, quote, urlparse

from palworld_aio.game_data import load_game_data
from palworld_aio.wiki_text import prepare_wiki_entries


MAX_TEAM_SIZE = 5
TEAM_SHARE_SCHEME = "palworld-companion"
TEAM_SHARE_HOST = "team-builder"


class EffectCategory(StrEnum):
    COMBAT = "Combat bonuses"
    PLAYER = "Player bonuses"
    MOBILITY = "Mobility"
    DEFENSE = "Healing and defense"
    RESOURCES = "Resources and drops"
    CAPTURE = "Capture"
    WORK = "Work and production"
    STATUS = "Status effects"
    UTILITY = "Utility"


@dataclass(frozen=True, slots=True)
class WorkCapability:
    name: str
    level: int


@dataclass(frozen=True, slots=True)
class TeamMember:
    member_id: str
    slug: str
    name: str
    icon: str
    elements: tuple[str, ...]
    rarity: int
    paldeck_index: int
    partner_skill: str
    partner_description: str
    effect_categories: tuple[EffectCategory, ...]
    work_capabilities: tuple[WorkCapability, ...]


@dataclass(frozen=True, slots=True)
class EffectContribution:
    member_id: str
    member_name: str
    partner_skill: str
    description: str
    quantity: int
    stacking: str


@dataclass(frozen=True, slots=True)
class EffectSummary:
    category: EffectCategory
    contributions: tuple[EffectContribution, ...]


@dataclass(frozen=True, slots=True)
class TeamAnalysis:
    selected_count: int
    unique_count: int
    duplicate_counts: tuple[tuple[str, int], ...]
    element_distribution: tuple[tuple[str, int], ...]
    work_distribution: tuple[tuple[str, int], ...]
    effects: tuple[EffectSummary, ...]
    coverage_notes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class TeamParseResult:
    member_ids: tuple[str, ...]
    invalid_identifiers: tuple[str, ...]
    truncated_count: int = 0


_CATEGORY_KEYWORDS: tuple[tuple[EffectCategory, tuple[str, ...]], ...] = (
    (
        EffectCategory.COMBAT,
        (
            "attack",
            "damage",
            "bullet",
            "weapon",
            "missile",
            "grenade",
            "flamethrower",
            "submachine gun",
            "launcher",
            "weak point",
        ),
    ),
    (
        EffectCategory.PLAYER,
        (
            "player's attack",
            "player's defense",
            "player attack",
            "player defense",
            "carrying capacity",
            "weapon durability",
            "armor durability",
        ),
    ),
    (
        EffectCategory.MOBILITY,
        (
            "can be ridden",
            "flying mount",
            "movement speed",
            "ride speed",
            "double jump",
            "glider",
            "air dash",
            "travel on water",
        ),
    ),
    (
        EffectCategory.DEFENSE,
        (
            "restore the health",
            "restores health",
            "healing",
            "shield",
            "less damage",
            "damage taken",
            "defense",
            "immune to",
            "life steal",
            "health regeneration",
        ),
    ),
    (
        EffectCategory.RESOURCES,
        (
            "drop",
            "items obtained",
            "more ore",
            "chromite",
            "logging efficiency",
            "mining efficiency",
            "collection range",
            "nearby items",
            "weight of",
        ),
    ),
    (
        EffectCategory.CAPTURE,
        (
            "capture",
            "pal sphere",
            "sphere consumption",
        ),
    ),
    (
        EffectCategory.WORK,
        (
            "while at a base",
            "assigned to ranch",
            "work suitability",
            "work speed",
            "workbench",
            "breeding farm",
            "incubation",
            "crop",
            "egg production",
        ),
    ),
    (
        EffectCategory.STATUS,
        (
            "burn",
            "darkness",
            "electrify",
            "freeze",
            "ivy cling",
            "muddy",
            "poison",
            "stun",
            "wetness",
            "status ailment",
        ),
    ),
)


def classify_partner_effect(description: str) -> tuple[EffectCategory, ...]:
    text = description.casefold()
    categories = tuple(
        category
        for category, keywords in _CATEGORY_KEYWORDS
        if any(keyword in text for keyword in keywords)
    )
    return categories or (EffectCategory.UTILITY,)


@lru_cache(maxsize=1)
def load_team_members() -> tuple[TeamMember, ...]:
    characters = load_game_data("characters.json")
    skills = load_game_data("skills.json")
    work_data = load_game_data("work_suitability.json")
    rows = prepare_wiki_entries("pals", characters.get("pals", []))
    element_names = {
        str(row.get("name")): str(row.get("display") or row.get("name"))
        for row in skills.get("elements", [])
        if isinstance(row, Mapping) and row.get("name")
    }
    work_names = {
        str(row.get("id")): str(row.get("display_name") or row.get("id"))
        for row in work_data.get("work_types", [])
        if isinstance(row, Mapping) and row.get("id")
    }

    members: list[TeamMember] = []
    for row in rows:
        member_id = str(row.get("asset") or "")
        stats = row.get("stats") if isinstance(row.get("stats"), Mapping) else {}
        raw_elements = row.get("elements")
        elements = tuple(
            element_names.get(str(element), str(element))
            for element in raw_elements
        ) if isinstance(raw_elements, Mapping) else ()
        raw_work = row.get("work_suitabilities")
        work_capabilities = tuple(sorted(
            (
                WorkCapability(work_names.get(str(work_id), str(work_id)), int(level))
                for work_id, level in raw_work.items()
                if isinstance(level, (int, float)) and level > 0
            ),
            key=lambda capability: (-capability.level, capability.name.casefold()),
        )) if isinstance(raw_work, Mapping) else ()
        description = str(row.get("_display_description") or "")
        members.append(TeamMember(
            member_id=member_id,
            slug=member_id.casefold(),
            name=str(row.get("name") or member_id),
            icon=str(row.get("icon") or ""),
            elements=elements,
            rarity=int(stats.get("rarity", 0) or 0),
            paldeck_index=int(stats.get("zukan_index", 0) or 0),
            partner_skill=str(row.get("partner_skill") or ""),
            partner_description=description,
            effect_categories=classify_partner_effect(description),
            work_capabilities=work_capabilities,
        ))
    return tuple(sorted(
        members,
        key=lambda member: (member.paldeck_index, member.name.casefold()),
    ))


@lru_cache(maxsize=1)
def team_member_index() -> Mapping[str, TeamMember]:
    return MappingProxyType({
        member.member_id: member
        for member in load_team_members()
    })


def normalize_team_ids(
    member_ids: Iterable[str],
    valid_member_ids: Iterable[str],
) -> tuple[str, ...]:
    valid = set(valid_member_ids)
    normalized = [member_id for member_id in member_ids if member_id in valid]
    return tuple(normalized[:MAX_TEAM_SIZE])


def filter_team_members(
    members: Sequence[TeamMember],
    *,
    query: str = "",
    element: str | None = None,
    category: EffectCategory | None = None,
    work: str | None = None,
) -> tuple[TeamMember, ...]:
    terms = query.casefold().split()
    element_key = element.casefold() if element else None
    work_key = work.casefold() if work else None
    result = []
    for member in members:
        haystack = " ".join((
            member.name,
            member.member_id,
            member.partner_skill,
            member.partner_description,
            " ".join(member.elements),
        )).casefold()
        if terms and not all(term in haystack for term in terms):
            continue
        if element_key and not any(
            value.casefold() == element_key for value in member.elements
        ):
            continue
        if category is not None and category not in member.effect_categories:
            continue
        if work_key and not any(
            capability.name.casefold() == work_key
            for capability in member.work_capabilities
        ):
            continue
        result.append(member)
    return tuple(result)


def analyze_team(
    member_ids: Sequence[str],
    members_by_id: Mapping[str, TeamMember],
) -> TeamAnalysis:
    selected = [members_by_id[member_id] for member_id in member_ids if member_id in members_by_id]
    id_counts = Counter(member.member_id for member in selected)
    element_counts = Counter(
        element
        for member in selected
        for element in member.elements
    )
    work_counts = Counter(
        capability.name
        for member in selected
        for capability in member.work_capabilities
    )

    effects: list[EffectSummary] = []
    for category in EffectCategory:
        contributions = []
        seen: set[str] = set()
        for member in selected:
            if member.member_id in seen or category not in member.effect_categories:
                continue
            seen.add(member.member_id)
            description_key = member.partner_description.casefold()
            if "does not stack" in description_key:
                stacking = "Does not stack"
            elif "stacks up to" in description_key:
                stacking = "Defined cap in description"
            else:
                stacking = "Stacking unknown"
            contributions.append(EffectContribution(
                member_id=member.member_id,
                member_name=member.name,
                partner_skill=member.partner_skill,
                description=member.partner_description,
                quantity=id_counts[member.member_id],
                stacking=stacking,
            ))
        if contributions:
            effects.append(EffectSummary(category, tuple(contributions)))

    categories = {summary.category for summary in effects}
    notes: list[str] = []
    if not selected:
        notes.append("Select Pals to compare their elements and partner skills.")
    else:
        notes.append(
            f"Element coverage: {len(element_counts)} "
            f"{'element' if len(element_counts) == 1 else 'elements'}."
        )
        if len(element_counts) == 1 and len(selected) > 1:
            notes.append("This team is concentrated in one element.")
        if EffectCategory.DEFENSE not in categories:
            notes.append("No healing or defensive partner skill was identified.")
        if EffectCategory.MOBILITY not in categories:
            notes.append("No mobility partner skill was identified.")
        if any(count > 1 for count in id_counts.values()):
            notes.append(
                "Duplicate effects are listed by quantity; non-stacking effects "
                "are not totaled."
            )
        notes.append(
            "Numeric effects are shown per Pal because cross-skill stacking rules "
            "are not defined by the bundled data."
        )

    duplicates = tuple(sorted(
        (
            (members_by_id[member_id].name, count)
            for member_id, count in id_counts.items()
            if count > 1
        ),
        key=lambda item: item[0].casefold(),
    ))
    return TeamAnalysis(
        selected_count=len(selected),
        unique_count=len(id_counts),
        duplicate_counts=duplicates,
        element_distribution=tuple(sorted(
            element_counts.items(),
            key=lambda item: (-item[1], item[0].casefold()),
        )),
        work_distribution=tuple(sorted(
            work_counts.items(),
            key=lambda item: (-item[1], item[0].casefold()),
        )),
        effects=tuple(effects),
        coverage_notes=tuple(notes),
    )


def build_team_share_url(
    member_ids: Sequence[str],
    members_by_id: Mapping[str, TeamMember],
) -> str:
    slugs = [
        quote(members_by_id[member_id].slug, safe="_-")
        for member_id in member_ids[:MAX_TEAM_SIZE]
        if member_id in members_by_id
    ]
    base = f"{TEAM_SHARE_SCHEME}://{TEAM_SHARE_HOST}"
    return f"{base}?team={','.join(slugs)}" if slugs else base


def parse_team_share_url(
    value: str,
    members_by_id: Mapping[str, TeamMember],
) -> TeamParseResult:
    parsed = urlparse(value.strip())
    query = parsed.query
    if not query and value.lstrip().startswith("team="):
        query = value.strip()
    raw_team = parse_qs(query, keep_blank_values=True).get("team", [""])[0]
    identifiers = [
        identifier.strip()
        for identifier in raw_team.split(",")[:50]
        if identifier.strip()
    ]
    lookup = {
        member.slug.casefold(): member.member_id
        for member in members_by_id.values()
    }
    lookup.update({
        member.member_id.casefold(): member.member_id
        for member in members_by_id.values()
    })
    member_ids: list[str] = []
    invalid: list[str] = []
    truncated_count = 0
    for identifier in identifiers:
        member_id = lookup.get(identifier.casefold()) if len(identifier) <= 128 else None
        if member_id is None:
            invalid.append(identifier[:128])
            continue
        if len(member_ids) >= MAX_TEAM_SIZE:
            truncated_count += 1
            continue
        member_ids.append(member_id)
    return TeamParseResult(tuple(member_ids), tuple(invalid), truncated_count)


def is_team_share_url(value: str) -> bool:
    parsed = urlparse(value.strip())
    if parsed.scheme.casefold() == TEAM_SHARE_SCHEME:
        return parsed.netloc.casefold() == TEAM_SHARE_HOST
    return parsed.path.rstrip("/").casefold().endswith("/team-builder")


class TeamHistory:
    def __init__(self, initial: Sequence[str] = ()) -> None:
        self._entries = [tuple(initial[:MAX_TEAM_SIZE])]
        self._index = 0

    @property
    def can_back(self) -> bool:
        return self._index > 0

    @property
    def can_forward(self) -> bool:
        return self._index + 1 < len(self._entries)

    @property
    def current(self) -> tuple[str, ...]:
        return self._entries[self._index]

    def push(self, member_ids: Sequence[str]) -> tuple[str, ...]:
        entry = tuple(member_ids[:MAX_TEAM_SIZE])
        if entry == self.current:
            return entry
        del self._entries[self._index + 1:]
        self._entries.append(entry)
        self._index += 1
        return entry

    def back(self) -> tuple[str, ...]:
        if self.can_back:
            self._index -= 1
        return self.current

    def forward(self) -> tuple[str, ...]:
        if self.can_forward:
            self._index += 1
        return self.current
