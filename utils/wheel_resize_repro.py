#!/usr/bin/env python3
"""Replay the reported resolution change that ends the game, headless.

The report: windowed, pick 1152x864, then 1024x768 -- both fine -- then
1024x600, and the process dies with

    Fatal Python error: Segmentation fault
      File "singularity/code/graphics/text.py", line 423 in print_text
      ...

The C frame under it is PyMem_Calloc() called from PyList_New(), i.e. the
allocator itself faulted while a three-element list was being built. That only
happens to a heap somebody else has already corrupted, so what this script is
for is making that sequence run on demand so it can be run under valgrind
(which names the writer) instead of being reproduced by hand.

    SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy PYTHONPATH=. \
        python3 utils/wheel_resize_repro.py

Three flags, combinable:

  --walk      (default) the three resolutions from the report, in order, with
              the options dialog open over a bare tree
  --game      put a real game behind the dialog: map screen, day/night on, the
              night mask being recomputed on ticks. This is the state the
              player was actually in.
  --wheel     after each step, spin the scroll wheel over the resolution list,
              which is the reported "the list keeps scrolling over and over"
              with a free-spinning mouse. A wheel flick must leave the
              resolution alone: the wheel scrolls the view, not the selection.

Note on what this does and does not prove. This script never reproduced the
segfault, and it cannot: it makes the options dialog the root of the tree, while
the game shows it as a child of the main menu, and it runs on the dummy driver,
which never reallocates a window behind the game's back. The crash was not in
the resize logic at all. What a notch did is still measurable -- a notch used to
be a real window resize and a flick was dozens of them -- and the window size is
printed after every step so that claim can be checked instead of believed.

The segfault was real, and what finds it is the real video driver plus a real
event loop, because converting an SDL event is what writes into the damaged
block: pygame's dict_from_event() increfs the pointer kept in the SDL window's
user data for every event's "window" attribute. Neither the unit tests nor
ui_smoke_test.py call pygame.event.wait(), which is why none of them saw it. The
writer was g._sdl2_window() building a throwaway pygame._sdl2.video.Window
wrapper on every call; see the note in singularity/code/graphics/g.py.

Exit status is 0 only if the whole sequence completes.

For a corruption hunt, the run has to use the real driver and a real event loop,
and PYTHONMALLOC=malloc is required, because pymalloc hides individual
allocations from memcheck:

    PYTHONMALLOC=malloc SDL_VIDEODRIVER=wayland PYTHONPATH=. \
    valgrind --error-limit=no --num-callers=30 \
        python3 -X faulthandler <a script that drives Dialog.show()>

Against the game before the fix that reports an invalid write inside
Py_INCREF, called from dict_from_event() -- i.e. into an already-freed block,
on every event that carries a window id.
"""

import os
import sys

# Must be set before pygame initialises its video/audio subsystems.
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

import pygame

from singularity.code import g, data, dirs, i18n, mixer

g.no_gui()
dirs.create_directories(False)
i18n.set_language(force=True)

import singularity.code.graphics.font as font_module
import singularity.code.graphics.theme as theme
import singularity.code.graphics.g as gg
from singularity.code.graphics import dialog

mixer.preinit(mixer.soundbuf)
pygame.init()
font_module.init()

data.load_themes()
theme.set_theme(None)
gg.init_graphics_system()
data.reload_all()

g.daynight = False
g.new_game("easy", initial_speed=0)
g.pl.intro_shown = True

from singularity.code.screens import options as options_module


# The three from the report, in the order it went through them.
WALK = [(1152, 864), (1024, 768), (1024, 600)]


def cached_font_sizes():
    return sum(len(face._font_cache) for face in gg.fonts.values())


def report(label):
    print("  %-18s window=%-12r layout=%-12r origin=%-8r fonts=%d"
          % (label, tuple(gg.window_size), tuple(gg.real_screen_size),
             tuple(gg.layout_origin), cached_font_sizes()))


