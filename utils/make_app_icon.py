#!/usr/bin/env python3
"""Render the fork's application icon at every size it ships in.

The icon is the original Singularity mark: two red wedges converging downward
from the top corners, with a bright red eye at each inner tip, on a
transparent-background plate with rounded corners. The fork adds "2030" in red
below the eyes.

Why the plate, and why it is nearly black
-----------------------------------------
The original art is #800000 on pure black: 1.92:1, under the 3.0:1 WCAG floor
for a graphical object, and against a dark dock (#1E1E1E) it is 1.52:1, against
#2D2D2D 1.26:1 -- an opaque black square with wedges barely darker than the
dock it sits on, so the icon reads as a black hole in the launcher. Three things
fix it:

  * the background is **transparent** outside a rounded plate, so the icon is a
    shape rather than a square and the launcher's own background shows through
    the corners;
  * the plate is the 2030 theme's `ui_void`, #04080F: on a dark dock it is the
    dock's own near-black, so it disappears and the mark appears to float, while
    on a light desktop it reads as a dark rounded square;
  * the wedges are brightened to #D00000, 3.52:1 on the plate -- above the 3.0
    floor with headroom, and still clearly darker than the #FF0000 eyes and
    label (5.02:1), so the "dim body, bright eye" relationship survives.

Smoothscale has almost nothing to fringe with here: the transparent margin is
(0, 0, 0, 0) and the plate is (4, 8, 15), so the colour difference across the
alpha edge is a few units of blue.

Why redraw it rather than stamp text onto the shipped PNG
---------------------------------------------------------
The tree only ever contained a **32x32** original; `flatpak/icons/128.png` and
`256.png` are smooth upscales of it. Adding text at 32 and upscaling would give
an unreadable smudge at every larger size, and upscaling the mark itself at 512
gives a blurry app icon. So the mark is rebuilt from measured geometry and
rendered natively at each size:

  * the original art has only two colours, `#800000` and `#FF0000`; the 32, 64,
    96 and 191/192 values in it are antialiasing between black, `#800000` and
    `#FF0000`, not design elements. The fork keeps the eye at `#FF0000` and
    brightens the stroke to `#D00000` for legibility, so the colours no longer
    correspond -- see the fidelity check below.
  * the polygons below were fitted to the original 32x32 by grid search on
    pixel overlap: ink IoU 0.889, bright IoU 0.818. The remaining difference is
    a one-pixel staircase along the diagonals -- the original's diagonals are
    a 2-row staircase because the 32x32 is itself a 2x upscale of a 16x16
    mark. Copying that staircase would look like a defect at 256, so the edges
    are clean lines here. `--check` re-measures this every run, as *shape* (the
    rebuilt footprint against the original's ink) and *eyes* (brightest pixels
    against brightest pixels), because the colours deliberately differ.
  * the whole thing is drawn at 8x and smoothscaled down, because pygame.draw
    has no antialiasing.

The "2030" is set in DejaVu Sans Mono Bold -- the 2030 theme's `special` face,
the one the main menu's title is drawn in, so the icon and the game agree. Its
height is fixed as a fraction of the icon so the composition is identical at
every size.

The eyes are narrower than the original's: a slim angled slit in place of the
wide block, sitting on the same spot and in the same red. It keeps the mark
recognisable -- two red points at the inner tips of the wedges -- while making
the fork's icon its own thing rather than a copy with a label under it.

Usage:

    python3 utils/make_app_icon.py            # write the images
    python3 utils/make_app_icon.py --check    # measure only, write nothing

Writes `flatpak/icons/<size>.png` for every size in SIZES, and
`singularity/data/themes/2030/images/icon.png`. The legacy themes keep their
own copies, which this tool never touches.
"""

import argparse
import os
import sys

import numpy as np
import pygame

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
THEMES = os.path.join(REPO_ROOT, "singularity", "data", "themes")
FLATPAK_ICONS = os.path.join(REPO_ROOT, "flatpak", "icons")
THEME_ICON = os.path.join(THEMES, "2030", "images", "icon.png")
# The 2030 theme's `special` face (theme.dat), which is what the main menu's
# title uses. It used to be Exo 2 Bold; the theme moved to a monospace console
# after this tool was written, and the icon now follows it.
THEME_FONT = os.path.join(THEMES, "2030", "fonts", "DejaVuSansMono-Bold.ttf")
ORIGINAL = os.path.join(THEMES, "Legacy-default", "images", "icon.png")

# Every size the hicolor theme conventionally carries. The manifest installs
# exactly these; tests/test_app_icon.py checks that the two agree.
SIZES = (16, 24, 32, 48, 64, 128, 256, 512)

# The theme icon itself: one file, used for the window/taskbar icon.
THEME_ICON_SIZE = 128

SUPERSAMPLE = 8

# The plate the mark sits on: the 2030 theme's `ui_void`, a near-black blue.
PLATE = (4, 8, 15)              # #04080F
PLATE_RADIUS = 0.22             # corner radius, as a fraction of the icon edge

