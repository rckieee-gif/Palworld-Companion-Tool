from __future__ import annotations
import os
import sys
import textwrap
import pytest
from pathlib import Path
from tests.dynamic_importer import import_from

_ctv = import_from('check_theme_violations')
Violation = _ctv.Violation
ScanResult = _ctv.ScanResult
scan_file = _ctv.scan_file
scan_directory = _ctv.scan_directory
main = _ctv.main
_is_whitelisted = _ctv._is_whitelisted
_uses_theme = _ctv._uses_theme
RE_HEX_COLOR = _ctv.RE_HEX_COLOR
RE_RGBA_COLOR = _ctv.RE_RGBA_COLOR
CATEGORY_NAMES = _ctv.CATEGORY_NAMES
CATEGORY_SEVERITY = _ctv.CATEGORY_SEVERITY
_plural = _ctv._plural
_SUPPORTS_COLOR = _ctv._SUPPORTS_COLOR


@pytest.fixture
def tmp_src(tmp_path):
    d = tmp_path / 'src'
    d.mkdir()
    return d


def _write(tmp_src: Path, rel: str, content: str) -> Path:
    p = tmp_src / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(textwrap.dedent(content), encoding='utf-8')
    return p


class TestPlural:
    def test_singular(self):
        assert _plural(1, 'violation') == '1 violation'
    def test_plural(self):
        assert _plural(3, 'violation') == '3 violations'
    def test_zero(self):
        assert _plural(0, 'file') == '0 files'


class TestCategoryNames:
    def test_all_categories_have_names(self):
        for cat in ('hardcolor-hex', 'hardcolor-rgba', 'inline-qss', 'hardcoded-font'):
            assert cat in CATEGORY_NAMES
            assert isinstance(CATEGORY_NAMES[cat], str)

    def test_all_categories_have_severity(self):
        for cat in ('hardcolor-hex', 'hardcolor-rgba', 'inline-qss', 'hardcoded-font'):
            assert cat in CATEGORY_SEVERITY
            assert CATEGORY_SEVERITY[cat] in ('error', 'warning')


class TestWhitelist:
    def test_styles_py(self):
        assert _is_whitelisted('palworld_aio/ui/styles.py')
    def test_constants_py(self):
        assert _is_whitelisted('palworld_aio/constants.py')
    def test_edit_pals_py(self):
        assert _is_whitelisted('palworld_aio/edit_pals.py')
    def test_qss_dir(self):
        assert _is_whitelisted('data/gui/darkmode.qss')
    def test_normal_file(self):
        assert not _is_whitelisted('palworld_aio/ui/main_window.py')
    def test_random_file(self):
        assert not _is_whitelisted('some/random/file.py')


class TestRegex:
    def test_hex_upper(self):
        assert RE_HEX_COLOR.search('color: #FF0000;')
    def test_hex_lower(self):
        assert RE_HEX_COLOR.search('color: #ff0000;')
    def test_hex_mixed(self):
        assert RE_HEX_COLOR.search('color: #Ff00Aa;')
    def test_no_hex_short(self):
        assert not RE_HEX_COLOR.search('#fff')
    def test_no_hex_8(self):
        assert not RE_HEX_COLOR.search('#FF000011')
    def test_rgba(self):
        assert RE_RGBA_COLOR.search('rgba(255, 0, 0, 0.5)')
    def test_rgba_spaces(self):
        assert RE_RGBA_COLOR.search('rgba( 255 , 0 , 0 , 0.5 )')
    def test_no_rgb(self):
        assert not RE_RGBA_COLOR.search('rgb(255, 0, 0)')


class TestUsesTheme:
    def test_constants_bg(self):
        assert _uses_theme('x = constants.BG')
    def test_constants_accent(self):
        assert _uses_theme('x = constants.ACCENT')
    def test_constants_font_family(self):
        assert _uses_theme('x = constants.FONT_FAMILY')
    def test_constants_button_hover(self):
        assert _uses_theme('f"color: {constants.BUTTON_HOVER}"')
    def test_style_const_dialog(self):
        assert _uses_theme('x = DIALOG_STYLE')
    def test_style_const_slot(self):
        assert _uses_theme('x = SLOT_EMPTY_STYLE')
    def test_game_data_element_colors(self):
        assert _uses_theme('c = _ELEMENT_COLORS.get(x)')
    def test_game_data_rank_colors(self):
        assert _uses_theme('c = _RANK_COLORS[1]')
    def test_no_constant(self):
        assert not _uses_theme('x = "#FF0000"')


