from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from functools import lru_cache
import logging
import re

from palworld_aio.game_data import load_game_data


LOGGER = logging.getLogger(__name__)

_GAME_TOKEN_RE = re.compile(
    r"\{[^{}]+\}|\[(?:EFFECT|ELEM|ICON):[^\]]+\]"
)
_PAL_VALUE_RE = re.compile(
    r"\{(?P<reference>Reference)?Passive(?P<passive>\d+)_"
    r"EffectValue(?P<effect>\d+)\}"
)
_REFERENCE_TEXT_RE = re.compile(r"\{ReferenceMsgId_(?P<name>[^{}]+)\}")
_STATUS_TAG_RE = re.compile(r"<Status_Up>(.*?)</>")
_RICH_TEXT_TAG_RE = re.compile(r"<[^>]+>")
_RANK_FAMILY_RE = re.compile(r"^(.*?)(\d+)(\D*)$")
_INTERNAL_PAL_RE = re.compile(
    r"^(?:BOSS_|PREDATOR_|GYM_|SUMMON_|Quest_)"
    r"|(?:_Oilrig|_Tower|_Quest|_BossRush)(?:_|$)",
    re.IGNORECASE,
)

_EFFECT_NAMES = {
    "Burn": "Burn",
    "Darkness": "Darkness",
    "Electrical": "Electrify",
    "Freeze": "Freeze",
    "IvyCling": "Ivy Cling",
    "Muddy": "Muddy",
    "Poison": "Poison",
    "Stun": "Stun",
    "Wetness": "Wetness",
}


def contains_game_tokens(text: str) -> bool:
    """Return whether text still contains an Unreal localization template token."""
    return bool(_GAME_TOKEN_RE.search(text or ""))


def _number(value: object) -> str:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return str(value)
    if numeric.is_integer():
        return str(int(numeric))
    return f"{numeric:g}"


def _range(values: Iterable[object]) -> str | None:
    displays: list[str] = []
    for value in values:
        if value is None:
            continue
        display = _number(value)
        if display not in displays:
            displays.append(display)
    if not displays:
        return None
    if len(displays) == 1:
        return displays[0]
    return f"{displays[0]}~{displays[-1]}"


def _clean_text(text: str) -> str:
    text = _RICH_TEXT_TAG_RE.sub("", text or "")
    lines = [" ".join(line.split()) for line in text.splitlines()]
    text = "\n".join(line for line in lines if line)
    text = re.sub(r"[ \t]+([,.;:)])", r"\1", text)
    text = re.sub(r"\(\s+", "(", text)
    return text.strip()


def _passive_signature(row: Mapping[str, object]) -> tuple[object, ...]:
    return tuple(
        row.get(f"{prefix}{index}")
        for prefix in ("efftype", "target_type")
        for index in range(1, 5)
    )


