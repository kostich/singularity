"""The wheel scrolls the view; it does not change the selection.

The report: with a free-spinning mouse (MX Master class) the lists "continue
scrolling over and over" and the game dies. Both come from the same place.

on_mousewheel() used to read only the *sign* of the event and then move a whole
window per event -- window - 1 rows -- by setting list_pos. On a list wired up
through UpdateListbox, setting list_pos is not a cursor move: it is the
setting. On the Options screen it runs

    update_resolution -> VideoPane.set_resolution -> gg.set_screen_size()
                      -> gg.apply_display_request()   (a real window resize)

so one flick of a high-resolution wheel reallocated the window dozens of times.
A modern wheel also reports a fraction of a row per event in precise_y, which
the sign test discarded, and that is why the list could not be scrolled gently.
"""

import pygame
import pytest

from singularity.code.graphics import dialog, listbox


# Enough rows that the list is longer than the visible window.
ROWS = 60


class Recorder(object):
    """Stands in for UpdateListbox.update_func, i.e. the setting."""

    def __init__(self):
        self.calls = []

    def __call__(self, value):
        self.calls.append(value)


def _wheel(y=0, precise=None, flipped=False):
    return pygame.event.Event(pygame.MOUSEWHEEL, {
        "x": 0, "y": y,
        "flipped": flipped,
        "precise_x": 0.0,
        "precise_y": float(y) if precise is None else precise,
        "which": 0, "touch": False,
    })


@pytest.fixture
def chosen(graphics):
    """A visible listbox of ROWS strings, with its update_func recorded."""
    top = dialog.TopDialog()
    top.visible = True
    top.make_top()
    top.update()

    recorder = Recorder()
    lb = listbox.UpdateListbox(top, (0, 0), (.5, .5),
                               list=[str(i) for i in range(ROWS)],
                               update_func=recorder)
    lb.visible = True
    top.update()

    # Building the list already fired the callback once; start clean.
    recorder.calls.clear()

    yield top, lb, recorder

    lb.visible = False
    top.visible = False


def _flush(top):
    """Run the pending rebuild, as a frame would."""
    top.needs_rebuild = True
    top.prepare_for_redraw()
    top.update()


def _limit(lb):
    """The furthest the view may scroll: elements beyond the visible window."""
    return lb.scrollbar.slider.slider_max


def test_one_notch_moves_the_view_one_row(chosen):
    top, lb, _ = chosen
    assert lb.scrollbar.scroll_pos == 0

    lb.on_mousewheel(_wheel(y=-1))          # wheel down
    assert lb.scrollbar.scroll_pos == 1

    lb.on_mousewheel(_wheel(y=1))           # wheel up
    assert lb.scrollbar.scroll_pos == 0


def test_the_wheel_never_moves_the_selection(chosen):
    """This is the part that used to resize the window from a wheel event."""
    top, lb, recorder = chosen
    lb.list_pos = 3
    recorder.calls.clear()

    for _ in range(20):
        lb.on_mousewheel(_wheel(y=-1))
        _flush(top)

    assert lb.list_pos == 3, "the selection moved"
    assert recorder.calls == [], "the wheel ran the list's callback"
    # The view did move, which is the whole point.
    assert lb.scrollbar.scroll_pos > 0


def test_a_flick_cannot_run_past_the_end(chosen):
    """A burst must stop at the last page, not overshoot it."""
    top, lb, _ = chosen
    limit = _limit(lb)
    assert limit > 0

    for _ in range(limit + 40):
        lb.on_mousewheel(_wheel(y=-1))
        _flush(top)

    assert lb.scrollbar.scroll_pos == _limit(lb)
    assert lb.scrollbar.scroll_pos <= limit

    for _ in range(limit + 40):
        lb.on_mousewheel(_wheel(y=1))
        _flush(top)

    assert lb.scrollbar.scroll_pos == 0


def test_one_event_cannot_cross_the_whole_list(chosen):
    """A wheel that reports a huge delta still moves at most one window."""
    top, lb, _ = chosen
    window = lb.scrollbar.window

    lb.on_mousewheel(_wheel(y=0, precise=-99999.0))
    _flush(top)

    assert lb.scrollbar.scroll_pos == min(window, _limit(lb))


def test_a_fraction_of_a_row_adds_up(chosen):
    """A touchpad or a free-spinning wheel reports parts of a row."""
    top, lb, _ = chosen

    for _ in range(2):
        lb.on_mousewheel(_wheel(y=0, precise=-0.4))
        _flush(top)
    assert lb.scrollbar.scroll_pos == 0, "0.8 of a row moved the list"

    lb.on_mousewheel(_wheel(y=0, precise=-0.4))
    _flush(top)
    assert lb.scrollbar.scroll_pos == 1

    # And the leftover travels with the gesture rather than being rounded away.
    lb.on_mousewheel(_wheel(y=0, precise=-0.8))
    _flush(top)
    assert lb.scrollbar.scroll_pos == 2


