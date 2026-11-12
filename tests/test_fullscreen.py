"""Fullscreen switches in place, and never recreates the window.

pygame.display.set_mode() destroys and recreates the window. Doing that under a
running game left the replacement window without keyboard or mouse input: the
game sat in pygame.event.wait() while the music, on its own thread, kept
playing. Switching therefore goes through pygame._sdl2.video.Window, which
changes the existing window's state, and display.set_mode() is used only at
startup.

The tests drive a fake window manager, because the SDL dummy driver has none: it
cannot restore a window's size after a fullscreen cycle. The fake lets us cover
both a compositor that puts the window back and one that leaves it at the
desktop size.
"""

import time

import pytest
import pygame


# What the SDL dummy driver reports, so fullscreen means this size here.
DESKTOP = (1024, 768)

# The window the "player" chose.
CHOSEN = (800, 600)


def _settle(gg):
    """Pretend the last programmatic mode change was long ago.

    mode_change_settling() is a wall-clock window, so a test moves the clock
    rather than sleeping through it.
    """
    gg._mode_changed_at = 0.0


def _resize(top, size):
    """Deliver a VIDEORESIZE the way a window manager would."""
    top.handle(pygame.event.Event(pygame.VIDEORESIZE,
                                  {"size": size,
                                   "w": size[0], "h": size[1]}))


def _resize_window(width, height):
    """Resize the real window, the way a window manager would.

    pygame resizes the display surface along with the window, so this leaves
    exactly the state a compositor leaves behind: a bigger buffer that nothing
    has drawn into yet.
    """
    from pygame._sdl2 import video

    video.Window.from_display_module().size = (width, height)
    pygame.event.clear()


class FakeWindow(object):
    """A window whose fullscreen state a window manager honours.

    restores_size models the difference between compositors that put the window
    back where it was when fullscreen ends, and those that leave it at the
    desktop size.
    """

    def __init__(self, size, desktop, restores_size=True):
        self.size = tuple(size)
        self.desktop = tuple(desktop)
        self.fullscreen = False
        self.restores_size = restores_size
        self._before = None

    def set_fullscreen(self, value):
        if value and not self.fullscreen:
            self._before = self.size
            self.size = self.desktop
        elif not value and self.fullscreen:
            if self.restores_size and self._before:
                self.size = self._before
        self.fullscreen = bool(value)

    def set_windowed(self):
        """The SDL call that actually clears the fullscreen flag."""
        self.set_fullscreen(False)


class OldWindow(FakeWindow):
    """A pygame build whose Window has only set_fullscreen()."""

    set_windowed = None


class StubbornWindow(FakeWindow):
    """A window manager that will not resize a window on request.

    Some compositors simply ignore a size set while they are still tearing the
    window out of fullscreen. That is the case that used to be reported as a
    success.
    """

    refuse_resize = False

    @property
    def size(self):
        return self._size

    @size.setter
    def size(self, value):
        if self.refuse_resize:
            return
        self._size = value


class MaximizedWindow(object):
    """A compositor that gives the window back maximized, and will not resize it.

    The reported session: leaving fullscreen restores the maximized geometry
    (desktop width, less the work area) rather than the size the player chose,
    and every size request is ignored because the window is maximized. The exit
    worked -- the window is decorated and no longer covers the screen.
    """

    def __init__(self, size, desktop, restored):
        self._size = tuple(size)
        self.desktop = tuple(desktop)
        self.restored = tuple(restored)
        self.fullscreen = False

    @property
    def size(self):
        return self._size

    @size.setter
    def size(self, value):
        pass  # a maximized window will not be resized

    def set_fullscreen(self, value):
        if value and not self.fullscreen:
            self._size = self.desktop
        elif not value and self.fullscreen:
            self._size = self.restored
        self.fullscreen = bool(value)

    def set_windowed(self):
        self.set_fullscreen(False)


