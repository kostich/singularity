#!/usr/bin/env python3
"""Probe a real display for fullscreen switching and input health.

Run this on the machine where the game misbehaves, in the same session:

    python3 utils/window_probe.py

It opens its own small window -- not the game -- and reports which SDL calls
actually switch fullscreen here, whether the drawing surface follows the
window, and whether input still arrives afterwards.

All three matter, because they are the three things the game depends on:

  * pygame.display.set_mode() works, but destroys and recreates the window.
    That is what left the game without any input at all, so switching does not
    use it any more.
  * pygame.display.toggle_fullscreen() does not work on Wayland: SDL prints
    "skipping toggle_fullscreen on wayland" and returns -1, meaning "not
    supported". It changes nothing.
  * pygame._sdl2.video.Window.set_fullscreen() changes the existing window's
    state. This is what the game uses, so this is the interesting one.

Nothing is written anywhere; paste the output into the bug report.
"""

import sys
import time

import pygame


WINDOW = (800, 600)
SAMPLE_SECONDS = 3.0


def describe(counts):
    """Readable event tally, so a pasted report means something."""
    if not counts:
        return "none"

    parts = []
    for event_type, count in sorted(counts.items(), key=lambda kv: -kv[1]):
        try:
            name = pygame.event.event_name(event_type)
        except Exception:
            name = str(event_type)
        parts.append("%s=%d" % (name, count))

    return ", ".join(parts)


def sample_events(seconds):
    """Count the events that arrive over `seconds`, naming them."""
    counts = {}
    deadline = time.time() + seconds

    while time.time() < deadline:
        for event in pygame.event.get():
            counts[event.type] = counts.get(event.type, 0) + 1
        pygame.time.wait(10)

    return counts


def pump(attempts=50, delay_ms=10):
    """Drain and refill the queue, so asynchronous resizes land."""
    for _ in range(attempts):
        pygame.event.pump()
        pygame.time.wait(delay_ms)


def report_state(label, surface):
    print("  %-12s window %-12s surface %-12s focused %s"
          % (label,
             pygame.display.get_window_size(),
             surface.get_size() if surface is not None else "no surface",
             pygame.key.get_focused()))


def ask_for_input(what):
    print("  >>> %s" % what)
    print("  >>> MOVE THE MOUSE OVER THE WINDOW AND PRESS A FEW KEYS "
          "for %d seconds..." % SAMPLE_SECONDS)
    counts = sample_events(SAMPLE_SECONDS)
    print("      events:", describe(counts))
    return counts


def try_toggle_fullscreen(surface):
    """The API SDL does not implement on Wayland."""
    print()
    print("A. pygame.display.toggle_fullscreen()")

    try:
        result = pygame.display.toggle_fullscreen()
        print("   returned:", repr(result))
    except Exception as exc:
        print("   raised: %s: %s" % (type(exc).__name__, exc))
        return False

    # SDL returns 1 on success, 0 on failure and -1 for "not implemented".
    if result == 1:
        pump(10)
        report_state("after", pygame.display.get_surface())
        return True

    if result == -1:
        print("   -1 means NOT SUPPORTED: nothing changed on this display.")
    else:
        print("   it reported failure.")

    report_state("after", pygame.display.get_surface())
    print("   nothing to test: the window did not change state.")
    return False


def try_sdl2_window(surface, desktop):
    """The mechanism the game actually uses."""
    print()
    print("B. pygame._sdl2.video.Window.set_fullscreen()  <- what the game uses")

    try:
        from pygame._sdl2 import video as video2

        window = video2.Window.from_display_module()
        window.set_fullscreen(True)
    except Exception as exc:
        print("   raised: %s: %s" % (type(exc).__name__, exc))
        print("   RESULT: this build cannot switch in place; the game will")
        print("           fall back to asking for a restart.")
        return

    pump()
    report_state("fullscreen", pygame.display.get_surface())
    print("   same surface object:", pygame.display.get_surface() is surface)

    counts = ask_for_input("now in fullscreen")

    print()
    if pygame.display.get_window_size() != WINDOW:
        print("   RESULT: the window really went fullscreen.")
    else:
        print("   RESULT: the window did NOT change size. A compositor may")
        print("           treat this as a no-op for an already-maximised")
        print("           window, but fullscreen switching is not working.")

    if counts:
        print("   RESULT: input still arrives in fullscreen, so switching in")
        print("           place is safe on this display.")
    else:
        print("   RESULT: NO input arrived after switching. This display loses")
        print("           input on a mode change; that is the freeze the game")
        print("           has to avoid.")

    print()
    print("switching back to windowed...")
    try:
        window.set_fullscreen(False)
        pump()
        window.size = WINDOW
        pump()
    except Exception as exc:
        print("   raised on the way back: %s: %s" % (type(exc).__name__, exc))

    report_state("windowed", pygame.display.get_surface())

    if pygame.display.get_window_size() == WINDOW:
        print("   restored the window size exactly.")
    else:
        print("   NOTE: the size did not come back by itself. The game asks")
        print("         for it explicitly, so this is informational.")


def main():
    pygame.init()
    pygame.display.set_caption("Singularity display probe")

    surface = pygame.display.set_mode(WINDOW, pygame.RESIZABLE)

    print("driver:      ", pygame.display.get_driver())
    print("SDL:         ", ".".join(str(x) for x in pygame.get_sdl_version()))
    print("pygame:      ", pygame.version.ver)
    print("platform:    ", sys.platform)

    try:
        print("desktop sizes:", pygame.display.get_desktop_sizes())
    except Exception as exc:                       # pragma: no cover - probe
        print("desktop sizes: unavailable:", exc)

    print()
    report_state("windowed", surface)
    ask_for_input("baseline, before touching anything")

    if not try_toggle_fullscreen(surface):
        try_sdl2_window(surface, pygame.display.get_desktop_sizes())

    print()
    print("probe finished")
    pygame.quit()
    return 0


if __name__ == "__main__":
    sys.exit(main())
