#!/usr/bin/env python3
"""
Theme Architecture Enforcement Scanner

Detects places where UI code uses hardcoded colors, fonts, or inline
styles instead of loading them from the centralized theme system
(constants.py, styles.py, or darkmode.qss).

What it finds:
  - Hardcoded hex colors like #FF0000 inside setStyleSheet()
  - Hardcoded rgba() colors inside setStyleSheet()
  - Big inline style blocks that should be in the .qss file
  - Hardcoded font names like "Segoe UI" or "Arial"

By default, the theme system files themselves (styles.py, constants.py,
edit_pals.py, the .qss folder) are whitelisted so we don't flag the
theme system itself. Use --ruthless to scan EVERYTHING.

Usage:
  python check_theme_violations.py                          # scan src/
  python check_theme_violations.py --root src/              # same thing
  python check_theme_violations.py --ruthless               # scan EVERYTHING
  python check_theme_violations.py --strict                 # fail on warnings too
  python check_theme_violations.py -v                       # show code snippets
  python check_theme_violations.py --include-qss            # also scan .qss files
  python check_theme_violations.py --exclude tests/         # skip a directory

Exit codes:
  0  Clean — no violations found
  1  Violations found
  2  Invalid arguments (bad path, etc.)
"""
from __future__ import annotations

import argparse
import ast
import os
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

# ── Terminal Colors ──────────────────────────────────────────────

_SUPPORTS_COLOR = (
    hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()
    and os.environ.get('TERM') not in ('dumb', '')
)


def _c(code: str, text: str) -> str:
    if _SUPPORTS_COLOR:
        return f'{code}{text}\033[0m'
    return text


RED = lambda s: _c('\033[91m', s)
GREEN = lambda s: _c('\033[92m', s)
YELLOW = lambda s: _c('\033[93m', s)
BLUE = lambda s: _c('\033[94m', s)
MAGENTA = lambda s: _c('\033[95m', s)
CYAN = lambda s: _c('\033[96m', s)
BOLD = lambda s: _c('\033[1m', s)
DIM = lambda s: _c('\033[2m', s)

# ── Regex Patterns ───────────────────────────────────────────────

RE_HEX_COLOR = re.compile(r'#[0-9A-Fa-f]{6}\b')
RE_RGBA_COLOR = re.compile(r'rgba\(\s*\d+\s*,\s*\d+\s*,\s*\d+\s*,\s*[\d.]+\s*\)')
RE_SET_STYLESHEET = re.compile(r'\.setStyleSheet\s*\(')
RE_FONT_LITERAL = re.compile(
    r"""['"](?:Segoe UI|Consolas|Arial|Hack Nerd Font|Courier New|Tahoma|Verdana|Helvetica)['"]"""
)

# ── Whitelist (files that ARE allowed to contain styling) ─────────

WHITELIST_PATHS: Set[str] = {
    'palworld_aio/ui/styles.py',
    'palworld_aio/constants.py',
    'palworld_aio/edit_pals.py',
}
WHITELIST_PREFIXES: Tuple[str, ...] = ('data/gui/',)

# ── Allowed references (these are OK because they use theme system) ──

ALLOWED_CONSTANTS = re.compile(
    r'constants\.'
    r'(?:BG|GLASS|ACCENT|TEXT|MUTED|EMPHASIS|ALERT|SUCCESS|ERROR|BORDER'
    r'|BUTTON_FG|BUTTON_BG|BUTTON_HOVER|BUTTON_PRIMARY|BUTTON_SECONDARY'
    r'|FONT_FAMILY(?:_NERD|_MONO)?|FONT_SIZE(?:_BOLD|_LARGE|_SMALL|_XLARGE|_TINY)?'
    r'|SPACE_(?:SMALL|MEDIUM|LARGE)|CORNER_RADIUS|FRAME_CORNER_RADIUS|TREE_ROW_HEIGHT'
    r'|ELEMENT_\w+|TEXT_DIM|TEXT_BRIGHT|BG_LIGHT|BG_DARK'
    r'|BORDER_LIGHT|BORDER_ACCENT|GLASS_HEAVY|GLASS_LIGHT'
    r'|FONT_WEIGHT_\w+|PADDING_\w+|BUTTON_HEIGHT|CHIP_HEIGHT|ICON_SIZE_\w+'
    r'|CORNER_RADIUS_LARGE|CORNER_RADIUS_SMALL)'
)
ALLOWED_STYLE_CONSTS = re.compile(
    r'(?:DIALOG_STYLE|MENU_STYLE|STATS_PANEL_STYLE|PICKER_BG_STYLE'
    r'|PICKER_SEARCH_STYLE|PICKER_LIST_STYLE|INPUT_DIALOG_STYLE'
    r'|TOOLTIP_STYLE|CONTENT_PANEL_STYLE|SLOT_EMPTY_STYLE'
    r'|SLOT_HOVER_STYLE|SLOT_SELECTED_STYLE|_GLOBAL_FALLBACK_STYLE'
    r'|_PAL_STYLESHEET|DARK_STYLE_SPLASH)'
)
ALLOWED_GAME_DATA = re.compile(r'_ELEMENT_COLORS|_RANK_COLORS|_RANK_COLOR|_ELEMENT_MAP')
ALLOWED_DYNAMIC_PATTERNS = [
    re.compile(r'\.setProperty\s*\('),
    re.compile(r'\.property\s*\('),
    re.compile(r'styles\.\w+'),
    re.compile(r'ThemeManager\.'),
]