def _use_window_manager(monkeypatch, gg, restores_size=True):
    """Route the in-place path through a fake window manager.

    window.size is a plain attribute, so the assignments the game makes land
    exactly as they would on a real SDL window.
    """
    window = FakeWindow(gg.window_size, DESKTOP, restores_size)
    monkeypatch.setattr(gg, "_sdl2_window", lambda: window)
    monkeypatch.setattr(gg, "window_size_actual", lambda: window.size)
    return window


def _use_refusing_window_manager(monkeypatch, gg):
    """A window manager that honours fullscreen but not a resize."""
    window = StubbornWindow(gg.window_size, DESKTOP, restores_size=False)
    monkeypatch.setattr(gg, "_sdl2_window", lambda: window)
    monkeypatch.setattr(gg, "window_size_actual", lambda: window.size)
    return window


def _no_in_place_switch(monkeypatch, gg):
    """A pygame or driver that cannot change a window's state."""
    monkeypatch.setattr(gg, "_sdl2_window", lambda: None)


@pytest.fixture
def game(graphics):
    """A windowed game at CHOSEN on a DESKTOP-sized screen, with a top dialog."""
    gg = graphics
    gg.desktop_size = DESKTOP
    gg.set_screen_size(CHOSEN)
    gg.set_mode()

    from singularity.code.graphics import dialog

    top = dialog.TopDialog()
    top.visible = True
    top.update()

    yield gg, top

    # Reset the whole display state, including the fullscreen flag: a leftover
    # True would make the next test's set_screen_size() mean the desktop size.
    gg.fullscreen = False
    gg.set_screen_size(CHOSEN)
    gg.set_mode()


def test_fullscreen_switches_in_place(game, monkeypatch):
    """The painless path: same window, same surface, no restart asked for."""
    gg, top = game
    window = _use_window_manager(monkeypatch, gg)
    surface = gg.screen_surface

    assert gg.set_fullscreen(True)

    assert gg.fullscreen
    assert window.fullscreen
    assert gg.screen_surface is surface
    assert gg.window_size == DESKTOP
    assert gg.real_screen_size == DESKTOP
    assert not gg.restart_needed()


def test_a_toggle_never_calls_set_mode(game, monkeypatch):
    """set_mode() is the call that destroyed the window and lost its input."""
    gg, top = game
    _use_window_manager(monkeypatch, gg)

    calls = []
    real_set_mode = gg.set_mode

    def counting_set_mode():
        calls.append(1)
        real_set_mode()

    gg.set_mode = counting_set_mode
    try:
        assert gg.set_fullscreen(True)
        assert gg.set_fullscreen(False)
    finally:
        gg.set_mode = real_set_mode

    assert calls == []


def test_leaving_fullscreen_returns_to_the_chosen_window(game, monkeypatch):
    """A compositor that restores the window size needs nothing from us."""
    gg, top = game
    _use_window_manager(monkeypatch, gg, restores_size=True)

    gg.set_fullscreen(True)
    assert gg.window_size == DESKTOP

    gg.set_fullscreen(False)

    assert not gg.fullscreen
    assert gg.window_size == CHOSEN
    assert gg.real_screen_size == CHOSEN
    assert not gg.restart_needed()


def test_leaving_fullscreen_asks_for_the_size_when_the_wm_does_not(game,
                                                                monkeypatch):
    """Some compositors leave the window at desktop size; ask for ours.

    This is the case that looks like fullscreen never ended: a desktop-sized
    window is indistinguishable from a fullscreen one.
    """
    gg, top = game
    window = _use_window_manager(monkeypatch, gg, restores_size=False)

    gg.set_fullscreen(True)
    assert window.size == DESKTOP

    gg.set_fullscreen(False)

    # The game set the size itself, and then adopted what the window reports.
    assert window.size == CHOSEN
    assert gg.window_size == CHOSEN
    assert not gg.restart_needed()


def test_toggling_does_not_drift(game, monkeypatch):
    gg, top = game
    _use_window_manager(monkeypatch, gg)

    for _ in range(4):
        gg.set_fullscreen(True)
        gg.set_fullscreen(False)

    assert gg.window_size == CHOSEN
    assert gg.screen_size == CHOSEN
    assert not gg.restart_needed()


