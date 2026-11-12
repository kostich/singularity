"""--debug outlines what was redrawn; it must not change the frame.

The overlay used to keep a module-level list of the rings it drew in the
previous frame and add those rects back to updated_rect. updated_rect is not
just a present list -- g.layout_blit_pairs() turns each rect into a *blit
source region*, so the frame was assembled from rectangles chosen in an earlier
frame: after a geometry change or after a dialog opened, those rectangles were
no longer widgets, and the UI showed black bars, partial labels and text that
was there without --debug. That is how it was reported.

The overlay is now drawn on the screen surface after the blit, so it cannot
feed its own geometry back in.
"""

import pygame

from singularity.code import g
from singularity.code.graphics import dialog, text, widget as widget_module


def _colours(surface):
    step = max(2, min(surface.get_width(), surface.get_height()) // 10)
    seen = set()
    for x in range(2, surface.get_width() - 2, step):
        for y in range(2, surface.get_height() - 2, step):
            seen.add(surface.get_at((x, y))[:3])
    return seen


def _record_presents(monkeypatch):
    """Record the rects of every pygame.display.update() call."""
    seen = []
    real = pygame.display.update

    def spy(*rects):
        # The game passes a list of rects; the whole-window form passes none.
        flat = []
        for item in rects:
            if hasattr(item, "x"):
                flat.append(item)
            else:
                flat.extend(item)
        seen.append([(r.x, r.y, r.width, r.height) for r in flat])
        return real(*rects)

    monkeypatch.setattr(pygame.display, "update", spy)
    return seen


def _top_with_labels():
    top = dialog.TopDialog()
    top.visible = True
    top.make_top()
    top.update()

    first = text.Text(top, (0, 0), (.5, .08), text="ALPHA", text_size=24)
    second = text.Text(top, (0, .8), (.5, .08), text="BETA", text_size=24)
    top.update()
    return top, first, second


def test_the_overlay_does_not_replay_an_earlier_frame(graphics, monkeypatch):
    """A rect presented for one frame must not be presented again later."""
    was_debug = g.debug
    g.debug = True
    try:
        top, first, second = _top_with_labels()
        presents = _record_presents(monkeypatch)

        first.text = "ALPHA ONE"
        top.update()

        second.text = "BETA TWO"
        top.update()
    finally:
        g.debug = was_debug

    assert len(presents) == 2
    assert presents[0], "the first redraw should have presented something"
    assert presents[1], "the second redraw should have presented something"

    # The second frame changed a different widget, so no rect from the first
    # frame may appear again. With the old replay list, the first frame's rings
    # were handed to the second frame's blit and present.
    assert not (set(presents[0]) & set(presents[1]))


def test_there_is_no_stale_highlight_list():
    """Structural guard: the replay state must not come back."""
    assert not hasattr(widget_module, "debug_mode_undo_drawing_highlight")


def test_a_dialog_does_not_erase_the_labels_under_debug(graphics):
    """The reported symptom: text missing from the screen behind the submenu."""
    was_debug = g.debug
    g.debug = True
    try:
        top = dialog.TopDialog()
        top.visible = True
        top.make_top()
        top.update()

        label = text.Text(top, (0, 0), (.5, .08), text="READABLE",
                          text_size=24)
        top.update()

        before = len(_colours(label.surface))
        assert before > 1, "the label should have rendered something"

        # A modal low on the screen, so the label is behind it but not covered
        # by it: any change to its pixels is the fade and the overlay.
        modal = dialog.MessageDialog(top, text="Are you sure?",
                                     pos=(.5, .75), size=(.5, .2))
        top.lost_focus()
        modal.visible = True
        modal.needs_rebuild = True

        for _ in range(3):
            top.maybe_update()

        after = len(_colours(label.surface))
    finally:
        g.debug = was_debug

    # Erased would be one flat colour; dimmed keeps the text.
    assert after > 1
