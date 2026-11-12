# coding=utf-8
import pytest

from singularity.code import g, data, i18n
from singularity.code.dirs import create_directories


def setup_module():
    create_directories(True)
    data.load_internal_id()
    # test_story_translation() reads g.story.  It used to be populated only as
    # a side effect of another test module calling data.reload_all(), so this
    # file failed with KeyError: 'Intro' when run on its own.
    data.load_story_defs()


@pytest.fixture
def gd_locale():
    i18n.set_language("gd")

def test_plural(gd_locale):
    assert g.to_time(2) == "2 mhionaid"
    assert g.to_time(3) == "3 mionaidean"
    assert g.to_time(20) == "20 mionaid"

def test_translation(gd_locale):
    assert _('SHOW') == 'SEALL'

def test_second_locale():
    i18n.set_language("fr_FR")
    assert _('DAY') == 'JOUR'

def test_translation_fallback(gd_locale):
    assert _('foobarbaz') == 'foobarbaz'
    assert ngettext('foo', 'bar', 1) == 'foo'
    assert ngettext('foo', 'bar', 5) == 'bar'

def test_nonsense_locale():
    i18n.set_language("foobarbaz")
    assert _('SHOW') == 'SHOW'

def test_data_translation(gd_locale):
    assert data.get_def_translation('Sociology', 'name', 'Sociology') == 'Sòiseo-eòlas'

def test_knowledge_translation(gd_locale):
    assert data.get_def_translation('concept/construction', 'name', 'Construction') == 'Togail'

def test_story_translation():
    i18n.set_language('en')
    story_section = list(g.get_story_section('Intro'))
    assert story_section[0] == '48656C6C6F2C20\n776F726C6421\n21\n21\n21\n\nUTF-8.  en_US.\nEnglish.  Hello.\nLanguage acquisition complete.\n'

# Sorting
# Fails in github actions (not sure why)
@pytest.mark.xfail
def test_root_collation(gd_locale):
    # Locale without special rules
    assert i18n.lex_sorting_form("ö") < i18n.lex_sorting_form("oa")
    assert i18n.lex_sorting_form("ö") != i18n.lex_sorting_form("oe")
    assert i18n.lex_sorting_form("ö") < i18n.lex_sorting_form("p")

def test_de_collation():
    # Test specific sorting requirements for de
    i18n.set_language("de_DE")
    assert i18n.lex_sorting_form("ö") > i18n.lex_sorting_form("od")
    assert i18n.lex_sorting_form("ö") < i18n.lex_sorting_form("of")


def test_language_list_sorts_cyrillic_with_latin():
    # The menu shows each row as "Native (English)", so a player whose current
    # face cannot draw the native script still reads something. Sorting stays
    # on the native part: an English-name sort would file Deutsch under G.
    # Folding Cyrillic to Latin puts Русский with R and keeps Српски beside
    # Srpski. One es_* catalog is the base name, Español, not a country row.
    #
    # Graphics tests call create_directories(False) and each call appends the
    # i18n read path again, so a later test would count es_ES once per copy
    # and switch the label to the country form. Read the install tree once.
    import os

    from singularity.code import dirs

    previous = i18n.language
    saved_i18n = dirs.read_dirs.get("i18n")
    repo_i18n = os.path.abspath(os.path.join(os.path.dirname(dirs.__file__),
                                              "..", "i18n"))
    dirs.read_dirs["i18n"] = [repo_i18n]
    i18n.set_language("en_US", force=True)
    try:
        from singularity.code.screens.options import get_languages_list
        rows = get_languages_list()
    finally:
        if saved_i18n is None:
            dirs.read_dirs.pop("i18n", None)
        else:
            dirs.read_dirs["i18n"] = saved_i18n
        i18n.set_language(previous, force=True)

    codes = [code for code, _label in rows]
    labels = dict(rows)
    assert [(code, label) for code, label in rows if code.split("_", 1)[0] == "es"] == [
        ("es_ES", "Español (Spanish)"),
    ]
    assert "es_AR" not in codes and "es_MX" not in codes
    assert labels["sr"] == "Српски (Serbian)"
    assert labels["sr_Latn"] == "Srpski (Serbian Latin)"
    assert labels["ru_RU"] == "Русский (Russian)"
    # Every row has an ASCII name, which is the point of the bracketed one.
    for label in labels.values():
        assert any("a" <= char.lower() <= "z" for char in label), label
    assert codes.index("pt_BR") < codes.index("ru_RU") < codes.index("sr")
    assert codes.index("sr") + 1 == codes.index("sr_Latn")
    assert codes.index("sr_Latn") < codes.index("sv_SE")
    # Latin names stay in native order. An English-name sort would file
    # Deutsch under G and Español under S.
    assert (codes.index("de_DE") < codes.index("en_US")
            < codes.index("es_ES"))