# ── Category display names (plain English) ──────────────────────

CATEGORY_NAMES: Dict[str, str] = {
    'hardcolor-hex': 'Hardcoded hex color',
    'hardcolor-rgba': 'Hardcoded rgba color',
    'inline-qss': 'Inline style block',
    'hardcoded-font': 'Hardcoded font name',
}
CATEGORY_EMOJI: Dict[str, str] = {
    'hardcolor-hex': '🎨',
    'hardcolor-rgba': '🎨',
    'inline-qss': '📝',
    'hardcoded-font': '🔤',
}
CATEGORY_SEVERITY: Dict[str, str] = {
    'hardcolor-hex': 'error',
    'hardcolor-rgba': 'error',
    'inline-qss': 'warning',
    'hardcoded-font': 'warning',
}


# ══════════════════════════════════════════════════════════════════
#  Data
# ══════════════════════════════════════════════════════════════════

@dataclass
class Violation:
    file_path: Path
    line: int
    col: int
    category: str
    severity: str
    message: str
    snippet: str


@dataclass
class ScanResult:
    violations: List[Violation] = field(default_factory=list)

    @property
    def errors(self) -> List[Violation]:
        return [v for v in self.violations if v.severity == 'error']

    @property
    def warnings(self) -> List[Violation]:
        return [v for v in self.violations if v.severity == 'warning']

    def merge(self, other: 'ScanResult') -> None:
        self.violations.extend(other.violations)


# ══════════════════════════════════════════════════════════════════
#  Scanning
# ══════════════════════════════════════════════════════════════════

def _is_whitelisted(rel_path: str) -> bool:
    if rel_path in WHITELIST_PATHS:
        return True
    for prefix in WHITELIST_PREFIXES:
        if rel_path.startswith(prefix):
            return True
    return False


def _uses_theme(line: str) -> bool:
    if ALLOWED_CONSTANTS.search(line):
        return True
    if ALLOWED_STYLE_CONSTS.search(line):
        return True
    if ALLOWED_GAME_DATA.search(line):
        return True
    return False


def _is_setstylesheet(line: str) -> bool:
    return bool(RE_SET_STYLESHEET.search(line))


def _is_dynamic(line: str) -> bool:
    for pat in ALLOWED_DYNAMIC_PATTERNS:
        if pat.search(line):
            return True
    return False


def _count_style_props(text: str) -> int:
    return len(re.findall(
        r'(?:background|color|border|padding|margin|font'
        r'|radius|opacity|outline|shadow|gradient|width|height)',
        text, re.IGNORECASE,
    ))


def _is_inline_block(lines: List[str], idx: int) -> bool:
    """Check if a setStyleSheet call spans multiple CSS properties."""
    text = lines[idx]
    depth = text.count('(') - text.count(')')
    for i in range(idx + 1, min(idx + 60, len(lines))):
        text += lines[i]
        depth += lines[i].count('(') - lines[i].count(')')
        if depth <= 0:
            break
    return _count_style_props(text) >= 3


