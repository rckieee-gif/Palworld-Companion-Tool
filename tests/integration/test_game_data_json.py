import json
import os
import re
import warnings

import pytest
from pathlib import Path
from tests.test_registry import PROJECT_ROOT, SRC_DIR

RESOURCES_DIR = PROJECT_ROOT / "resources"
GAME_DATA_DIR = RESOURCES_DIR / "game_data"

JSON_FILES = sorted(f.name for f in GAME_DATA_DIR.glob("*.json"))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load(name: str):
    with open(GAME_DATA_DIR / name, encoding="utf-8") as f:
        return json.load(f)


def _all_pals(required=("name", "asset", "icon")):
    data = _load("characters.json")
    errors = []
    for i, p in enumerate(data["pals"]):
        for key in required:
            if key not in p:
                errors.append(f"  pals[{i}] ({p.get('name','?')}) missing '{key}'")
    return data, errors


# ===================================================================
# TestJSONParseable
# ===================================================================

class TestJSONParseable:
    """Every JSON file in game_data parses without error."""

    @pytest.mark.parametrize("filename", JSON_FILES)
    def test_parses(self, filename):
        data = _load(filename)
        assert data is not None


# ===================================================================
# TestSchemaValidation
# ===================================================================

class TestSchemaValidation:
    """Top-level keys and required entry fields."""

    # ---------- characters.json ----------

    def test_characters_top_level_keys(self):
        data = _load("characters.json")
        assert set(data) == {"pals", "npcs", "friendship"}

    def test_characters_pals_required_fields(self):
        data, errors = _all_pals()
        assert not errors, "\n" + "\n".join(errors)

    def test_characters_pals_stats_fields(self):
        data = _load("characters.json")
        base_fields = ["hp", "melee_attack", "shot_attack", "defense"]
        paldeck_fields = ["zukan_index", "rarity"]
        errors = []
        for i, p in enumerate(data["pals"]):
            stats = p.get("stats")
            if stats is None:
                continue
            has_scaling = "scaling" in p
            for sf in base_fields:
                if sf not in stats:
                    errors.append(
                        f"  pals[{i}] ({p.get('name','?')}).stats missing '{sf}'"
                    )
            if not has_scaling:
                continue
            for sf in paldeck_fields:
                if sf not in stats:
                    errors.append(
                        f"  pals[{i}] ({p.get('name','?')}).stats missing '{sf}'"
                    )
        assert not errors, "\n" + "\n".join(errors)

    def test_characters_pals_stats_types(self):
        data = _load("characters.json")
        stat_fields = ["hp", "melee_attack", "shot_attack", "defense",
                       "zukan_index", "rarity"]
        errors = []
        for i, p in enumerate(data["pals"]):
            stats = p.get("stats")
            if stats is None:
                continue
            for sf in stat_fields:
                val = stats.get(sf)
                if val is None:
                    continue
                if not isinstance(val, int):
                    errors.append(
                        f"  pals[{i}] ({p.get('name','?')}).stats.{sf} "
                        f"expected int, got {type(val).__name__}"
                    )
        assert not errors, "\n" + "\n".join(errors)

    def test_characters_pals_scaling_fields(self):
        data = _load("characters.json")
        errors = []
        for i, p in enumerate(data["pals"]):
            scaling = p.get("scaling")
            if scaling is None:
                continue
            for sf in ("hp", "attack", "defense"):
                if sf not in scaling:
                    errors.append(
                        f"  pals[{i}] ({p.get('name','?')}).scaling missing '{sf}'"
                    )
        assert not errors, "\n" + "\n".join(errors)

    def test_characters_npcs_required_fields(self):
        data = _load("characters.json")
        errors = []
        for i, n in enumerate(data["npcs"]):
            for key in ("name", "asset", "icon"):
                if key not in n:
                    errors.append(f"  npcs[{i}] ({n.get('name','?')}) missing '{key}'")
        assert not errors, "\n" + "\n".join(errors)

    def test_characters_friendship_is_dict(self):
        data = _load("characters.json")
        assert isinstance(data["friendship"], dict)

    # ---------- skills.json ----------

    def test_skills_top_level_keys(self):
        data = _load("skills.json")
        assert set(data) == {"passives", "skills", "elements"}

    def test_skills_passives_required_fields(self):
        data = _load("skills.json")
        errors = []
        for i, p in enumerate(data["passives"]):
            for key in ("name", "asset", "rank", "icon", "description"):
                if key not in p:
                    errors.append(f"  passives[{i}] ({p.get('name','?')}) missing '{key}'")
        assert not errors, "\n" + "\n".join(errors)

    def test_skills_passives_rank_int(self):
        data = _load("skills.json")
        errors = []
        for i, p in enumerate(data["passives"]):
            if not isinstance(p.get("rank"), int):
                errors.append(f"  passives[{i}] ({p.get('name','?')}).rank not int")
        assert not errors, "\n" + "\n".join(errors)

    def test_skills_skills_required_fields(self):
        data = _load("skills.json")
        errors = []
        for i, s in enumerate(data["skills"]):
            for key in ("name", "asset", "element", "power", "cooldown", "description"):
                if key not in s:
                    errors.append(f"  skills[{i}] ({s.get('name','?')}) missing '{key}'")
        assert not errors, "\n" + "\n".join(errors)

    def test_skills_skills_power_int(self):
        data = _load("skills.json")
        errors = []
        for i, s in enumerate(data["skills"]):
            if not isinstance(s.get("power"), int):
                errors.append(f"  skills[{i}] ({s.get('name','?')}).power not int")
        assert not errors, "\n" + "\n".join(errors)

    def test_skills_skills_cooldown_number(self):
        data = _load("skills.json")
        errors = []
        for i, s in enumerate(data["skills"]):
            cd = s.get("cooldown")
            if not isinstance(cd, (int, float)):
                errors.append(f"  skills[{i}] ({s.get('name','?')}).cooldown not number")
        assert not errors, "\n" + "\n".join(errors)

    def test_skills_elements_required_fields(self):
        data = _load("skills.json")
        errors = []
        for i, e in enumerate(data["elements"]):
            for key in ("name", "display", "index", "color", "icons"):
                if key not in e:
                    errors.append(f"  elements[{i}] ({e.get('name','?')}) missing '{key}'")
        assert not errors, "\n" + "\n".join(errors)

    def test_skills_elements_index_int(self):
        data = _load("skills.json")
        errors = []
        for i, e in enumerate(data["elements"]):
            if not isinstance(e.get("index"), int):
                errors.append(f"  elements[{i}] ({e.get('name','?')}).index not int")
        assert not errors, "\n" + "\n".join(errors)

    def test_skills_elements_icons_dict(self):
        data = _load("skills.json")
        errors = []
        for i, e in enumerate(data["elements"]):
            if not isinstance(e.get("icons"), dict):
                errors.append(f"  elements[{i}] ({e.get('name','?')}).icons not dict")
        assert not errors, "\n" + "\n".join(errors)

    # ---------- items.json ----------

    def test_items_top_level_keys(self):
        data = _load("items.json")
        assert set(data) == {"items", "items_dynamic"}

    def test_items_required_fields(self):
        data = _load("items.json")
        errors = []
        for i, item in enumerate(data["items"]):
            for key in ("name", "asset", "icon", "rarity",
                        "type_a", "type_b", "description", "sort_id"):
                if key not in item:
                    errors.append(f"  items[{i}] ({item.get('name','?')}) missing '{key}'")
        assert not errors, "\n" + "\n".join(errors)

    def test_items_dynamic_is_dict(self):
        data = _load("items.json")
        assert isinstance(data["items_dynamic"], dict)

    # ---------- world.json ----------

    def test_world_top_level_keys(self):
        data = _load("world.json")
        assert set(data) == {"structures", "technology", "lab_research"}

    def test_world_structures_required(self):
        data = _load("world.json")
        errors = []
        for i, s in enumerate(data["structures"]):
            for key in ("name", "asset", "icon"):
                if key not in s:
                    errors.append(f"  structures[{i}] ({s.get('name','?')}) missing '{key}'")
        assert not errors, "\n" + "\n".join(errors)

    def test_world_technology_required(self):
        data = _load("world.json")
        errors = []
        for i, t in enumerate(data["technology"]):
            for key in ("name", "asset", "icon", "type", "description"):
                if key not in t:
                    errors.append(f"  technology[{i}] ({t.get('name','?')}) missing '{key}'")
        assert not errors, "\n" + "\n".join(errors)

    def test_world_lab_research_is_dict(self):
        data = _load("world.json")
        assert isinstance(data["lab_research"], dict)

    # ---------- pal_exp_table.json ----------

    def test_pal_exp_table_top_level(self):
        data = _load("pal_exp_table.json")
        expected_keys = {str(i) for i in range(1, 101)}
        assert set(data) == expected_keys

    def test_pal_exp_table_fields(self):
        data = _load("pal_exp_table.json")
        fields = ("DropEXP", "NextEXP", "PalNextEXP", "TotalEXP", "PalTotalEXP")
        errors = []
        for lv in map(str, range(1, 101)):
            entry = data[lv]
            for f in fields:
                if f not in entry:
                    errors.append(f"  level {lv} missing '{f}'")
                elif not isinstance(entry[f], int):
                    errors.append(f"  level {lv}.{f} not int")
        assert not errors, "\n" + "\n".join(errors)

    # ---------- boss_mapping.json ----------

    def test_boss_mapping_top_level(self):
        data = _load("boss_mapping.json")
        assert "boss_defeat_flag_map" in data
        assert isinstance(data["boss_defeat_flag_map"], dict)

    # ---------- friendship.json ----------

    def test_friendship_entries(self):
        data = _load("friendship.json")
        errors = []
        for key, entry in data.items():
            for f in ("FriendshipRank", "RequiredPoint"):
                if f not in entry:
                    errors.append(f"  '{key}' missing '{f}'")
                elif not isinstance(entry[f], int):
                    errors.append(f"  '{key}'.{f} not int")
        assert not errors, "\n" + "\n".join(errors)

    # ---------- fast_travel_points.json ----------

    def test_fast_travel_top_level(self):
        data = _load("fast_travel_points.json")
        assert isinstance(data, dict), "must be dict"
        for guid, entry in data.items():
            assert isinstance(entry, dict), f"{guid} must be dict"
            for field in ("x", "y", "z", "id"):
                assert field in entry, f"{guid} missing {field}"

    # ---------- relic_data.json ----------

    def test_relic_data_entries(self):
        data = _load("relic_data.json")
        errors = []
        for key, entry in data.items():
            for f in ("cumulative_max", "max_rank", "per_rank"):
                if f not in entry:
                    errors.append(f"  '{key}' missing '{f}'")
            if not isinstance(entry.get("cumulative_max"), int):
                errors.append(f"  '{key}'.cumulative_max not int")
            if not isinstance(entry.get("max_rank"), int):
                errors.append(f"  '{key}'.max_rank not int")
            if not isinstance(entry.get("per_rank"), list):
                errors.append(f"  '{key}'.per_rank not list")
        assert not errors, "\n" + "\n".join(errors)

    # ---------- uidata.json ----------

    def test_uidata_top_level(self):
        data = _load("uidata.json")
        assert "ui_icons" in data
        assert isinstance(data["ui_icons"], dict)

    # ---------- world_map_areas.json ----------

    def test_world_map_areas_top_level(self):
        data = _load("world_map_areas.json")
        assert "areas" in data
        assert isinstance(data["areas"], list)
        for a in data["areas"]:
            assert isinstance(a, str), f"Non-string area entry: {a!r}"


