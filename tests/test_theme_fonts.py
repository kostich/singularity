"""A theme's fonts must be able to draw what the game will ask them to.

pygame gives no reliable "is this glyph present" answer: `Font.metrics()` hands
back the .notdef metrics for a missing character, so a font without Cyrillic
looks perfectly healthy until a Russian player sees a row of boxes. These tests
compare a rendered character against a rendered codepoint that no font here
defines (U+10FFFD, in a private use plane): if the two bitmaps are identical,
the character fell back to .notdef and is not really there.

The corpus is not a guess -- it is the text a language actually shows: its
catalogue, the English that stands in for anything it leaves untranslated, the
data files the screens read, and the two glyphs the map screen draws as text
(U+25AE and U+25B6, map.py). Each language is measured against its own face,
because a theme may name one per language (`theme_ar.dat`) and because SDL_ttf
gives a widget one face for a whole string: there is no per-character
fallback, so a glyph the game draws has to be in the face that draws it.
"""

import glob
import os

import polib
import pygame
import pytest

from singularity.code.graphics import g, theme


# A codepoint no font in this repository defines, used to render .notdef.
NOTDEF = "\U0010FFFD"

# Printable ASCII without the space, which draws nothing in every face.
PRINTABLE_ASCII = {chr(code) for code in range(0x20, 0x7F)} - {" "}

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
I18N = os.path.join(REPO_ROOT, "singularity", "i18n")
DATA = os.path.join(REPO_ROOT, "singularity", "data")


def languages():
    """Every shipped language code, plus None for English.

    None is the face a language with no variant of its own draws with: no
    variant file applies, so the theme's base face does.
    """
    codes = [None]
    for name in sorted(os.listdir(I18N)):
        if name.startswith("lang_") and os.path.isdir(os.path.join(I18N, name)):
            codes.append(name[len("lang_"):])
    return codes


LANGUAGES = [pytest.param(code, id=code or "en") for code in languages()]

# Each language is parsed once; the parametrised tests ask for it twice.
_CHARACTERS = {}


def language_characters(language):
    """Every character the game can show with this language selected.

    The translated text where there is any and the English it falls back to
    where there is not, plus the .dat content the screens read and the two
    glyphs the map HUD draws as text.
    """
    if language in _CHARACTERS:
        return _CHARACTERS[language]

    chars = set("\u25ae\u25b6")
    if language is None:
        paths = sorted(glob.glob(os.path.join(I18N, "*.pot")))
    else:
        paths = sorted(glob.glob(os.path.join(I18N, "lang_" + language,
                                              "*.po")))
    for path in paths:
        for entry in polib.pofile(path):
            strings = [entry.msgstr or entry.msgid]
            for form in sorted(entry.msgstr_plural or {}):
                strings.append(entry.msgstr_plural[form] or entry.msgid)
            for text in strings:
                chars.update(char for char in text if char.strip())

    # The .dat files are shown through the catalogue, but their own text is
    # what an entry with no translation falls back to.
    for path in sorted(glob.glob(os.path.join(DATA, "*.dat"))):
        with open(path, encoding="utf-8", errors="replace") as fd:
            for line in fd:
                chars.update(char for char in line
                             if ord(char) > 127 and not char.isspace())

    _CHARACTERS[language] = chars
    return chars


def notdef_bitmap(font):
    return pygame.image.tobytes(font.render(NOTDEF, True, (255, 255, 255)),
                                "RGBA")


def missing_characters(font, chars):
    box = notdef_bitmap(font)
    missing = []
    for char in sorted(chars):
        # A zero-width character cannot be a box: .notdef always has width,
        # and pygame refuses to render text with none.
        if font.size(char)[0] == 0:
            continue
        bitmap = pygame.image.tobytes(font.render(char, True, (255, 255, 255)),
                                      "RGBA")
        if bitmap == box:
            missing.append(char)
    return missing


def font_file(theme_id, slot, language=None):
    """The file a theme resolves a font slot to, following its parents.

    With a language, that language's variant is asked first: a variant that
    names the slot overrides it, and one that does not inherits, which is how a
    theme changes one face for one script.
    """
    owner = theme.themes[theme_id]
    variant = owner._variants.get(language)
    if variant is not None and slot in variant.font_infos:
        return variant.font_infos[slot]
    if slot in owner._variants[None].font_infos:
        return owner._variants[None].font_infos[slot]
    for parent in owner.iter_parents():
        if slot in parent._variants[None].font_infos:
            return parent._variants[None].font_infos[slot]
    raise AssertionError("%s declares no %r font" % (theme_id, slot))


def test_the_corpus_is_not_trivially_empty():
    """Guard the guard: an empty corpus would make every check below pass."""
    chars = set()
    for language in languages():
        chars |= language_characters(language)
    assert len(chars) > 100
    assert "\u0416" in chars, "Cyrillic is part of what the game displays"
    assert "\u25ae" in chars and "\u25b6" in chars
    # The scripts the theme names a face for are shipped languages, not theory.
    assert {"ar", "bn", "hi", "ja", "zh_CN"} <= set(languages())