def scan_file(file_path: Path, root: Path, ruthless: bool = False) -> ScanResult:
    result = ScanResult()
    rel = str(file_path.relative_to(root))

    # Skip whitelisted files unless in ruthless mode
    if not ruthless and _is_whitelisted(rel):
        return result

    try:
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            lines_raw = f.readlines()
    except OSError:
        return result

    lines = [l.rstrip('\n') for l in lines_raw]

    for idx, ln in enumerate(lines):
        lineno = idx + 1

        # ── setStyleSheet lines ──
        if _is_setstylesheet(ln):
            # Skip if it only uses theme constants (unless ruthless)
            if not ruthless and _uses_theme(ln):
                still_has_hardcoded = bool(RE_HEX_COLOR.search(ln)) or bool(RE_RGBA_COLOR.search(ln))
                if not still_has_hardcoded:
                    continue
            # Skip property-setter lines (they're dynamic by design — unless ruthless)
            if not ruthless and _is_dynamic(ln) and not RE_HEX_COLOR.search(ln) and not RE_RGBA_COLOR.search(ln):
                continue

            hexes = RE_HEX_COLOR.findall(ln)
            if hexes:
                result.violations.append(Violation(
                    file_path, lineno, 0, 'hardcolor-hex', 'error',
                    f'Uses hex color {hexes[0]} directly — should come from constants.py',
                    ln.strip(),
                ))

            rgba = RE_RGBA_COLOR.findall(ln)
            if rgba:
                result.violations.append(Violation(
                    file_path, lineno, 0, 'hardcolor-rgba', 'error',
                    'Uses rgba() color directly — should come from constants.py',
                    ln.strip(),
                ))

            if _is_inline_block(lines, idx):
                result.violations.append(Violation(
                    file_path, lineno, 0, 'inline-qss', 'warning',
                    'Multiple style properties in code — should move to darkmode.qss',
                    ln.strip(),
                ))

        # ── Non-setStyleSheet lines with hardcoded fonts ──
        elif (m := RE_FONT_LITERAL.search(ln)):
            used_font = m.group(0)
            has_constants_ref = any(x in ln for x in (
                'FONT_FAMILY', 'FONT_FAMILY_MONO', 'FONT_FAMILY_NERD', 'constants.'
            ))
            if not has_constants_ref:
                result.violations.append(Violation(
                    file_path, lineno, 0, 'hardcoded-font', 'warning',
                    f'Hardcoded font {used_font} — use FONT_FAMILY constant instead',
                    ln.strip(),
                ))

    return result


def scan_qss_file(file_path: Path, root: Path, ruthless: bool = False) -> ScanResult:
    result = ScanResult()
    rel = str(file_path.relative_to(root))

    if not ruthless and _is_whitelisted(rel):
        return result

    try:
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            lines_raw = f.readlines()
    except OSError:
        return result

    lines = [l.rstrip('\n') for l in lines_raw]

    for idx, ln in enumerate(lines):
        lineno = idx + 1

        hexes = RE_HEX_COLOR.findall(ln)
        if hexes:
            result.violations.append(Violation(
                file_path, lineno, 0, 'hardcolor-hex', 'error',
                f'Uses hex color {hexes[0]} directly — should come from constants.py',
                ln.strip(),
            ))

        rgba = RE_RGBA_COLOR.findall(ln)
        if rgba:
            result.violations.append(Violation(
                file_path, lineno, 0, 'hardcolor-rgba', 'error',
                'Uses rgba() color directly — should come from constants.py',
                ln.strip(),
            ))

        if (m := RE_FONT_LITERAL.search(ln)):
            used_font = m.group(0)
            result.violations.append(Violation(
                file_path, lineno, 0, 'hardcoded-font', 'warning',
                f'Hardcoded font {used_font} — use FONT_FAMILY constant instead',
                ln.strip(),
            ))

    return result


def scan_directory(root: Path, excludes: Optional[List[str]] = None,
                   ruthless: bool = False,
                   include_qss: bool = False) -> ScanResult:
    result = ScanResult()
    patterns = excludes or []
    for py_file in sorted(root.rglob('*.py')):
        rel = str(py_file.relative_to(root))
        if any(rel.startswith(e.strip('/')) for e in patterns):
            continue
        result.merge(scan_file(py_file, root, ruthless=ruthless))
    if include_qss:
        for qss_file in sorted(root.rglob('*.qss')):
            rel = str(qss_file.relative_to(root))
            if any(rel.startswith(e.strip('/')) for e in patterns):
                continue
            result.merge(scan_qss_file(qss_file, root, ruthless=ruthless))
    return result


# ══════════════════════════════════════════════════════════════════
#  Reporting
# ══════════════════════════════════════════════════════════════════

