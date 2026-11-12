#!/usr/bin/env python3
"""Regenerate the 2030 theme's artwork.

The 2030 theme has its own `images/` so it can diverge from the legacy themes,
and this is what produces most of it: a dark "tactical display" treatment of
the same equirectangular Earth the legacy themes use, plus the chevron
scrollbar arrow.

The theme's `icon.png` is **not** made here: it is the fork's application icon,
the original red-eyed Singularity mark with "2030" below it, and it is produced
at every size by `utils/make_app_icon.py`. Keeping the two apart means this
script cannot quietly overwrite the app icon with something else.

The button glyphs are **not** made here either: the theme moved to a vendored
icon set, and `utils/make_icon_set.py` rasterises Lucide into `images/icon_*.png`.
This script must not write those files, which is why the fifteen hand-drawn
glyphs it used to produce are gone rather than kept as a fallback.

The legacy themes are not touched by this script: each theme resolves images
from its own `images/` directory, so `Legacy-default`, `Legacy-nightmode` and
`Legacy-vector` keep their 16x16 placeholder arrow -- a black shape keyed out
of a magenta field, which is barely visible on their dark blue -- exactly as
upstream shipped it.

Everything here is derived from art that already ships in this repository,
which keeps the licence story simple: `earth.jpg` and `earth_night.jpg` come
from `Legacy-default/images/` and stay CC-BY-SA 3.0 as data (see LICENSE.CC-
BY-SA-3.txt); the arrow is drawn by this script from primitives and is
original to the fork.

Deterministic: no randomness, no timestamps, no network. Run it from anywhere:

    python3 utils/make_2030_art.py            # rewrite the images
    python3 utils/make_2030_art.py --check    # measure, write nothing

Only pygame and NumPy are used -- the same two the game already requires -- so
this stays runnable on a machine that can run the gate. The day grade is a
single cool luminance ramp rather than per-class masks, because a mask boundary
in a photograph is a visible seam, and a seam across the Indian Ocean is a bug
report.
"""

import argparse
import hashlib
import os
import sys

import numpy as np
import pygame

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
THEMES = os.path.join(REPO_ROOT, "singularity", "data", "themes")
SOURCE = os.path.join(THEMES, "Legacy-default", "images")
TARGET = os.path.join(THEMES, "2030", "images")

# The 2030 palette, from singularity/data/themes/2030/theme.dat.
UI_VOID = (4, 8, 15)
UI_PANEL = (10, 22, 34)
UI_EDGE = (44, 106, 130)
UI_EDGE_BRIGHT = (95, 227, 255)

# The theme image loader keys transparency off this exact colour:
#
#     image = pygame.image.load(filename).convert()      # alpha channel dropped
#     image.set_colorkey((255, 0, 255, 255), RLEACCEL)
#     return image.convert_alpha()
#
# so a PNG with a real alpha channel does not keep it: convert() throws the
# alpha away and every transparent pixel becomes opaque black. A chevron drawn
# on a transparent surface that way renders as a black box with a chevron in
# it. Everything transparent in these files has to be literally 255,0,255.
MAGENTA_KEY = (255, 0, 255)

LUMA = np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)

# The day ramp: input luminance -> output colour. The Earth is mostly dark
# ocean (53.8%) with bright land (22.5%) and bright clouds and ice (23.6%), so
# a single ramp keeps the photograph's structure while pulling the whole thing
# into the panel palette. The top of the ramp is deliberately short of white:
# pure white clouds would outshine every label and marker drawn on top.
DAY_STOPS = [
    (0.00, (3, 7, 11)),
    (0.05, (6, 16, 22)),
    (0.20, (18, 42, 50)),
    (0.45, (48, 74, 76)),
    (0.70, (82, 108, 106)),
    (0.90, (112, 140, 142)),
    (1.00, (128, 156, 158)),
]

# The night side: near-black, with the city lights kept warm. Amber against a
# cyan day is the one warm accent in the whole look, which is what makes it
# read as a light source rather than a stain.
NIGHT_STOPS = [
    (0.00, (3, 6, 10)),
    (0.10, (10, 14, 20)),
    (0.35, (70, 48, 22)),
    (0.60, (180, 140, 80)),
    (1.00, (255, 214, 150)),
]