class WikiTextResolver:
    """Resolve extracted game localization templates into readable wiki text."""

    def __init__(
        self,
        *,
        passives: Sequence[Mapping[str, object]],
        elements: Sequence[Mapping[str, object]],
        append_text: Mapping[str, object],
        pals: Sequence[Mapping[str, object]],
    ) -> None:
        self._passives = {
            str(row.get("asset")): row
            for row in passives
            if row.get("asset")
        }
        self._families: dict[str, list[tuple[int, Mapping[str, object]]]] = {}
        for asset, row in self._passives.items():
            match = _RANK_FAMILY_RE.match(asset)
            if not match:
                continue
            family = f"{match.group(1)}{{rank}}{match.group(3)}"
            self._families.setdefault(family, []).append((int(match.group(2)), row))
        for rows in self._families.values():
            rows.sort(key=lambda entry: entry[0])

        self._elements = {
            str(row.get("name")): str(row.get("display") or row.get("name"))
            for row in elements
            if row.get("name")
        }
        self._append_text = {
            str(key).casefold(): str(value)
            for key, value in append_text.items()
        }

        self._pal_fallbacks: dict[tuple[str, str], list[Mapping[str, object]]] = {}
        for pal in pals:
            if not _is_public_pal(pal):
                continue
            key = (
                str(pal.get("partner_skill") or ""),
                str(pal.get("description") or ""),
            )
            self._pal_fallbacks.setdefault(key, []).append(pal)

    def resolve_partner_skill(self, pal: Mapping[str, object]) -> str:
        description = str(pal.get("description") or "")
        if not description:
            return ""

        sources = [pal]
        fallback_key = (
            str(pal.get("partner_skill") or ""),
            description,
        )
        sources.extend(
            candidate
            for candidate in self._pal_fallbacks.get(fallback_key, [])
            if candidate is not pal
        )

        def replace_passive(match: re.Match[str]) -> str:
            list_key = "reference_passives" if match.group("reference") else "passives"
            passive_number = int(match.group("passive"))
            effect_number = int(match.group("effect"))
            for source in sources:
                value = self._pal_passive_range(
                    source,
                    list_key=list_key,
                    passive_number=passive_number,
                    effect_number=effect_number,
                )
                if value is not None:
                    return value
            return self._unavailable(match.group(0), pal)

        description = _PAL_VALUE_RE.sub(replace_passive, description)
        if "{ActiveSkillMainValueByRank}" in description:
            description = description.replace(
                "{ActiveSkillMainValueByRank}",
                self._pal_array_range(sources, "active_skill_main_value", pal),
            )
        if "{ActiveSkillOverWriteEffectTime}" in description:
            description = description.replace(
                "{ActiveSkillOverWriteEffectTime}",
                self._pal_array_range(
                    sources,
                    "active_skill_overwrite_effect",
                    pal,
                ),
            )
        description = _REFERENCE_TEXT_RE.sub(self._replace_reference_text, description)
        description = re.sub(r"\[ICON:[^\]]+\]", " ", description)
        description = re.sub(
            r"\[ELEM:([^\]]+)\]",
            lambda match: self._elements.get(match.group(1), match.group(1)),
            description,
        )
        description = re.sub(
            r"\[EFFECT:([^\]]+)\]",
            lambda match: _EFFECT_NAMES.get(
                match.group(1),
                re.sub(r"(?<=[a-z])(?=[A-Z])", " ", match.group(1)),
            ),
            description,
        )
        return self._finish(description, pal)

    def resolve_passive(self, passive: Mapping[str, object]) -> str:
        description = str(passive.get("description") or "")

        def replace_value(match: re.Match[str]) -> str:
            value = passive.get(f"effect{match.group(1)}")
            if value is None:
                return self._unavailable(match.group(0), passive)
            numeric = float(value)
            prefix = description[:match.start()].rsplit("\n", 1)[-1].casefold()
            if numeric < 0 and (
                "extension" in prefix
                or re.search(r"\b(?:decrease|reduce)[^.]*\bby\s*$", prefix)
            ):
                numeric = abs(numeric)
            return _number(numeric)

        description = re.sub(r"\{EffectValue(\d+)\}", replace_value, description)
        return self._finish(description, passive)

    def _pal_passive_range(
        self,
        pal: Mapping[str, object],
        *,
        list_key: str,
        passive_number: int,
        effect_number: int,
    ) -> str | None:
        raw_assets = pal.get(list_key)
        if not isinstance(raw_assets, list) or passive_number > len(raw_assets):
            return None
        assets = [str(asset) for asset in raw_assets if asset]
        if passive_number > len(assets):
            return None
        target_asset = assets[passive_number - 1]
        target = self._passives.get(target_asset)
        if target is None:
            return None

        signature = _passive_signature(target)
        related_rows = []
        seen_assets: set[str] = set()
        for asset in assets:
            row = self._passives.get(asset)
            if row is None or _passive_signature(row) != signature or asset in seen_assets:
                continue
            related_rows.append(row)
            seen_assets.add(asset)

        rows = related_rows
        if len(rows) <= 1:
            match = _RANK_FAMILY_RE.match(target_asset)
            if match:
                family = f"{match.group(1)}{{rank}}{match.group(3)}"
                family_rows = [
                    row
                    for _rank, row in self._families.get(family, [])
                    if _passive_signature(row) == signature
                ]
                if family_rows:
                    rows = family_rows

        return _range(row.get(f"effect{effect_number}") for row in rows)

    def _pal_array_range(
        self,
        sources: Sequence[Mapping[str, object]],
        field: str,
        pal: Mapping[str, object],
    ) -> str:
        for source in sources:
            values = source.get(field)
            if isinstance(values, list):
                display = _range(values)
                if display is not None:
                    return display
        return self._unavailable(f"{{{field}}}", pal)

    def _replace_reference_text(self, match: re.Match[str]) -> str:
        base = match.group("name").casefold()
        values = [
            self._append_text.get(f"{base}_rank_{rank}", "")
            for rank in range(1, 6)
        ]
        values = [value for value in values if value.strip()]
        if not values:
            LOGGER.warning("No append text found for %s", match.group(0))
            return "value unavailable"
        return self._compress_rank_text(values)

    @staticmethod
    def _compress_rank_text(values: Sequence[str]) -> str:
        parsed = []
        for value in values:
            status_values = _STATUS_TAG_RE.findall(value)
            template = _STATUS_TAG_RE.sub("{}", value)
            parsed.append((_clean_text(template), status_values))
        first_template, first_values = parsed[0]
        last_template, last_values = parsed[-1]
        if (
            first_template == last_template
            and first_values
            and len(first_values) == len(last_values)
        ):
            replacements = [
                first if first == last else f"{first}~{last}"
                for first, last in zip(first_values, last_values)
            ]
            result = first_template
            for replacement in replacements:
                result = result.replace("{}", replacement, 1)
            return result
        first = _clean_text(values[0])
        last = _clean_text(values[-1])
        return first if first == last else f"Rank 2: {first}; Rank 5: {last}"

    def _finish(self, description: str, source: Mapping[str, object]) -> str:
        description = _clean_text(description)
        unresolved = _GAME_TOKEN_RE.findall(description)
        if unresolved:
            LOGGER.warning(
                "Unresolved wiki tokens for %s: %s",
                source.get("asset") or source.get("name") or "unknown entry",
                ", ".join(unresolved),
            )
            description = _GAME_TOKEN_RE.sub("value unavailable", description)
            description = _clean_text(description)
        return description

    @staticmethod
    def _unavailable(token: str, source: Mapping[str, object]) -> str:
        LOGGER.warning(
            "No game-data value for %s on %s",
            token,
            source.get("asset") or source.get("name") or "unknown entry",
        )
        return "value unavailable"