def _plural(n: int, word: str) -> str:
    return f'{n} {word}{"s" if n != 1 else ""}'


def print_report(result: ScanResult, root: Path, *, verbose: bool = False) -> None:
    if not result.violations:
        print()
        print(f'  {GREEN(BOLD("✓ PASS — No style violations found!"))}')
        print(f'  {DIM("  All UI code is using the centralized theme system.")}')
        print()
        return

    by_file: Dict[Path, List[Violation]] = defaultdict(list)
    by_cat: Dict[str, int] = defaultdict(int)
    for v in result.violations:
        by_file[v.file_path].append(v)
        by_cat[v.category] += 1

    n_err = len(result.errors)
    n_wrn = len(result.warnings)
    n_tot = len(result.violations)
    n_fls = len(by_file)

    print()
    heading = f'✗ FAIL — {_plural(n_tot, "violation")} found across {_plural(n_fls, "file")}'
    print(f'  {RED(BOLD(heading))}')
    total_sev = ''
    if n_err:
        total_sev += RED(f'{n_err} error{"s" if n_err != 1 else ""}')
    if n_err and n_wrn:
        total_sev += ', '
    if n_wrn:
        total_sev += YELLOW(f'{n_wrn} warning{"s" if n_wrn != 1 else ""}')
    print(f'  {DIM(total_sev)}')
    print()

    # Summary by category
    print(f'  {BOLD("Breakdown by type")}')
    for cat, count in sorted(by_cat.items(), key=lambda x: -x[1]):
        emoji = CATEGORY_EMOJI.get(cat, '•')
        name = CATEGORY_NAMES.get(cat, cat)
        if CATEGORY_SEVERITY.get(cat) == 'error':
            print(f'    {emoji} {RED(f"{name:25s}")} {BOLD(str(count))}')
        else:
            print(f'    {emoji} {YELLOW(f"{name:25s}")} {BOLD(str(count))}')
    print()

    # Per-file detail
    print(f'  {BOLD("Per-file details")}')
    for fpath, violations in sorted(by_file.items()):
        rel = str(fpath.relative_to(root))
        print(f'\n  {CYAN(rel)}')
        for v in sorted(violations, key=lambda x: x.line):
            if v.severity == 'error':
                marker = RED('✗')
            else:
                marker = YELLOW('⚠')
            cat_name = CATEGORY_NAMES.get(v.category, v.category)
            loc = DIM(f'L{v.line}')
            print(f'    {marker} {cat_name:25s} {loc}  {v.message}')
            if verbose:
                print(f'         {DIM(v.snippet[:100])}')
    print()


# ══════════════════════════════════════════════════════════════════
#  CLI
# ══════════════════════════════════════════════════════════════════

def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description='Find hardcoded styles that bypass the theme system.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            'Examples:\n'
            '  %(prog)s                        Scan src/ (default)\n'
            '  %(prog)s --ruthless             Scan everything, no exceptions\n'
            '  %(prog)s --strict               Also fail on warnings\n'
            '  %(prog)s -v                     Show code snippets\n'
            '  %(prog)s --include-qss          Also scan .qss files\n'
        ),
    )
    parser.add_argument(
        '--root', type=Path, default=Path('src'),
        help='Directory to scan (default: src/)',
    )
    parser.add_argument(
        '--ruthless', action='store_true',
        help='Disable whitelist — scan theme files too (styles.py, etc.)',
    )
    parser.add_argument(
        '--strict', action='store_true',
        help='Treat warnings as errors — fail on anything',
    )
    parser.add_argument(
        '-v', '--verbose', action='store_true',
        help='Show the actual code line for each violation',
    )
    parser.add_argument(
        '--include-qss', action='store_true',
        help='Also scan .qss stylesheet files for hardcoded values',
    )
    parser.add_argument(
        '--exclude', action='append', default=[],
        help='Skip files/directories (repeatable)',
    )
    args = parser.parse_args(argv)

    root = args.root.resolve()
    if not root.is_dir():
        print(f'Error: {root} is not a directory', file=sys.stderr)
        return 2

    result = scan_directory(root, excludes=args.exclude, ruthless=args.ruthless,
                            include_qss=args.include_qss)
    print_report(result, root, verbose=args.verbose)

    if not result.violations:
        return 0
    if args.strict:
        return 1
    return 1 if result.errors else 0


if __name__ == '__main__':
    sys.exit(main())