def test_flipped_inverts_the_wheel(chosen):
    top, lb, _ = chosen
    lb.on_mousewheel(_wheel(y=-1))
    _flush(top)
    assert lb.scrollbar.scroll_pos == 1

    lb.on_mousewheel(_wheel(y=-1, flipped=True))
    _flush(top)
    assert lb.scrollbar.scroll_pos == 0


def test_a_horizontal_only_gesture_is_ignored(chosen):
    top, lb, _ = chosen
    lb.on_mousewheel(_wheel(y=0, precise=0.0))
    _flush(top)
    assert lb.scrollbar.scroll_pos == 0


def test_a_list_that_fits_does_not_scroll(chosen):
    """Five rows in a sixteen-row window: there is nowhere to go."""
    top, lb, _ = chosen
    lb.list = [str(i) for i in range(3)]
    _flush(top)

    for _ in range(10):
        lb.on_mousewheel(_wheel(y=-1))
        _flush(top)

    assert lb.scrollbar.scroll_pos == 0
    assert lb.list_pos == 0


@pytest.mark.parametrize("button", [4, 5, 6, 7])
def test_a_wheel_axis_button_is_never_a_click(chosen, button):
    """The horizontal axis is a wheel too, and it is not a click.

    X11 reports the vertical wheel as buttons 4/5 and the horizontal one as
    6/7. SDL2 converts only 4/5 into MOUSEWHEEL, so 6/7 arrived as an ordinary
    MOUSEBUTTONUP and were dispatched to the CLICK handlers -- and
    Listbox.on_click() selects the row under the pointer. On the Options screen
    that row is the resolution, so a horizontal flick of a free-spinning wheel
    changed the resolution instead of scrolling the list.
    """
    top, lb, recorder = chosen
    lb.list_pos = 3
    lb.has_focus = True
    recorder.calls.clear()

    top.handle(pygame.event.Event(pygame.MOUSEBUTTONUP,
                                  {"pos": lb.collision_rect.center,
                                   "button": button}))

    # Nothing it posted may be handled either: the old path posted PAGE keys.
    for event in pygame.event.get():
        top.handle(event)

    assert lb.list_pos == 3, "a wheel axis moved the selection"
    assert recorder.calls == [], "a wheel axis ran the list's callback"
    assert lb.scrollbar.scroll_pos == lb.scrollbar.scroll_pos


def test_the_legacy_wheel_fallback_never_pages(chosen, monkeypatch):
    """A build without MOUSEWHEEL must still not turn a wheel into a page key.

    fake_key(PAGEUP) posts a KEYDOWN, and Listbox.got_key() moves list_pos from
    it. On a list wired up through UpdateListbox that is the setting, so one
    notch could pick a different resolution. The wheel may only scroll.
    """
    top, lb, recorder = chosen
    monkeypatch.setattr(dialog, "SDL_V2", False)

    lb.list_pos = 3
    lb.has_focus = True
    recorder.calls.clear()
    posted_before = len(pygame.event.get())
    assert posted_before == 0

    for button in (4, 5):
        top.handle(pygame.event.Event(pygame.MOUSEBUTTONUP,
                                      {"pos": lb.collision_rect.center,
                                       "button": button}))
        for event in pygame.event.get():
            top.handle(event)

    assert lb.list_pos == 3, "the legacy wheel path moved the selection"
    assert recorder.calls == []


def _release_over_row(lb, button, row=3):
    """A mouse button release in the middle of one row of the list."""
    rect = lb.display_elements[row].collision_rect
    return pygame.event.Event(pygame.MOUSEBUTTONUP,
                              {"pos": rect.center, "button": button})


@pytest.mark.parametrize("button", [0, 2, 4, 5, 6, 7, 8, 9])
def test_only_the_primary_button_selects_a_row(chosen, button):
    """Hovering, scrolling and stray buttons must not choose a row.

    The report: "the option changes only if I scroll while the cursor is within
    the option list". That is the shape of this handler -- it selects whatever
    row is under the event's position, so any event carrying a position selects
    when it lands on a row and does nothing when it lands outside. Requiring the
    primary button is what makes the pointer's location irrelevant on its own:
    a wheel is a wheel, whatever number a driver picks for it.
    """
    top, lb, recorder = chosen
    lb.list_pos = 0
    recorder.calls.clear()

    # Delivered straight to the widget, so this holds even for a button number
    # the dialog has never heard of.
    lb.on_click(_release_over_row(lb, button))

    assert lb.list_pos == 0, "button %r chose a row" % (button,)
    assert recorder.calls == [], "button %r ran the list's callback" % (button,)