def test_asking_for_the_state_we_are_already_in_does_nothing(game,
                                                            monkeypatch):
    gg, top = game
    window = _use_window_manager(monkeypatch, gg)
    calls = []

    original = window.set_fullscreen
    monkeypatch.setattr(window, "set_fullscreen",
                        lambda value: (calls.append(value), original(value)))

    # Already windowed.
    assert gg.set_fullscreen(False)

    assert calls == []


def test_a_resolution_change_applies_in_place(game, monkeypatch):
    gg, top = game
    window = _use_window_manager(monkeypatch, gg)

    gg.set_screen_size((900, 700))
    assert gg.restart_needed()

    assert gg.apply_display_request()

    assert window.size == (900, 700)
    assert gg.window_size == (900, 700)
    assert not gg.restart_needed()


def test_fullscreen_falls_back_to_a_restart_without_the_window_api(game,
                                                                  monkeypatch):
    """Older pygame, or a build without the SDL2 window API."""
    gg, top = game
    _no_in_place_switch(monkeypatch, gg)
    surface = gg.screen_surface

    assert not gg.set_fullscreen(True)

    assert gg.fullscreen
    assert gg.screen_surface is surface
    assert gg.window_size == CHOSEN
    assert gg.restart_needed()

    # A restart is set_mode() at startup.
    gg.set_mode()

    assert gg.window_size == DESKTOP
    assert not gg.restart_needed()


def test_fullscreen_falls_back_when_the_window_call_raises(game, monkeypatch):
    """The driver may refuse: that must never surface as a player-visible error.

    pygame.display.toggle_fullscreen() does exactly this on Wayland -- it prints
    "skipping toggle_fullscreen on wayland" and returns -1, which is why the
    game does not use it.
    """
    gg, top = game

    class Refusing(object):
        def set_fullscreen(self, value):
            raise pygame.error("no window manager integration")

    monkeypatch.setattr(gg, "_sdl2_window", lambda: Refusing())

    assert not gg.set_fullscreen(True)

    assert gg.fullscreen
    assert gg.restart_needed()


def test_restart_is_not_needed_before_there_is_a_window(game):
    """prefs.dat and the command line set fullscreen before pygame.init()."""
    gg, top = game
    saved = gg.screen_surface

    try:
        gg.screen_surface = None
        gg.set_fullscreen(True)

        assert not gg.restart_needed()
    finally:
        gg.screen_surface = saved


def test_the_toggle_is_reported_to_the_options_screen(game, monkeypatch):
    """The button must show the state the game is actually in."""
    from singularity.code.screens import main_menu, options

    gg, top = game
    _use_window_manager(monkeypatch, gg)

    menu = main_menu.MainMenu()
    menu.visible = True
    menu.needs_reconfig = True
    menu.needs_rebuild = True
    menu.update()

    opts = options.OptionsScreen(menu)
    opts.visible = True
    opts.needs_rebuild = True
    opts.update()

    opts.video_pane.set_fullscreen(True)

    assert gg.fullscreen
    assert opts.video_pane.fullscreen_toggle.active
    assert not gg.restart_needed()

    opts.video_pane.set_fullscreen(False)

    assert not gg.fullscreen
    assert not opts.video_pane.fullscreen_toggle.active

    opts.visible = False


def test_a_real_resize_is_adopted(game):
    """Dragging the corner still resizes the UI, with no restart involved."""
    gg, top = game
    _settle(gg)

    _resize(top, (900, 700))

    assert gg.window_size == (900, 700)
    assert gg.windowed_size == (900, 700)
    # The chosen resolution is untouched: a drag changes the window, and
    # screen_size is what lands in prefs.dat as "xres". Writing it back here is
    # how one drag stored a window size (3440x1371) as a resolution.
    assert gg.screen_size == CHOSEN
    # The window manager already applied this, so nothing is pending: nobody is
    # asked to restart because they resized a window.
    assert not gg.restart_needed()