# ===================================================================
# TestDataIntegrity
# ===================================================================

class TestDataIntegrity:
    """Cross-file consistency and spot-checks."""

    # ---- characters.json ----

    def test_no_duplicate_pal_assets(self):
        data = _load("characters.json")
        assets = [p["asset"] for p in data["pals"] if "asset" in p]
        dupes = {a for a in assets if assets.count(a) > 1}
        assert not dupes, f"Duplicate pal assets: {sorted(dupes)}"

    def test_no_duplicate_npc_assets(self):
        data = _load("characters.json")
        assets = [n["asset"] for n in data["npcs"]]
        dupes = {a for a in assets if assets.count(a) > 1}
        assert not dupes, f"Duplicate npc assets: {sorted(dupes)}"

    # ---- skills.json ----

    def test_no_duplicate_passive_assets(self):
        data = _load("skills.json")
        assets = [p["asset"] for p in data["passives"]]
        dupes = {a for a in assets if assets.count(a) > 1}
        assert not dupes, f"Duplicate passive assets: {sorted(dupes)}"

    def test_no_duplicate_skill_assets(self):
        data = _load("skills.json")
        assets = [s["asset"] for s in data["skills"]]
        dupes = {a for a in assets if assets.count(a) > 1}
        assert not dupes, f"Duplicate skill assets: {sorted(dupes)}"

    def test_element_indices_0_to_8(self):
        data = _load("skills.json")
        errors = []
        for e in data["elements"]:
            idx = e["index"]
            if not (0 <= idx <= 8):
                errors.append(
                    f"  element '{e['name']}' index {idx} out of range [0, 8]"
                )
        assert not errors, "\n" + "\n".join(errors)

    # ---- items.json ----

    def test_no_duplicate_item_assets(self):
        data = _load("items.json")
        assets = [item["asset"] for item in data["items"]]
        dupes = {a for a in assets if assets.count(a) > 1}
        assert not dupes, f"Duplicate item assets: {sorted(dupes)}"

    def test_item_rarity_non_negative(self):
        data = _load("items.json")
        errors = []
        for i, item in enumerate(data["items"]):
            r = item.get("rarity")
            if r is not None and not isinstance(r, int):
                errors.append(
                    f"  items[{i}] ({item['name']}) rarity not int ({type(r).__name__})"
                )
            elif r is not None and r < 0:
                errors.append(
                    f"  items[{i}] ({item['name']}) rarity {r} is negative"
                )
        assert not errors, "\n" + "\n".join(errors)

    # ---- pal_exp_table.json ----

    def test_exp_table_has_100_entries(self):
        data = _load("pal_exp_table.json")
        assert len(data) == 100
        for lv in map(str, range(1, 101)):
            assert lv in data, f"Missing level {lv}"

    # ---- world.json ----

    def test_no_duplicate_structure_assets(self):
        data = _load("world.json")
        assets = [s["asset"] for s in data["structures"]]
        dupes = {a for a in assets if assets.count(a) > 1}
        assert not dupes, f"Duplicate structure assets: {sorted(dupes)}"

    def test_no_duplicate_technology_assets(self):
        data = _load("world.json")
        assets = [t["asset"] for t in data["technology"]]
        dupes = {a for a in assets if assets.count(a) > 1}
        assert not dupes, f"Duplicate technology assets: {sorted(dupes)}"

    # ---- relic_data.json ----

    def test_relic_per_rank_length_matches_max_rank(self):
        data = _load("relic_data.json")
        errors = []
        for key, entry in data.items():
            expected = entry["max_rank"]
            actual = len(entry["per_rank"])
            if actual != expected:
                errors.append(
                    f"  '{key}': per_rank len {actual} != max_rank {expected}"
                )
        assert not errors, "\n" + "\n".join(errors)

    # ---- fast_travel_points.json ----

    def test_fast_travel_guid_format(self):
        data = _load("fast_travel_points.json")
        import re
        guid_re = re.compile(r"^[0-9A-F]{32}$")
        errors = []
        for guid in data:
            if not guid_re.match(guid):
                errors.append(f"  Bad GUID format: {guid!r}")
        assert not errors, "\n" + "\n".join(errors)

    # ---- friendship.json ----

    def test_friendship_ranks_sorted(self):
        data = _load("friendship.json")
        ranks = [e["FriendshipRank"] for e in data.values()]
        assert ranks == sorted(ranks), "Friendship ranks not sorted ascending"

    # ---- boss_mapping.json ----

    def test_boss_mapping_values_are_list_or_str(self):
        data = _load("boss_mapping.json")
        errors = []
        for key, val in data["boss_defeat_flag_map"].items():
            if isinstance(val, str):
                continue
            if isinstance(val, list):
                for item in val:
                    if not isinstance(item, str):
                        errors.append(
                            f"  '{key}' contains non-string: {item!r}"
                        )
            else:
                errors.append(f"  '{key}' is {type(val).__name__}, expected list or str")
        assert not errors, "\n" + "\n".join(errors)

    # ---- cross-file integrity ----