def test_the_primary_button_still_selects_the_row_under_the_pointer(chosen):
    """The behaviour that must survive: clicking a row picks it."""
    top, lb, recorder = chosen
    lb.list_pos = 0
    recorder.calls.clear()

    lb.on_click(_release_over_row(lb, 1, row=2))

    assert lb.list_pos == 2
    assert recorder.calls == [2]


@pytest.mark.parametrize("button", [2, 4, 5, 6, 7, 8])
def test_only_the_primary_button_double_clicks_a_row(chosen, button):
    """A repeated wheel button is not a double-click.

    A wheel axis is not a click: a repeated wheel button already looks like a
    pair of clicks, and answering it would open a row from a notch.
    """
    top, lb, _ = chosen
    clicks = []
    lb.on_double_click_on_item = lambda event: clicks.append(event.button)

    lb.on_double_click(_release_over_row(lb, button, row=2))

    assert clicks == [], "button %r ran the double-click callback" % (button,)


def test_a_primary_double_click_still_reaches_its_callback(chosen):
    top, lb, _ = chosen
    clicks = []
    lb.on_double_click_on_item = lambda event: clicks.append(event.button)

    lb.on_double_click(_release_over_row(lb, 1, row=2))

    assert clicks == [1]


def _click(lb, row, offset=(0, 0), button=1):
    """One primary click inside row `row`, moved by `offset` pixels."""
    rect = lb.display_elements[row].collision_rect
    lb.on_click(pygame.event.Event(
        pygame.MOUSEBUTTONUP,
        {"pos": (rect.centerx + offset[0], rect.centery + offset[1]),
         "button": button}))


def test_a_double_click_survives_the_hand_moving_between_the_clicks(chosen):
    """The row that was hit is the target; the pixel distance is not.

    `Dialog.handle()` wanted two releases within ten pixels of each other in
    total. Six right and six down is a taxicab distance of twelve -- an ordinary
    hand on a trackpad -- and the pair was dropped, so double-clicking a base, a
    saved game or a difficulty did nothing at all. Both of these clicks land
    inside one 24px row.
    """
    top, lb, _ = chosen
    clicks = []
    lb.on_double_click_on_item = lambda event: clicks.append(event.button)

    _click(lb, 3)
    assert clicks == [], "one click is not a double-click"

    _click(lb, 3, offset=(6, 6))
    assert clicks == [1], "a drifting double-click on one row was dropped"
    assert lb.list_pos == 3


def test_two_clicks_on_different_rows_are_not_a_double_click(chosen):
    top, lb, _ = chosen
    clicks = []
    lb.on_double_click_on_item = lambda event: clicks.append(event.button)

    _click(lb, 2)
    _click(lb, 3)

    assert clicks == []
    assert lb.list_pos == 3


def test_a_third_click_starts_a_new_pair(chosen):
    """The pair is consumed, so whatever it opened is not opened again."""
    top, lb, _ = chosen
    clicks = []
    lb.on_double_click_on_item = lambda event: clicks.append(event.button)

    _click(lb, 2)
    _click(lb, 2)
    _click(lb, 2)

    assert clicks == [1], "three clicks fired %d times" % (len(clicks),)


def test_a_click_past_the_last_row_never_pairs_up(chosen):
    """Empty space below the list selects the first row, and may not open it."""
    top, lb, _ = chosen
    clicks = []
    lb.on_double_click_on_item = lambda event: clicks.append(event.button)

    lb.list = ["only one"]
    _flush(top)

    _click(lb, 5)
    _click(lb, 5)

    assert clicks == [], "a click on empty space opened a row"
    assert lb.list_pos == 0


def test_a_slow_second_click_is_not_a_double_click(chosen, monkeypatch):
    top, lb, _ = chosen
    clicks = []
    lb.on_double_click_on_item = lambda event: clicks.append(event.button)

    now = [1000.0]
    monkeypatch.setattr(
        listbox, "time",
        type("Clock", (), {"time": staticmethod(lambda: now[0])}))

    _click(lb, 2)
    now[0] += lb.DOUBLE_CLICK_SECONDS + .01
    _click(lb, 2)
    assert clicks == [], "two separate clicks were read as a double-click"

    # Just inside the window, and it counts.
    now[0] += lb.DOUBLE_CLICK_SECONDS - .01
    _click(lb, 2)
    assert clicks == [1]