def _ramp(lum, stops):
    """Map a luminance array to RGB through a list of (stop, colour)."""
    positions = np.array([stop for stop, __ in stops], dtype=np.float32)
    channels = []
    for index in range(3):
        values = np.array([colour[index] for __, colour in stops],
                          dtype=np.float32)
        channels.append(np.interp(lum, positions, values))
    return np.stack(channels, axis=-1)


def _load_rgb(path):
    """Load an image as an [x][y][rgb] float array in 0..1."""
    surface = pygame.image.load(path)
    return (pygame.surfarray.array3d(surface).astype(np.float32) / 255.0), surface


def _save_rgb(path, pixels):
    """Save an [x][y][rgb] float array in 0..1 as JPEG.

    SDL's JPEG writer takes no quality argument and produced 727KB for the day
    image where Pillow's q=88 produced 212KB at a lower measured error -- so
    Pillow is used when it is installed. It is not a new dependency of the
    game: the committed images are what ships, and the fallback is the writer
    the game already links against, only larger.
    """
    bytes_rgb = (np.clip(pixels, 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8)
    try:
        from PIL import Image
    except ImportError:
        height, width = pixels.shape[1], pixels.shape[0]
        surface = pygame.Surface((width, height))
        pygame.surfarray.blit_array(surface, bytes_rgb)
        pygame.image.save(surface, path)
        return "SDL"

    Image.fromarray(bytes_rgb.transpose(1, 0, 2)).save(
        path, "JPEG", quality=88, optimize=True, progressive=True,
        subsampling=1)
    return "Pillow"


def grade_day(pixels):
    """The day side: one cool ramp, a teal lift on water, and a graticule."""
    lum = pixels @ LUMA
    out = _ramp(lum, DAY_STOPS) / 255.0

    # Water is blue-dominant with almost no red; land and ice are not. Lifting
    # only the water keeps the seas reading as seas after the ramp has flattened
    # everything to one hue family.
    red, __, blue = pixels[:, :, 0], pixels[:, :, 1], pixels[:, :, 2]
    water = np.clip((blue - red * 1.30) / 0.12, 0.0, 1.0)[:, :, np.newaxis]
    # 12%, not 20%: the ocean is what the danger-level markers are drawn on,
    # and lifting it further cost them contrast (1.38 -> 1.20 against a
    # danger_level_0 marker). A hint of teal is enough to read as water.
    out = out * (1.0 - water * 0.12) + water * 0.12 * (
        np.array([0.01, 0.04, 0.06], dtype=np.float32)
        + lum[:, :, np.newaxis] * np.array([0.04, 0.14, 0.18],
                                          dtype=np.float32))

    # A 30-degree graticule: 12 meridians and 6 parallels. At 2048x1024 that is
    # a line every 171px, which survives being scaled to a 1024-wide window as
    # a single pixel. Thinner and it aliases; denser and the globe reads as
    # graph paper.
    height, width = out.shape[1], out.shape[0]
    edge = np.array(UI_EDGE, dtype=np.float32) / 255.0
    for meridian in range(0, 360, 30):
        x = int(meridian / 360.0 * width)
        out[x:x + 2, :, :] = out[x:x + 2, :, :] * 0.90 + edge * 0.10
    for parallel in range(-60, 90, 30):
        y = int((90.0 - parallel) / 180.0 * height)
        out[:, y:y + 2, :] = out[:, y:y + 2, :] * 0.90 + edge * 0.10

    # The equator, brighter: it is the one line a player can orient by.
    y = height // 2
    out[:, y:y + 2, :] = out[:, y:y + 2, :] * 0.82 + edge * 0.18

    return out


def grade_night(pixels):
    """The night side: near-black, with the city lights kept amber."""
    lum = pixels @ LUMA

    # Below the top decile there is nothing but empty ocean and cloud haze;
    # map that to the void so the night side is genuinely dark, and let the
    # lights carry the whole image.
    out = _ramp(lum, NIGHT_STOPS) / 255.0
    return out


def _supersample(size, draw, factor=4, opaque=None):
    """Draw at `factor`x and smoothscale down for antialiased edges.

    With `opaque`, the figure is drawn with alpha and then flattened onto the
    magenta key. The alpha is *thresholded*, not blended: smoothscale() over a
    magenta field would leave magenta-tinted fringe pixels, and set_colorkey()
    only removes the exact colour.
    """
    if opaque is not None:
        big = pygame.Surface((size * factor, size * factor))
        big.fill(opaque)
        draw(big, size * factor)
        return pygame.transform.smoothscale(big, (size, size))

    big = pygame.Surface((size * factor, size * factor), pygame.SRCALPHA)
    draw(big, size * factor)
    small = pygame.transform.smoothscale(big, (size, size))

    alpha = pygame.surfarray.array_alpha(small)
    rgb = pygame.surfarray.array3d(small)
    out = np.empty_like(rgb)
    out[:] = np.array(MAGENTA_KEY, dtype=np.uint8)
    mask = alpha >= 128
    out[mask] = rgb[mask]

    surface = pygame.Surface((size, size))
    pygame.surfarray.blit_array(surface, out)
    return surface


def make_arrow(size=64):
    """An up-pointing chevron: the scrollbar rotates this in 90-degree steps.

    _ArrowButton.reconfig() rotates by 0 for the leading arrow of a vertical
    scrollbar, +90 for the leading arrow of a horizontal one, and -90 / -180
    for the trailing ones. pygame rotates counter-clockwise, so "up" at 0
    degrees becomes left, right and down in the other three slots -- which is
    what each of those buttons needs. Point it any other way and every arrow
    on every scrollbar is inverted.
    """
    def draw(surface, scale):
        def point(fx, fy):
            return (int(fx * scale), int(fy * scale))

        # A filled band, not a thick polyline: pygame.draw.lines() with a wide
        # width mitres the join badly, which turned the apex into a wedge with
        # a thin spur and made the two arms different slopes.
        outline = [point(0.16, 0.60), point(0.50, 0.26), point(0.84, 0.60)]
        inside = [point(0.84, 0.74), point(0.50, 0.40), point(0.16, 0.74)]
        pygame.draw.polygon(surface, UI_EDGE_BRIGHT, outline + inside)

    return _supersample(size, draw)


# The placeholder a picture slot falls back to is **generated like the plates**,
# by `utils/make_dialog_art.py` and under the same style contract. It used to be
# drawn here as analog-TV static, and a hand-drawn placeholder beside 138
# generated plates read as a picture from a different game.
#
# This script no longer writes it. `dialog_placeholder.jpg` is imported from a
# master with the rest, and a `.png` and a `.jpg` on one stem would leave
# `find_files()` picking whichever `os.listdir()` returned last -- so the static
# had to go rather than merely stop being regenerated.
#
# What it is now: an unlit empty interior with one faint band of interference,
# made at the same seed and through the same grade as every other plate, then
# darkened (`PLACEHOLDER_DARKEN` in the dialog-art pipeline) so that it cannot be
# mistaken for content. In numbers: peak luminance 0.478 against the old static's
# 0.716, mean 0.141 against 0.207.


def as_the_game_loads(path):
    """Load an image exactly as g.load_image() does.

    Two conventions, and both have to be read here: a real alpha channel when
    the file carries one (the button glyphs) and the magenta key otherwise
    (the arrow). Reading the arrow with the alpha path would give a magenta
    box, and reading a glyph with the key path would give an opaque block.
    """
    image = pygame.image.load(path)
    if image.get_flags() & pygame.SRCALPHA:
        return image.convert_alpha()
    image = image.convert()
    image.set_colorkey(MAGENTA_KEY + (255,), pygame.RLEACCEL)
    return image.convert_alpha()


def arrow_direction(surface):
    """Which way the chevron points, from its silhouette.

    A chevron is a band, so its ink centroid sits in the middle and says
    nothing. Its *point* is one solid run of ink, while its open end shows the
    two separated tips of the arms -- count runs along the extreme rows and
    columns and the direction follows.
    """
    alpha = pygame.surfarray.array_alpha(surface)
    ink = (alpha > 60).T                      # [y][x]
    rows = np.where(ink.any(axis=1))[0]
    cols = np.where(ink.any(axis=0))[0]
    if not len(rows) or not len(cols):
        return "empty"

    def runs(line):
        count, previous = 0, False
        for value in line:
            if value and not previous:
                count += 1
            previous = value
        return count

    top, bottom = runs(ink[rows[0]]), runs(ink[rows[-1]])
    left, right = runs(ink[:, cols[0]]), runs(ink[:, cols[-1]])

    if top == 1 and bottom == 2:
        return "up"
    if bottom == 1 and top == 2:
        return "down"
    if left == 1 and right == 2:
        return "left"
    if right == 1 and left == 2:
        return "right"
    return "unclear (top=%d bottom=%d left=%d right=%d)" % (top, bottom,
                                                            left, right)


def stats(pixels, classify_by=None):
    """Luminance summary. Water and land are classified on `classify_by`.

    Classifying each image on its own pixels would compare different things:
    the grade changes which pixels are blue-dominant, so the mask has to come
    from the original photograph for a before/after number to mean anything.
    """
    reference = pixels if classify_by is None else classify_by
    lum = pixels @ LUMA
    ref_lum = reference @ LUMA
    red, __, blue = (reference[:, :, 0], reference[:, :, 1],
                     reference[:, :, 2])
    water = (blue > red * 1.30) & (ref_lum < 0.20)
    land = (ref_lum > 0.20) & ~water
    return {
        "mean": float(lum.mean()),
        "p50": float(np.percentile(lum, 50)),
        "p99": float(np.percentile(lum, 99)),
        "water": float(lum[water].mean()) if water.any() else 0.0,
        "land": float(lum[land].mean()) if land.any() else 0.0,
    }


def contrast(a, b):
    """WCAG contrast ratio between two 0..1 luminance values."""
    high, low = max(a, b), min(a, b)
    return (high + 0.05) / (low + 0.05)


def verify_images():
    """Load what was just written the way the game does, and report on it."""
    arrow = as_the_game_loads(os.path.join(TARGET, "arrow.png"))
    total = arrow.get_width() * arrow.get_height()
    opaque = int((pygame.surfarray.array_alpha(arrow) > 60).sum())
    print("arrow  %dx%d  %d of %d pixels opaque, %d transparent via the key"
          % (arrow.get_width(), arrow.get_height(), opaque, total,
             total - opaque))
    for angle, slot in ((0, "leading, vertical"),
                        (90, "leading, horizontal"),
                        (-90, "trailing, horizontal"),
                        (-180, "trailing, vertical")):
        rotated = pygame.transform.rotate(arrow, angle)
        print("       %4d deg %-22s points %s"
              % (angle, slot, arrow_direction(rotated)))


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true",
                        help="measure the result and write nothing")
    args = parser.parse_args()

    pygame.init()
    # convert() needs a display surface, and the dummy driver gives us one
    # headlessly; this is the same path the game takes.
    pygame.display.set_mode((64, 64))

    day_src = os.path.join(SOURCE, "earth.jpg")
    night_src = os.path.join(SOURCE, "earth_night.jpg")

    day, __ = _load_rgb(day_src)
    night, __ = _load_rgb(night_src)

    before = stats(day)
    graded = grade_day(day)
    after = stats(graded, classify_by=day)
    night_graded = grade_night(night)

    print("day   %dx%d  mean luminance %.3f -> %.3f"
          % (day.shape[0], day.shape[1], before["mean"], after["mean"]))
    print("      water %.3f -> %.3f   land %.3f -> %.3f   p99 %.3f -> %.3f"
          % (before["water"], after["water"], before["land"], after["land"],
             before["p99"], after["p99"]))
    print("      land/water contrast %.2f -> %.2f"
          % (contrast(before["land"], before["water"]),
             contrast(after["land"], after["water"])))
    print("night %dx%d  mean luminance %.3f -> %.3f"
          % (night.shape[0], night.shape[1], stats(night)["mean"],
             stats(night_graded)["mean"]))

    # The reason for darkening at all: the map draws danger-coloured markers
    # and light text on top of this.
    marker = (0, 0, 255)
    marker_lum = float(np.array(marker, dtype=np.float32) / 255.0 @ LUMA)
    print("      danger_level_0 marker on water: contrast %.2f -> %.2f"
          % (contrast(marker_lum, before["water"]),
             contrast(marker_lum, after["water"])))

    if args.check:
        print("--check: nothing written")
        return 0

    os.makedirs(TARGET, exist_ok=True)
    day_writer = _save_rgb(os.path.join(TARGET, "earth.jpg"), graded)
    night_writer = _save_rgb(os.path.join(TARGET, "earth_night.jpg"),
                             night_graded)
    pygame.image.save(make_arrow(64), os.path.join(TARGET, "arrow.png"))

    print("JPEG writer: %s" % (day_writer
                               if day_writer == night_writer
                               else "%s/%s" % (day_writer, night_writer)))
    written = ["earth.jpg", "earth_night.jpg", "arrow.png"]
    for name in written:
        path = os.path.join(TARGET, name)
        print("wrote %-16s %7d bytes" % (name, os.path.getsize(path)))

    print()
    verify_images()

    return 0


if __name__ == "__main__":
    sys.exit(main())