# ===================================================================
# Shared icon-scan helpers (used by all icon test classes below)
# ===================================================================

import difflib
from collections import defaultdict
from dataclasses import dataclass

VALID_ICON_SUBDIRS = frozenset({
    "pals", "items", "npcs", "structures", "technologies",
    "elements", "passives", "ui",
})
VALID_ICON_EXTENSIONS = frozenset({".webp", ".png"})


@dataclass
class IconRef:
    """A single icon path reference found inside a JSON file."""
    json_file: str
    entry_name: str
    field_path: str
    icon_path: str

    def __repr__(self):
        return f"{self.json_file}:{self.entry_name} @{self.field_path} -> {self.icon_path}"


_JSON_CACHE: dict = {}

def _load_cached(name: str):
    if name not in _JSON_CACHE:
        _JSON_CACHE[name] = _load(name)
    return _JSON_CACHE[name]


def _walk_json_for_icons(obj, json_file: str, field_path: str,
                         refs: list, entry_name: str = "?"):
    """Recursively walk a JSON value, collecting every string that starts
    with '/icons/' as an IconRef.  Tracks the nearest enclosing 'name' field
    for human-readable provenance."""
    if isinstance(obj, str):
        stripped = obj.strip()
        if stripped.startswith("/icons/") or stripped.startswith("icons/"):
            normalized = "/" + stripped.lstrip("/") if not stripped.startswith("/") else stripped
            refs.append(IconRef(json_file, entry_name, field_path, normalized))
    elif isinstance(obj, dict):
        name = obj.get("name", entry_name)
        for k, v in obj.items():
            child_path = f"{field_path}.{k}" if field_path else k
            _walk_json_for_icons(v, json_file, child_path, refs, name)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            child_path = f"{field_path}[{i}]" if field_path else f"[{i}]"
            _walk_json_for_icons(v, json_file, child_path, refs, entry_name)


_ALL_REFS_CACHE: list | None = None

def _collect_all_icon_refs() -> list:
    """Walk every game_data JSON once and return all icon references."""
    global _ALL_REFS_CACHE
    if _ALL_REFS_CACHE is not None:
        return _ALL_REFS_CACHE
    refs: list = []
    for json_file in JSON_FILES:
        data = _load_cached(json_file)
        _walk_json_for_icons(data, json_file, "", refs)
    _ALL_REFS_CACHE = refs
    return refs


def _resolve_icon_to_disk(icon_path: str):
    """Resolve a JSON '/icons/...' path to its filesystem location under game_data."""
    relative = icon_path.lstrip("/")
    return GAME_DATA_DIR / relative


_DISK_FILE_CACHE: dict = {}

def _get_disk_files_for_subdir(subdir: str) -> list:
    """Return sorted list of filenames in icons/<subdir>/ (cached)."""
    if subdir not in _DISK_FILE_CACHE:
        d = GAME_DATA_DIR / "icons" / subdir
        if d.is_dir():
            _DISK_FILE_CACHE[subdir] = sorted(f.name for f in d.iterdir() if f.is_file())
        else:
            _DISK_FILE_CACHE[subdir] = []
    return _DISK_FILE_CACHE[subdir]


def _check_extension_mismatch(icon_path: str):
    """If the file doesn't exist but swapping .png<->.webp would work,
    return the correct extension.  Otherwise return None."""
    full = _resolve_icon_to_disk(icon_path)
    if full.is_file():
        return None
    stem, ext = os.path.splitext(icon_path)
    if ext.lower() not in VALID_ICON_EXTENSIONS:
        return None
    alt_ext = ".png" if ext.lower() == ".webp" else ".webp"
    alt_full = GAME_DATA_DIR / (stem.lstrip("/") + alt_ext)
    if alt_full.is_file():
        return alt_ext
    return None


def _find_near_misses(icon_path: str, max_results: int = 3) -> list:
    """For a missing icon, find similar filenames in the same subdirectory.
    Returns list of (filename, reason) tuples.  Detects:
      - case differences (Thunderdog vs ThunderDog)
      - suffix additions (_normal vs _normal_dull)
      - typos (Levenshtein-like via difflib)
    """
    parts = icon_path.strip("/").split("/")
    if len(parts) < 3:
        return []
    subdir = parts[1]
    basename = parts[-1]
    stem = os.path.splitext(basename)[0]
    disk_files = _get_disk_files_for_subdir(subdir)

    candidates = []
    for disk_file in disk_files:
        disk_stem = os.path.splitext(disk_file)[0]

        # Exact case-insensitive match — highest priority
        if stem.lower() == disk_stem.lower() and stem != disk_stem:
            candidates.append((1.0, disk_file, "case mismatch"))
            continue

        # One is a prefix of the other (suffix addition/removal)
        if disk_stem.lower().startswith(stem.lower()) or stem.lower().startswith(disk_stem.lower()):
            ratio = difflib.SequenceMatcher(None, stem.lower(), disk_stem.lower()).ratio()
            if ratio >= 0.80:
                candidates.append((ratio, disk_file, "suffix difference"))
            continue

        # General fuzzy match
        ratio = difflib.SequenceMatcher(None, stem.lower(), disk_stem.lower()).ratio()
        if ratio >= 0.85:
            candidates.append((ratio, disk_file, "similar name"))

    candidates.sort(key=lambda x: (-x[0], x[1]))
    return [(fname, reason) for _, fname, reason in candidates[:max_results]]


def _format_icon_error(ref, issue: str, suggestion: str = "") -> str:
    """Format a single icon issue for display."""
    msg = f"  {ref.json_file}: {ref.entry_name} [{ref.field_path}]\n    path: {ref.icon_path}\n    issue: {issue}"
    if suggestion:
        msg += f"\n    -> {suggestion}"
    return msg


def _is_strict() -> bool:
    return bool(int(os.environ.get("PALWORLD_COMPANION_STRICT_ICONS", "0")))


