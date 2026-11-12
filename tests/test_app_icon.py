"""The application icon: every size present, labelled, legible, and legacy untouched.

The fork's icon is the original red-eyed Singularity mark with "2030" in red
below the eyes, on a transparent-background plate with rounded corners, rendered
natively at each size by `utils/make_app_icon.py`. These tests are about the
artefacts, not the drawing: that the files exist at the sizes the Flatpak
manifest installs, that the label is really there, that the corners are really
transparent and the plate really rounded (a launcher composites the icon onto
its own background), that the mark clears the WCAG contrast floor *measured off
the shipped pixels*, and that none of the legacy themes' artwork moved.
"""

import hashlib
import os
import re

import numpy as np
import pytest
import pygame

from singularity.code.graphics import g, theme


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ICON_DIR = os.path.join(REPO_ROOT, "flatpak", "icons")
MANIFEST = os.path.join(REPO_ROOT, "flatpak",
                        "io.github.singularity.Singularity2030.yml")

THEMES = os.path.join(REPO_ROOT, "singularity", "data", "themes")
THEME_ICON = os.path.join(THEMES, "2030", "images", "icon.png")

# Upstream's 32x32 mark, which the fork redraws but must not replace in place.
LEGACY_ICON_SHA256 = \
    "5a38f2ae81ccc8fcdb7d579a9aade990fa21b1a14b57325dab2d8dd27813f627"


def manifest_sizes():
    """The sizes the Flatpak manifest's install loop actually copies."""
    with open(MANIFEST, encoding="utf-8") as fd:
        text = fd.read()
    match = re.search(r"for size in ([0-9 ]+); do", text)
    assert match, "the manifest's icon install loop has changed shape"
    return tuple(int(value) for value in match.group(1).split())


def red_pixels(surface, top=0, bottom=None):
    """Count pixels whose red channel dominates, in a horizontal band."""
    arr = pygame.surfarray.array3d(surface)[:, top:bottom]
    return int(((arr[:, :, 0] > 60)
                & (arr[:, :, 1] < 60)
                & (arr[:, :, 2] < 60)).sum())


def corner_points(size):
    return ((0, 0), (size - 1, 0), (0, size - 1), (size - 1, size - 1))


def luminance(color):
    """WCAG relative luminance of an sRGB colour.

    Written out here rather than imported from the generator, so the tool
    cannot mark its own arithmetic as correct.
    """
    def linear(value):
        value = value / 255.0
        if value <= 0.04045:
            return value / 12.92
        return ((value + 0.055) / 1.055) ** 2.4

    red, green, blue = (linear(channel) for channel in color[:3])
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def contrast(one, other):
    """WCAG contrast ratio between two sRGB colours."""
    first, second = luminance(one), luminance(other)
    return (max(first, second) + 0.05) / (min(first, second) + 0.05)


def test_the_manifest_installs_every_icon_we_ship():
    """A size on disk that is not installed is a file nobody sees."""
    on_disk = sorted(int(name[:-4]) for name in os.listdir(ICON_DIR)
                     if name.endswith(".png"))

    assert on_disk == sorted(manifest_sizes())
    assert 32 in on_disk and 64 in on_disk and 128 in on_disk \
        and 256 in on_disk, "Flathub wants 64, 128 and 256 at minimum"


@pytest.mark.parametrize("size", manifest_sizes())
def test_every_shipped_icon_is_square_and_the_right_size(size):
    surface = pygame.image.load(os.path.join(ICON_DIR, "%d.png" % size))

    assert surface.get_size() == (size, size)


@pytest.mark.parametrize("size", [s for s in manifest_sizes() if s >= 32])
def test_the_label_is_in_the_lower_half_of_every_readable_size(size):
    """The mark sits in the top half; "2030" has to be below it.

    Splitting the icon at the mark's baseline is what makes this a test of the
    *label* rather than of "there is red somewhere": the eyes alone are all in
    the upper half, so red below that line can only be the numbers.
    """
    surface = pygame.image.load(os.path.join(ICON_DIR, "%d.png" % size))

    eyes_and_label = red_pixels(surface)
    eyes_only = red_pixels(surface, bottom=int(size * 0.52))

    assert eyes_only > 0, "the mark should be in the upper half"
    assert eyes_and_label > eyes_only, \
        "%d.png has no red label below the eyes" % size


def test_the_label_reads_as_four_digits_at_128():
    """Enough ink for four characters, not a smear: count separate columns.

    At 128 the label is 27px tall; rendered with gaps between the digits it has
    a clear column structure, which is what "2030" looking like "2030" means in
    pixel terms.
    """
    surface = pygame.image.load(os.path.join(ICON_DIR, "128.png"))
    arr = pygame.surfarray.array3d(surface)[:, int(128 * 0.6):]
    ink = (arr[:, :, 0] > 60) & (arr[:, :, 1] < 60)

    columns = ink.any(axis=1)
    runs, previous = 0, False
    for value in columns:
        if value and not previous:
            runs += 1
        previous = value
    assert runs == 4, ("the label should be four separate glyph columns, got %d"
                       % runs)