def test_a_resize_never_asks_for_a_new_mode(game):
    """Structural proof against the old feedback loop.

    The loop needed the resize handler to call set_mode(): that asks the window
    manager for a size, which answers with another resize event. If handling a
    resize never calls set_mode(), there is nothing to loop on.
    """
    gg, top = game
    _settle(gg)

    calls = []
    real_set_mode = gg.set_mode

    def counting_set_mode():
        calls.append(gg.window_size)
        real_set_mode()

    gg.set_mode = counting_set_mode
    try:
        for size in ((900, 700), DESKTOP, (900, 700), DESKTOP, (900, 700)):
            _resize(top, size)
    finally:
        gg.set_mode = real_set_mode

    assert calls == []


def test_a_stale_resize_cannot_put_us_back_to_desktop_size(game, monkeypatch):
    """The reported oscillation, as one sequence.

    Leaving fullscreen makes the window manager deliver a resize event carrying
    the size just left, i.e. the desktop. Accepting it made the window
    desktop-sized again, which looks exactly like fullscreen, so the next click
    went back in.
    """
    gg, top = game
    _use_window_manager(monkeypatch, gg)

    gg.set_fullscreen(True)
    gg.set_fullscreen(False)
    assert gg.window_size == CHOSEN

    # The mode change is recent, so this event is its echo.
    assert gg.mode_change_settling()
    _resize(top, DESKTOP)

    assert gg.window_size == CHOSEN
    assert gg.screen_size == CHOSEN


def test_a_resize_while_fullscreen_is_ignored(game, monkeypatch):
    gg, top = game
    _use_window_manager(monkeypatch, gg)

    gg.set_fullscreen(True)
    # Even long after the mode change: in fullscreen the window is the desktop
    # and there is nothing to resize.
    _settle(gg)
    _resize(top, (900, 700))

    assert gg.fullscreen
    assert gg.window_size == DESKTOP


def test_an_adopted_size_is_clamped_to_the_desktop(game):
    gg, top = game

    assert gg.adopt_window_size((9999, 9999))

    assert gg.window_size == DESKTOP
    assert gg.real_screen_size == DESKTOP


def test_a_degenerate_reported_size_is_ignored(game, monkeypatch):
    """A compositor can answer 0x0 for a window that is still being mapped.

    Believing it is catastrophic rather than cosmetic: every font size is
    derived from the layout height (text.convert_font_size), so a 0x0 layout
    renders every glyph at 0px. The game then draws its panes with no text at
    all, which reads as "the fonts are broken" and sends you looking in the
    wrong place entirely.
    """
    gg, top = game
    good = gg.window_size

    monkeypatch.setattr(pygame.display, "get_window_size", lambda: (0, 0))

    assert gg.window_size_actual() == good


def test_a_degenerate_size_cannot_collapse_the_layout(game, monkeypatch):
    gg, top = game
    _use_window_manager(monkeypatch, gg)

    # get_window_size() and the surface both go bad, which is the worst case.
    monkeypatch.setattr(pygame.display, "get_window_size", lambda: (0, 0))

    gg.set_fullscreen(True)

    assert gg.real_screen_size[0] > 0
    assert gg.real_screen_size[1] > 0
    assert gg.window_size[0] > 0
    assert gg.window_size[1] > 0


def test_usable_size_rejects_what_a_window_cannot_be():
    from singularity.code.graphics import g as gg

    assert not gg._usable_size(None)
    assert not gg._usable_size((0, 0))
    assert not gg._usable_size((800,))
    # Below the minimum the game accepts.
    assert not gg._usable_size((50, 40))
    assert gg._usable_size((800, 600))


def test_a_window_the_compositor_sized_is_laid_out_in(game, monkeypatch):
    """A window manager may size the window without us asking.

    The display surface follows the window automatically, so the UI is then
    drawn into a smaller area than the window and the difference is whatever
    the compositor left in the reallocated buffer -- the band of stripes down
    the side of a resized window.
    """
    gg, top = game
    _settle(gg)

    monkeypatch.setattr(gg, "window_size_actual", lambda: (1024, 700))

    top.maybe_update()

    assert gg.window_size == (1024, 700)
    assert gg.real_screen_size == (1024, 700)
    assert gg.layout_origin == (0, 0)
    # The window already is that size, so nothing is waiting to be applied.
    assert not gg.restart_needed()
    # The chosen resolution is untouched: this was the compositor, not the
    # player picking a different resolution.
    assert gg.screen_size == CHOSEN


