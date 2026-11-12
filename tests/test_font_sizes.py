"""Font sizes and font faces must not fall through the floor.

The report: turn fullscreen off, then pick 1280x1024 from the resolution list,
and the process died inside SDL_ttf while a Text widget searched for a font
size that fits the new layout.

Two things on that path were wrong on their own. The size search is a bisect
between 0 and the largest size the layout allows (text.font_bisect), and it
answers 0 when nothing fits, which is what a widget whose own rect collapsed
asks for; a 0-point face is not a font, every glyph in it measures zero. And
the face was built from a hand-written file object that reported one byte less
than the file and never advanced its position.

These tests pin both ends: no zero-point face reaches SDL_ttf, and a Text
widget measures itself at every layout size the reported session passed
through.
"""

import pytest

from singularity.code.graphics import g as gg
from singularity.code.graphics import constants, dialog, text


# The sizes from the report, in the order it went through them.
REPORTED_SIZES = [
    (3440, 1440),
    (1280, 1024),
    (800, 600),
    (1280, 1024),
]


@pytest.mark.parametrize("requested", [0, -1, -500])
def test_a_zero_point_face_is_never_returned(graphics, requested):
    """The bisect can answer 0; the face cache must not believe it."""
    face = gg.fonts["normal"][requested]

    assert face.get_height() > 0
    assert face.size("Resolution:")[0] > 0


@pytest.mark.parametrize("height", [100, 200, 767, 768, 1024, 1440])
def test_convert_font_size_never_scales_text_to_nothing(graphics, height):
    """Everything is scaled from the layout height, including down to zero."""
    saved = gg.real_screen_size
    try:
        gg.real_screen_size = (100, height)
        for size in (1, 5, 20, 36):
            assert text.convert_font_size(size) >= 1
    finally:
        gg.real_screen_size = saved


def test_a_text_widget_measures_itself_at_every_reported_size(graphics):
    """The frame the crash was in: resize -> calc_text_size -> font."""
    saved_top = dialog.Dialog.top
    saved_layout = gg.real_screen_size
    try:
        top = dialog.TopDialog()
        top.visible = True
        top.make_top()
        top.update()

        label = text.Text(top, (.01, .01), (.14, .05),
                          text="Resolution:", align=constants.LEFT,
                          background_color="clear")
        top.update()

        for size in REPORTED_SIZES:
            # The layout, not the window: text.convert_font_size() reads this
            # and every font size in the tree follows from it.
            gg.real_screen_size = size
            top.needs_resize = True
            top.prepare_for_redraw()

            assert label.font is not None, size
            assert label.font.get_height() > 0, size
            assert label.real_size[0] > 0 and label.real_size[1] > 0, size
            assert label.collision_rect.width > 0, size
    finally:
        gg.real_screen_size = saved_layout
        dialog.Dialog.top = saved_top