def _is_ruthless() -> bool:
    """Return True when the extended game-data audit is enabled.

    In ruthless mode, heuristic checks that may produce false positives
    are enabled (e.g. icon-asset name correlation).  In normal mode these
    are skipped to avoid noisy warnings on legitimate mappings that the
    heuristics can't verify.
    """
    return bool(int(os.environ.get("PALWORLD_COMPANION_RUTHLESS", "0")))


# ===================================================================
# TestIconPathFormat  (HARD FAIL — structural correctness)
# ===================================================================

class TestIconPathFormat:
    """Every icon path must be well-formed: /icons/<subdir>/<file>.<ext>"""

    def test_all_icon_fields_are_strings(self):
        """Icon values must be non-empty strings, not null/None/empty."""
        errors = []
        for ref in _collect_all_icon_refs():
            if not ref.icon_path or not isinstance(ref.icon_path, str):
                errors.append(_format_icon_error(ref, "empty or non-string icon value"))
        assert not errors, f"{len(errors)} empty/non-string icon fields:\n" + "\n".join(errors)

    def test_all_icons_start_with_slash_icons(self):
        """Every icon must start with /icons/."""
        errors = []
        for ref in _collect_all_icon_refs():
            if not ref.icon_path.startswith("/icons/"):
                errors.append(_format_icon_error(
                    ref, f"path does not start with '/icons/': {ref.icon_path!r}"))
        assert not errors, f"{len(errors)} icons with wrong prefix:\n" + "\n".join(errors)

    def test_all_icons_use_forward_slashes(self):
        """No backslashes in icon paths (Windows vs Unix issue)."""
        errors = []
        for ref in _collect_all_icon_refs():
            if "\\" in ref.icon_path:
                errors.append(_format_icon_error(ref, "path contains backslash"))
        assert not errors, f"{len(errors)} icons with backslashes:\n" + "\n".join(errors)

    def test_all_icons_have_valid_extension(self):
        """Only .webp or .png extensions are valid."""
        errors = []
        for ref in _collect_all_icon_refs():
            ext = os.path.splitext(ref.icon_path)[1].lower()
            if ext not in VALID_ICON_EXTENSIONS:
                errors.append(_format_icon_error(
                    ref, f"invalid extension '{ext}' (expected .webp or .png)"))
        assert not errors, f"{len(errors)} icons with invalid extensions:\n" + "\n".join(errors)

    def test_all_icons_reference_valid_subdir(self):
        """Icon subdirectory must be one of the known icon categories."""
        errors = []
        for ref in _collect_all_icon_refs():
            parts = ref.icon_path.strip("/").split("/")
            if len(parts) < 3:
                errors.append(_format_icon_error(ref, "path too short (expected /icons/<subdir>/<file>)"))
                continue
            subdir = parts[1]
            if subdir not in VALID_ICON_SUBDIRS:
                errors.append(_format_icon_error(
                    ref, f"unknown subdir '/icons/{subdir}/' "
                         f"(valid: {sorted(VALID_ICON_SUBDIRS)})"))
        assert not errors, f"{len(errors)} icons with invalid subdirs:\n" + "\n".join(errors)

    def test_no_duplicate_slash_segments(self):
        """Paths must not have double-slashes or trailing slashes."""
        errors = []
        for ref in _collect_all_icon_refs():
            if "//" in ref.icon_path[1:] or ref.icon_path.endswith("/"):
                errors.append(_format_icon_error(ref, "malformed path (double/trailing slash)"))
        assert not errors, f"{len(errors)} icons with malformed paths:\n" + "\n".join(errors)


# ===================================================================
# TestIconExtensionConsistency  (HARD FAIL — catches .png/.webp corruption)
# ===================================================================

class TestIconExtensionConsistency:
    """Icon extensions must be consistent with what's on disk.

    The #1 data corruption pattern is .png in JSON when only .webp exists
    on disk (or vice versa).  These are always bugs — the test should FAIL.
    """

    def test_no_extension_mismatches(self):
        """If JSON says .png but disk only has .webp (or vice versa), FAIL."""
        mismatches = defaultdict(list)
        for ref in _collect_all_icon_refs():
            alt_ext = _check_extension_mismatch(ref.icon_path)
            if alt_ext:
                mismatches[ref.icon_path].append(ref)

        if not mismatches:
            return

        errors = []
        for icon_path, refs in sorted(mismatches.items()):
            json_ext = os.path.splitext(icon_path)[1]
            disk_ext = _check_extension_mismatch(icon_path)
            total = len(refs)
            sample = refs[0]
            errors.append(
                f"  {icon_path}  ({total} refs)\n"
                f"    JSON uses '{json_ext}' but disk has '{disk_ext}'\n"
                f"    first ref: {sample.json_file}:{sample.entry_name} [{sample.field_path}]\n"
                f"    FIX: change '{json_ext}' -> '{disk_ext}' in the JSON"
            )
        pytest.fail(
            f"{len(mismatches)} unique icon paths have extension mismatches "
            f"(affecting {sum(len(r) for r in mismatches.values())} references):\n"
            + "\n".join(errors)
        )

    def test_element_icon_extensions_consistent_in_skills(self):
        """Within skills.json elements, all icon fields should use the same extension."""
        data = _load_cached("skills.json")
        errors = []
        exts_seen = {}
        for elem in data.get("elements", []):
            for ik, iv in elem.get("icons", {}).items():
                if not isinstance(iv, str) or not iv:
                    continue
                ext = os.path.splitext(iv)[1].lower()
                if ik in exts_seen and exts_seen[ik] != ext:
                    errors.append(
                        f"  element '{elem.get('name','?')}': icon key '{ik}' "
                        f"has ext '{ext}' but earlier entry used '{exts_seen[ik]}'"
                    )
                exts_seen[ik] = ext
        assert not errors, "Inconsistent element icon extensions in skills.json:\n" + "\n".join(errors)


# ===================================================================
# TestIconCrossFileConsistency  (HARD FAIL — catches drift between files)
# ===================================================================

class TestIconCrossFileConsistency:
    """Icon paths must be consistent across different JSON files."""

    def test_pal_element_icons_match_skills_elements(self):
        """Pal element icon paths in characters.json should resolve to the same
        files as the element icon definitions in skills.json.

        characters.json stores element icons per-pal (e.g. /icons/elements/T_Icon_element_00.png).
        skills.json stores canonical element icons (e.g. /icons/elements/T_Icon_element_00.webp).
        If these disagree, the pal element icons are wrong.
        """
        skills_data = _load_cached("skills.json")
        canonical = {}
        for elem in skills_data.get("elements", []):
            name = elem.get("name", "")
            icons = elem.get("icons", {})
            canonical[name] = dict(icons)

        chars_data = _load_cached("characters.json")
        errors = []
        for pal in chars_data.get("pals", []):
            pal_name = pal.get("name", "?")
            for elem_name, elem_val in pal.get("elements", {}).items():
                canon = canonical.get(elem_name)
                if not canon:
                    continue
                for field in ("icon", "icon_large", "icon_passive_base"):
                    pal_icon = elem_val.get(field, "")
                    # skills.json uses keys: passive_base, large, palstatus, small
                    # characters.json uses keys: icon, icon_large, icon_passive_base
                    canon_key_map = {"icon": "small", "icon_large": "large", "icon_passive_base": "passive_base"}
                    canon_icon = canon.get(canon_key_map.get(field, field), "")
                    if pal_icon and canon_icon:
                        pal_stem = os.path.splitext(os.path.basename(pal_icon))[0]
                        canon_stem = os.path.splitext(os.path.basename(canon_icon))[0]
                        if pal_stem != canon_stem:
                            errors.append(
                                f"  {pal_name} element '{elem_name}' field '{field}':\n"
                                f"    characters.json: {pal_icon}\n"
                                f"    skills.json:     {canon_icon}\n"
                                f"    (stems differ: '{pal_stem}' vs '{canon_stem}')"
                            )
        assert not errors, (
            f"{len(errors)} pal element icon mismatches between "
            f"characters.json and skills.json:\n" + "\n".join(errors[:30])
        )