def test_the_theme_icon_carries_the_same_label(graphics):
    """The window/taskbar icon comes from the theme, so it needs the label too."""
    theme.set_theme("2030", force_reload=True)
    surface = g.images["icon"]
    size = surface.get_width()

    assert surface.get_width() == surface.get_height()
    assert red_pixels(surface, bottom=int(size * 0.55)) > 0, \
        "the 2030 theme icon has no label under the eyes"


@pytest.mark.parametrize("size", manifest_sizes())
def test_every_shipped_icon_carries_real_transparency(size):
    """A launcher draws the icon on its own background, so the corners must be
    transparent: an opaque square is the black box this icon used to be."""
    surface = pygame.image.load(os.path.join(ICON_DIR, "%d.png" % size))

    assert surface.get_flags() & pygame.SRCALPHA, \
        "%d.png has no alpha channel" % size
    for corner in corner_points(size):
        assert surface.get_at(corner)[3] == 0, \
            "%d.png is not transparent at %r" % (size, corner)
    assert surface.get_at((size // 2, size // 2))[3] == 255, \
        "%d.png has no opaque plate" % size


@pytest.mark.parametrize("size", manifest_sizes())
def test_the_plate_is_rounded_rather_than_a_square(size):
    """The corners are an arc, and the plate still reaches every edge midpoint.

    Both halves matter: transparent corners alone would also pass for a small
    floating square, and an opaque edge alone would pass for the old black box.
    """
    surface = pygame.image.load(os.path.join(ICON_DIR, "%d.png" % size))
    radius = int(round(0.22 * size))

    for midpoint in ((0, size // 2), (size // 2, 0),
                     (size - 1, size // 2), (size // 2, size - 1)):
        assert surface.get_at(midpoint)[3] == 255, \
            "%d.png: the plate does not reach edge midpoint %r" % (size, midpoint)

    # Along the top edge the cut is a run of transparent pixels, then opaque.
    cut = 0
    while surface.get_at((cut, 0))[3] == 0:
        cut += 1
    assert 0 < cut <= radius, \
        "%d.png: the corner cut is %d pixels wide, radius is %d" % (
            size, cut, radius)
    assert surface.get_at((radius, 0))[3] == 255, \
        "%d.png: the top edge is still transparent at the radius" % size

    # The arc, not a diagonal chamfer: inside the corner box, the point on the
    # diagonal is plate and the point on the edge is still cut away.
    centre = radius // 2
    assert surface.get_at((centre, centre))[3] == 255, \
        "%d.png: the corner box has no plate in it" % size
    assert surface.get_at((0, centre))[3] < 255, \
        "%d.png: the corner is square, not rounded" % size


def test_the_mark_clears_the_contrast_floor_measured_off_the_pixels():
    """Sampled from the shipped 256x256, not read from the generator's constants.

    The old art was #800000 on black: 1.92:1, under the 3.0:1 WCAG floor for a
    graphical object, and 1.52:1 against a #1E1E1E dock.
    """
    size = 256
    surface = pygame.image.load(os.path.join(ICON_DIR, "%d.png" % size))
    rgb = pygame.surfarray.array3d(surface)
    opaque = pygame.surfarray.array_alpha(surface) > 250
    flat = rgb.reshape(-1, 3)
    flat_opaque = opaque.reshape(-1)

    def dominant(mask):
        colours, counts = np.unique(flat[mask], axis=0, return_counts=True)
        return tuple(int(value) for value in colours[counts.argmax()])

    plate = dominant(flat_opaque)
    assert sum(plate) < 60, "the plate should be near-black, got %r" % (plate,)

    wedges = dominant(flat_opaque
                      & (flat[:, 0] > 100) & (flat[:, 0] < 250)
                      & (flat[:, 1] < 20) & (flat[:, 2] < 20))
    assert wedges[0] > plate[0] + 100, \
        "the wedges are not a red mark on the plate: %r" % (wedges,)

    # The label lives below the mark's baseline; the eyes are all above it.
    below = np.zeros((size, size), dtype=bool)
    below[:, int(size * 0.6):] = True
    label = dominant(flat_opaque & below.reshape(-1)
                     & (flat[:, 0] >= 250) & (flat[:, 1] == 0) & (flat[:, 2] == 0))

    assert contrast(wedges, plate) >= 3.0, \
        "wedges %r on plate %r are %.2f:1, under the 3.0 floor" % (
            wedges, plate, contrast(wedges, plate))
    assert contrast(label, plate) >= 4.5, \
        "label %r on plate %r is %.2f:1, under the 4.5 floor" % (
            label, plate, contrast(label, plate))
    assert luminance(wedges) < luminance(label), \
        "the wedges must stay darker than the label, or it stops reading as a mark"


def test_the_legacy_theme_icons_are_byte_for_byte_unchanged():
    """Upstream art, and the fork's whole promise about the legacy themes."""
    for theme_id in ("Legacy-default", "Legacy-nightmode"):
        path = os.path.join(THEMES, theme_id, "images", "icon.png")
        with open(path, "rb") as fd:
            digest = hashlib.sha256(fd.read()).hexdigest()
        assert digest == LEGACY_ICON_SHA256, theme_id
