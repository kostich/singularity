"""Exactly one SDL2 window wrapper may exist at a time, and it must stay alive.

The report: windowed, switching resolution from the Video tab, and the process
died with

    Fatal Python error: Segmentation fault
      File ".../singularity/code/graphics/text.py", line 423 in print_text

The faulting instruction was pymalloc popping a free list -- `mov (%rdi),%rcx`
with a pool header holding garbage -- so the heap had already been damaged.
valgrind put the writer in pygame's event conversion:

    Invalid write of size 4
       at Py_INCREF
       by dict_from_event (event.c)
       by pgEvent_New
       by pg_event_wait
    Address ... is 0 bytes inside a block of size 32 free'd
       by _Py_Dealloc

dict_from_event() ends with

    if (!window || !(pgWindow = SDL_GetWindowData(window, "pg_window"))) {
        pgWindow = Py_None;
    }
    Py_INCREF(pgWindow);

so it increfs whatever object the SDL window's user data points at, without
checking that the object is alive. That object is the pygame._sdl2.video.Window
wrapper, and g._sdl2_window() used to build a fresh one on every call and drop
it immediately: apply_display_request() and request_window_focus() each left a
freed object in the slot, and the next event to arrive wrote through it. The
corruption then surfaced wherever an allocation touched the damaged block --
which was a Text widget.

These tests pin the one thing the fix controls: the wrapper is made once, kept,
and replaced only when the window it belongs to is replaced.
"""

import pytest

from singularity.code.graphics import g as gg


def _forget():
    """Reset the cache, whether or not the build has the fix's helper."""
    getattr(gg, "_forget_sdl2_window", lambda: None)()


def _window_api(graphics):
    """The wrapper, or a skip when this build has no SDL2 window API."""
    _forget()
    window = gg._sdl2_window()
    if window is None:
        pytest.skip("this pygame build has no SDL2 window API")
    return window


def test_the_wrapper_is_created_once_and_kept(graphics):
    """Every call must return the same live object, not a fresh throwaway."""
    first = _window_api(graphics)

    for _ in range(20):
        assert gg._sdl2_window() is first


def test_a_resolution_change_reuses_the_wrapper(graphics):
    """Resizing in place is the path that used to leave a freed object behind."""
    first = _window_api(graphics)
    saved = (gg.desktop_size, gg.screen_size, gg.window_size, gg.fullscreen)

    try:
        gg.desktop_size = ()
        gg.set_screen_size((800, 600))
        gg.set_mode()
        # set_mode() replaced the window, so it replaced the wrapper too.
        after_mode = gg._sdl2_window()
        assert after_mode is not None
        assert after_mode is not first

        for size in ((1024, 768), (1024, 600)):
            gg.set_screen_size(size)
            gg.apply_display_request()
            assert gg._sdl2_window() is after_mode
    finally:
        (gg.desktop_size, gg.screen_size, gg.window_size,
         gg.fullscreen) = saved
        gg.set_screen_size(gg.screen_size, fs=gg.fullscreen)
        gg.set_mode()


def test_replacing_the_window_replaces_the_wrapper(graphics):
    """A wrapper for a destroyed window must never be handed out again."""
    first = _window_api(graphics)

    try:
        gg.set_mode()
        second = gg._sdl2_window()

        assert second is not None
        assert second is not first
    finally:
        gg.set_mode()


def test_a_build_without_the_window_api_still_works(graphics, monkeypatch):
    """No SDL2 window API must degrade to "ask for a restart", never raise."""
    import pygame

    video = pytest.importorskip("pygame._sdl2.video")
    _forget()

    class NoWindowAPI(object):
        """A pygame built without _sdl2.video, or one that refuses."""

        @staticmethod
        def from_display_module():
            raise pygame.error("no window")

    monkeypatch.setattr(video, "Window", NoWindowAPI)

    try:
        assert gg._sdl2_window() is None
    finally:
        _forget()
