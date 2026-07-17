from __future__ import annotations
from tests.dynamic_importer import import_from

_i18n = import_from('i18n')
t = _i18n.t
init_language = _i18n.init_language
get_language = _i18n.get_language
set_language = _i18n.set_language


def test_t_returns_key_for_missing():
    result = t("nonexistent.key.xyz")
    assert result == "nonexistent.key.xyz"


def test_t_returns_default():
    result = t("nonexistent.key", default="FALLBACK")
    assert result == "FALLBACK"


def test_get_language_returns_string():
    lang = get_language()
    assert isinstance(lang, str)


def test_set_language_and_get():
    set_language("en_US")
    assert get_language() == "en_US"