def _is_public_pal(item: Mapping[str, object]) -> bool:
    stats = item.get("stats")
    zukan_index = stats.get("zukan_index", 0) if isinstance(stats, Mapping) else 0
    asset = str(item.get("asset") or "")
    return bool(
        item.get("name")
        and asset
        and isinstance(zukan_index, (int, float))
        and zukan_index > 0
        and not _INTERNAL_PAL_RE.search(asset)
    )


def _is_public_entry(category: str, item: Mapping[str, object]) -> bool:
    if category == "pals":
        return _is_public_pal(item)
    if category == "passive_skills":
        return str(item.get("category") or "").endswith("SortDisplayable")
    if category == "active_skills":
        return bool(item.get("name")) and not (
            item.get("name") == item.get("asset")
            and not str(item.get("description") or "").strip()
        )
    if category == "items":
        return bool(item.get("name")) and not (
            item.get("name") == item.get("asset")
            and (
                item.get("sort_id") == 9999
                or not str(item.get("description") or "").strip()
            )
        )
    if category == "buildings":
        return bool(item.get("name")) and not (
            item.get("name") == item.get("asset")
            and not str(item.get("description") or "").strip()
        )
    return True


def prepare_wiki_entries(
    category: str,
    items: Sequence[Mapping[str, object]],
    *,
    resolver: WikiTextResolver | None = None,
) -> list[dict[str, object]]:
    """Filter internal records and attach resolved text used by the Wiki UI."""
    if category in ("pals", "passive_skills"):
        resolver = resolver or get_wiki_text_resolver()
    prepared: list[dict[str, object]] = []
    for item in items:
        if not _is_public_entry(category, item):
            continue
        display_item = dict(item)
        if category == "pals":
            assert resolver is not None
            display_item["_display_description"] = resolver.resolve_partner_skill(item)
        elif category == "passive_skills":
            assert resolver is not None
            display_item["_display_description"] = resolver.resolve_passive(item)
        prepared.append(display_item)
    return prepared


@lru_cache(maxsize=1)
def get_wiki_text_resolver() -> WikiTextResolver:
    skills = load_game_data("skills.json")
    characters = load_game_data("characters.json")
    append_text = load_game_data("append_text.json")
    return WikiTextResolver(
        passives=skills.get("passives", []),
        elements=skills.get("elements", []),
        append_text=append_text.get("append_text", {}),
        pals=characters.get("pals", []),
    )
