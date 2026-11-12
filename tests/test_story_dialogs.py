"""The intro is read, not scrolled.

A story page is the one dialog a player reads a paragraph in, and it was shown
in a box half the screen across and half of it down -- which a page of prose
overflows. The box and the dialog type size are now measured so that every page
fits, in every shipped translation, at every resolution the gate renders.
"""

import pytest

from singularity.code.graphics import dialog, theme

from singularity.code.screens.map import MapScreen


# The narrowest, the default and the tallest the gate renders.
RESOLUTIONS = ((800, 600), (1024, 768), (1280, 800), (1920, 1080))


def _top(gg, size):
    gg.desktop_size = ()
    gg.set_screen_size(size)
    gg.set_mode()
    top = dialog.TopDialog()
    top.visible = True
    top.make_top()
    top.update()
    return top


@pytest.mark.parametrize("size", RESOLUTIONS)
def test_every_intro_page_fits_its_dialog(graphics, size):
    from singularity.code import g

    theme.set_theme("2030", force_reload=True)
    top = _top(graphics, size)
    box = MapScreen.story_dialog_size()
    assert box is not None

    pages = list(g.get_story_section("Intro"))
    assert pages, "the intro section is empty"

    for number, page in enumerate(pages):
        made = dialog.MessageDialog(top, size=box, text=page,
                                    art_key="dialog_story")
        made.visible = True
        made.needs_rebuild = True
        top.update()

        total, visible = made.body_line_count()
        assert total <= visible, (
            "intro page %d needs %d lines of a %d-line body at %r"
            % (number + 1, total, visible, size))
        made.visible = False
        made.parent = None

    top.visible = False


@pytest.mark.parametrize("theme_id", ("Legacy-default", "Legacy-nightmode",
                                      "Legacy-vector"))
def test_a_legacy_story_page_keeps_its_shipped_box(graphics, theme_id):
    """The old panel is part of the old look: half across, half down."""
    theme.set_theme(theme_id, force_reload=True)
    assert MapScreen.story_dialog_size() is None

    top = _top(graphics, (1024, 768))
    made = dialog.MessageDialog(top, text="Day 0.")
    made.visible = True
    made.needs_rebuild = True
    top.update()

    assert made.size == (.50, .5)
    made.visible = False
    top.visible = False