@pytest.mark.parametrize("language", LANGUAGES)
@pytest.mark.parametrize("slot", ["normal", "special"])
def test_2030_fonts_draw_everything_the_game_displays(graphics, language, slot):
    """The new default theme must not leave a character of any language as a box.

    Each language is measured against the face it draws with -- its variant
    where the theme names one, the base face otherwise -- and against its own
    text rather than the union of every language: a Japanese face is not
    expected to draw Bengali, but a Bengali face that could not draw `CPU` is
    a bug all the same, because the game puts Latin beside every script.
    """
    theme.set_theme("2030", force_reload=True)

    font = pygame.font.Font(font_file("2030", slot, language), 24)
    missing = missing_characters(font, language_characters(language))

    assert not missing, ("%s/%s cannot draw %r in %s"
                         % ("2030", slot, "".join(missing), language or "en"))


@pytest.mark.parametrize("language", LANGUAGES)
def test_the_speed_glyphs_are_real_glyphs_not_notdef(graphics, language):
    """The map HUD draws its pause bar and speed arrows as these characters."""
    theme.set_theme("2030", force_reload=True)

    for slot in ("normal", "special"):
        font = pygame.font.Font(font_file("2030", slot, language), 24)
        box = notdef_bitmap(font)
        for char in ("\u25ae", "\u25b6"):
            bitmap = pygame.image.tobytes(font.render(char, True,
                                                      (255, 255, 255)), "RGBA")
            assert bitmap != box, "%s/%s draws U+%04X as .notdef in %s" % (
                "2030", slot, ord(char), language or "en")


@pytest.mark.parametrize("language", LANGUAGES)
@pytest.mark.parametrize("slot", ["normal", "special"])
def test_every_active_face_draws_printable_ascii(graphics, language, slot):
    """No language's face may be a script face and nothing else.

    The language menu names every row in English as well as natively, an entry
    with no translation falls back to the English source, and the readouts are
    digits and Latin labels. So the face a Bengali player reads with has to
    draw "CPU" and "2026" too, not only Bengali. utils/subset_fonts.py
    completes each subset from DejaVu for exactly this.
    """
    theme.set_theme("2030", force_reload=True)

    font = pygame.font.Font(font_file("2030", slot, language), 24)
    missing = missing_characters(font, PRINTABLE_ASCII)

    assert not missing, ("%s/%s cannot draw ASCII %r in %s"
                         % ("2030", slot, "".join(missing), language or "en"))


@pytest.mark.parametrize("language", LANGUAGES)
@pytest.mark.parametrize("slot", ["normal", "special"])
def test_a_character_no_face_has_shows_a_box_not_a_space(graphics, language,
                                                         slot):
    """The fallback glyph must be drawn, or a gap reads as a typo.

    pygame renders .notdef for a character the face has not got. Every Noto
    face here ships that glyph with no outline at all, so the player saw a gap
    the width of a space and no way to tell it from a lost character.
    utils/subset_fonts.py puts DejaVu's hollow box there instead.
    """
    theme.set_theme("2030", force_reload=True)

    font = pygame.font.Font(font_file("2030", slot, language), 24)
    bitmap = pygame.image.tobytes(font.render(NOTDEF, True, (255, 255, 255)),
                                  "RGBA")
    ink = sum(1 for index in range(3, len(bitmap), 4) if bitmap[index])

    assert ink > 0, ("%s/%s draws a missing character as nothing in %s"
                     % ("2030", slot, language or "en"))


def test_every_face_the_theme_names_ships_with_the_theme(graphics):
    """A Flatpak installs no system fonts, so the theme must carry its own.

    `find_files()` resolves a font name against <theme>/fonts, and every name
    in a 2030 variant is a plain filename rather than an absolute path, so a
    variant that still pointed at a system font would fail here.
    """
    theme.set_theme("2030", force_reload=True)

    fonts_dir = os.path.join(REPO_ROOT, "singularity", "data", "themes", "2030",
                             "fonts")
    for language in languages():
        for slot in ("normal", "special"):
            path = font_file("2030", slot, language)
            assert os.path.dirname(path) == fonts_dir, path
            assert os.path.isfile(path), path


def test_the_legacy_themes_keep_the_fonts_they_shipped_with(graphics):
    """The old themes must not be restyled by work done for the new one.

    Not a coverage check: `acknowtt.ttf` has never carried Cyrillic, and
    `Legacy-default/theme_ru_RU.dat` overrides it with the superstar face for
    exactly that reason. That is upstream's arrangement, and changing it would
    change how the legacy themes look.
    """
    assert os.path.basename(font_file("Legacy-default", "normal")) == \
        "DejaVuSans.ttf"
    assert os.path.basename(font_file("Legacy-default", "special")) == \
        "acknowtt.ttf"

    for theme_id in ("Legacy-nightmode", "Legacy-vector"):
        for slot in ("normal", "special"):
            assert font_file(theme_id, slot) == font_file("Legacy-default",
                                                          slot)