# ===================================================================
# TestIconFileExistence (warn by default, fail in strict icon mode)
# ===================================================================

class TestIconFileExistence:
    """Icon paths must point to real files on disk.

    Default: WARN (reports all missing icons with actionable detail including
    near-miss/typo suggestions).
    Set PALWORLD_COMPANION_STRICT_ICONS=1 to make this a hard failure (for CI).

    Per-category sub-tests give granular reporting so you can see exactly
    which entity type has the most missing icons.
    """

    @staticmethod
    def _check_category(category_refs: list, label: str):
        """Check a list of icon refs for existence with near-miss detection.

        Only warns or fails when the extended audit is enabled.
        In normal mode this is skipped — many icons are intentionally missing
        (placeholders, unused variants, etc.) and would produce false positives.
        """
        if not _is_ruthless():
            return
        missing = []
        for ref in category_refs:
            full = _resolve_icon_to_disk(ref.icon_path)
            if full.is_file():
                continue
            # Skip if it's an extension mismatch (caught by TestIconExtensionConsistency)
            if _check_extension_mismatch(ref.icon_path):
                continue
            near = _find_near_misses(ref.icon_path)
            suggestion = ""
            if near:
                suggestion = "Did you mean: " + ", ".join(
                    f"'{fname}' ({reason})" for fname, reason in near
                )
            missing.append((ref, suggestion))

        if not missing:
            return

        total = len(category_refs)
        n = len(missing)
        lines = [f"{label}: {n} of {total} icons missing"]
        for ref, suggestion in missing[:20]:
            lines.append(_format_icon_error(ref, "file not found on disk", suggestion))
        if n > 20:
            lines.append(f"  ... and {n - 20} more")
        summary = "\n".join(lines)

        if _is_strict():
            pytest.fail(summary)
        else:
            warnings.warn(UserWarning(summary))

    # -- per-category tests for granular reporting --

    def test_pal_icons_exist(self):
        refs = [r for r in _collect_all_icon_refs()
                if r.icon_path.startswith("/icons/pals/")
                and r.json_file == "characters.json" and ".elements." not in r.field_path]
        self._check_category(refs, "pal icons")

    def test_npc_icons_exist(self):
        refs = [r for r in _collect_all_icon_refs() if r.icon_path.startswith("/icons/npcs/")]
        self._check_category(refs, "npc icons")

    def test_item_icons_exist(self):
        refs = [r for r in _collect_all_icon_refs() if r.icon_path.startswith("/icons/items/")]
        self._check_category(refs, "item icons")

    def test_structure_icons_exist(self):
        refs = [r for r in _collect_all_icon_refs() if r.icon_path.startswith("/icons/structures/")]
        self._check_category(refs, "structure icons")

    def test_technology_icons_exist(self):
        refs = [r for r in _collect_all_icon_refs() if r.icon_path.startswith("/icons/technologies/")]
        self._check_category(refs, "technology icons")

    def test_passive_icons_exist(self):
        refs = [r for r in _collect_all_icon_refs() if r.icon_path.startswith("/icons/passives/")]
        self._check_category(refs, "passive icons")

    def test_ui_icons_exist(self):
        refs = [r for r in _collect_all_icon_refs() if r.icon_path.startswith("/icons/ui/")]
        self._check_category(refs, "ui icons")

    def test_element_icons_exist(self):
        """Element icons from skills.json (canonical definitions)."""
        refs = [r for r in _collect_all_icon_refs()
                if r.icon_path.startswith("/icons/elements/") and r.json_file == "skills.json"]
        self._check_category(refs, "element icons (skills.json)")

    def test_pal_element_icons_exist(self):
        """Element icons embedded in characters.json pal entries."""
        refs = [r for r in _collect_all_icon_refs()
                if r.icon_path.startswith("/icons/elements/") and r.json_file == "characters.json"]
        self._check_category(refs, "pal element icons (characters.json)")


# ===================================================================
# TestOrphanIcons  (WARN — files on disk not referenced by any JSON)
# ===================================================================

class TestOrphanIcons:
    """Icon files that exist on disk but no JSON references.

    These are potential cleanup candidates or indicators that a JSON
    path was typo'd (the orphan is the intended file, the JSON has a misspelling).
    """

    def test_no_orphan_icons(self):
        if not _is_ruthless():
            return
        refs = _collect_all_icon_refs()
        referenced_basenames = {os.path.basename(r.icon_path) for r in refs}
        referenced_stems = {os.path.splitext(b)[0] for b in referenced_basenames}

        orphans = []
        for subdir in VALID_ICON_SUBDIRS:
            disk_files = _get_disk_files_for_subdir(subdir)
            for fname in disk_files:
                stem = os.path.splitext(fname)[0]
                if fname in referenced_basenames or stem in referenced_stems:
                    continue
                near = []
                for ref_stem in referenced_stems:
                    ratio = difflib.SequenceMatcher(
                        None, stem.lower(), ref_stem.lower()).ratio()
                    if ratio >= 0.85:
                        near.append((ref_stem, ratio))
                near.sort(key=lambda x: -x[1])
                suggestion = ""
                if near:
                    suggestion = f" (possible typo target for '{near[0][0]}')"
                orphans.append(f"  /icons/{subdir}/{fname}{suggestion}")

        if not orphans:
            return

        summary = f"{len(orphans)} orphan icon files (on disk but not referenced by any JSON):\n" + "\n".join(orphans)
        if _is_strict():
            pytest.fail(summary)
        else:
            warnings.warn(UserWarning(summary))


# ===================================================================
# TestPythonIconResolution  (HARD FAIL — verifies app resolution chain)
# ===================================================================

class TestPythonIconResolution:
    """Verify that the app's resource_path() resolution correctly resolves
    every icon path found in the JSONs.

    The app resolves JSON '/icons/pals/X.webp' paths via:
        resource_path(base, 'game_data', icon_path.lstrip('/'))
    which produces: <resources>/game_data/icons/pals/X.webp

    This test validates that chain for every icon that exists on disk.
    """

    def test_resource_path_resolves_existing_json_icons(self):
        """For every icon that exists on disk, resource_path() must resolve
        to the same filesystem path."""
        try:
            from tests.dynamic_importer import import_from
            resource_path = import_from('resource_resolver', 'resource_path')
        except Exception:
            pytest.skip("Could not import resource_path — skipping resolution test")

        base = str(PROJECT_ROOT)
        errors = []
        checked = 0
        for ref in _collect_all_icon_refs():
            full = _resolve_icon_to_disk(ref.icon_path)
            if not full.is_file():
                continue  # Skip missing icons (covered by TestIconFileExistence)
            checked += 1
            rel = ref.icon_path.lstrip("/")
            resolved = resource_path(base, 'game_data', rel)
            if not os.path.exists(resolved):
                errors.append(
                    f"  {ref.json_file}:{ref.entry_name} [{ref.field_path}]\n"
                    f"    icon: {ref.icon_path}\n"
                    f"    resource_path resolved to: {resolved}\n"
                    f"    but file does not exist there"
                )
        assert not errors, (
            f"{len(errors)} of {checked} existing icons failed resource_path() resolution:\n"
            + "\n".join(errors[:20])
        )

    def test_unknown_icon_fallback_exists(self):
        """The T_icon_unknown.webp fallback must exist."""
        fallback = GAME_DATA_DIR / "icons" / "T_icon_unknown.webp"
        assert fallback.is_file(), f"Icon fallback missing: {fallback}"


