"""The image loader: a real alpha channel must survive, the colour key must too.

`g.load_image()` serves two conventions at once. Upstream art draws on a
magenta field and is made transparent by a colour key; newer art (the app icon)
carries a real alpha channel, because a rounded corner cannot be expressed with
a binary key.

The loader used to call `convert()` unconditionally, and `convert()` throws the
alpha channel away: every transparent pixel came back opaque black. These tests
pin both paths, so "the icon loads as a black box" cannot come back.
"""

import os

import pytest
import pygame

from singularity.code.graphics import g, theme


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
THEME_ICON = os.path.join(REPO_ROOT, "singularity", "data", "themes",
                          "2030", "images", "icon.png")


def alpha_at(surface, x, y):
    return surface.get_at((x, y))[3]


def test_a_png_with_real_alpha_keeps_it(tmp_path, graphics):
    """Rounded corners are only possible if alpha survives the load."""
    path = str(tmp_path / "alpha.png")
    source = pygame.Surface((16, 16), pygame.SRCALPHA)
    source.fill((0, 0, 0, 0))
    pygame.draw.circle(source, (255, 0, 0, 255), (8, 8), 4)
    pygame.image.save(source, path)

    loaded = g.load_image(path)

    assert loaded.get_flags() & pygame.SRCALPHA, \
        "the loaded surface has no alpha channel at all"
    assert loaded.get_size() == (16, 16)
    for corner in ((0, 0), (15, 0), (0, 15), (15, 15)):
        assert alpha_at(loaded, *corner) == 0, \
            "corner %r came back opaque; convert() ate the alpha" % (corner,)
    centre = loaded.get_at((8, 8))
    assert centre[3] == 255 and centre[0] == 255, \
        "the opaque centre pixel did not survive: %r" % (centre,)


def test_a_magenta_field_still_becomes_transparent(tmp_path, graphics):
    """Every image upstream shipped is keyed this way; it must not change."""
    path = str(tmp_path / "keyed.png")
    source = pygame.Surface((16, 16))
    source.fill((255, 0, 255))
    pygame.draw.rect(source, (0, 128, 0), pygame.Rect(4, 4, 8, 8))
    pygame.image.save(source, path)

    loaded = g.load_image(path)

    for corner in ((0, 0), (15, 0), (0, 15), (15, 15)):
        assert alpha_at(loaded, *corner) == 0, \
            "the magenta field is not transparent at %r" % (corner,)
    centre = loaded.get_at((8, 8))
    assert centre[3] == 255, "the drawn square came back transparent"
    assert centre[:3] == (0, 128, 0), \
        "the colour key altered a pixel that was not magenta: %r" % (centre,)


def test_the_2030_theme_icon_loads_with_transparent_corners(graphics):
    """The end-to-end case: the shipped icon, through the real theme load.

    The icon is drawn on a plate with rounded corners, and a launcher composites
    it onto its own background. If the loader flattened its alpha, the window
    icon and the taskbar icon would be a black rounded rectangle -- the exact
    artefact this fixes.
    """
    theme.set_theme("2030", force_reload=True)
    surface = g.images["icon"]
    size = surface.get_width()

    assert surface.get_height() == size
    assert surface.get_flags() & pygame.SRCALPHA, \
        "the theme icon lost its alpha channel in load_image()"
    for corner in ((0, 0), (size - 1, 0), (0, size - 1), (size - 1, size - 1)):
        assert alpha_at(surface, *corner) == 0, \
            "the theme icon is opaque at %r" % (corner,)
    assert alpha_at(surface, size // 2, size // 2) == 255, \
        "the theme icon's plate is transparent in the middle"
