#!/usr/bin/env python3
"""Rasterise the 2030 theme's button glyphs from Lucide.

The theme used to draw fifteen glyphs from primitives in
`utils/make_2030_art.py`: strokes and polygons assembled by hand. They were
consistent with each other and readable at 24px, and they were also fifteen
small inventions standing in for a solved problem. This vendors a real set
instead.

**The set.** Lucide, pinned to tag `0.469.0`, licensed ISC -- see `LICENSE`
beside the SVG sources. ISC is what made it the choice: it is permissive enough
to sit in a GPL-2+ work with a notice, which rules out several better-known
packs by licence alone (Papirus and Breeze are GPL-3 and LGPL-3 respectively,
and this game is GPL-2+).

**What ships.** The SVG sources are vendored under
`singularity/data/themes/2030/icons/` so the artwork in the repository is
reproducible without a network, and this script turns them into the PNGs the
game actually loads:

    singularity/data/themes/2030/images/icon_<name>.png     64x64, RGBA

Rasterising needs ImageMagick (`magick`), which is a build-time dependency only:
the committed PNGs are what the game reads. Nothing here runs at startup.

    python3 utils/make_icon_set.py            # rewrite the glyphs
    python3 utils/make_icon_set.py --check    # measure, write nothing
"""

import argparse
import hashlib
import os
import re
import subprocess
import sys

import numpy as np
import pygame

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
THEME = os.path.join(REPO_ROOT, "singularity", "data", "themes", "2030")
SOURCES = os.path.join(THEME, "icons")
TARGET = os.path.join(THEME, "images")

# The stroke colour the theme draws a glyph in, from theme.dat: `ui_edge_bright`.
GLYPH_COLOUR = (95, 227, 255)

# The size a button asks for. Buttons scale a glyph to 60% of their own height,
# and the largest a button gets is about 100px, so 64 is generous and 32 would
# start to alias on the diagonal strokes.
GLYPH_SIZE = 64

# Rasterise well above the shipped size and let pygame bring it down: ImageMagick
# antialiases at 256, and that is what keeps a 2px hairloom from breaking up.
SUPERSAMPLE = 256

# The game's icon name -> the Lucide drawing it is made from. Keeping the name
# on the left is what makes this a drop-in: every button already asks for
# `icon_ok`, `icon_save` and so on, so replacing the artwork changes no call
# site.
ICONS = {
    "ok": "check",
    "cancel": "x",
    "back": "chevron-left",
    "forward": "chevron-right",
    "prev": "skip-back",
    "next": "skip-forward",
    "play": "play",
    "pause": "pause",
    "load": "folder-open",
    "save": "save",
    "delete": "trash-2",
    "stats": "chart-column",
    "filter": "filter",
    "warning": "triangle-alert",
    "options": "sliders-horizontal",
    "exit": "log-out",
    "research": "flask-conical",
    "knowledge": "book-open",
    "report": "file-text",
    "log": "scroll-text",
}

# Which Lucide release the vendored SVGs came from, so the sources can be
# refreshed deliberately rather than drifting.
LUCIDE_TAG = "0.469.0"


def source_path(drawing):
    return os.path.join(SOURCES, drawing + ".svg")


def target_path(name):
    return os.path.join(TARGET, "icon_%s.png" % (name,))


def rasterise(drawing, colour=GLYPH_COLOUR):
    """Render one vendored SVG to a square RGBA surface at SUPERSAMPLE size.

    Lucide draws with `stroke="currentColor"`, which has no meaning outside a
    web page: the colour is substituted here, at the source, so the
    antialiasing ImageMagick produces is already the right colour rather than
    white edges tinted afterwards.
    """
    with open(source_path(drawing), "r", encoding="utf-8") as handle:
        svg = handle.read()

    svg = svg.replace("currentColor", "#%02X%02X%02X" % colour)
    svg = re.sub(r'width="24"', 'width="%d"' % SUPERSAMPLE, svg, count=1)
    svg = re.sub(r'height="24"', 'height="%d"' % SUPERSAMPLE, svg, count=1)

    import tempfile

    with tempfile.TemporaryDirectory() as directory:
        svg_path = os.path.join(directory, "glyph.svg")
        png_path = os.path.join(directory, "glyph.png")
        with open(svg_path, "w", encoding="utf-8") as handle:
            handle.write(svg)
        subprocess.run(["magick", "-background", "none", svg_path,
                        "-resize", "%dx%d" % (SUPERSAMPLE, SUPERSAMPLE),
                        png_path], check=True)
        return pygame.image.load(png_path).convert_alpha()