def spin_wheel(pane, notches, x=None, y=None):
    """Feed the resolution list MOUSEWHEEL events, as a free-spinning mouse does.

    A high-resolution wheel delivers a burst of these per flick, so the point
    is the burst: each event is dispatched the way dialog.Dialog.handle() does
    it, through the registered handlers.
    """
    listbox = pane.resolution_choice
    if x is None:
        x, y = listbox.collision_rect.center
    pygame.mouse.set_pos((x, y))

    for index in range(notches):
        event = pygame.event.Event(pygame.MOUSEWHEEL,
                                   {"x": 0, "y": -1, "flipped": False,
                                    "precise_x": 0.0, "precise_y": -1.0,
                                    "which": 0, "touch": False})
        dialog.Dialog.top.handle(event)


def run_ticks(count, map_screen=None):
    """Deliver timer ticks, the way the game's USEREVENT does.

    EarthImage.on_tick() advances one step of the *next* night mask per tick,
    and get_night_mask() walks the remaining steps on demand. Those steps take
    pygame.surfarray.pixels_alpha() views of a surface and write through them,
    which is the most likely place for a stale pixel buffer to appear.
    """
    for _ in range(count):
        dialog.Dialog.top.handle(pygame.event.Event(pygame.USEREVENT))
        if map_screen is not None:
            map_screen.map.on_tick(pygame.event.Event(pygame.USEREVENT))
        dialog.Dialog.top.maybe_update()
        pygame.display.flip()


def build_game(menu):
    """The map screen the player was looking at, day/night on."""
    from singularity.code.screens import map as mapscreen

    g.new_game("easy", initial_speed=0)
    g.pl.intro_shown = True

    map_screen = mapscreen.MapScreen(parent=menu)
    g.map_screen = map_screen

    g.daynight = True
    map_screen.visible = True
    map_screen.needs_reconfig = True
    map_screen.needs_rebuild = True
    map_screen.map.reset_night_mask_computation()
    dialog.Dialog.top.maybe_update()
    pygame.display.flip()

    # Let the night mask settle and the globe draw a few times.
    run_ticks(8, map_screen)
    return map_screen


def main(argv):
    mode = "wheel" if "--wheel" in argv else "walk"
    with_game = "--game" in argv

    # No known desktop, so the sizes below are honoured rather than clamped.
    gg.desktop_size = ()
    gg.set_screen_size(WALK[0])
    gg.set_mode()

    print("mode:", mode, "game:", with_game)
    report("start")

    from singularity.code.screens import main_menu

    menu = main_menu.MainMenu()
    menu.visible = True
    menu.needs_rebuild = True
    dialog.Dialog.top.maybe_update()
    pygame.display.flip()

    map_screen = build_game(menu) if with_game else None
    report("game up")

    screen = options_module.OptionsScreen(menu)
    screen.visible = True
    screen.needs_rebuild = True
    # Only the active tab is a child of the dialog, so the video pane has to be
    # the selected one for its labels to be laid out -- what the Video tab does.
    screen.set_tabs_pane(screen.video_pane)
    dialog.Dialog.top.maybe_update()
    pygame.display.flip()
    report("dialog open")

    pane = screen.video_pane

    if mode == "walk":
        # The first is already the current size; step through the rest.
        for size in WALK:
            pane.set_resolution(size)
            if map_screen is not None:
                map_screen.needs_resize = True
                map_screen.needs_rebuild = True
                run_ticks(3, map_screen)
            dialog.Dialog.top.maybe_update()
            pygame.display.flip()
            report("click %s" % (size,))
            assert gg.screen_size == size, (gg.screen_size, size)
    else:
        for size in WALK[1:]:
            pane.set_resolution(size)
            if map_screen is not None:
                map_screen.needs_resize = True
                map_screen.needs_rebuild = True
                run_ticks(3, map_screen)
            dialog.Dialog.top.maybe_update()
            pygame.display.flip()
            report("click %s" % (size,))

            # A flick, not a notch: the MX Master class of wheel sends tens of
            # these per gesture.
            for burst in range(3):
                spin_wheel(pane, 10)
                dialog.Dialog.top.maybe_update()
                pygame.display.flip()
            report("after 30 notches")

    print("SEQUENCE COMPLETED WITHOUT A CRASH")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
