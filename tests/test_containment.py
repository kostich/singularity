"""Every visible widget must fit inside its parent, at every resolution.

This is the check that was missing. A widget that does not fit is silently
clipped by widget.remake_surfaces(), so a layout bug does not crash and does
not fail any other test. It just hides parts of the UI. That is how the
right-hand half of the map, the info window and the Options fullscreen toggle
all disappeared at 3440x1440 while the gate stayed green.

The screens are nested the way the real game nests them: MapScreen is a CHILD
of the MainMenu root (screens/main_menu.py), not a parentless screen. Building
it parentless, as the UI harness did, takes a different path through
_calc_size and hides this whole class of bug.
"""

import pytest

from singularity.code import g


# Everything the gate runs with, plus the wide and tall extremes.
RESOLUTIONS = [
    (800, 600),
    (1024, 768),
    (1280, 800),
    (1366, 768),
    (1920, 1080),
    (2560, 1440),
    (3440, 1440),
    (3840, 2160),
    (5120, 1440),
]


def _problems(root):
    """Every visible widget whose rect is not inside its parent's rect."""
    found = []
    stack = [root]

    while stack:
        widget = stack.pop()
        if not widget.visible:
            continue

        parent = widget.parent
        if (parent is not None
                and widget.collision_rect is not None
                and parent.collision_rect is not None
                and not parent.collision_rect.contains(widget.collision_rect)):
            found.append("%r at %s inside parent %r at %s"
                         % (widget, tuple(widget.collision_rect),
                            parent, tuple(parent.collision_rect)))

        stack.extend(widget.children)

    return found


def _layout(gg, size, screen):
    """Size the display to `size`, lay `screen` out, and return it."""
    gg.desktop_size = ()
    gg.set_screen_size(size)
    gg.set_mode()

    screen.visible = True
    screen.needs_reconfig = True
    screen.needs_rebuild = True
    screen.update()

    return screen


@pytest.mark.parametrize("size", RESOLUTIONS)
def test_main_menu_and_map_contain_their_children(graphics, size):
    from singularity.code.screens import main_menu

    menu = _layout(graphics, size, main_menu.MainMenu())

    # The map screen is a child of the menu in the real game, and it covers the
    # window. This is the arrangement that was broken.
    map_screen = menu.map_screen
    map_screen.visible = True
    map_screen.needs_rebuild = True
    map_screen.update()

    assert map_screen.real_size == graphics.real_screen_size
    assert not _problems(menu)


@pytest.mark.parametrize("size", RESOLUTIONS)
def test_options_panes_contain_their_children(graphics, size):
    from singularity.code.screens import main_menu, options

    menu = _layout(graphics, size, main_menu.MainMenu())

    opts = options.OptionsScreen(menu)
    opts.visible = True
    opts.needs_rebuild = True
    opts.update()

    # Every tab in turn: the fullscreen toggle lives in the video pane, and a
    # pane only gets children once set_tabs_pane() makes it the visible one.
    for pane in opts.tabs_panes:
        opts.set_tabs_pane(pane)
        opts.needs_rebuild = True
        opts.update()
        pane.needs_rebuild = True
        opts.update()

        assert not _problems(opts)


@pytest.mark.parametrize("size", RESOLUTIONS)
def test_game_screens_contain_their_children(graphics, size):
    from singularity.code.screens import main_menu, research, log
    from singularity.code.screens import knowledge, report, savegame
    from singularity.code.screens import location as locscreen

    menu = _layout(graphics, size, main_menu.MainMenu())

    base_location = [loc for loc in g.pl.locations.values() if loc.bases][0]

    screens = [
        ("research", research.ResearchScreen(menu)),
        ("location", locscreen.LocationScreen(menu)),
        ("savegame", savegame.SavegameScreen(menu)),
        ("log", log.LogScreen(menu)),
        ("knowledge", knowledge.KnowledgeScreen(menu)),
        ("report", report.ReportScreen(menu)),
    ]

    screens[1][1].location = base_location

    for name, screen in screens:
        screen.visible = True
        screen.needs_reconfig = True
        screen.needs_rebuild = True
        screen.update()

        assert not _problems(screen), name

        screen.visible = False


@pytest.mark.parametrize("size", RESOLUTIONS)
def test_a_dialog_opened_from_a_window_fits_inside_it(graphics, size):
    """A message shown *over* a screen used to hang off the bottom of it.

    The research screen's danger help is the case a player reported: the message
    is a MessageDialog placed at the centre of the *screen*, which is not the
    centre of the window it is drawn in. Its surface is then clipped to that
    window, and the part cut away is the bottom -- the OK button. This is the
    geometry check for it, at every resolution.
    """
    from singularity.code.graphics import dialog
    from singularity.code.screens import main_menu, research

    menu = _layout(graphics, size, main_menu.MainMenu())

    for name, parent in (("menu", menu),
                         ("research", research.ResearchScreen(menu))):
        parent.visible = True
        parent.needs_reconfig = True
        parent.needs_rebuild = True
        parent.update()

        message = dialog.MessageDialog(parent, text="A message.")
        message.visible = True
        message.needs_rebuild = True
        message.update()

        assert not _problems(message), (size, name)
        # And the button row is inside the dialog's own surface, not carved off
        # the bottom of it.
        assert message.ok_button.collision_rect.bottom <= (
            message.collision_rect.bottom), (size, name)

        message.visible = False
        parent.visible = False