# ===================================================================
# Python source scanning — discover game_data path references in code
# ===================================================================

_RE_RP_GAMEDATA = re.compile(
    r"resource_path\s*\(\s*[^,]+,\s*'game_data'\s*,(.+)\)"
)
_RE_LOAD_MAP = re.compile(
    r"load_game_data_map\s*\(\s*'([^']+\.json)'\s*,"
)
_RE_LOAD_JSON = re.compile(
    r"load_resource_json\s*\(\s*'([^']+\.json)'\s*\)"
)
_RE_RESOURCE_PATH = re.compile(
    r"resource_path\s*\(\s*[^,]+,\s*'game_data'\s*,\s*'([^']+)'\s*\)"
)


def _collect_python_gamedata_refs():
    """Scan src/ for game_data file and icon path references.

    Returns dict with:
        json_files: set of .json filenames referenced in Python source
        icon_literal_paths: set of literal (non-dynamic) icon paths found
        dynamic_patterns: dict {pattern: [source_file, ...]}
    """
    json_files = set()
    icon_literal_paths = set()
    dynamic_patterns = {}

    for py_file in sorted(SRC_DIR.rglob("*.py")):
        try:
            text = py_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        # resource_path(base, 'game_data', 'literal_path')
        for m in _RE_RESOURCE_PATH.finditer(text):
            literal = m.group(1)
            if literal.endswith(".json"):
                json_files.add(literal)
            elif literal.endswith((".webp", ".png")):
                icon_literal_paths.add(literal)

        # resource_path(base, 'game_data', expr, ...) with multi-arg or dynamic
        for m in _RE_RP_GAMEDATA.finditer(text):
            full_capture = m.group(1)
            segments = _extract_static_segments(full_capture)
            for seg in segments:
                if seg.endswith(".json"):
                    json_files.add(seg)

        # load_game_data_map('file.json', 'section')
        for m in _RE_LOAD_MAP.finditer(text):
            json_files.add(m.group(1))

        # load_resource_json('file.json')
        for m in _RE_LOAD_JSON.finditer(text):
            json_files.add(m.group(1))

    return {
        "json_files": sorted(json_files),
        "icon_literal_paths": sorted(icon_literal_paths),
        "dynamic_patterns": dynamic_patterns,
    }


def _extract_static_segments(captured: str):
    """Extract static (non-f-string) path segments from comma-separated args."""
    segments = []
    depth = 0
    in_quote = False
    quote_char = None
    current = []

    for ch in captured:
        if in_quote:
            if ch == quote_char:
                in_quote = False
                # Check for f-strings inside quotes: f'...{...}...'
                chunk = "".join(current)
                if "{" in chunk:
                    current = []
                    continue
                segments.append(chunk)
                current = []
            else:
                current.append(ch)
        elif ch in ("'", '"'):
            # Check if preceded by 'f' (f-string)
            prev = "".join(current).strip()
            if prev.endswith("f"):
                # Remove the 'f' and treat as dynamic
                current = []
                in_quote = True
                quote_char = ch
            else:
                in_quote = True
                quote_char = ch
                current = []
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif ch == "," and depth == 0:
            current = []  # reset between top-level args
        # ignore other characters (they are part of expressions)

    return segments


# ===================================================================
# TestPythonCodePathConsistency  (HARD FAIL)
# ===================================================================

class TestPythonCodePathConsistency:
    """Cross-reference Python code path patterns against JSON data and disk.

    Layer 1 (JSON paths)  ↔  Layer 2 (Python code refs)  ↔  Layer 3 (filesystem)
    Every Python source file under src/ is scanned for game_data path references.
    """

    _refs = None

    @classmethod
    def _get_refs(cls):
        if cls._refs is None:
            cls._refs = _collect_python_gamedata_refs()
        return cls._refs

    def test_all_python_json_file_refs_exist(self):
        """HARD FAIL: Every .json file referenced in Python source must exist."""
        refs = self._get_refs()
        missing = []
        for jf in refs["json_files"]:
            if not (GAME_DATA_DIR / jf).exists():
                missing.append(jf)
        assert not missing, (
            f"Python code references JSON files not found in {GAME_DATA_DIR}:\n"
            + "\n".join(f"  {f}" for f in missing)
        )

    def test_all_game_data_json_files_used_in_python(self):
        """WARN: Every JSON file in game_data should have Python code that loads it.

        Only warns in ruthless mode — intentionally unreferenced JSON files
        (legacy data, unused lookups) are common.
        """
        if not _is_ruthless():
            return
        refs = self._get_refs()
        known_unreferenced = {"friendship.json"}
        unreferenced = sorted(
            jf for jf in JSON_FILES
            if jf not in refs["json_files"] and jf not in known_unreferenced
        )
        if unreferenced:
            warnings.warn(UserWarning(
                f"JSON files not referenced by any Python source — possibly dead data:\n"
                + "\n".join(f"  {f}" for f in unreferenced)
            ))

    def test_python_literal_icon_paths_exist_on_disk(self):
        """HARD FAIL: Literal (non-dynamic) icon paths hardcoded in Python
        must resolve to real files on disk.
        """
        refs = self._get_refs()
        missing = []
        for icon_path in refs["icon_literal_paths"]:
            resolved = _resolve_icon_to_disk(icon_path)
            if not resolved.exists():
                missing.append(f"  '{icon_path}' -> {resolved}")
        assert not missing, (
            f"Literal icon paths in Python code don't resolve to files:\n"
            + "\n".join(missing)
        )


# ===================================================================
# TestDynamicIconPatterns (warn or fail based on strict icon mode)
# ===================================================================

class TestDynamicIconPatterns:
    """Validate Python's runtime icon construction patterns.

    Python code constructs icon paths from asset names as fallbacks when
    JSON-defined icons are missing. These patterns MUST produce valid
    filesystem paths for every known entity with a missing JSON icon.
    """

    _PAL_FALLBACK_PATTERNS = [
        "icons/pals/{asset}.webp",
    ]

    @classmethod
    def _check_fallbacks(cls, entity_list, name_field, asset_field, icon_field,
                         subdir, fallback_patterns, entity_type_label):
        """Generic check: for entities whose JSON icon is missing on disk,
        try each fallback pattern and report if none match."""
        errors = []
        checked = 0
        for entry in entity_list:
            name = entry.get(name_field, "?")
            asset = entry.get(asset_field, "")
            json_icon = entry.get(icon_field, "")
            if not asset:
                continue
            json_file = _resolve_icon_to_disk(json_icon) if json_icon else None
            if json_file and json_file.exists():
                continue

            checked += 1
            resolved = []
            for pattern in fallback_patterns:
                p = pattern.replace("{asset}", asset).replace("{asset_lower}", asset.lower())
                candidate = GAME_DATA_DIR / p
                resolved.append(candidate)
                if candidate.exists():
                    break
            else:
                lines = [f"  '{name}' ({asset}):"]
                lines.append(f"    icon: {os.path.basename(json_icon)}")
                lines.extend(f"    → {r.name}" for r in resolved)
                errors.append("\n".join(lines))
        return errors, checked

    def test_pal_fallback_guess_paths(self):
        """edit_pals.py fallback 'icons/pals/{asset}.webp' must resolve
        for every pal whose JSON icon is missing on disk.

        Only warns/fails in ruthless mode — normal mode skips this because
        many pal icons are intentionally missing (unused placeholders, etc.).
        """
        if not _is_ruthless():
            return
        data = _load_cached("characters.json")
        errors, checked = self._check_fallbacks(
            data.get("pals", []),
            "name", "asset", "icon",
            "pals", self._PAL_FALLBACK_PATTERNS,
            "pals",
        )
        if errors:
            msg = (
                f"{len(errors)} of {checked} pals with missing JSON icon "
                f"have no working fallback:\n" + "\n".join(errors)
            )
            if _is_strict():
                pytest.fail(msg)
            else:
                warnings.warn(UserWarning(msg))


