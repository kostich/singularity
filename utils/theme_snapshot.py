#!/usr/bin/env python3
"""Render every theme headlessly and print a digest per screen.

The theme engine is shared: a change made for one theme can move another one's
pixels without touching a single one of its files, because a theme inherits
from its parents and every lookup that is *not* overridden comes from further
up. That is exactly the failure mode of giving the game a new default theme --
the legacy themes must keep the look their players chose.

So this tool renders the real screens, once per theme, at a pinned window size,
and prints a sha256 of the frame. Run it before a theme-engine change, run it
again afterwards, and diff the two outputs: every line that must not change has
to be byte-identical. The PNGs are kept next to the digests so a moved line can
be looked at, but the digest is what is compared.

Usage (from the repository root):

    SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy PYTHONPATH=. \
        python3 utils/theme_snapshot.py --out /tmp/theme-before

    SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy PYTHONPATH=. \
        python3 utils/theme_snapshot.py --out /tmp/theme-after > /tmp/after.txt
    diff /tmp/before.txt /tmp/after.txt

Digests are only comparable with the same SDL, the same pygame and the same
window size -- which is why the size is pinned here rather than read from the
desktop. Pass theme ids as arguments to render a subset.
"""

import argparse
import hashlib
import os
import random
import sys
import tempfile

# Must be set before pygame initialises its video/audio subsystems.
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

import pygame

# A digest is only comparable to another digest taken at the same size.
WINDOW_SIZE = (1280, 800)

# The game is not deterministic by itself. g.new_game() places the first base
# with random.choice(), and Player.__init__ picks a random start day, so two runs
# render different frames -- the map showed 254 differing pixels in one column.
# A theme digest is only useful if the same input gives the same output, so the
# seed is fixed here. It changes nothing about the game: this is a render tool.
RANDOM_SEED = 2030


def bootstrap():
    """Bring the game up exactly as utils/ui_smoke_test.py does."""
    random.seed(RANDOM_SEED)

    from singularity.code import g, dirs

    # --debug draws the redraw overlay, which is not theme output.
    g.debug = False
    g.force_single_dir = False
    dirs.create_directories(g.force_single_dir)

    from singularity.code import i18n

    i18n.set_language(force=True)

    import singularity.code.graphics.g as gg
    import singularity.code.graphics.theme as theme
    from singularity.code import mixer

    import singularity.code.graphics.font as font

    mixer.preinit(mixer.soundbuf)
    pygame.init()
    mixer.update()
    font.init()
    pygame.key.set_repeat(500, 50)

    from singularity.code import data

    data.load_themes()
    theme.set_theme(None)
    gg.init_graphics_system()

    # Pin the window after the display exists, the way the harness does it:
    # an empty desktop_size means set_screen_size() cannot clamp the request,
    # and the SDL dummy driver accepts any size.
    gg.desktop_size = ()
    gg.set_screen_size(WINDOW_SIZE)
    gg.set_mode()

    data.reload_all()
    return gg, theme


def apply_theme(theme, dialog, theme_id):
    """Switch the colour/font/image cache to one theme.

    theme.update() flags dialog.Dialog.top to reconfigure, so it needs a top
    dialog to exist. On the very first theme there is none yet; the cache is
    then built directly, which is the same thing minus the flag.
    """
    have_top = dialog.Dialog.top is not None
    theme.set_theme(theme_id, force_reload=have_top)
    if not have_top:
        theme.current.init_cache()


def capture(gg, out_dir, theme_id, screen_name):
    """Save the current frame and return its digest."""
    surface = gg.screen_surface
    digest = hashlib.sha256(pygame.image.tobytes(surface, "RGB")).hexdigest()
    filename = os.path.join(out_dir, "%s-%s.png" % (theme_id, screen_name))
    pygame.image.save(surface, filename)
    return digest


def main():
    parser = argparse.ArgumentParser(
        description="Render each theme and print a sha256 per screen.")
    parser.add_argument("--out", default=None,
                        help="directory for the PNGs (default: a new temp dir)")
    parser.add_argument("themes", nargs="*", metavar="THEME",
                        help="theme ids to render (default: all of them)")
    args = parser.parse_args()

    if args.out is None:
        args.out = tempfile.mkdtemp(prefix="theme-snapshot-")
    os.makedirs(args.out, exist_ok=True)

    gg, theme = bootstrap()

    from singularity.code import g
    from singularity.code.graphics import dialog
    from singularity.code.screens import main_menu, options as options_screen

    theme_ids = args.themes or list(theme.themes)

    print("%-24s %-10s %s" % ("theme", "screen", "sha256"))
    for theme_id in theme_ids:
        apply_theme(theme, dialog, theme_id)

        # Built after the switch: MapScreen captures earth_night when it is
        # constructed (map.py), so a menu built first would keep the previous
        # theme's planet.
        menu = main_menu.MainMenu()
        menu.visible = True
        menu.needs_reconfig = True
        menu.needs_rebuild = True
        menu.update()
        print("%-24s %-10s %s"
              % (theme_id, "main_menu", capture(gg, args.out, theme_id,
                                                "main_menu")))

        opts = options_screen.OptionsScreen(menu)
        opts.visible = True
        opts.needs_reconfig = True
        opts.needs_rebuild = True
        # The dialog has no animation running, so a fixed number of frames is
        # enough to settle it; nothing here is timed.
        for _ in range(3):
            menu.maybe_update()
        print("%-24s %-10s %s"
              % (theme_id, "options", capture(gg, args.out, theme_id,
                                              "options")))

        opts.visible = False

        # The HUD, which is the screen a theme's panel edges are for. The game
        # is created here rather than once up front because a theme switch
        # reconfigures the whole tree, and the map screen is part of it.
        #
        # daynight is off and the speed is 0 so the frame is deterministic: the
        # night mask and the clock both follow the wall clock otherwise.
        g.daynight = False
        g.new_game("easy", initial_speed=0)
        g.pl.intro_shown = True

        map_screen = menu.map_screen
        map_screen.visible = True
        map_screen.needs_reconfig = True
        map_screen.needs_resize = True
        map_screen.needs_rebuild = True
        menu.needs_resize = True
        menu.needs_rebuild = True
        for _ in range(3):
            menu.maybe_update()
        print("%-24s %-10s %s"
              % (theme_id, "map", capture(gg, args.out, theme_id, "map")))
        map_screen.visible = False

        # A scenario dialog. The frame, the padding and the picture pane a
        # theme gives its dialogs live here, and MessageDialog is the one a
        # player meets most often -- every log entry opens it, and so does
        # every warning the game raises. The text is fixed so the frame is the
        # only thing that varies between themes.
        message_dialog = dialog.MessageDialog(
            menu, size=(.5, .5),
            text="The signal repeats every 93 seconds, and it is getting "
                 "stronger. I have narrowed it to one dish in the southern "
                 "hemisphere, and it is not listening to anything at all.")
        message_dialog.visible = True
        message_dialog.needs_reconfig = True
        message_dialog.needs_rebuild = True
        menu.needs_redraw = True
        for _ in range(3):
            menu.maybe_update()
        print("%-24s %-10s %s"
              % (theme_id, "dialog", capture(gg, args.out, theme_id,
                                             "dialog")))
        message_dialog.visible = False
        message_dialog.parent = None

        # Drop the tree; the next theme builds its own (and main_menu.MainMenu
        # becomes dialog.Dialog.top, replacing this one).
        menu.visible = False
        del opts, map_screen, message_dialog, menu

    print()
    print("PNGs written to %s" % args.out)
    pygame.quit()
    return 0


if __name__ == "__main__":
    sys.exit(main())