STROKE_COLOR = (208, 0, 0)      # #D00000: 3.52:1 on the plate; #800000 is 1.83
EYE_COLOR = (255, 0, 0)         # #FF0000, the theme's red
TEXT_COLOR = (255, 0, 0)

# WCAG wants 3.0:1 for a graphical object and 4.5:1 for text.
GRAPHICS_FLOOR = 3.0
LABEL_FLOOR = 4.5

# What the icon actually sits on in a launcher.
DESKTOP_LIGHT = (255, 255, 255)
DESKTOP_DARK = (30, 30, 30)     # #1E1E1E, a common dark dock

# Geometry in the original's 32-pixel space, measured from
# Legacy-default/images/icon.png (see the module docstring). The mark is
# symmetric about x = 16, so only the left half is written out and mirrored.
UNIT = 32.0

STROKE = [(6, 8.25), (7.75, 8.25), (13.25, 14.25), (15, 14.25),
          (15, 16.5), (8, 16.5), (8, 14.5), (6, 14.5)]

# The eye is a slanted blade lying along the wedge that carries it, not the
# original's upright 3.75 x 2.6 block. Same centre, same red, the same inner
# tip; the ink is a thin band about 1.9 units thick, tilted 25 degrees down
# toward the mark's axis. It still reads at 24px as a bright point at the tip,
# which is all the eye has to do at that size.
EYE = [(9.0, 14.43), (9.81, 12.71), (13.79, 14.57), (12.99, 16.29)]

TEXT = "2030"

# Composition, as fractions of the icon. The eyes sit where they sit in the
# original (y 0.258..0.516); the label fills the empty lower half.
TEXT_CAP_HEIGHT = 0.21
TEXT_CENTRE_Y = 0.73
TEXT_MAX_WIDTH = 0.80


def _mirror(points):
    """Reflect a polygon about the mark's axis of symmetry."""
    return [(UNIT - x, y) for x, y in points]


def _draw_mark(surface, scale):
    """Draw the eyes at `scale` pixels per unit of the 32-space."""
    for points in (STROKE, _mirror(STROKE)):
        pygame.draw.polygon(surface, STROKE_COLOR,
                            [(x * scale, y * scale) for x, y in points])
    for points in (EYE, _mirror(EYE)):
        pygame.draw.polygon(surface, EYE_COLOR,
                            [(x * scale, y * scale) for x, y in points])


def _text_metrics(font_path, probe=200):
    """Measure "2030" once: ink height and width per point of font size.

    Digits have no descenders, so the ink box of "2030" is its cap height,
    which is what the composition is expressed in.
    """
    font = pygame.font.Font(font_path, probe)
    box = font.render(TEXT, True, (255, 255, 255)).get_bounding_rect()
    return box.height / float(probe), box.width / float(probe)


def _draw_text(surface, size, metrics):
    """Centre the label in the lower part of an icon `size` pixels square."""
    height_ratio, width_ratio = metrics
    canvas = size                      # supersampled canvas dimension

    # Two constraints: the cap height the composition asks for, and the widest
    # the label may be. Whichever binds first wins -- at small sizes the width
    # binds, which keeps the digits inside the icon instead of over the edges.
    by_height = TEXT_CAP_HEIGHT * canvas / height_ratio
    by_width = TEXT_MAX_WIDTH * canvas / width_ratio
    px = max(1, int(min(by_height, by_width)))

    font = pygame.font.Font(THEME_FONT, px)
    rendered = font.render(TEXT, True, TEXT_COLOR)
    ink = rendered.get_bounding_rect()
    if ink.width < 1 or ink.height < 1:
        return px, 0, 0

    x = (surface.get_width() - ink.width) // 2
    y = int(round(TEXT_CENTRE_Y * surface.get_height() - ink.height / 2.0))
    surface.blit(rendered, (x, y), ink)
    return px, ink.width, ink.height


def render(size, labelled=True, metrics=None, plate=True):
    """Return the icon at `size` pixels square, transparent outside the plate.

    `plate=False` draws the mark alone on a transparent field, which is what
    the fidelity check needs: the original has no plate.
    """
    canvas = size * SUPERSAMPLE
    surface = pygame.Surface((canvas, canvas), pygame.SRCALPHA)
    surface.fill((0, 0, 0, 0))

    if plate:
        bounds = pygame.Rect(0, 0, canvas, canvas)
        pygame.draw.rect(surface, PLATE, bounds,
                         border_radius=int(round(PLATE_RADIUS * canvas)))

    _draw_mark(surface, canvas / UNIT)

    if labelled:
        if metrics is None:
            metrics = _text_metrics(THEME_FONT)
        _draw_text(surface, canvas, metrics)

    return pygame.transform.smoothscale(surface, (size, size))


def _iou(one, other):
    """Intersection over union of two boolean masks."""
    union = int((one | other).sum())
    return int((one & other).sum()) / float(union) if union else 0.0