def test_a_button_over_the_globe_survives_the_globe_redrawing(graphics):
    """The space buttons flickered between the foreground and the background.

    The globe is redrawn as its terminator moves, and children are drawn in
    order -- so the globe painted over the buttons that sit on top of it, and
    nothing ever painted them back. At one frame they were there and at the next
    they were not, which is the cycle the player saw.
    """
    from singularity.code.screens import main_menu

    menu = _layout(graphics, (1024, 600), main_menu.MainMenu())
    map_screen = menu.map_screen
    map_screen.visible = True
    map_screen.needs_rebuild = True
    map_screen.update()

    # A space location is hidden until its prerequisite is researched, and the
    # player who reported the flicker had researched it. A button that was never
    # visible was also never sized, so it needs a layout pass of its own.
    moon = g.locations["MOON"]
    saved, moon.prerequisites = moon.prerequisites, []
    map_screen.needs_rebuild = True
    map_screen.update()

    globe = map_screen.map
    button = map_screen.location_buttons["MOON"]
    assert button.visible, "the space location is still hidden"
    button.needs_resize = True
    map_screen.update()

    assert globe.collision_rect.colliderect(button.collision_rect), (
        "this resolution no longer puts the button over the globe")

    inset = (button.collision_rect.centerx - button.collision_rect.left,
             button.collision_rect.centery - button.collision_rect.top)
    expected = button.surface.get_at(inset)[:3]

    globe.needs_redraw = True
    map_screen.update()

    assert button.needs_redraw is False, "the button was not repainted"
    assert menu.surface.get_at(button.collision_rect.center)[:3] == expected

    moon.prerequisites = saved


def test_strict_layout_turns_a_clip_into_an_error(graphics):
    """The opt-in guard the harness uses: a bad rect must not stay silent."""
    from singularity.code.graphics import widget

    parent = widget.BorderedWidget(None, (0, 0), (0.5, 0.5))
    parent.visible = True
    parent.update()

    child = widget.BorderedWidget(parent, (0, 0), (0.5, 0.5))
    child.visible = True

    # Fits, so this is fine either way.
    child.update()
    assert parent.collision_rect.contains(child.collision_rect)

    # Force it off the parent; strict mode must refuse to draw it.
    child.pos = (0.9, 0.9)
    child.needs_resize = True
    child.needs_reposition = True

    saved = graphics.strict_layout
    try:
        graphics.strict_layout = True
        with pytest.raises(RuntimeError, match="does not fit on its parent"):
            child.update()
    finally:
        graphics.strict_layout = saved


def test_a_widget_size_is_never_negative(graphics):
    """A size that works out below zero becomes zero.

    Sizes are fractions of the layout or of the parent, and a fraction built by
    subtraction -- Listbox.rebuild() makes "-1 + scrollbar_rel_width",
    Scrollbar.resize() makes "(size * 2) - 1" -- is negative when whatever it
    measures against is degenerate. That is not a widget that is merely small:
    it is a rectangle pygame refuses to carve.
    """
    from singularity.code.graphics import widget

    top = widget.BorderedWidget(None, (0, 0), (1, 1))
    top.visible = True
    top.update()

    parent = widget.BorderedWidget(top, (0, 0), (.5, .5))
    parent.visible = True
    parent.update()

    child = widget.BorderedWidget(parent, (0, 0), (.5, .5))
    child.visible = True
    child.update()

    # What _calc_size() returns when the fraction it multiplied went negative.
    child._calc_size = lambda: (40, -30)
    child.needs_resize = True
    child.needs_reposition = True
    child.prepare_for_redraw()

    assert child.real_size == (40, 0)
    assert child.collision_rect.height == 0
    assert child.surface is not None


def test_a_rect_pygame_refuses_is_clipped_not_fatal(graphics):
    """subsurface() answers a negative rect with pygame.error, not ValueError.

    Only ValueError was caught, so this ended the game: the reported crash was
    "pygame.error: Parameter 'height' is invalid" from an open Options dialog,
    while it re-measured itself for a new resolution.
    """
    from singularity.code.graphics import widget

    top = widget.BorderedWidget(None, (0, 0), (1, 1))
    top.visible = True
    top.update()

    parent = widget.BorderedWidget(top, (0, 0), (.5, .5))
    parent.visible = True
    parent.update()

    child = widget.BorderedWidget(parent, (0, 0), (.5, .5))
    child.visible = True
    child.update()

    # As if the floor in resize() were not there: pygame will not carve this.
    child._real_size = (40, -30)
    child.needs_reposition = True
    child.prepare_for_redraw()

    assert child.surface is not None
    assert child.surface.get_width() >= 0
    assert child.surface.get_height() >= 0


def test_strict_layout_still_reports_a_widget_that_does_not_fit(graphics):
    """Catching pygame.error must not swallow a real containment bug."""
    from singularity.code.graphics import widget

    top = widget.BorderedWidget(None, (0, 0), (1, 1))
    top.visible = True
    top.update()

    parent = widget.BorderedWidget(top, (0, 0), (.5, .5))
    parent.visible = True
    parent.update()

    child = widget.BorderedWidget(parent, (0, 0), (2, .1))
    child.visible = True
    child.update()

    child._real_size = (10, -5)
    child.needs_reposition = True

    saved = graphics.strict_layout
    try:
        graphics.strict_layout = True
        with pytest.raises(RuntimeError, match="does not fit on its parent"):
            child.prepare_for_redraw()
    finally:
        graphics.strict_layout = saved
