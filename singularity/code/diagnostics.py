#file: diagnostics.py
#This file is part of Endgame: Singularity.

#Endgame: Singularity is free software; you can redistribute it and/or modify
#it under the terms of the GNU General Public License as published by
#the Free Software Foundation; either version 2 of the License, or
#(at your option) any later version.

#Endgame: Singularity is distributed in the hope that it will be useful,
#but WITHOUT ANY WARRANTY; without even the implied warranty of
#MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#GNU General Public License for more details.

#You should have received a copy of the GNU General Public License
#along with Endgame: Singularity; if not, write to the Free Software
#Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

"""Helpers for finding out where a hung game is stuck.

The game's main thread spends almost all of its time inside SDL. When SDL
blocks, Ctrl+C does nothing: Python only runs its signal handler between
bytecodes, and the blocked call never returns to the interpreter. The process
then looks alive -- music keeps playing on the mixer thread -- while no event is
ever handled again.

faulthandler's signal handlers are plain C and run even then, so a signal dumps
every thread's stack and names the call that is blocking.
"""

import faulthandler
import os
import signal
import sys


# Ctrl+\ in a terminal, and `kill -USR1 <pid>` from anywhere else. Both are
# handled by faulthandler itself, so they work while the main thread is stuck.
FREEZE_SIGNALS = ("SIGQUIT", "SIGUSR1")


def enable_freeze_diagnostics(stream=None):
    """Installs the stack-dumping handlers and returns what was installed.

    Safe on platforms without these signals: nothing is registered and an empty
    tuple is returned.
    """
    if stream is None:
        stream = sys.stderr

    try:
        faulthandler.enable(file=stream, all_threads=True)
    except (AttributeError, ValueError, OSError):
        return ()

    installed = []

    for name in FREEZE_SIGNALS:
        sig = getattr(signal, name, None)
        if sig is None:
            continue

        try:
            faulthandler.register(sig, file=stream,
                                  all_threads=True, chain=False)
        except (AttributeError, ValueError, OSError):
            continue

        installed.append(name)

    return tuple(installed)


def freeze_diagnostics_hint():
    """One line telling the player how to find out what a hang is doing."""
    return ("If the game stops responding, press Ctrl+\\ (or run "
            "\"kill -USR1 %d\" in another terminal) to print where it is "
            "stuck." % os.getpid())


def _fmt_size(size):
    if not size:
        return "unknown"

    try:
        return "%dx%d" % (int(size[0]), int(size[1]))
    except (TypeError, IndexError, ValueError):
        return str(size)


def describe_display():
    """One line describing the display, the layout and the font scaling.

    Printed under --debug, because the most confusing failure this game can have
    is text that does not appear. Every font size is scaled from the layout
    height (text.convert_font_size), so a collapsed layout renders every glyph
    at 0px and the game draws its panes with no text at all -- which looks like
    broken fonts, not like a layout problem. This line says which of the two it
    is, without needing a stack dump.
    """
    from singularity.code.graphics import g as gg
    from singularity.code.graphics import text as text_graphics

    driver = "?"
    try:
        import pygame

        if pygame.display.get_init():
            driver = pygame.display.get_driver()
    except Exception:
        pass

    surface = gg.screen_surface
    surface_size = tuple(surface.get_size()) if surface is not None else None

    fonts = ", ".join(
        "%s %d->%dpx" % (name, size, text_graphics.convert_font_size(size))
        for name, size in sorted(gg.configured_text_sizes.items()))

    origin = gg.layout_origin or (0, 0)
    # What the compositor says the window is, next to what we think it is: a
    # disagreement between these two is the whole cause of a band of unpainted
    # window along one edge.
    actual = gg.window_size_actual()

    return ("display: driver=%s window=%s actual=%s layout=%s origin=%d,%d "
            "desktop=%s fullscreen=%s surface=%s | fonts: %s"
            % (driver, _fmt_size(gg.window_size), _fmt_size(actual),
               _fmt_size(gg.real_screen_size),
               origin[0], origin[1], _fmt_size(gg.desktop_size),
               gg.fullscreen, _fmt_size(surface_size), fonts))
