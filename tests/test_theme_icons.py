"""The button glyphs: present, distinct, credited, and actually asked for.

The glyphs are artwork, so most of what could go wrong is invisible to the
tests that check behaviour: a missing file draws no glyph and the button simply
looks shorter, which is not an error anywhere. These tests are about the gap
between the name a button asks for and the file the theme ships.
"""

import os
import re

import pygame
import pytest

from singularity.code.graphics import g, theme


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
THEME = os.path.join(REPO_ROOT, "singularity", "data", "themes", "2030")
ICONS = os.path.join(THEME, "icons")
IMAGES = os.path.join(THEME, "images")


def icon_names_in_code():
    """Every `icon="icon_..."` a screen or widget asks for."""
    wanted = set()
    pattern = re.compile(r'icon\s*=\s*"([a-z0-9_]+)"')
    for root, _dirs, files in os.walk(
            os.path.join(REPO_ROOT, "singularity", "code")):
        for filename in files:
            if not filename.endswith(".py"):
                continue
            with open(os.path.join(root, filename), "r",
                      encoding="utf-8") as handle:
                wanted.update(pattern.findall(handle.read()))
    return wanted


def test_the_code_asks_for_icons():
    """Guard the guard: no names found would make the check below vacuous."""
    names = icon_names_in_code()
    assert len(names) > 10, names
    assert "icon_ok" in names and "icon_delete" in names


def test_every_icon_the_code_asks_for_exists(graphics):
    """A button naming a glyph the theme does not ship draws no glyph at all."""
    theme.set_theme("2030", force_reload=True)

    missing = sorted(name for name in icon_names_in_code()
                     if name not in g.images)

    assert not missing, "the theme ships no %r" % (missing,)


def test_every_shipped_glyph_has_its_source(graphics):
    """The SVG each PNG came from is vendored, so the artwork is reproducible."""
    from utils import make_icon_set

    sources = {os.path.splitext(name)[0]
               for name in os.listdir(ICONS) if name.endswith(".svg")}
    assert sources, "no vendored SVG sources"

    # The mapping is what turns a game name (`icon_ok`, which is what a button
    # asks for) into a Lucide drawing (`check`, which is what the file is
    # called). Comparing the two sets directly would compare two vocabularies.
    for name, drawing in make_icon_set.ICONS.items():
        assert drawing in sources, \
            "%s comes from %s.svg, which is not vendored" % (name, drawing)
        assert os.path.exists(os.path.join(IMAGES, "icon_%s.png" % (name,))), \
            "%s is mapped but not rendered" % (name,)


@pytest.mark.parametrize("name", sorted(
    os.path.splitext(filename)[0]
    for filename in os.listdir(IMAGES)
    if filename.startswith("icon_") and filename.endswith(".png")))
def test_a_shipped_glyph_is_a_usable_size_and_has_ink(graphics, name):
    theme.set_theme("2030", force_reload=True)

    surface = g.images[name]
    assert surface.get_size() == (64, 64), surface.get_size()
    assert surface.get_flags() & pygame.SRCALPHA, \
        "%s lost its alpha channel" % (name,)

    alpha = pygame.surfarray.array_alpha(surface)
    ink = int((alpha > 60).sum())
    assert ink > 40, "%s is nearly empty" % (name,)
    assert ink < 64 * 64 * 0.60, "%s is a block, not a glyph" % (name,)


def test_no_two_glyphs_are_the_same_drawing(graphics):
    """A copy-paste in the name table is the mistake that ships silently."""
    theme.set_theme("2030", force_reload=True)

    seen = {}
    for name in sorted(g.images):
        if not name.startswith("icon_"):
            continue
        mark = pygame.image.tobytes(g.images[name], "RGBA")
        assert mark not in seen, "%s is the same drawing as %s" % (
            name, seen.get(mark))
        seen[mark] = name


def test_the_icon_set_is_credited_and_licensed():
    """ISC requires the notice; a vendored set without one is not usable."""
    licence = os.path.join(ICONS, "LICENSE")
    readme = os.path.join(ICONS, "README.txt")

    assert os.path.exists(licence), "the icon set ships without its licence"
    with open(licence, "r", encoding="utf-8") as handle:
        text = handle.read()
    assert "ISC License" in text
    assert "Lucide Contributors" in text, "the copyright line is missing"

    assert os.path.exists(readme)
    with open(readme, "r", encoding="utf-8") as handle:
        readme_text = handle.read()
    # The licence question that made this set the choice is recorded, so a
    # future swap to a GPL-3 pack has to argue with a document.
    assert "ISC" in readme_text and "GPL-2+" in readme_text


@pytest.mark.parametrize("theme_id", ("Legacy-default", "Legacy-nightmode",
                                      "Legacy-vector"))
def test_a_legacy_theme_draws_no_glyph(graphics, theme_id):
    """`icon_buttons = none` is what keeps the old buttons word-only."""
    theme.set_theme(theme_id, force_reload=True)

    assert g.dialog_style("icon_buttons") == "none"