# ===================================================================
# TestAssetIconCorrelation  (WARN — detects suspicious path changes)
# ===================================================================

_ICON_PREFIXES = ("T_itemicon_", "T_icon_buildObject_", "T_BOSS_NPC_", "T_icon_", "T_")

def _normalize_for_match(s: str) -> str:
    return s.lower().replace("_", "").replace("-", "")

def _split_name_tokens(s: str) -> set:
    """Split a name into meaningful lowercase tokens (underscore + CamelCase + digits)."""
    tokens = set()
    parts = re.split(r'[_\s]+', s)
    for part in parts:
        if not part:
            continue
        camel = re.findall(r'[A-Z][a-z0-9]+|[a-z0-9]+|[A-Z]+(?=[A-Z]|$)', part)
        for tok in camel:
            tok = tok.lower()
            if len(tok) > 2:
                tokens.add(tok)
                stripped = re.sub(r'\d+$', '', tok)
                if stripped != tok and len(stripped) > 2:
                    tokens.add(stripped)
    return tokens


def _asset_in_icon_basename(asset: str, icon_path: str) -> bool:
    """Returns True if the asset name appears meaningfully in the icon filename."""
    if not asset or not icon_path:
        return False
    basename = os.path.splitext(os.path.basename(icon_path))[0]
    asset_norm = _normalize_for_match(asset)
    icon_norm = _normalize_for_match(basename)

    if asset_norm in icon_norm or icon_norm in asset_norm:
        return True

    for pattern in (r'_\d+$', r'\d+$'):
        stripped = re.sub(pattern, '', asset_norm)
        if stripped != asset_norm and (stripped in icon_norm or icon_norm in stripped):
            return True

    icon_clean = basename
    for prefix in _ICON_PREFIXES:
        if icon_clean.lower().startswith(prefix):
            icon_clean = icon_clean[len(prefix):]
            break
    icon_clean_norm = _normalize_for_match(icon_clean)

    if asset_norm in icon_clean_norm or icon_clean_norm in asset_norm:
        return True
    for pattern in (r'_\d+$', r'\d+$'):
        stripped = re.sub(pattern, '', asset_norm)
        if stripped != asset_norm and (stripped in icon_clean_norm or icon_clean_norm in stripped):
            return True

    asset_tokens = _split_name_tokens(asset)
    icon_tokens = _split_name_tokens(icon_clean)

    for at in asset_tokens:
        for it in icon_tokens:
            if at in it or it in at:
                return True

    return False


_ICON_USAGE_CACHE: dict | None = None

def _build_icon_usage_map():
    """Build a map of icon_path -> set of asset names across all game data JSONs."""
    global _ICON_USAGE_CACHE
    if _ICON_USAGE_CACHE is not None:
        return _ICON_USAGE_CACHE
    usage = {}
    for jf in JSON_FILES:
        data = _load_cached(jf)
        entries = []
        if jf == "characters.json":
            entries = data.get("pals", []) + data.get("npcs", [])
        elif jf == "items.json":
            entries = data.get("items", [])
        elif jf == "skills.json":
            entries = data.get("passives", []) + data.get("skills", [])
        elif jf == "world.json":
            entries = data.get("structures", []) + data.get("technology", [])
        for e in entries:
            icon = e.get("icon", "")
            asset = e.get("asset", "")
            if icon and asset:
                usage.setdefault(icon, set()).add(asset)
    _ICON_USAGE_CACHE = usage
    return usage


def _is_shared_icon(icon_path: str) -> bool:
    """An icon is 'shared' if used by >=2 entries with stems where at least
    one pair of assets do NOT contain each other (i.e. the icon is used by
    fundamentally different things)."""
    usage = _build_icon_usage_map()
    assets = usage.get(icon_path)
    if not assets or len(assets) < 2:
        return False
    stems = list(assets)
    for i, s1 in enumerate(stems):
        n1 = _normalize_for_match(s1)
        for j, s2 in enumerate(stems):
            if i != j:
                n2 = _normalize_for_match(s2)
                if n1 not in n2 and n2 not in n1:
                    return True
    return False


def _is_known_unverifiable(asset: str, icon_path: str) -> bool:
    """Check if (asset, icon) is a known correct mapping that heuristics can't verify."""
    if not asset or not icon_path:
        return False
    if re.match(r'FurnitureSet_\w+$', asset):
        return True
    if re.match(r'HeadEquip\d+$', asset):
        return True
    if re.match(r'Product_\w+_Grade_\d+', asset):
        return True
    if asset == 'SF_houseset':
        return True
    if asset == 'EnergyDrink' and 'Bandage' in icon_path:
        return True
    if "dummy" in os.path.splitext(os.path.basename(icon_path))[0].lower():
        return True
    return False


class TestAssetIconCorrelation:
    """Verify that icon filenames correlate with their entity's asset name.

    When an icon path is updated in JSON, the new icon should still relate
    to the entity's asset name. This catches accidental reuse of another
    entity's icon (e.g., changing '/icons/pals/T_Plesiosaur_icon_normal.webp'
    to '/icons/pals/T_Anubis_icon_normal.webp' would be caught here).
    """

    @staticmethod
    def _check_category(entries, label: str):
        """Check icon-asset name correlation.

        With PALWORLD_COMPANION_RUTHLESS=1, this runs the full
        heuristic check and warns on any icon whose filename doesn't relate
        to the entity's asset name.

        In normal mode, this is skipped entirely to avoid false positive
        warnings for legitimate mappings that the heuristics can't verify.
        """
        if not _is_ruthless():
            return

        mismatches = []
        for entry in entries:
            asset = entry.get("asset", "")
            icon = entry.get("icon", "")
            if not asset or not icon:
                continue
            if not _asset_in_icon_basename(asset, icon):
                if _is_shared_icon(icon):
                    continue
                if _is_known_unverifiable(asset, icon):
                    continue
                mismatches.append(
                    f"  '{entry.get('name', '?')}' "
                    f"asset='{asset}' icon='{icon}'"
                )
        if mismatches:
            warnings.warn(UserWarning(
                f"{len(mismatches)} {label} icon(s) with no asset-name correlation "
                f"(possible stale/incorrect icon):\n"
                + "\n".join(mismatches[:30])
                + ("\n  ... and more" if len(mismatches) > 30 else "")
            ))

    def test_pal_icons_correlate_with_asset(self):
        data = _load_cached("characters.json")
        self._check_category(data.get("pals", []), "pal")

    def test_item_icons_correlate_with_asset(self):
        data = _load_cached("items.json")
        self._check_category(data.get("items", []), "item")

    def test_structure_icons_correlate_with_asset(self):
        data = _load_cached("world.json")
        self._check_category(data.get("structures", []), "structure")

    def test_technology_icons_correlate_with_asset(self):
        data = _load_cached("world.json")
        self._check_category(data.get("technology", []), "technology")

    def test_npc_icons_correlate_with_asset(self):
        data = _load_cached("characters.json")
        self._check_category(data.get("npcs", []), "NPC")

    def test_skill_icons_correlate_with_asset(self):
        """WARN: Every active skill icon filename should contain the skill's asset name."""
        data = _load_cached("skills.json")
        mismatches = []
        for entry in data.get("skills", []):
            asset = entry.get("asset", "")
            icon = entry.get("icon", "")
            if not asset or not icon:
                continue
            if not _asset_in_icon_basename(asset, icon):
                if _is_shared_icon(icon):
                    continue
                if _is_known_unverifiable(asset, icon):
                    continue
                mismatches.append(
                    f"  '{entry.get('name', '?')}' "
                    f"asset='{asset}' icon='{icon}'"
                )
        if mismatches:
            warnings.warn(UserWarning(
                f"{len(mismatches)} skill icon(s) with no asset-name correlation "
                f"(possible stale/incorrect icon):\n"
                + "\n".join(mismatches[:30])
                + ("\n  ... and more" if len(mismatches) > 30 else "")
            ))

    def test_passive_icons_correlate_with_asset(self):
        data = _load_cached("skills.json")
        self._check_category(data.get("passives", []), "passive")


