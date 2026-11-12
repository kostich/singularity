"""Opening a dialog dims what is behind it; it must never erase it.

gg.fade_mask is blitted over every widget of the parent screen when a modal
dialog opens. That mask is created from gg.ALPHA, which is converted with
convert_alpha() and passed as the *depth* argument to pygame.Surface(). The
depth argument copies the pixel format but not the SRCALPHA flag, so the mask
came out opaque: pygame ignored its 175 alpha and blitted it as a solid black
rectangle. Everything behind a dialog -- backgrounds and text together -- was
wiped on the first frame, and stayed wiped until it happened to be redrawn.

That reads as "no fonts render when I open a screen", while the new dialog's
own widgets draw after the mask and look perfectly correct.
"""

import pygame

from singularity.code.graphics import dialog, text


def _colours(surface):
    """The distinct colours in a surface, sampled coarsely."""
    step = max(2, min(surface.get_width(), surface.get_height()) // 10)
    seen = set()
    for x in range(2, surface.get_width() - 2, step):
        for y in range(2, surface.get_height() - 2, step):
            seen.add(surface.get_at((x, y))[:3])
    return seen


def _top_with_label():
    """A top-level dialog with one labelled child, drawn once."""
    top = dialog.TopDialog()
    top.visible = True
    top.make_top()
    top.update()

    label = text.Text(top, (0, 0), (.5, .12), text="HELLO WORLD",
                      text_size=24)
    top.update()
    return top, label


def test_the_fade_mask_is_transparent(graphics):
    """SRCALPHA is what makes the blit blend; without it the mask is a wall."""
    gg = graphics
    _top_with_label()

    assert gg.fade_mask is not None
    assert gg.fade_mask.get_flags() & pygame.SRCALPHA
    # The depth of the fade belongs to the theme now, so this pins the property
    # the test is actually about -- a real, partial alpha survived the surface
    # construction -- and ties it to the theme rather than to one number. A mask
    # that came back opaque (255) is the bug this file exists for; a mask of
    # alpha 0 would be no fade at all.
    alpha = gg.fade_mask.get_at((0, 0))[3]
    assert alpha == gg.resolve_color_alias("fade_mask_color")[3]
    assert 0 < alpha < 255


def test_the_fade_mask_dims_a_colour_instead_of_replacing_it(graphics):
    gg = graphics
    _top_with_label()

    probe = pygame.Surface((32, 32))
    probe.fill((0, 0, 200, 255))
    probe.blit(gg.fade_mask, (0, 0))

    blue = probe.get_at((16, 16))[2]

    # 200 dimmed by 175/255 is 62. Erasing it would leave 0, and ignoring the
    # alpha entirely would leave 200.
    assert 20 < blue < 120


def test_fading_the_parent_keeps_the_labels_readable(graphics):
    """The mechanism, without another dialog drawn on top of it."""
    top, label = _top_with_label()

    before = _colours(label.surface)
    assert len(before) > 1, "the label should have rendered something"

    top.faded = True
    top.update()

    after = _colours(label.surface)

    # Erased: one flat colour. Dimmed: the text is still there, darker.
    assert len(after) > 1
    assert max(sum(c) for c in after) < max(sum(c) for c in before)

    top.faded = False


def test_opening_a_dialog_does_not_erase_the_screen_behind_it(graphics):
    """The player-visible case, with a modal that does not cover the label."""
    top, label = _top_with_label()

    before = _colours(label.surface)

    # Bottom of the screen, so the label at the top is behind the dialog but
    # not covered by it: what happens to its pixels is the fade and nothing
    # else.
    modal = dialog.MessageDialog(top, text="Are you sure?",
                                 pos=(.5, .72), size=(.5, .2))
    top.lost_focus()
    modal.visible = True
    modal.needs_rebuild = True
    top.maybe_update()

    after = _colours(label.surface)

    assert modal.collision_rect.top >= label.collision_rect.bottom
    assert len(after) > 1
    assert max(sum(c) for c in after) < max(sum(c) for c in before)

    modal.visible = False
    top.regained_focus()


def _chrome_probe(dialog_object):
    """One pixel of a dialog's own chrome: in its band, above the title."""
    x = int(dialog_object.real_size[0] * .55)
    return dialog_object.surface.get_at((x, 3))[:3]


def test_a_window_behind_another_window_dims_its_own_chrome(graphics):
    """The second level was dimmed and the first level was not.

    The mask reaches a dialog's children, so a window's contents went dark --
    but a dialog is drawn *above* the mask, and its frame, band and title are
    painted into its own surface, so they stayed at full brightness and the
    window underneath still looked like the live one.
    """
    from singularity.code.graphics import theme

    top = dialog.TopDialog()
    top.visible = True
    top.make_top()
    top.update()
    theme.set_theme("2030", force_reload=True)

    first = dialog.MessageDialog(top, text="The first window.", size=(.45, .45))
    first.visible = True
    first.needs_rebuild = True
    top.update()
    bright = _chrome_probe(first)

    second = dialog.MessageDialog(top, text="The second window.", size=(.4, .4))
    # What call_dialog() does to the dialog it opens *from*, which is the
    # window that must go dark.
    first.lost_focus()
    second.visible = True
    second.needs_rebuild = True
    top.update()
    dimmed = _chrome_probe(first)

    assert first.faded and not second.faded
    assert dimmed != bright, "the window behind did not dim its chrome"
    # Dimmed by the mask, not repainted some other colour.
    alpha = graphics.fade_mask.get_at((0, 0))[3]
    expected = [channel * (255 - alpha) // 255 for channel in bright]
    for got, want in zip(dimmed, expected):
        assert abs(got - want) <= 3, (dimmed, expected)

    # The window in front is the live one, and stays at full brightness even
    # when it is the only thing to redraw.
    front = _chrome_probe(second)
    second.needs_redraw = True
    top.update()
    assert _chrome_probe(second) == front

    second.visible = False
    first.visible = False
    first.regained_focus()


def test_a_legacy_panel_has_no_chrome_to_dim(graphics):
    """`window_shape = rect` paints no frame of its own, so nothing changes."""
    from singularity.code.graphics import theme

    top = dialog.TopDialog()
    top.visible = True
    top.make_top()
    top.update()
    theme.set_theme("Legacy-default", force_reload=True)

    made = dialog.MessageDialog(top, text="A legacy message.", size=(.45, .45))
    made.visible = True
    made.needs_rebuild = True
    top.update()
    before = _chrome_probe(made)

    made.lost_focus()
    made.needs_redraw = True
    top.update()

    assert made.faded
    assert made.fades_own_chrome() is False
    assert _chrome_probe(made) == before

    made.visible = False