def test_a_refused_resize_is_not_forgotten(game, monkeypatch):
    """Ignoring the echo is right; ignoring a size that sticks is not."""
    gg, top = game
    window = _use_window_manager(monkeypatch, gg)

    # A mode change has just been asked for, so this resize is its echo and is
    # dropped. (set_mode() no longer arms this: at startup the next resize is
    # the compositor's real answer, not an echo.)
    gg.note_mode_change()
    assert gg.mode_change_settling()
    _resize(top, (900, 700))
    assert gg.window_size == CHOSEN

    # The settle window has passed and the window really is 900x700: whatever
    # swallowed the event, the layout has to catch up with the window.
    _settle(gg)
    window.size = (900, 700)
    top.maybe_update()

    assert gg.window_size == (900, 700)
    assert gg.real_screen_size == (900, 700)


def test_the_first_resize_after_startup_is_not_an_echo(game):
    """Opening a window must not arm the guard against our own resize.

    The first thing a compositor says after set_mode() is the size it actually
    gave the window. Treating that as an echo of our own request threw the real
    window size away, and the layout then stayed at 3370x1370 inside a
    3440x1371 window.
    """
    gg, top = game

    # set_mode() was the last thing the fixture did.
    assert not gg.mode_change_settling()

    _resize(top, (1024, 700))

    assert gg.window_size == (1024, 700)
    assert gg.real_screen_size == (1024, 700)


def test_reconciling_leaves_fullscreen_alone(game, monkeypatch):
    """In fullscreen the window is the desktop, so there is nothing to adopt --
    and adopting it would overwrite the remembered windowed size."""
    gg, top = game
    window = _use_window_manager(monkeypatch, gg)

    gg.set_fullscreen(True)
    _settle(gg)
    window.size = (1000, 700)

    top.maybe_update()

    assert gg.fullscreen
    assert gg.window_size == DESKTOP
    assert gg.windowed_size == CHOSEN


def test_the_surface_is_re_grabbed_after_a_resize(game):
    """pygame picks the replacement window surface up lazily.

    Until display.get_surface() is called again the cached surface still
    describes the previous allocation, so a frame drawn into it and presented
    through it belongs to the old size -- which is the difference between the
    UI really being laid out in the window and merely believing it is.
    """
    gg, top = game
    _settle(gg)

    _resize_window(1024, 700)

    assert gg.reconcile_window_size()

    assert gg.window_size == (1024, 700)
    assert gg.screen_surface.get_size() == (1024, 700)


def test_a_geometry_change_presents_the_whole_window(game, monkeypatch):
    """One frame presents all of the window, then the cheap path comes back."""
    gg, top = game
    _settle(gg)

    presented = []
    monkeypatch.setattr(pygame.display, "update",
                        lambda *rects: presented.append(tuple(rects)))

    _resize_window(1024, 700)
    top.maybe_update()

    assert gg.window_size == (1024, 700)
    # No rects means "the whole window".
    assert presented
    assert presented[-1] == ()

    # And the frame after that goes back to presenting only what changed: this
    # is a one-off after a geometry change, not a permanently slower path.
    presented.clear()
    top.needs_redraw = True
    top.update()

    assert presented
    assert presented[-1] != ()


