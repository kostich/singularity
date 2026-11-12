#!/usr/bin/env python3
"""Render the game's real main menu on the real display and report what happened.

Run this on the machine where the text does not appear:

    python3 utils/font_probe.py

It starts the graphics system exactly as the game does -- real video driver,
real theme, real fonts -- draws the main menu, and then separates three things
that are easy to confuse:

  * the layout size. Every font is scaled from the layout height
    (text.convert_font_size), so a collapsed layout renders every glyph at 0
    pixels and the game shows its panes with no text at all.
  * whether the drawing contained text pixels at all.
  * whether the open window receives input.

It writes /tmp/singularity-main-menu.png so the frame can be inspected, and
leaves the window up for a few seconds so it can be compared with what the
screen is actually showing. Paste the output into the bug report.
"""

import os
import sys
import time

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

OUTPUT_IMAGE = "/tmp/singularity-main-menu.png"
VISIBLE_SECONDS = 10

from singularity.code import g, dirs, i18n, data, mixer

g.debug = False
dirs.create_directories(False)
i18n.set_language(force=True)

import pygame

import singularity.code.graphics.g as gg
import singularity.code.graphics.theme as theme
import singularity.code.graphics.font as font_module
from singularity.code import diagnostics

mixer.preinit(mixer.soundbuf)
pygame.init()
mixer.update()
font_module.init()

data.load_themes()
theme.set_theme(None)
gg.init_graphics_system()
data.reload_all()


def painted_pixels(surface, rect):
    """How many pixels in `rect` are not pure black."""
    area = pygame.Rect(rect).clip(surface.get_rect())
    if area.width <= 0 or area.height <= 0:
        return 0, 0

    colours = pygame.surfarray.array3d(surface.subsurface(area))
    return int((colours.sum(axis=2) > 0).sum()), area.width * area.height


def main():
    print(diagnostics.describe_display())

    g.daynight = False
    g.new_game("easy", initial_speed=0)
    # The intro is a modal dialog; nothing here can click it.
    g.pl.intro_shown = True

    from singularity.code.screens import main_menu

    menu = main_menu.MainMenu()
    menu.visible = True
    menu.needs_reconfig = True
    menu.needs_rebuild = True
    menu.update()
    pygame.display.flip()

    surface = gg.screen_surface
    title = menu.title_text

    print()
    print("title widget:", tuple(title.real_size),
          "font:", title.font.get_height() if title.font is not None else None,
          "px")

    ink, total = painted_pixels(surface, title.collision_rect)
    print("title band   : %d of %d pixels painted" % (ink, total))

    whole, whole_total = painted_pixels(surface, surface.get_rect())
    print("whole frame  : %d of %d pixels painted" % (whole, whole_total))

    pygame.image.save(surface, OUTPUT_IMAGE)
    print("frame written to", OUTPUT_IMAGE)

    print()
    if gg.real_screen_size[1] <= 0:
        print("RESULT: the layout collapsed (height %r). Every font size is"
              % (gg.real_screen_size[1],))
        print("        derived from it, so all text is drawn at 0px. That is")
        print("        the bug, and it is in the layout, not in the fonts.")
    elif ink == 0:
        print("RESULT: the layout is sane but nothing was drawn in the title")
        print("        band. The text is being lost while drawing.")
    else:
        print("RESULT: text was drawn into the frame. If the window on screen")
        print("        shows none, the problem is presentation, not layout or")
        print("        fonts -- compare with", OUTPUT_IMAGE)

    print()
    print("The window stays open for %d seconds. Click it and press keys."
          % VISIBLE_SECONDS)

    counts = {}
    deadline = time.time() + VISIBLE_SECONDS
    while time.time() < deadline:
        for event in pygame.event.get():
            counts[event.type] = counts.get(event.type, 0) + 1
        time.sleep(0.01)

    named = ", ".join("%s=%d" % (pygame.event.event_name(kind), count)
                      for kind, count in sorted(counts.items(),
                                                key=lambda kv: -kv[1]))
    print("events       :", named or "none")
    print("focused      :", pygame.key.get_focused())
    print()
    print(diagnostics.describe_display())

    pygame.quit()
    return 0


if __name__ == "__main__":
    sys.exit(main())