def make_glyph(surface, size=GLYPH_SIZE):
    """Bring one rasterised drawing down to the size a button asks for.

    The alpha is scaled and the colour laid on flat, the rule
    `make_2030_art._glyph_surface` used: scaling a colour image averages RGB as
    well as alpha, and every edge picks up whatever the transparent pixels
    happened to contain. Scaling one channel cannot.
    """
    small = pygame.transform.smoothscale(surface, (size, size))
    out = pygame.Surface((size, size), pygame.SRCALPHA)
    out.fill(GLYPH_COLOUR + (255,))
    pygame.surfarray.pixels_alpha(out)[:] = pygame.surfarray.array_alpha(small)
    return out


def ink_count(surface):
    return int((pygame.surfarray.array_alpha(surface) > 60).sum())


def digest(surface):
    return hashlib.sha256(pygame.image.tobytes(surface, "RGBA")).hexdigest()


def build(verbose=True):
    """Write every glyph, and return the surfaces so they can be checked."""
    if not os.path.isdir(SOURCES):
        raise SystemExit("no icons directory at %s" % (SOURCES,))

    built = {}
    for name, drawing in sorted(ICONS.items()):
        if not os.path.exists(source_path(drawing)):
            raise SystemExit("missing source for %s: %s"
                             % (name, source_path(drawing)))
        glyph = make_glyph(rasterise(drawing))
        pygame.image.save(glyph, target_path(name))
        built[name] = glyph
        if verbose:
            print("wrote %-22s %3d bytes  ink %4d/%d"
                  % (os.path.basename(target_path(name)),
                     os.path.getsize(target_path(name)),
                     ink_count(glyph), GLYPH_SIZE * GLYPH_SIZE))
    return built


def verify(built):
    """The properties that make a glyph usable, measured rather than asserted:

    it has ink, it is not a block, it is the size a button expects, and no two
    glyphs are the same drawing -- a copy-paste in the table is the mistake that
    would otherwise ship silently.
    """
    print("%-14s %-6s %-8s %s" % ("icon", "size", "ink", "digest"))
    seen = {}
    for name, glyph in sorted(built.items()):
        ink = ink_count(glyph)
        mark = digest(glyph)
        print("icon_%-9s %-6s %-8d %s"
              % (name, "%dx%d" % glyph.get_size(), ink, mark[:16]))
        assert glyph.get_size() == (GLYPH_SIZE, GLYPH_SIZE), glyph.get_size()
        assert ink > 40, "%s is nearly empty" % (name,)
        assert ink < GLYPH_SIZE * GLYPH_SIZE * 0.60, \
            "%s is a block, not a glyph" % (name,)
        assert mark not in seen, "%s is a copy of %s" % (name, seen.get(mark))
        seen[mark] = name
    print("%d glyphs, all %dx%d, all distinct"
          % (len(built), GLYPH_SIZE, GLYPH_SIZE))


def check():
    """Measure the shipped files, writing nothing."""
    surfaces = {}
    for name in sorted(ICONS):
        path = target_path(name)
        if not os.path.exists(path):
            raise SystemExit("missing %s -- run without --check" % (path,))
        surface = pygame.image.load(path).convert_alpha()
        if surface.get_size() != (GLYPH_SIZE, GLYPH_SIZE):
            raise SystemExit("%s is %r, not %dx%d"
                             % (path, surface.get_size(),
                                GLYPH_SIZE, GLYPH_SIZE))
        surfaces[name] = surface
    verify(surfaces)
    print("--check: nothing written")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Rasterise the vendored Lucide glyphs into the theme.")
    parser.add_argument("--check", action="store_true",
                        help="measure the shipped files and write nothing")
    args = parser.parse_args(argv)

    pygame.init()
    pygame.display.set_mode((1, 1))

    if args.check:
        return check()
    verify(build())
    return 0


if __name__ == "__main__":
    sys.exit(main())