class TestScanFile:
    def test_clean(self, tmp_src):
        p = _write(tmp_src, 'clean.py', 'x = 42\nprint("hello")\n')
        assert len(scan_file(p, tmp_src).violations) == 0

    def test_hardcoded_hex(self, tmp_src):
        p = _write(tmp_src, 'bad.py', 'label.setStyleSheet("color: #FF0000;")\n')
        r = scan_file(p, tmp_src)
        assert 'hardcolor-hex' in {v.category for v in r.violations}

    def test_hardcoded_rgba(self, tmp_src):
        p = _write(tmp_src, 'bad.py', 'label.setStyleSheet("background: rgba(255, 0, 0, 0.5);")\n')
        r = scan_file(p, tmp_src)
        assert 'hardcolor-rgba' in {v.category for v in r.violations}

    def test_hardcoded_font(self, tmp_src):
        p = _write(tmp_src, 'bad.py', 'label.setFont(QFont("Segoe UI"))\n')
        r = scan_file(p, tmp_src)
        assert 'hardcoded-font' in {v.category for v in r.violations}

    def test_whitelisted_file_skipped(self, tmp_src):
        p = _write(tmp_src, 'palworld_aio/ui/styles.py',
                   'DIALOG_STYLE = \'background: #0A0B0E; color: #FFFFFF;\'\n')
        assert len(scan_file(p, tmp_src).violations) == 0

    def test_whitelisted_not_skipped_in_ruthless(self, tmp_src):
        p = _write(tmp_src, 'palworld_aio/ui/styles.py',
                   'label.setStyleSheet("color: #FF0000;")\n')
        r = scan_file(p, tmp_src, ruthless=True)
        assert len(r.violations) > 0

    def test_constants_allowed(self, tmp_src):
        p = _write(tmp_src, 'good.py',
                   'from constants import ACCENT\nlabel.setStyleSheet(f"color: {ACCENT};")\n')
        r = scan_file(p, tmp_src)
        assert 'hardcolor-hex' not in {v.category for v in r.violations}

    def test_setproperty_allowed(self, tmp_src):
        p = _write(tmp_src, 'good.py', 'widget.setProperty("active", True)\n')
        assert len(scan_file(p, tmp_src).violations) == 0

    def test_game_data_colors_allowed(self, tmp_src):
        p = _write(tmp_src, 'good.py',
                   'c = _ELEMENT_COLORS.get(elem, "#FFF")\n_RANK_COLORS[1]\n')
        assert len(scan_file(p, tmp_src).violations) == 0

    def test_multiple_hex(self, tmp_src):
        p = _write(tmp_src, 'bad.py',
                   'label.setStyleSheet("color: #FF0000; background: #00FF00;")\n')
        r = scan_file(p, tmp_src)
        hex_v = [v for v in r.violations if v.category == 'hardcolor-hex']
        assert len(hex_v) >= 1
        assert '#FF0000' in hex_v[0].message or '#00FF00' in hex_v[0].message

    def test_inline_qss_block(self, tmp_src):
        p = _write(tmp_src, 'bad.py',
                   'btn.setStyleSheet("""\n    QPushButton {\n'
                   '        background: rgba(125, 211, 252, 0.12);\n'
                   '        color: #7DD3FC;\n'
                   '        border: 1px solid rgba(125,211,252,0.2);\n'
                   '        border-radius: 6px;\n'
                   '        padding: 8px 16px;\n'
                   '    }\n""")\n')
        r = scan_file(p, tmp_src)
        assert 'inline-qss' in {v.category for v in r.violations}

    def test_empty(self, tmp_src):
        p = _write(tmp_src, 'empty.py', '')
        assert len(scan_file(p, tmp_src).violations) == 0

    def test_syntax_error(self, tmp_src):
        p = tmp_src / 'broken.py'
        p.write_text('def foo(:\n', encoding='utf-8')
        assert isinstance(scan_file(p, tmp_src), ScanResult)


class TestScanDirectory:
    def test_clean(self, tmp_src):
        _write(tmp_src, 'a.py', 'x = 1\n')
        _write(tmp_src, 'b.py', 'y = 2\n')
        assert len(scan_directory(tmp_src).violations) == 0

    def test_mixed(self, tmp_src):
        _write(tmp_src, 'good.py', 'x = 1\n')
        _write(tmp_src, 'bad.py', 'label.setStyleSheet("color: #FF0000;")\n')
        assert len(scan_directory(tmp_src).violations) > 0

    def test_whitelisted_dir(self, tmp_src):
        _write(tmp_src, 'data/gui/darkmode.qss', 'QPushButton { color: #FFF; }\n')
        result = scan_directory(tmp_src)
        assert len(result.violations) == 0

    def test_ruthless_whitelisted(self, tmp_src):
        _write(tmp_src, 'data/gui/darkmode.qss', 'color: #000\n')
        result = scan_directory(tmp_src, ruthless=True)
        assert len(result.violations) == 0


class TestScanResult:
    def test_errors_warnings(self):
        r = ScanResult()
        r.violations = [
            Violation(Path('a.py'), 1, 0, 'x', 'error', 'm', 's'),
            Violation(Path('b.py'), 2, 0, 'y', 'warning', 'm', 's'),
        ]
        assert len(r.errors) == 1
        assert len(r.warnings) == 1

    def test_merge(self):
        r1 = ScanResult()
        r2 = ScanResult()
        r1.violations.append(Violation(Path('a.py'), 1, 0, 'x', 'error', 'm', 's'))
        r2.violations.append(Violation(Path('b.py'), 2, 0, 'y', 'warning', 'm', 's'))
        r1.merge(r2)
        assert len(r1.violations) == 2


class TestMainExitCode:
    def test_clean_returns_0(self, tmp_src):
        _write(tmp_src, 'clean.py', 'x = 1\n')
        assert main(['--root', str(tmp_src)]) == 0

    def test_violation_returns_1(self, tmp_src):
        _write(tmp_src, 'bad.py', 'label.setStyleSheet("color: #FF0000;")\n')
        assert main(['--root', str(tmp_src)]) == 1

    def test_invalid_dir_returns_2(self):
        assert main(['--root', '/nonexistent/path']) == 2

    def test_ruthless_flag_accepted(self, tmp_src):
        _write(tmp_src, 'clean.py', 'x = 1\n')
        assert main(['--ruthless', '--root', str(tmp_src)]) == 0

    def test_verbose_flag_accepted(self, tmp_src):
        _write(tmp_src, 'clean.py', 'x = 1\n')
        assert main(['--verbose', '--root', str(tmp_src)]) == 0