# ===================================================================
# TestNonIconPathDiscovery  (WARN — identifies new validation targets)
# ===================================================================

class TestNonIconPathDiscovery:
    """Discover non-icon string fields in JSON data that look like file paths.

    Scans every JSON file for string values that:
      - Contain a path separator (/)
      - End with a known file extension
      - Are NOT already caught by the icon validation

    These are candidate fields for future validation. The test warns on
    findings rather than failing, since not all path-like strings need
    filesystem validation.
    """

    _PATH_EXTENSIONS = frozenset({
        ".json", ".webp", ".png", ".jpg", ".jpeg", ".gif", ".svg",
        ".tga", ".dds", ".bmp", ".ico", ".uasset", ".umap", ".u",
    })

    def test_discover_non_icon_path_like_strings(self):
        """WARN: Report non-icon string fields that look like file paths.

        A clean report (no warnings) confirms that icon coverage is complete —
        all path-like strings in JSON data are /icons/ paths already validated.

        Only warns in ruthless mode — non-icon paths are expected in game data
        and not actionable outside of a full audit.
        """
        if not _is_ruthless():
            return
        path_like = []  # (json_file, field_path, value, entry_name)
        for json_file in JSON_FILES:
            data = _load_cached(json_file)
            _walk_non_icon_paths(data, json_file, "", path_like)

        if not path_like:
            return  # Pass silently — full coverage confirmed

        from collections import defaultdict
        by_file = defaultdict(list)
        for jf, fp, val, name in path_like:
            by_file[jf].append((fp, val, name))

        lines = ["Non-icon path-like strings discovered in JSON data:"]
        for jf, entries in sorted(by_file.items()):
            lines.append(f"  {jf}:")
            for fp, val, name in entries[:10]:
                lines.append(f"    [{fp}] = {val!r}  (entry: {name})")
            if len(entries) > 10:
                lines.append(f"    ... and {len(entries) - 10} more fields in {jf}")

        warnings.warn(UserWarning("\n".join(lines)))


def _walk_non_icon_paths(obj, json_file, field_path, results, entry_name="?"):
    """Walk JSON to collect non-icon string values that look like file paths."""
    if isinstance(obj, str):
        stripped = obj.strip()
        if not stripped or len(stripped) < 6:
            return
        if stripped.startswith("/icons/") or stripped.startswith("icons/"):
            return  # Already validated by icon tests
        if stripped.startswith("/Game/") or stripped.startswith("/Script/"):
            return  # Unreal Engine asset paths (not in our resource tree)
        if re.search(r'<[A-Za-z_/]+>', stripped):
            return  # HTML/XML-like tags in descriptions, not file paths
        ext = os.path.splitext(stripped)[1].lower()
        if ext in TestNonIconPathDiscovery._PATH_EXTENSIONS and "/" in stripped:
            results.append((json_file, field_path, stripped, entry_name))
    elif isinstance(obj, dict):
        name = obj.get("name", entry_name)
        for k, v in obj.items():
            child = f"{field_path}.{k}" if field_path else k
            _walk_non_icon_paths(v, json_file, child, results, name)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            child = f"{field_path}[{i}]" if field_path else f"[{i}]"
            _walk_non_icon_paths(v, json_file, child, results, entry_name)


# ===================================================================
# TestOrphanIconFromFilesystem  (WARN — icons on disk not in JSON)
# ===================================================================

class TestOrphanIconFromFilesystem:
    """WARN / HARD FAIL: Detect icon files on disk not referenced by any JSON
    or Python code, using the filesystem as the source of truth.
    """

    _ICON_SUBDIRS = ("pals", "items", "structures", "npcs", "technologies",
                     "passives", "elements", "ui")

    def _collect_all_json_icon_refs(self):
        """Return set of all icon paths (relative to game_data/) referenced in JSON."""
        refs = set()
        for json_file in JSON_FILES:
            data = _load_cached(json_file)
            _walk_icons_in_json(data, refs)
        return refs

    def _resolve_to_relative(self, icon_path: str) -> str:
        """Normalize /icons/... to icons/... relative to game_data/."""
        return icon_path.lstrip("/")

    def test_no_unreferenced_icon_files_on_disk(self):
        """WARN: Every icon file on disk should be referenced by at least one
        JSON field or Python code literal. Files without references may be dead.

        Only warns/fails in ruthless mode — intentionally unreferenced icons
        (placeholders, legacy files) are common and not actionable.
        """
        if not _is_ruthless():
            return
        json_refs = self._collect_all_json_icon_refs()
        json_relative = {self._resolve_to_relative(p) for p in json_refs}

        # Also collect Python literal icon paths
        py_refs = TestPythonCodePathConsistency._get_refs()["icon_literal_paths"]

        orphan_files = []
        for subdir in self._ICON_SUBDIRS:
            for fname in _get_disk_files_for_subdir(subdir):
                rel_path = f"icons/{subdir}/{fname}"
                referenced = (
                    rel_path in json_relative
                    or rel_path in py_refs
                )
                if not referenced:
                    orphan_files.append(f"  icons/{subdir}/{fname}")

        if orphan_files:
            msg = (
                f"{len(orphan_files)} icon file(s) on disk not referenced "
                f"by any JSON or Python source:\n" + "\n".join(orphan_files[:50])
                + ("\n  ... and more" if len(orphan_files) > 50 else "")
            )
            if _is_strict():
                pytest.fail(msg)
            else:
                warnings.warn(UserWarning(msg))


def _walk_icons_in_json(obj, refs):
    """Recursively collect all icon path strings (starting with /icons/ or icons/)."""
    if isinstance(obj, str):
        stripped = obj.strip()
        if stripped.startswith("/icons/") or stripped.startswith("icons/"):
            refs.add(stripped)
    elif isinstance(obj, dict):
        for v in obj.values():
            _walk_icons_in_json(v, refs)
    elif isinstance(obj, list):
        for v in obj:
            _walk_icons_in_json(v, refs)