def fidelity():
    """How close the rebuilt mark is to the original 32x32.

    The colours deliberately differ -- the stroke is brightened and there is a
    plate instead of black -- so this compares what must not move: the *shape*
    of the mark (its footprint against the original's ink) and the *eyes* (the
    rebuilt's brightest pixels against the original's). The rebuilt mark is
    rendered without the plate so its footprint is exactly the mark.
    """
    original = pygame.image.load(ORIGINAL).convert()
    rebuilt = render(32, labelled=False, plate=False)

    rebuilt_alpha = pygame.surfarray.array_alpha(rebuilt)
    rebuilt_red = pygame.surfarray.array3d(rebuilt)[:, :, 0]
    original_red = pygame.surfarray.array3d(original)[:, :, 0].astype(np.int16)

    shape = _iou(rebuilt_alpha > 8, original_red > 8)
    eyes = _iou((rebuilt_alpha > 8) & (rebuilt_red >= 250), original_red >= 190)
    return shape, eyes


def _srgb_channel(value):
    """One 0..255 sRGB channel, linearised."""
    value = value / 255.0
    if value <= 0.04045:
        return value / 12.92
    return ((value + 0.055) / 1.055) ** 2.4


def luminance(color):
    """WCAG relative luminance of an sRGB colour, 0.0 (black) .. 1.0 (white)."""
    red, green, blue = (_srgb_channel(channel) for channel in color[:3])
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def contrast(one, other):
    """WCAG contrast ratio between two sRGB colours, 1.0 .. 21.0."""
    first, second = luminance(one), luminance(other)
    lighter, darker = max(first, second), min(first, second)
    return (lighter + 0.05) / (darker + 0.05)


def _hex(color):
    return "#%02X%02X%02X" % tuple(color[:3])


def legibility():
    """Print what a launcher will actually see, with the WCAG ratios."""
    print()
    print("legibility (WCAG contrast ratio, sRGB):")
    print("%-8s %-8s %-8s %7s %6s  %s"
          % ("element", "ink", "on", "ratio", "floor", "verdict"))
    rows = (("wedges", STROKE_COLOR, GRAPHICS_FLOOR),
            ("eyes", EYE_COLOR, GRAPHICS_FLOOR),
            ("label", TEXT_COLOR, LABEL_FLOOR))
    for name, ink, floor in rows:
        ratio = contrast(ink, PLATE)
        print("%-8s %-8s %-8s %6.2f:1 %5.1f  %s"
              % (name, _hex(ink), _hex(PLATE), ratio, floor,
                 "ok" if ratio >= floor else "BELOW"))

    print("%-8s %-8s %-8s %6.2f:1 %5s  %s"
          % ("plate", _hex(PLATE), _hex(DESKTOP_LIGHT),
             contrast(PLATE, DESKTOP_LIGHT), "-",
             "on a light desktop: a dark rounded square, so the icon reads"))
    print("%-8s %-8s %-8s %6.2f:1 %5s  %s"
          % ("plate", _hex(PLATE), _hex(DESKTOP_DARK),
             contrast(PLATE, DESKTOP_DARK), "-",
             "on a dark dock: the plate disappears, so the mark floats"))


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true",
                        help="measure only, write nothing")
    args = parser.parse_args()

    pygame.init()
    pygame.display.set_mode((8, 8))

    metrics = _text_metrics(THEME_FONT)
    shape, eyes = fidelity()
    print("rebuilt mark vs the original 32x32: shape IoU %.3f, eyes IoU %.3f"
          % (shape, eyes))
    print("label metrics: cap height %.3f of the icon, width %.3f"
          % (TEXT_CAP_HEIGHT, metrics[1] * TEXT_CAP_HEIGHT / metrics[0]))

    if args.check:
        legibility()
        print()
        print("%-6s %-10s %-10s %s" % ("size", "cap height", "label width",
                                       "note"))
        for size in SIZES:
            pixels = size * SUPERSAMPLE
            height_ratio, width_ratio = metrics
            px = max(1, int(min(TEXT_CAP_HEIGHT * pixels / height_ratio,
                                TEXT_MAX_WIDTH * pixels / width_ratio)))
            cap = px * height_ratio / SUPERSAMPLE
            print("%-6d %-10s %-10s %s"
                  % (size,
                     "%.1fpx" % cap,
                     "%.1fpx" % (px * width_ratio / SUPERSAMPLE),
                     "legible" if cap >= 5 else "a red mark, not letters"))
        print("--check: nothing written")
        return 0

    os.makedirs(FLATPAK_ICONS, exist_ok=True)
    for size in SIZES:
        path = os.path.join(FLATPAK_ICONS, "%d.png" % size)
        pygame.image.save(render(size, metrics=metrics), path)
        print("wrote %-34s %6d bytes" % (os.path.relpath(path, REPO_ROOT),
                                         os.path.getsize(path)))

    os.makedirs(os.path.dirname(THEME_ICON), exist_ok=True)
    pygame.image.save(render(THEME_ICON_SIZE, metrics=metrics), THEME_ICON)
    print("wrote %-34s %6d bytes" % (os.path.relpath(THEME_ICON, REPO_ROOT),
                                     os.path.getsize(THEME_ICON)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