def test_the_parts_of_the_window_the_layout_does_not_cover_are_painted(game):
    """What the player saw: a band of stripes down the side of the window.

    The window grew and its buffer was reallocated, so the strips beside the
    layout area held uninitialised memory. Nothing in the widget tree draws
    there, so unless the frame paints them they stay that way for ever.
    """
    gg, top = game
    _settle(gg)

    # 8:3, wider than LAYOUT_MAX_ASPECT, so the UI is centred with bands.
    _resize_window(1600, 600)
    gg.screen_surface.fill((0, 255, 0))

    top.maybe_update()

    assert gg.layout_origin[0] > 0
    bands = gg.outside_layout_rects()
    assert len(bands) == 2

    for band in bands:
        assert gg.screen_surface.get_at(
            (band.centerx, band.centery))[:3] == (0, 0, 0)

    # The layout area itself was painted over, i.e. the frame was really drawn
    # and not just cleared.
    inside = (gg.layout_origin[0] + 5, gg.layout_size[1] // 2)
    assert gg.screen_surface.get_at(inside)[:3] != (0, 255, 0)


def test_a_successful_exit_records_the_windowed_state(game, monkeypatch):
    gg, top = game
    _use_window_manager(monkeypatch, gg, restores_size=False)

    gg.set_fullscreen(True)
    assert gg.windowed_size == CHOSEN

    assert gg.set_fullscreen(False)

    assert not gg.restart_needed()
    assert gg._applied_fullscreen is False
    assert gg.windowed_size == CHOSEN
    assert gg.window_size == CHOSEN


def test_leaving_fullscreen_returns_promptly(game, monkeypatch):
    """The exit used to wait out an entire pump budget on every toggle.

    That is the ~200 ms "stuck" pause with the toggle already flipped and the
    window still fullscreen. It happened on the path where the window manager
    does not put the window back by itself and the game has to ask.
    """
    gg, top = game
    _use_window_manager(monkeypatch, gg, restores_size=False)

    gg.set_fullscreen(True)

    started = time.monotonic()
    assert gg.set_fullscreen(False)
    elapsed = time.monotonic() - started

    assert gg.window_size == CHOSEN
    assert not gg.restart_needed()
    assert elapsed < 0.12, "leaving fullscreen took %.3fs" % elapsed


def test_a_refused_fullscreen_exit_asks_for_a_restart(game, monkeypatch):
    """A display that will not shrink the window must not claim success.

    This was the bug: the size request was discarded because SDL still had the
    window flagged fullscreen, the desktop size was then read back and recorded
    as the windowed state, and restart_needed() reported nothing to do. The
    player got a window that looked fullscreen, no restart offered, and no way
    out until the game was started again.
    """
    gg, top = game
    window = _use_refusing_window_manager(monkeypatch, gg)

    gg.set_fullscreen(True)
    assert window.size == DESKTOP

    # From here on the compositor ignores resize requests.
    window.refuse_resize = True

    assert not gg.set_fullscreen(False)

    assert not gg.fullscreen
    # The window really is still the desktop, so the layout follows it rather
    # than drawing into a strip of it.
    assert gg.window_size == DESKTOP
    assert gg.real_screen_size == DESKTOP
    # But the game does not pretend that is the window size the player chose.
    assert gg.windowed_size == CHOSEN
    assert gg.restart_needed()


def test_a_build_without_set_windowed_still_leaves_fullscreen(game, monkeypatch):
    """The fallback for a pygame that has only set_fullscreen()."""
    gg, top = game
    window = OldWindow(gg.window_size, DESKTOP, restores_size=False)
    monkeypatch.setattr(gg, "_sdl2_window", lambda: window)
    monkeypatch.setattr(gg, "window_size_actual", lambda: window.size)

    gg.set_fullscreen(True)
    assert window.size == DESKTOP

    assert gg.set_fullscreen(False)

    assert gg.window_size == CHOSEN
    assert not gg.restart_needed()


def test_a_refused_exit_gives_up_quickly(game, monkeypatch):
    """The reported pause: the toggle flipped, ~200 ms of nothing, still fullscreen.

    The old code asked for the size, waited out an entire pump budget for a
    window that was never going to change, and then reported success. So the
    pause and the lie arrived together.
    """
    gg, top = game
    window = _use_refusing_window_manager(monkeypatch, gg)

    gg.set_fullscreen(True)
    window.refuse_resize = True

    started = time.monotonic()
    applied = gg.set_fullscreen(False)
    elapsed = time.monotonic() - started

    assert not applied
    assert elapsed < 0.2, "the refused exit took %.3fs" % elapsed


def test_a_maximized_compositor_still_counts_as_leaving_fullscreen(game,
                                                                  monkeypatch):
    """The reported case: the window comes back maximized, not at the chosen size.

    Every size request is ignored because the window is maximized, so the exact
    size never arrives -- but the window did leave fullscreen. Demanding the
    exact size made a working switch report a pending restart, which armed the
    "you must restart" prompt on a session where fullscreen was turning off.
    """
    gg, top = game
    window = MaximizedWindow(gg.window_size, DESKTOP, (900, 700))
    monkeypatch.setattr(gg, "_sdl2_window", lambda: window)
    monkeypatch.setattr(gg, "window_size_actual", lambda: window.size)

    assert gg.set_fullscreen(True)
    assert gg.window_size == DESKTOP

    assert gg.set_fullscreen(False)

    # Not the chosen size: the compositor maximized the window instead.
    assert gg.window_size == (900, 700)
    assert gg.real_screen_size == (900, 700)
    # The size the player chose is still remembered for the next round trip...
    assert gg.windowed_size == CHOSEN
    # ...and nothing is waiting to be applied, so nothing may prompt.
    assert not gg.restart_needed()


def test_the_restart_prompt_is_gone(game):
    """The toggle applies in place, so there is nothing to restart for.

    The prompt was upstream dead code -- check_restart() was hardcoded to
    "need_restart = False" with the comment "Test all changes that require a
    restart. Currently, none." -- that d1cd8ec wired to restart_needed() while
    the in-place switch was still believed impossible. Now that the running
    window changes, a restart prompt can only mislead: whatever was asked for
    has already happened.
    """
    from singularity.code.screens import options

    assert not hasattr(options.OptionsScreen, "check_restart")
    assert not hasattr(options, "offer_restart")
    # restart() existed only to serve those two.
    assert not hasattr(options, "restart")


class RestorableMaximizedWindow(object):
    """A window that is maximized and ignores resizes until it is restored.

    The reported session: leaving fullscreen hands the window back maximized at
    3440x1371, and from then on picking a resolution does nothing at all,
    because SDL ignores SDL_SetWindowSize on a maximized window. It is not
    broken, it is maximized -- and the game never said so, never restored it,
    and every request was dropped without a word.
    """

    def __init__(self, size, desktop):
        self._size = tuple(size)
        self.desktop = tuple(desktop)
        self.fullscreen = False
        self.maximized = False

    @property
    def size(self):
        return self._size

    @size.setter
    def size(self, value):
        if not self.maximized:
            self._size = tuple(value)

    def set_fullscreen(self, value):
        if value and not self.fullscreen:
            self.maximized = False
            self._size = self.desktop
        self.fullscreen = bool(value)

    def set_windowed(self):
        # What this session's compositor does: the window comes back maximized,
        # a work area shorter than the desktop.
        self.fullscreen = False
        self.maximized = True

    def restore(self):
        self.maximized = False


def test_a_maximized_window_can_still_be_resized(game, monkeypatch):
    """Picking a resolution must re-size a maximized window, not be dropped."""
    gg, top = game

    # As the session is left after a fullscreen round trip: windowed, maximized,
    # and laid out in the geometry the compositor chose.
    window = RestorableMaximizedWindow((DESKTOP[0], DESKTOP[1] - 69), DESKTOP)
    window.maximized = True
    monkeypatch.setattr(gg, "_sdl2_window", lambda: window)
    monkeypatch.setattr(gg, "window_size_actual", lambda: window.size)
    gg.adopt_window_size(window.size, clamp=False)

    gg.set_screen_size(CHOSEN)
    assert gg.apply_display_request()

    assert not window.maximized
    assert window.size == gg.compute_window_size(CHOSEN, False)
    assert gg.window_size == window.size
    assert gg.real_screen_size == window.size
    assert not gg.restart_needed()
