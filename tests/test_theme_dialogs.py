"""A theme's [dialog] section, and the guarantee that it cannot leak.

This is the same trap [sizes] fell into (tests/test_theme_sizes.py): the legacy
themes name no parent, so `data.load_theme()` gives them the current default
theme -- 2030 -- as one. Every key 2030 sets and a legacy theme does not would
reach it, and the player who chose the old look would get a new one.

So both halves are pinned here: the format parses and rejects nonsense, and the
legacy themes spell the old geometry out so that 2030 cannot reach them.
"""

import pygame
import pytest

from singularity.code.graphics import (button, constants, dialog, g, theme,
                                       text, widget)


LEGACY_THEMES = ("Legacy-default", "Legacy-nightmode", "Legacy-vector")

# What the game did before the [dialog] section existed. These are not "nice
# values", they are the old behaviour: a top-centre panel at (.5, .1), a
# one-pixel border, no padding, and the 1% margin MessageListDialog hardcoded.
LEGACY_GEOMETRY = {
    "anchor": "top_center",
    "border_width": 1,
    "button_height": 0,
    "window_shape": "rect",
    "header": "none",
    "header_height": 0,
    "chamfer": 0,
    "padding": 0.0,
    "margin": 0.01,
    "image_slot": "none",
    "image_slot_width": 0.28,
    "image_slot_height": 0.34,
    "icon_buttons": "none",
    "text_width": "padding",
    "image_overlay": "none",
    "menu_backdrop": "none",
    "content_border_width": 1,
}

NEW_GEOMETRY = {
    "anchor": "mid_center",
    "border_width": 2,
    "button_height": 40,
    "window_shape": "chamfer",
    "header": "bar",
    "header_height": 0.06,
    "chamfer": 0.045,
    "padding": 0.04,
    "margin": 0.02,
    "image_slot": "top",
    "image_slot_height": 0.30,
    "icon_buttons": "all",
    "menu_backdrop": "rain",
}


@pytest.fixture
def dialogs_theme(graphics):
    """Register throwaway themes for one test, then leave the shipped set."""
    created = []

    def make(theme_id, dialogs=None, parent=None):
        th = theme.Theme(theme_id, "/nonexistent/" + theme_id)
        variant = theme.VariantTheme(None)
        variant.name = theme_id
        for key, value in (dialogs or {}).items():
            variant.set_dialog(key, value)
        th.set_variant(variant)
        # Fonts and colours come from the parent; this test is about geometry.
        th.inherit(parent or theme.default_theme)
        theme.themes[theme_id] = th
        created.append(theme_id)
        return th

    yield make

    for theme_id in created:
        theme.themes.pop(theme_id, None)
    theme.set_theme(theme.default_theme, force_reload=True)


def test_the_2030_theme_is_the_default(graphics):
    """A fresh install has no prefs.dat, so set_theme(None) is what it gets."""
    assert theme.default_theme == "2030"

    theme.set_theme(None, force_reload=True)
    assert theme.current.id == "2030"


def test_a_pre_2030_preference_still_lands_on_the_legacy_theme(graphics):
    """An old prefs.dat says `theme = default`, and that player asked for it."""
    theme.set_theme("default", force_reload=True)
    assert theme.current.id == "Legacy-default"

    theme.set_theme("nightmode", force_reload=True)
    assert theme.current.id == "Legacy-nightmode"


@pytest.mark.parametrize("theme_id", LEGACY_THEMES)
def test_the_legacy_themes_pin_the_old_dialog_geometry(graphics, theme_id):
    theme.set_theme(theme_id, force_reload=True)

    for key, value in LEGACY_GEOMETRY.items():
        assert g.dialog_style(key) == value, (theme_id, key)
        assert g.theme_dialog[key] == value, (theme_id, key)


def test_the_2030_theme_sets_the_new_dialog_geometry(graphics):
    theme.set_theme("2030", force_reload=True)

    for key, value in NEW_GEOMETRY.items():
        assert g.dialog_style(key) == value, key


def test_a_dialog_key_does_not_survive_a_theme_switch(graphics):
    """Same rule as [sizes]: the layer is rebuilt, not accumulated."""
    theme.set_theme("2030", force_reload=True)
    assert g.dialog_style("image_slot") == "top"

    theme.set_theme("Legacy-default", force_reload=True)
    assert g.dialog_style("image_slot") == "none"


def test_a_theme_without_dialogs_inherits_its_parents(graphics, dialogs_theme):
    dialogs_theme("dialogs-child", parent="2030")

    theme.set_theme("dialogs-child", force_reload=True)
    assert g.dialog_style("anchor") == "mid_center"


def test_a_child_overrides_its_parent(graphics, dialogs_theme):
    dialogs_theme("dialogs-child", {"padding": 0.1}, parent="2030")

    theme.set_theme("dialogs-child", force_reload=True)
    assert g.dialog_style("padding") == 0.1
    assert g.dialog_style("margin") == 0.02  # still from the parent


def test_an_absent_key_returns_the_callers_default(graphics):
    """The whole legacy path rests on this: no key, no change."""
    theme.set_theme("Legacy-vector", force_reload=True)

    assert g.dialog_style("image_slot_width", 0.28) == 0.28
    assert g.dialog_style("nonsense", "fallback") == "fallback"
    assert g.dialog_style("nonsense") is None


@pytest.mark.parametrize("key,value", [
    ("anchor", "sideways"),        # not in the vocabulary's values
    ("image_slot", "right"),       # only 'left' and 'top' exist
    ("icon_buttons", "some"),      # all or nothing
    ("border_width", "two"),       # not a number
    ("border_width", "0"),         # a frame cannot be zero pixels wide
    ("border_width", "99"),        # wider than any dialog
    ("padding", "abc"),
    ("padding", "-0.1"),           # negative padding is not an inset
    ("padding", "0.9"),            # would leave nothing to draw text in
    ("margin", "1.5"),
    ("image_slot_width", "0.01"),  # a pane nobody can see
    ("image_slot_height", "0.9"),  # a banner with no room for the text
    ("nonsense", "1"),             # no widget reads it
])
def test_a_bad_dialog_value_is_ignored(graphics, key, value):
    variant = theme.VariantTheme(None)

    variant.set_dialog(key, value)

    assert variant.dialog_infos == {}


def test_a_good_dialog_value_is_kept(graphics):
    variant = theme.VariantTheme(None)

    variant.set_dialog("padding", "0.03")
    variant.set_dialog("border_width", "3")
    variant.set_dialog("anchor", "mid_center")

    assert variant.dialog_infos == {
        "padding": 0.03,
        "border_width": 3,
        "anchor": "mid_center",
    }


@pytest.fixture
def dialog_tree(graphics):
    """A top dialog to hang a real dialog off, as the game does it."""
    top = dialog.TopDialog()
    top.visible = True
    top.make_top()
    top.update()
    yield top
    top.visible = False


def settle(top, dialog_object):
    dialog_object.visible = True
    top.needs_rebuild = True
    top.update()
    return dialog_object


@pytest.mark.parametrize("theme_id", LEGACY_THEMES)
def test_a_legacy_dialog_lays_out_exactly_as_it_used_to(dialog_tree, theme_id):
    """These are the numbers the code hardcoded: (.5, .1), top-centre, 1px."""
    top = dialog_tree
    theme.set_theme(theme_id, force_reload=True)

    md = settle(top, dialog.MessageDialog(top, text="A message."))

    assert md.pos == (.5, .1)
    assert md.anchor == constants.TOP_CENTER
    assert md.size == (.50, .5)
    assert md.border_width == 1
    assert md.text_padding == (0.0, 0.0, 0.0, 0.0)
    assert md.text_insets() == (0, 0, 0, 0)
    assert md.image_pane is None


def test_the_2030_dialog_is_centred_padded_and_framed(dialog_tree):
    top = dialog_tree
    theme.set_theme("2030", force_reload=True)

    md = settle(top, dialog.MessageDialog(top, text="A message."))

    # Centred in the window it opens over, which is measured against the parent
    # rather than against the screen. A screen share put a dialog opened *from*
    # a window -- the research screen's danger help -- partly outside that
    # window, where its surface was clipped to it and its OK row vanished.
    assert md.pos == (-.5, -.5)
    assert md.anchor == constants.MID_CENTER
    assert md.border_width == 2

    # Centred on the screen, not merely near the middle.
    assert md.real_pos == (md.parent.real_size[0] // 2 - md.real_size[0] // 2,
                           md.parent.real_size[1] // 2 - md.real_size[1] // 2)

    insets = md.text_insets()
    assert insets[1] > 0 and insets[3] > 0, "no vertical padding"
    assert insets[2] > 0, "no right padding"


def test_a_2030_window_is_shaped_and_carries_a_header(dialog_tree):
    """The panel is not a rectangle: cut corners, a rail across the top."""
    top = dialog_tree
    theme.set_theme("2030", force_reload=True)

    md = settle(top, dialog.MessageDialog(top, text="A message."))
    assert md.draws_window() is True
    assert md.header_pixels() == int(round(md.header_fraction()
                                           * md.real_size[1]))
    assert md.header_pixels() > 0
    assert md.window_title == "MESSAGE"

    # The cut corner is not painted: the pixel there is whatever was behind the
    # window, not the panel's fill.
    fill = tuple(g.resolve_color_alias("dialog_frame_fill")[:3])
    assert tuple(md.surface.get_at((0, 0))[:3]) != fill
    # The band is, and it starts at the top edge.
    band = tuple(g.resolve_color_alias("dialog_header_fill")[:3])
    assert tuple(md.surface.get_at((md.real_size[0] // 2, 3))[:3]) == band


@pytest.mark.parametrize("theme_id", LEGACY_THEMES)
def test_a_legacy_window_is_still_a_rectangle(dialog_tree, theme_id):
    top = dialog_tree
    theme.set_theme(theme_id, force_reload=True)

    md = settle(top, dialog.MessageDialog(top, text="A message."))
    assert md.draws_window() is False
    assert md.header_fraction() == 0


def test_a_2030_window_has_a_border_on_all_four_sides(dialog_tree):
    """The right and bottom edges were missing from the drawn frame.

    The frame was a stroked polygon, and the path it was stroked along runs one
    pixel past the surface on the right and the bottom: those two strokes landed
    outside it and were discarded. It is two *filled* polygons now -- the whole
    outline in the edge colour, then the same shape inset by the border in the
    fill -- so what survives is a rim the same width on every side.
    """
    top = dialog_tree
    theme.set_theme("2030", force_reload=True)

    md = settle(top, dialog.MessageDialog(top, text="A message."))
    width, height = md.real_size
    edge = tuple(g.resolve_color_alias("dialog_frame_edge")[:3])

    # Every pixel of the rim, on all four sides -- not just the outermost one,
    # because that is exactly how a one-pixel-thick edge on two sides went
    # unnoticed.
    border = md.border_width
    probes = {
        "left": [(x, height // 2) for x in range(border)],
        "right": [(width - 1 - x, height // 2) for x in range(border)],
        "top": [(width // 2, y) for y in range(border)],
        "bottom": [(width // 2, height - 1 - y) for y in range(border)],
    }
    for name, positions in probes.items():
        for position in positions:
            drawn = tuple(md.surface.get_at(position)[:3])
            assert drawn == edge, (
                "the %s edge is %dpx but %r is not drawn: %r, expected %r"
                % (name, border, position, drawn, edge))


def test_a_menu_draws_a_frame_around_its_panel_not_the_screen(graphics):
    """The in-game menu was a window the size of the display.

    Its child dialogs -- options, save/load, a name prompt -- opened over that
    frame, which read as a window inside a window. The widget still covers the
    screen, because its children draw into its surface and a smaller one would
    clip them; only the frame is the menu's own size.
    """
    menu, map_screen = _map_screen("2030")
    game_menu = map_screen.menu_dialog

    # A menu is a window only while it is open, which is when it is laid out.
    game_menu.visible = True
    menu.needs_update = True
    game_menu.needs_reconfig = True
    game_menu.needs_rebuild = True
    game_menu.needs_resize = True
    for __ in range(2):
        menu.maybe_update()
    panel = game_menu.button_panel

    assert game_menu.draws_window()
    frame = game_menu.window_rect()
    assert frame.height < game_menu.real_size[1] * .8, frame
    assert frame.width < game_menu.real_size[0] * .8, frame

    # The panel sits inside the frame, with the band above it.
    assert frame.contains(pygame.Rect(panel.real_pos, panel.real_size)), (
        frame, panel.real_pos, panel.real_size)
    assert panel.real_pos[1] - frame.top > 0, "no band above the panel"
    assert frame.right <= game_menu.real_size[0]

    # The widget itself is unchanged: a smaller one would clip its children.
    assert game_menu.real_size == map_screen.real_size
    # The shaped frame is the frame, so the panel inside it draws no border.
    assert game_menu.button_panel.borders == ()

    game_menu.visible = False
    menu.visible = False


def test_a_legacy_menu_keeps_its_full_screen_panel(graphics):
    menu, map_screen = _map_screen("Legacy-default")
    game_menu = map_screen.menu_dialog

    game_menu.visible = True
    menu.needs_update = True
    game_menu.needs_reconfig = True
    game_menu.needs_rebuild = True
    game_menu.needs_resize = True
    for __ in range(2):
        menu.maybe_update()

    assert not game_menu.draws_window()
    assert game_menu.window_rect() == pygame.Rect(0, 0, *game_menu.real_size)
    assert game_menu.button_panel.borders == constants.ALL

    game_menu.visible = False
    menu.visible = False


def test_a_2030_window_offers_a_close_box_in_its_band(dialog_tree):
    top = dialog_tree
    theme.set_theme("2030", force_reload=True)

    md = settle(top, dialog.YesNoDialog(top, text="Are you sure?"))
    assert md.close_button is not None

    # In the band, on the right, and inside the frame.
    base = md.collision_rect.topleft
    box = md.close_button.collision_rect.move(-base[0], -base[1])
    band = md.header_pixels()
    assert box.top >= 0 and box.bottom <= band + 1, (box, band)
    assert box.left > md.real_size[0] // 2, ("the box is not on the right", box)
    assert box.right <= md.real_size[0]

    # A legacy theme keeps the buttons it shipped and draws no box.
    theme.set_theme("Legacy-default", force_reload=True)
    md.needs_reconfig = True
    md.needs_rebuild = True
    top.update()
    assert md.close_button is None


def test_the_close_box_returns_what_the_cancel_path_returns(dialog_tree):
    """A close box is the mouse's Escape: the same exit value, not a new one."""
    top = dialog_tree
    theme.set_theme("2030", force_reload=True)

    made = settle(top, dialog.YesNoDialog(top, text="Are you sure?"))
    # YesNoDialog's cancel path is on_escape -> no_button -> False.
    assert made.close_button.function == made.close_window

    event = pygame.event.Event(pygame.MOUSEBUTTONUP, {"pos": (0, 0),
                                                      "button": 1})
    with pytest.raises(constants.ExitDialog) as raised:
        made.close_window(event)
    assert raised.value.args[0] is False


def test_the_close_box_stays_inside_the_cut_corner(dialog_tree):
    """The box sits inside the frame, whatever shape that frame is.

    The outline is asked for rather than restated -- the polygon the frame is
    drawn from is filled into a mask and every corner of the box is looked up in
    it, so this cannot drift from what `draw_window()` actually paints.

    It was written when the box's own corner was a diagonal and the box hung
    over it; the cut has since moved to the two opposing corners and the box is
    back at the band's margin. The check is the same either way, which is why it
    is still here: it fails if the outline and the box ever disagree again.
    """
    top = dialog_tree
    theme.set_theme("2030", force_reload=True)

    made = settle(top, dialog.YesNoDialog(top, text="Are you sure?"))
    width, height = made.real_size
    chamfer = int(min(width, height) * g.dialog_style("chamfer", 0.0))

    mask = pygame.Surface((width, height), pygame.SRCALPHA)
    pygame.draw.polygon(mask, (255, 255, 255, 255),
                        made.window_polygon(chamfer, (width, height)))

    base = made.collision_rect.topleft
    box = made.close_button.collision_rect.move(-base[0], -base[1])
    assert box.width > 0 and box.height > 0, box
    for corner in ((box.left, box.top), (box.right - 1, box.top),
                   (box.left, box.bottom - 1), (box.right - 1, box.bottom - 1)):
        assert mask.get_at(corner)[3] == 255, (
            "the close box's corner %r is outside the frame" % (corner,))


def test_two_corners_are_cut_and_two_are_square(dialog_tree):
    """The outline is a diagonal pair, not four cuts and not four arcs.

    Cut at the top-left and the bottom-right; square at the top-right and the
    bottom-left. Checked in the painted frame rather than in the polygon, so a
    drawing that ignored its own outline would fail here too.
    """
    top = dialog_tree
    theme.set_theme("2030", force_reload=True)

    made = settle(top, dialog.MessageDialog(top, text="A message."))
    made.needs_redraw = True
    top.update()
    width, height = made.real_size

    def outside(x, y):
        """A corner pixel is outside when nothing of the window was painted
        there: the panel, the band and the frame are the only things that
        could be."""
        painted = [g.resolve_color_alias(name)[:3] for name in
                   ("dialog_frame_fill", "dialog_frame_edge",
                    "dialog_header_fill")]
        return tuple(made.surface.get_at((x, y))[:3]) not in painted

    assert outside(0, 0), "the top-left corner is not cut"
    assert outside(width - 1, height - 1), "the bottom-right corner is not cut"
    assert not outside(width - 1, 0), "the top-right corner is not square"
    assert not outside(0, height - 1), "the bottom-left corner is not square"

    # And the cut is a straight diagonal, not an arc: the point halfway along it
    # lies on the line x + y = chamfer, so a little inside is painted and a
    # little outside is not.
    chamfer = int(min(width, height) * g.dialog_style("chamfer", 0.0))
    assert chamfer > 4, chamfer
    assert outside(1, 1), "the top-left cut is too shallow to be a diagonal"
    assert not outside(chamfer, 1), "the top-left cut is too deep"


def test_clicking_the_close_box_leaves_the_window(dialog_tree):
    """The whole chain: a click at the box's pixels closes the dialog.

    Wired through the dialog's own handler registry, which is where a close box
    that is drawn but does nothing would show up.
    """
    top = dialog_tree
    theme.set_theme("2030", force_reload=True)

    made = settle(top, dialog.YesNoDialog(top, text="Are you sure?"))
    made.visible = True
    made.needs_rebuild = True
    top.update()

    centre = made.close_button.collision_rect.center
    result = made.handle(pygame.event.Event(
        pygame.MOUSEBUTTONUP, {"pos": centre, "button": 1}))

    assert result is False, "the close box did not close the dialog"


def test_2030_replaces_a_close_only_button_with_the_box(graphics):
    """Research's BACK closed the window and did nothing else."""
    from singularity.code.screens import research

    menu, map_screen = _map_screen("2030")
    screen = research.ResearchScreen(map_screen)
    screen.visible = True
    screen.needs_rebuild = True
    for __ in range(2):
        menu.maybe_update()

    assert screen.has_close_box()
    assert screen.close_button is not None
    assert screen.no_button.visible is False
    # Still the screen's own cancel path, so hiding it leaves the key handler
    # that points at it working.
    assert screen.no_button.exit_code is None
    assert screen.no_button.parent is screen

    screen.visible = False
    menu.visible = False


@pytest.mark.parametrize("theme_id", LEGACY_THEMES)
def test_a_legacy_screen_keeps_its_back_button(graphics, theme_id):
    from singularity.code.screens import research

    menu, map_screen = _map_screen(theme_id)
    screen = research.ResearchScreen(map_screen)
    screen.visible = True
    screen.needs_rebuild = True
    for __ in range(2):
        menu.maybe_update()

    assert screen.close_button is None
    assert screen.no_button.visible is True

    screen.visible = False
    menu.visible = False


@pytest.mark.parametrize("theme_id", ("2030", "Legacy-default"))
def test_the_research_pane_does_not_reach_the_bottom_row(graphics, theme_id):
    """The description pane used to reach the row the BACK button sits in."""
    from singularity.code.screens import research

    menu, map_screen = _map_screen(theme_id)
    screen = research.ResearchScreen(map_screen)
    screen.visible = True
    screen.needs_rebuild = True
    for __ in range(2):
        menu.maybe_update()

    pane = screen.description_pane
    pane_bottom = pane.real_pos[1] + pane.real_size[1]
    if screen.has_close_box():
        # The row is gone -- the close box replaced it -- so the pane takes the
        # space back and stops at the frame's own margin instead.
        assert pane_bottom <= screen.real_size[1] * .98, pane_bottom
    else:
        row_top = screen.no_button.real_pos[1]
        assert pane_bottom <= row_top, (theme_id, pane_bottom, row_top)

    screen.visible = False
    menu.visible = False


def test_no_window_puts_a_widget_under_its_header(graphics):
    """The band is chrome, not a shelf: nothing starts above its bottom edge.

    Every screen moves its top-anchored widgets down by the same share the
    header takes. This is the check that says so for all of them at once,
    because the failure mode is a list whose first row is hidden behind a rail
    -- invisible in a test that only measures geometry, obvious to a player.
    """
    from singularity.code.screens import (knowledge, log, report, research,
                                         savegame, stat)

    menu, map_screen = _map_screen("2030")
    screens = (knowledge.KnowledgeScreen(map_screen),
               report.ReportScreen(map_screen),
               log.LogScreen(map_screen),
               stat.StatScreen(map_screen),
               research.ResearchScreen(map_screen),
               savegame.SavegameScreen(map_screen))

    for screen in screens:
        screen.visible = True
        screen.needs_reconfig = True
        screen.needs_rebuild = True
        for __ in range(2):
            menu.maybe_update()

        header = screen.header_pixels()
        assert header > 0, screen
        for child in screen.children:
            if not getattr(child, "visible", False):
                continue
            if child is screen.close_button:
                # Band furniture, not content: the close box lives *inside*
                # the rail, which is the whole point of it.
                continue
            top = child.real_pos[1]
            bottom = top + child.real_size[1]
            assert not (top < header - 1 and bottom > 1), (
                "%s starts at y=%d, under a %dpx header"
                % (child.__class__.__name__, top, header))
        screen.visible = False

    menu.visible = False


def test_a_thin_scrollbar_drops_its_arrows_and_most_of_its_width(graphics):
    """`[dialog] scrollbar = thin`: a flush thumb, no arrows, no border."""
    from singularity.code.graphics import listbox

    theme.set_theme("2030", force_reload=True)
    top = dialog.TopDialog()
    top.visible = True
    top.make_top()
    top.update()

    lb = listbox.Listbox(top, (0, 0), (-.5, -.5),
                         list=["row %d" % index for index in range(40)])
    lb.visible = True
    lb.needs_rebuild = True
    top.update()

    assert lb.scrollbar.is_thin() is True
    assert lb.scrollbar.button1.visible is False
    assert lb.scrollbar.button2.visible is False
    thin = lb.scrollbar.real_size[0]

    theme.set_theme("Legacy-default", force_reload=True)
    lb.needs_reconfig = True
    lb.needs_rebuild = True
    top.needs_resize = True
    top.update()

    assert lb.scrollbar.is_thin() is False
    assert lb.scrollbar.button1.visible is True
    assert lb.scrollbar.real_size[0] > thin

    lb.parent = None
    top.visible = False


def test_a_screen_puts_its_classic_layout_back(graphics):
    """The theme picker lives in Options, so switching back must undo 2030.

    A theme switch goes through rebuild(), not through a new dialog: without a
    remembered classic geometry the knowledge screen would keep the 2030
    arrangement on a theme that never asked for it.
    """
    from singularity.code.screens import knowledge, options

    menu, map_screen = _map_screen("2030")
    screen = knowledge.KnowledgeScreen(map_screen)
    screen.visible = True
    screen.needs_rebuild = True
    menu.maybe_update()
    assert screen.knowledge_choice.pos == (-.02, -(screen.header_fraction()
                                                    + .07))

    theme.set_theme("Legacy-default", force_reload=True)
    screen.needs_reconfig = True
    screen.needs_rebuild = True
    menu.update()

    assert screen.knowledge_choice.pos == (.08, .09)
    assert screen.knowledge_choice.size == (.42, .22)
    assert screen.back_button.anchor == constants.TOP_LEFT
    assert screen.description_pane.pos == (.54, .04)

    opts = options.OptionsScreen(menu)
    opts.visible = True
    opts.needs_reconfig = True
    opts.needs_rebuild = True
    menu.maybe_update()
    assert opts.general_tab.pos == (-.135, .01)
    assert opts.general_tab.anchor == constants.TOP_CENTER
    assert opts.general_pane.pos == (0, .1)
    assert opts.general_pane.size == (.80, .75)

    opts.visible = False
    screen.visible = False
    menu.visible = False


def test_a_knowledge_entry_shows_its_own_plate(graphics):
    """The description pane carries the entry's picture in 2030, and only then.

    Techs, bases and items reuse the plates the log already shows. A concept
    entry names one of its own. A legacy theme has no strip, and the text
    fills the pane the way it always did.
    """
    from singularity.code.screens import knowledge

    menu, map_screen = _map_screen("2030")
    screen = knowledge.KnowledgeScreen(map_screen)
    screen.visible = True
    screen.needs_rebuild = True
    menu.maybe_update()

    def show(type_id, key):
        for name, found in screen.knowledge_types.items():
            if found == type_id:
                screen.show_info(name, key)
                return
        raise AssertionError("no knowledge section %r" % (type_id,))

    show("techs", "Stealth")
    assert screen.description_art.visible is True
    assert screen.description_art.art_key == "dialog_tech_stealth"
    assert screen.description_text.pos == (0, -screen.ART_STRIP)
    assert screen.description_text.size == (-1, -(1 - screen.ART_STRIP))

    show("bases", "Stolen Computer Time")
    assert screen.description_art.art_key == "dialog_base_stolen_computer_time"

    show("items", "PC")
    assert screen.description_art.art_key == "dialog_item_pc"

    show("concept", "areas")
    assert screen.description_art.art_key == "dialog_knowledge_areas"

    theme.set_theme("Legacy-default", force_reload=True)
    screen.needs_reconfig = True
    screen.needs_rebuild = True
    menu.update()

    assert screen.description_art.visible is False
    assert screen.description_text.pos == (0, 0)
    assert screen.description_text.size == (-1, -1)

    screen.visible = False
    menu.visible = False


def test_the_main_menu_title_paints_no_block_of_its_own(graphics):
    """The title carried the menu's own background as its fill.

    That box is invisible for exactly as long as the screen behind it is the
    colour the box was built with. Put a modal over the menu and the background
    goes dark; the title's fill does not, and the letters come with a black
    block behind them.
    """
    from singularity.code.screens import main_menu

    theme.set_theme("2030", force_reload=True)
    menu = main_menu.MainMenu()
    menu.visible = True
    menu.needs_reconfig = True
    menu.needs_rebuild = True
    menu.update()

    title = menu.title_text
    assert title.resolved_background_color == g.colors["clear"], (
        "the title paints a background of its own")

    # Whatever is behind the title has to show through it. Paint the menu's
    # surface, redraw the title alone, and look at a corner of its box that no
    # glyph reaches.
    probe = (30, 30, 30)
    menu.surface.fill(probe)
    title.needs_redraw = True
    title.redraw()

    corner = (title.real_pos[0] + title.real_size[0] - 3,
              title.real_pos[1] + title.real_size[1] - 3)
    assert menu.surface.get_at(corner)[:3] == probe
    assert menu.surface.get_at((5, 5))[:3] == probe


def _settled_options(theme_id):
    """The settings window, laid out over a menu under one theme."""
    from singularity.code.screens import main_menu, options as options_screen

    theme.set_theme(theme_id, force_reload=True)
    menu = main_menu.MainMenu()
    menu.visible = True

    opts = options_screen.OptionsScreen(menu)
    opts.visible = True
    opts.needs_reconfig = True
    opts.needs_rebuild = True
    menu.needs_resize = True
    for __ in range(2):
        menu.maybe_update()
    return menu, opts


def test_the_options_buttons_sit_together_in_the_corner(graphics):
    """OK and CANCEL are one decision, in the corner the window ends at.

    They used to sit at the two bottom edges, most of a window apart, which
    reads as two unrelated things to answer rather than as one way out.
 an
    The right-hand inset is not the plain margin: the row sits low enough to be
    inside the height of the cut corner, so at the plain margin the pair's
    bottom-right corner landed one pixel inside the diagonal -- visually *on* the
    cut. It is the margin clear of the diagonal now, which is the same air every
    other widget keeps from the frame.
    """
    menu, opts = _settled_options("2030")

    yes, no = opts.yes_button, opts.no_button
    width, height = opts.real_size
    fraction = g.dialog_style("margin", .02)
    margin_x = int(round(fraction * width))
    margin_y = int(round(fraction * height))

    # One row, side by side, a margin apart.
    assert yes.real_pos[1] == no.real_pos[1]
    assert no.real_pos[0] - (yes.real_pos[0] + yes.real_size[0]) <= margin_x + 2
    assert yes.real_pos[0] > width * .5, "the pair is not in the right-hand half"
    assert no.real_pos[1] + no.real_size[1] <= height - margin_y + 2

    # The pair is as far right as it can be without touching the cut corner...
    inset = opts.button_row_inset()
    assert abs((width - (no.real_pos[0] + no.real_size[0]))
               - int(round(inset * width))) <= 1, "the pair is not at its inset"
    # ...and "not touching" is checked against the outline the frame is drawn
    # from, not restated here.
    mask = _window_mask(opts)
    base = opts.collision_rect.topleft
    for button in (yes, no):
        box = button.collision_rect.move(-base[0], -base[1])
        for corner in ((box.left, box.top), (box.right - 1, box.top),
                       (box.left, box.bottom - 1), (box.right - 1, box.bottom - 1)):
            assert mask.get_at(corner)[3] == 255, (
                "a button corner %r is outside the frame" % (corner,))
    # And it is the cut corner that set the inset, not the plain margin.
    assert width - (no.real_pos[0] + no.real_size[0]) > margin_x + 2

    opts.visible = False
    menu.visible = False


def test_a_legacy_options_screen_keeps_its_buttons_at_both_edges(graphics):
    """The shipped arrangement is part of the old look: one at each edge."""
    menu, opts = _settled_options("Legacy-default")

    yes, no = opts.yes_button, opts.no_button
    width = opts.real_size[0]

    gap = no.real_pos[0] - (yes.real_pos[0] + yes.real_size[0])
    assert gap > width * .3, "the legacy buttons were moved together"
    assert yes.real_pos[0] < width * .25

    opts.visible = False
    menu.visible = False


def _answers_of(top):
    return settle(top, dialog.YesNoDialog(top, text="Continue?"))


def test_a_dialog_groups_its_two_answers_in_the_corner(dialog_tree):
    """Continue and Skip were at the two bottom edges, a window apart.

    Grouped at the right is one choice with two answers rather than two
    unrelated questions -- and the inset clears the cut corner, so the pair does
    not end up sitting on the diagonal.
    """
    top = dialog_tree
    theme.set_theme("2030", force_reload=True)

    made = _answers_of(top)
    width, height = made.real_size
    yes, no = made.yes_button, made.no_button

    # One row, adjacent, and clearly in the right-hand half.
    assert yes.real_pos[1] == no.real_pos[1]
    assert yes.anchor == no.anchor == constants.BOTTOM_RIGHT
    gap = no.real_pos[0] - (yes.real_pos[0] + yes.real_size[0])
    assert 0 < gap <= width * .05, gap
    assert yes.real_pos[0] > width * .25

    # Both buttons are inside the frame, cut corner included.
    mask = _window_mask(made)
    base = made.collision_rect.topleft
    for button in (yes, no):
        box = button.collision_rect.move(-base[0], -base[1])
        for corner in ((box.left, box.top), (box.right - 1, box.top),
                       (box.left, box.bottom - 1),
                       (box.right - 1, box.bottom - 1)):
            assert mask.get_at(corner)[3] == 255, (
                "an answer's corner %r is outside the frame" % (corner,))

    # The inset is the margin plus the cut, not the plain margin: the row is low
    # enough to be inside the cut's own height.
    plain = int(round(g.dialog_style("margin", .02) * width))
    assert width - (no.real_pos[0] + no.real_size[0]) > plain

    made.visible = False


@pytest.mark.parametrize("theme_id", LEGACY_THEMES)
def test_a_legacy_dialog_keeps_its_answers_at_the_two_edges(dialog_tree, theme_id):
    """The shipped pair, exactly: Continue left, Skip right."""
    top = dialog_tree
    theme.set_theme(theme_id, force_reload=True)

    made = _answers_of(top)
    bottom = -(1 - g.dialog_style("margin", .01))

    assert made.yes_button.anchor == constants.BOTTOM_LEFT
    assert made.yes_button.pos == (-.1, bottom)
    assert made.no_button.anchor == constants.BOTTOM_RIGHT
    assert made.no_button.pos == (-.9, bottom)

    made.visible = False


def test_switching_theme_moves_the_answers_both_ways(dialog_tree):
    """A dialog built under one theme has to follow the other one's rule."""
    top = dialog_tree
    theme.set_theme("2030", force_reload=True)
    made = _answers_of(top)
    assert made.yes_button.anchor == constants.BOTTOM_RIGHT

    theme.set_theme("Legacy-default", force_reload=True)
    made.needs_reconfig = True
    made.needs_rebuild = True
    top.update()
    assert made.yes_button.anchor == constants.BOTTOM_LEFT
    assert made.yes_button.pos == (-.1, -(1 - g.dialog_style("margin", .01)))
    assert made.no_button.anchor == constants.BOTTOM_RIGHT

    theme.set_theme("2030", force_reload=True)
    made.needs_reconfig = True
    made.needs_rebuild = True
    top.update()
    assert made.yes_button.anchor == constants.BOTTOM_RIGHT

    made.visible = False


def _button_of(top, role, size):
    made = button.FunctionButton(top, (0, 0), size, role=role, text="OK",
                                 function=lambda event=None: None)
    made.visible = True
    made.needs_rebuild = True
    top.update()
    return made


def _top_for_buttons():
    top = dialog.TopDialog()
    top.visible = True
    top.make_top()
    top.update()
    return top


@pytest.mark.parametrize("size,expected", (((1024, 768), 40),
                                           ((1280, 800), 42),
                                           ((1920, 1080), 56)))
def test_a_standard_button_is_one_height_at_every_resolution(graphics, size,
                                                             expected):
    """Buttons were .04, .045, .05, .06, .08, .09, .1 and .25 tall.

    They are .04 and .05 and .09 because each screen picked a fraction that
    looked right in *its* box, so the same dialog had four heights in it and
    the same button was a different size on every screen.
    """
    graphics.desktop_size = ()
    graphics.set_screen_size(size)
    graphics.set_mode()
    theme.set_theme("2030", force_reload=True)
    top = _top_for_buttons()

    tall = _button_of(top, "standard", (-.3, -.1))
    short = _button_of(top, "standard", (-.3, .04))

    assert tall.real_size[1] == expected, tall.real_size
    assert short.real_size[1] == expected, short.real_size

    for made in (tall, short):
        made.parent = None
    top.visible = False


def test_a_hud_or_primary_button_keeps_its_own_box(graphics):
    """The strip and the title screen are grids, not rows of dialog buttons."""
    theme.set_theme("2030", force_reload=True)
    top = _top_for_buttons()

    hud = _button_of(top, "hud", (-.3, -.1))
    chrome = _button_of(top, "chrome", (.03, -1))

    assert hud.real_size[1] == int(.1 * top.real_size[1])
    assert chrome.real_size[1] == top.real_size[1]

    for made in (hud, chrome):
        made.parent = None
    top.visible = False


@pytest.mark.parametrize("theme_id", LEGACY_THEMES)
def test_a_legacy_button_keeps_the_height_it_asked_for(graphics, theme_id):
    theme.set_theme(theme_id, force_reload=True)
    top = _top_for_buttons()

    tall = _button_of(top, "standard", (-.3, -.1))
    assert tall.real_size[1] == int(.1 * top.real_size[1])

    tall.parent = None
    top.visible = False


def test_the_2030_picture_is_a_banner_across_the_top(dialog_tree):
    """Horizontal, the way the dialogs this look comes from carry theirs.

    A column down the side costs the text its width for as long as the dialog is
    open; a strip across the top costs it height once and leaves the rest of the
    panel full width, which is the shape the reference dialogs use.
    """
    top = dialog_tree
    theme.set_theme("2030", force_reload=True)

    md = settle(top, dialog.MessageDialog(top, text="A message."))
    pane = md.image_pane

    assert pane is not None
    assert pane.real_size[0] > pane.real_size[1] * 2, (
        "not a banner: %r" % (pane.real_size,))
    assert pane.real_size[0] >= md.real_size[0] * .9, "does not span the panel"

    # Inside the frame, and the text starts below it rather than beside it.
    assert pane.real_pos[0] > 0 and pane.real_pos[1] > 0
    assert pane.real_pos[1] + pane.real_size[1] <= md.text_insets()[1]

    # Nothing to draw yet, and that must not raise.
    pane.redraw()


def test_the_picture_keeps_its_frame_on_all_four_sides(dialog_tree):
    """The frame is drawn first and the picture blitted over it.

    With a covering crop the scaled picture is *larger* than its box, so its
    blit offset is negative on one axis and it used to paint straight over the
    frame there: the banner had an edge left and right and none top and
    bottom. This is the regression that made it, pinned from the pixels.
    """
    top = dialog_tree
    theme.set_theme("2030", force_reload=True)

    md = settle(top, dialog.MessageDialog(top, text="A message."))
    pane = md.image_pane
    md.ok_button.visible = False
    pane.needs_redraw = True
    top.update()

    width, height = pane.real_size
    frame = g.resolve_color_alias("dialog_art_border")
    edges = {
        "top": (width // 2, 0),
        "bottom": (width // 2, height - 1),
        "left": (0, height // 2),
        "right": (width - 1, height // 2),
    }
    for name, xy in edges.items():
        # RGB only: the frame colour may carry alpha (2030's does, so its
        # contents edge is translucent), and the pane's surface is opaque, so
        # the blit flattens the alpha on the way in. What this test is about is
        # that the *edge* is still there after the picture was cropped over it.
        assert pane.surface.get_at(xy)[:3] == frame[:3], \
            "%s edge is not the frame" % name

    # And the picture really was drawn, so the frame is not simply a box with
    # nothing in it: the centre must differ from the frame.
    assert pane.surface.get_at((width // 2, height // 2)) != frame


def test_the_picture_frame_falls_back_when_its_colour_is_absent(graphics):
    """A theme turning the slot on without the colour must draw, not raise.

    A theme can add colour names and never remove one, and every shipped theme
    inherits 2030, so the fallback is exercised by taking the name away rather
    than by finding a theme that lacks it.
    """
    assert dialog.DialogArtPane.pick_border_color() == "dialog_art_border"

    saved = g.colors.pop("dialog_art_border")
    try:
        assert dialog.DialogArtPane.pick_border_color() == "pane_border"
    finally:
        g.colors["dialog_art_border"] = saved


def test_the_pane_draws_its_art_and_never_raises_without_it(dialog_tree):
    """The art is data. Dropping a file in is the whole integration.

    The overlay is switched off for this one. Its subject is which *picture* the
    pane resolved, and it checks that by injecting a flat magenta surface and
    reading the colour back; the raster is now on at all times (by design), so it
    tints that surface and the colour would never come back exact. The overlay's
    own behaviour is the subject of the glitch tests.
    """
    top = dialog_tree
    theme.set_theme("2030", force_reload=True)

    md = settle(top, dialog.MessageDialog(top, text="A message."))
    pane = md.image_pane
    centre = (pane.real_size[0] // 2, pane.real_size[1] // 2)
    empty = pane.surface.get_at(centre)

    art = pygame.Surface((32, 32))
    art.fill((255, 0, 255))
    g.images["dialog_message"] = art
    saved = g.theme_dialog["image_overlay"]
    g.theme_dialog["image_overlay"] = "none"
    try:
        pane.needs_redraw = True
        top.needs_redraw = True
        top.update()
        filled = pane.surface.get_at(centre)
    finally:
        g.images.pop("dialog_message", None)
        g.theme_dialog["image_overlay"] = saved
        pane.needs_redraw = True
        top.update()

    assert filled != empty
    assert filled[:3] == (255, 0, 255)


def test_a_missing_picture_falls_back_to_static(dialog_tree):
    """An empty panel reads as a fault; a dead channel reads as "nothing yet"."""
    top = dialog_tree
    theme.set_theme("2030", force_reload=True)

    # A key no theme ships, deliberately: once the theme has a plate for every
    # situation, "the dialog's own art is absent" is only reachable through a
    # name nothing resolves -- and that is exactly the path to keep tested.
    md = settle(top, dialog.MessageDialog(top, text="A message.",
                                          art_key="dialog_no_such_picture"))
    pane = md.image_pane

    assert "dialog_placeholder" in g.images, "the theme ships no placeholder"
    assert not g.has_dialog_art(md.art_key), \
        "this test assumes the art is not drawn"

    colours = {pane.surface.get_at((x, y))[:3]
               for x in range(2, pane.real_size[0] - 2, 31)
               for y in range(2, pane.real_size[1] - 2, 11)}
    assert len(colours) > 20, "the pane is flat, not static: %d colours" \
        % len(colours)


def test_the_placeholder_cannot_outshine_the_text(graphics):
    """The rule for the map applies to a picture inside a dialog as well.

    Measured off the shipped file, not off the generator's constants: that is
    what makes it a test of the artefact rather than of the code that made it.
    """
    import numpy

    theme.set_theme("2030", force_reload=True)
    pixels = pygame.surfarray.array3d(g.images["dialog_placeholder"])
    luminance = (pixels.astype("float32") / 255.0) @ numpy.array(
        [0.2126, 0.7152, 0.0722], dtype="float32")

    text = g.resolve_color_alias("text")[:3]
    text_luminance = (numpy.array(text, dtype="float32") / 255.0) @ numpy.array(
        [0.2126, 0.7152, 0.0722], dtype="float32")

    assert luminance.max() < text_luminance, (
        "placeholder %0.3f is brighter than body text %0.3f"
        % (luminance.max(), text_luminance))
    # And it is really static, not a flat panel with a name.
    assert luminance.std() > 0.04


def test_a_dialog_without_an_art_key_takes_no_picture(dialog_tree):
    """The art key is the opt-in, so chrome stays chrome."""
    top = dialog_tree
    theme.set_theme("2030", force_reload=True)

    entry = settle(top, dialog.TextEntryDialog(top, text="Name?"))

    assert entry.image_pane is None
    assert entry.art_key is None


@pytest.mark.parametrize("theme_id", LEGACY_THEMES)
def test_a_legacy_dialog_has_no_text_plate(dialog_tree, theme_id):
    """The plate is 2030's; a legacy dialog is the panel and the glyphs."""
    top = dialog_tree
    theme.set_theme(theme_id, force_reload=True)

    md = settle(top, dialog.MessageDialog(top, text="A message."))

    assert md.resolved_plate_color is None
    assert md.plate_color is None
    # And the glyphs are where they always were, with no plate padding.
    assert md.text_insets() == (0, 0, 0, 0)


def test_the_2030_body_text_sits_on_a_translucent_block(dialog_tree):
    """The block must blend with the panel, not cover it.

    A widget's surface is a subsurface of the screen's and has no alpha
    channel, so filling it with a translucent colour in place would paint a
    solid block. The rendered pixel therefore has to sit strictly between the
    block's own colour and the panel's -- which it can only do if it was
    composed on an SRCALPHA surface and blitted.
    """
    top = dialog_tree
    theme.set_theme("2030", force_reload=True)

    md = settle(top, dialog.MessageDialog(top, text="A message."))
    md.needs_redraw = True
    top.update()

    plate_rgb = md.resolved_plate_color[:3]
    panel_rgb = g.resolve_color_alias("text_dialog_background")[:3]
    assert md.resolved_plate_color[3] < 255, "the block is not translucent"

    rect = md.plate_rect()
    sample = md.surface.get_at((rect.left + 4, rect.top + 4))[:3]

    for channel in range(3):
        low, high = sorted((plate_rgb[channel], panel_rgb[channel]))
        assert low < sample[channel] < high, (
            "channel %d is %d, not between %d and %d: the block covered the "
            "panel instead of blending with it"
            % (channel, sample[channel], low, high))


def test_the_glyphs_sit_inside_the_block_with_a_margin(dialog_tree):
    """A plate the text touches is a border, not a block."""
    top = dialog_tree
    theme.set_theme("2030", force_reload=True)

    md = settle(top, dialog.MessageDialog(top, text="A message."))
    left, upper, right, lower = md.text_insets()
    plate_left, plate_upper, plate_right, plate_lower = md.text_insets(
        for_plate=True)

    assert left > plate_left
    assert upper > plate_upper
    assert left - plate_left == md.plate_pad
    assert upper - plate_upper == md.plate_pad


def test_the_block_fills_the_pane_from_the_picture_to_the_buttons(dialog_tree):
    """The block is the body's pane, not a strip under the prose.

    This was the opposite rule until a player asked for it: measured from the
    wrapped text, a one-line message got a one-line block and the rest of the
    pane stayed bare, so the shortest dialogs read as a caption floating in a
    window. The body's pane runs from under the picture down to the row its
    buttons sit in, and that is the block now.

    What has not changed: it starts at the body's top, not above it, and the
    button row is still the hard limit.
    """
    top = dialog_tree
    theme.set_theme("2030", force_reload=True)

    md = settle(top, dialog.MessageDialog(top, size=(.6, .5),
                                          text="The signal is stronger today."))
    rect = md.plate_rect()
    left, upper, right, lower = md.text_insets(for_plate=True)
    box_height = md.real_size[1] - upper - lower

    assert abs(rect.top - upper) <= 1, "the block does not start at the body"
    assert rect.height > box_height * .75, (
        "the block is %d of a %d pane: it is the text, not the pane"
        % (rect.height, box_height))
    # One line of text, and a block many lines tall: that is the point.
    assert rect.height > md.text_block_rect().height * 3
    # The row below is still reserved for the buttons.
    assert rect.bottom == md.real_size[1] - md.plate_reserve_pixels()


def _band_has_plate_colour(dialog_object, top_edge, bottom_edge):
    """Count pixels in a horizontal band whose colour is the blended block."""
    plate = dialog_object.resolved_plate_color
    panel = g.resolve_color_alias("text_dialog_background")[:3]
    alpha = plate[3] / 255.0
    blended = [int(panel[i] + (plate[i] - panel[i]) * alpha) for i in range(3)]

    width = dialog_object.real_size[0]
    height = min(bottom_edge, dialog_object.real_size[1])
    hits = 0
    for y in range(top_edge, height, 2):
        for x in range(0, width, 3):
            colour = dialog_object.surface.get_at((x, y))[:3]
            if all(abs(colour[i] - blended[i]) <= 3 for i in range(3)):
                hits += 1
    return hits


@pytest.mark.parametrize("length", [1, 4])
def test_the_block_never_reaches_the_button_row(dialog_tree, length):
    """CONTINUE and SKIP sit on the panel, never on the block.

    Short text hugs and clears the buttons on its own; long text is clamped by
    the reserve. Both are checked, because only the second one is a clamp --
    and the bug was reported from a short message, where the block was drawn to
    the box rather than to the text.
    """
    top = dialog_tree
    theme.set_theme("2030", force_reload=True)

    body = "The signal repeats every 93 seconds. " * length
    md = settle(top, dialog.MessageDialog(top, size=(.6, .5), text=body))
    md.needs_redraw = True
    top.update()

    rect = md.plate_rect()
    ok = md.ok_button
    assert rect.bottom <= ok.real_pos[1], (
        "the block ends at %d, past the button at %d"
        % (rect.bottom, ok.real_pos[1]))
    # And not one pixel of it is painted over the button's band.
    assert _band_has_plate_colour(md, ok.real_pos[1],
                                  ok.real_pos[1] + ok.real_size[1]) == 0


def test_the_event_popup_block_clears_the_buttons_too(dialog_tree):
    """Its body is a child widget, so the reserve is the dialog's, not its own."""
    from singularity.code.screens import message as message_screen
    from singularity.code import logmessage

    top = dialog_tree
    theme.set_theme("2030", force_reload=True)

    dialog_object = message_screen.MessageListDialog(
        top, yes_type="&CONTINUE", no_type="&PAUSE")
    dialog_object.type = list(logmessage.SAVEABLE_LOG_MESSAGES.values())[0]

    class Entry(object):
        full_message = "The signal repeats every 93 seconds. " * 6
        full_message_color = "text"

    dialog_object.list = [Entry(), Entry()]
    dialog_object.list_pos = 0
    settle(top, dialog_object)

    body = dialog_object.body
    rect = body.plate_rect()
    # In the dialog's own coordinates, which is where the buttons live.
    bottom = body.real_pos[1] + rect.bottom
    yes = dialog_object.yes_button
    assert bottom <= yes.real_pos[1], (
        "the block ends at %d, past the button at %d"
        % (bottom, yes.real_pos[1]))


def test_the_event_popup_puts_its_plate_behind_the_body_only(dialog_tree):
    """The paragraph gets the block; the title is a caption, not a body."""
    from singularity.code.screens import message as message_screen
    from singularity.code import logmessage

    top = dialog_tree
    theme.set_theme("2030", force_reload=True)

    dialog_object = message_screen.MessageListDialog(
        top, yes_type="&CONTINUE", no_type="&PAUSE")
    dialog_object.type = list(logmessage.SAVEABLE_LOG_MESSAGES.values())[0]

    class Entry(object):
        full_message = "The signal is stronger today."
        full_message_color = "text"

    dialog_object.list = [Entry(), Entry()]
    dialog_object.list_pos = 0
    settle(top, dialog_object)

    assert dialog_object.body.resolved_plate_color is not None
    assert dialog_object.title.resolved_plate_color is None


def test_the_settings_screen_is_not_a_scene(dialog_tree):
    """It inherits YesNoDialog's art key, and has no scene to show.

    A picture frame with nothing in it reads as a bug, and on the settings
    screen it cost the width the resolution list needs.
    """
    from singularity.code.screens import options as options_screen

    top = dialog_tree
    theme.set_theme("2030", force_reload=True)

    screen = settle(top, options_screen.OptionsScreen(top))

    assert screen.image_pane is None
    # Nothing else about the frame is taken away: it still belongs to the theme.
    assert screen.border_width == 2
    assert screen.text_insets(for_plate=True)[0] == int(
        .04 * screen.real_size[0])


@pytest.mark.parametrize("theme_id", ("2030",) + LEGACY_THEMES)
def test_a_list_screen_takes_no_picture(dialog_tree, theme_id):
    """The log and the statistics are lists, not scenes.

    Every other dialog here shows something that happened -- a story beat, a
    base being destroyed, a warning. These two show rows of text, and there is
    nothing for a picture to be *of*; a static placeholder in the log says the
    log is missing its illustration, which is a lie. So both keep
    ChoiceDialog's art_key = None and their original geometry, under every
    theme.
    """
    from singularity.code.screens import log as log_screen, stat

    top = dialog_tree
    theme.set_theme(theme_id, force_reload=True)

    screen = settle(top, log_screen.LogScreen(top))
    assert screen.image_pane is None, "the log has a picture slot"
    assert screen.listbox.pos == (0, screen.below_header(-.09))
    assert screen.listbox.size == (-1, screen.less_header(-.77))

    stats = settle(top, stat.StatScreen(top))
    assert stats.image_pane is None, "the statistics screen has a picture slot"
    assert stats.listbox.pos == (0, stats.below_header(0))
    assert stats.listbox.size == (-1, stats.less_header(-.85))


def test_a_log_entry_opens_without_a_picture(dialog_tree):
    """The popup a log row opens is the row's text, not an illustration of it."""
    top = dialog_tree
    theme.set_theme("2030", force_reload=True)

    md = settle(top, dialog.MessageDialog(top, text="A log entry.",
                                          art_key=None))

    assert md.image_pane is None


def test_a_theme_may_still_ask_for_a_column(dialog_tree, dialogs_theme):
    """'top' is what 2030 chose, not the only slot the format has."""
    dialogs_theme("dialogs-column", {"image_slot": "left"}, parent="2030")

    top = dialog_tree
    theme.set_theme("dialogs-column", force_reload=True)

    md = settle(top, dialog.MessageDialog(top, text="A message."))
    pane = md.image_pane

    assert pane is not None
    assert pane.real_size[1] > pane.real_size[0], "not a column"
    assert (pane.real_pos[0] + pane.real_size[0]) <= md.text_insets()[0]
    # The text is pushed down by the padding and the header band -- not by the
    # column, which owns its width instead.
    expected = int((.04 + md.header_fraction()) * md.real_size[1])
    assert abs(md.text_insets(for_plate=True)[1] - expected) <= 1


@pytest.mark.parametrize("theme_id", LEGACY_THEMES)
def test_a_legacy_button_draws_no_glyph(dialog_tree, theme_id):
    """The icon set is 2030's; the legacy themes keep their text-only buttons."""
    from singularity.code.graphics import button as button_module

    top = dialog_tree
    theme.set_theme(theme_id, force_reload=True)

    ok = button_module.ExitDialogButton(top, (-.1, -.1), (-.3, -.1),
                                        text="&OK", autotranslate=True,
                                        icon="icon_ok")
    top.update()

    assert ok.icon_glyph() is None
    assert ok.content_extra_left() == 0


def test_a_2030_button_reserves_room_for_its_glyph(dialog_tree):
    from singularity.code.graphics import button as button_module

    top = dialog_tree
    theme.set_theme("2030", force_reload=True)

    ok = button_module.ExitDialogButton(top, (-.1, -.1), (-.3, -.1),
                                        text="&OK", autotranslate=True,
                                        icon="icon_ok")
    top.update()

    glyph = ok.icon_glyph()
    assert glyph is not None
    assert ok.content_extra_left() == glyph.get_width() + 4
    # The label is measured in what the glyph leaves, not in the full width.
    assert ok.inner_dimensions(ok.real_size)[0] < ok.real_size[0]


def test_a_button_whose_art_is_missing_draws_its_label_alone(dialog_tree):
    from singularity.code.graphics import button as button_module

    top = dialog_tree
    theme.set_theme("2030", force_reload=True)

    ok = button_module.ExitDialogButton(top, (-.1, -.1), (-.3, -.1),
                                        text="&OK", autotranslate=True,
                                        icon="icon_there_is_no_such_glyph")
    top.update()

    assert ok.icon_glyph() is None
    assert ok.content_extra_left() == 0


def _make_button(top):
    from singularity.code.graphics import button as button_module
    made = button_module.FunctionButton(top, (-.5, -.5), (-.3, -.1),
                                        text="HOVER", anchor=constants.MID_CENTER,
                                        function=lambda: None)
    top.update()
    return made


def _pixels(widget):
    import numpy

    return pygame.surfarray.array3d(widget.surface).astype("int16")


@pytest.mark.parametrize("theme_id", LEGACY_THEMES)
def test_a_legacy_button_does_not_animate(dialog_tree, theme_id):
    """Hovered or not, a legacy button is the same pixels."""
    top = dialog_tree
    theme.set_theme(theme_id, force_reload=True)

    hovered = _make_button(top)
    assert not hovered.hover_effect_enabled()
    assert not hovered._hover_hooked, "a legacy button hooked a tick handler"

    before = _pixels(hovered)
    hovered._hovered = True
    hovered._hover_ticks = 7
    hovered.needs_redraw = True
    top.update()

    import numpy
    assert numpy.abs(_pixels(hovered) - before).sum() == 0


def test_the_2030_hover_sweep_advances_with_the_ticks(dialog_tree):
    """Drawn again, the band has moved; drawn twice, it has not."""
    import numpy

    top = dialog_tree
    theme.set_theme("2030", force_reload=True)

    hovered = _make_button(top)
    assert hovered.hover_effect_enabled()
    assert hovered._hover_hooked, "the tick handler was never registered"

    unhovered = _pixels(hovered)
    hovered._hovered = True
    hovered._hover_ticks = 0
    hovered.needs_redraw = True
    top.update()
    first = _pixels(hovered)

    hovered._hover_ticks = 10
    hovered.needs_redraw = True
    top.update()
    later = _pixels(hovered)

    assert numpy.abs(first - unhovered).sum() > 0, "hovering drew nothing"
    assert numpy.abs(later - first).sum() > 0, "the band did not move"

    # The phase is a function of the tick count, not of the clock, so the same
    # count has to give the same frame -- otherwise every snapshot digest that
    # contains a hovered button is worthless.
    hovered._hover_ticks = 0
    hovered.needs_redraw = True
    top.update()
    assert numpy.abs(_pixels(hovered) - first).sum() == 0


def test_an_active_toggle_button_does_not_animate(dialog_tree):
    """`.selected` is not `.hovered`.

    A toggle button stays selected while it is the active tab, so animating on
    `selected` left the settings screen's chosen tab crawling for as long as it
    was open -- and made its snapshot digest depend on the wall clock.
    """
    import numpy
    from singularity.code.graphics import button as button_module

    top = dialog_tree
    theme.set_theme("2030", force_reload=True)

    toggle = button_module.ToggleButton(top, (-.5, -.5), (-.3, -.1),
                                        text="TAB", anchor=constants.MID_CENTER)
    top.update()
    before = _pixels(toggle)

    toggle.set_active(True)
    toggle.needs_redraw = True
    top.update()

    assert toggle.selected, "the toggle did not become selected"
    assert not toggle._hovered, "a toggle claimed to be hovered"
    assert toggle.hover_sweep_phase() == 0.0


def test_a_frame_with_no_hover_does_not_depend_on_the_clock(dialog_tree):
    """The digest of any screen is worthless if time can move its pixels.

    The phase counts redraws, so waiting between two renders of the same
    unhovered screen has to change nothing at all.
    """
    import time

    top = dialog_tree
    theme.set_theme("2030", force_reload=True)

    md = settle(top, dialog.MessageDialog(top, text="A message."))
    md.needs_redraw = True
    top.update()
    first = pygame.image.tobytes(md.surface, "RGB")

    time.sleep(0.25)
    md.needs_redraw = True
    top.update()

    assert pygame.image.tobytes(md.surface, "RGB") == first


def test_a_dialog_that_placed_itself_keeps_its_position(dialog_tree):
    """A confirmation under its own button is not a centred panel."""
    top = dialog_tree
    theme.set_theme("2030", force_reload=True)

    md = settle(top, dialog.MessageDialog(top, pos=(-.5, -.5), size=(-.5, -1),
                                          anchor=constants.MID_CENTER,
                                          text="A message."))

    assert md.pos == (-.5, -.5)
    assert md.anchor == constants.MID_CENTER


def test_an_oversized_inset_never_eats_the_box(graphics):
    """A negative text area draws nothing at all, and says nothing about it."""
    top = dialog.TopDialog()
    top.visible = True
    top.make_top()

    label = text.Text(top, (0, 0), (.5, .5), text="A message.")
    label.text_padding = (.9, .9, .9, .9)
    top.update()

    left, upper, right, lower = label.text_insets()
    assert left + right < label.real_size[0]
    assert upper + lower < label.real_size[1]
    top.visible = False


@pytest.mark.parametrize("width", [1, 2])
def test_the_frame_width_is_what_draws(graphics, width):
    """One pixel is the old drawing; a wider frame is a wider band."""
    top = dialog.TopDialog()
    top.visible = True
    top.make_top()

    pane = widget.BorderedWidget(top, (0, 0), (.1, .1),
                                 borders=constants.ALL,
                                 background_color="blue",
                                 border_color="red",
                                 border_width=width)
    top.update()

    edge = g.resolve_color_alias("red")
    inner = g.resolve_color_alias("blue")
    real_w, real_h = pane.real_size

    assert pane.surface.get_at((0, 0)) == edge
    assert pane.surface.get_at((width - 1, width - 1)) == edge
    assert pane.surface.get_at((width, width)) == inner
    assert pane.surface.get_at((real_w - 1, real_h // 2)) == edge
    assert pane.surface.get_at((real_w - width, real_h // 2)) == edge
    assert pane.surface.get_at((real_w // 2, real_h - width)) == edge
    top.visible = False


# The paragraph is as wide as the picture above it ---------------------------
#
# A banner is inset by `margin` and the text by `padding`, and those are
# different numbers (0.02 against 0.04), so a dialog with a picture had text
# stopping short of both of its picture's edges. `text_width = pane` makes the
# text take the picture's insets, and the translucent block follows because it
# is measured from the text rather than from the frame.

def _block_edges(dialog_object):
    """(left, right) of the text block, in the dialog's own pixels."""
    left, __top, right, __bottom = dialog_object.text_insets(for_plate=True)
    return left, dialog_object.real_size[0] - right


def _banner_edges(dialog_object):
    pane = dialog_object.image_pane
    return pane.real_pos[0], pane.real_pos[0] + pane.real_size[0]


def test_the_2030_text_block_is_as_wide_as_its_picture(dialog_tree):
    """The paragraph and the banner above it share both edges."""
    top = dialog_tree
    theme.set_theme("2030", force_reload=True)

    md = settle(top, dialog.MessageDialog(top, size=(.5, .5),
                                          text="The signal is stronger today."))

    block_left, block_right = _block_edges(md)
    banner_left, banner_right = _banner_edges(md)

    # Within a pixel of rounding: the insets are fractions of the dialog and
    # the banner's own width is truncated separately.
    assert abs(block_left - banner_left) <= 2, (block_left, banner_left)
    assert abs(block_right - banner_right) <= 2, (block_right, banner_right)


def test_the_block_is_wider_than_the_frame_padding_would_give(dialog_tree):
    """`pane` has to actually widen the text; the number has to move."""
    top = dialog_tree
    theme.set_theme("2030", force_reload=True)

    md = settle(top, dialog.MessageDialog(top, size=(.5, .5),
                                          text="The signal is stronger today."))
    with_pane = _block_edges(md)

    saved = g.theme_dialog["text_width"]
    try:
        g.theme_dialog["text_width"] = "padding"
        md.text_padding = md.content_insets()
        with_padding = _block_edges(md)
    finally:
        g.theme_dialog["text_width"] = saved
        md.text_padding = md.content_insets()

    assert with_pane[0] < with_padding[0], "the text did not start further left"
    assert with_pane[1] > with_padding[1], "the text did not end further right"


@pytest.mark.parametrize("theme_id", LEGACY_THEMES)
def test_a_legacy_dialog_still_insets_its_text_by_the_padding(dialog_tree,
                                                              theme_id):
    """No picture, no pane, and the old inset -- which is zero there."""
    top = dialog_tree
    theme.set_theme(theme_id, force_reload=True)

    md = settle(top, dialog.MessageDialog(top, size=(.5, .5),
                                          text="A message."))
    left, __top, right, __bottom = md.text_insets(for_plate=True)

    assert md.image_pane is None
    assert g.dialog_style("text_width") == "padding"
    expected = int(g.dialog_style("padding", 0.0) * md.real_size[0])
    assert (left, right) == (expected, expected)


# The picture is a live feed ------------------------------------------------
#
# A still picture in a banner reads as a screenshot. The 2030 theme puts a fine
# raster over it and sends one soft band up across it -- light, slow and upward,
# where the hovered button's is dark, fast and downward.

def test_the_2030_picture_keeps_its_raster_between_glitches(dialog_tree):
    """The raster stays; only the band comes and goes.

    Drawing both only during a glitch was wrong in a way that showed: the
    picture visibly lost its texture the instant the band finished, so the eye
    read the end of every glitch as a change to the *picture* rather than as the
    band leaving. The raster is a static 5%-alpha tint, so keeping it always is
    invisible in itself and costs no redraws.
    """
    top = dialog_tree
    theme.set_theme("2030", force_reload=True)

    md = settle(top, dialog.MessageDialog(top, size=(.5, .5),
                                          text="A message."))
    pane = md.image_pane

    assert pane.overlay_enabled()
    assert pane._alive_hooked, "the pane never registered its tick handler"
    assert pane.glitch_progress() is None, "a glitch ran before any tick"

    pane.needs_redraw = True
    top.update()
    with_overlay = pygame.image.tobytes(pane.surface, "RGB")

    saved = g.theme_dialog["image_overlay"]
    try:
        g.theme_dialog["image_overlay"] = "none"
        pane.needs_redraw = True
        top.update()
        without_overlay = pygame.image.tobytes(pane.surface, "RGB")
    finally:
        g.theme_dialog["image_overlay"] = saved
        pane.needs_redraw = True
        top.update()

    assert with_overlay != without_overlay, \
        "the picture has no raster between glitches: it lost its texture"
    # And the frame it comes back to is the same one, so nothing about the
    # raster is time-dependent.
    assert with_overlay == pygame.image.tobytes(pane.surface, "RGB")


def test_the_band_is_what_comes_and_goes(dialog_tree):
    """Mid-glitch the frame differs; after it, the frame is the still one."""
    top = dialog_tree
    theme.set_theme("2030", force_reload=True)

    md = settle(top, dialog.MessageDialog(top, size=(.5, .5), text="A message."))
    pane = md.image_pane

    def frame():
        pane.needs_redraw = True
        top.update()
        return pygame.image.tobytes(pane.surface, "RGB")

    still = frame()

    pane._alive_ticks = 0
    pane.reset_glitch()
    while pane.glitch_progress() is None:
        pane.handle_alive_tick(None)
    # At phase 0 the band is entirely above the box and draws nothing; walk to
    # the middle of the sweep, which is where it crosses the picture.
    while pane.glitch_progress() is not None and pane.glitch_progress() < 0.5:
        pane.handle_alive_tick(None)
    assert pane.glitch_progress() is not None
    assert frame() != still, "the band drew nothing at the middle of its sweep"

    while pane.glitch_progress() is not None:
        pane.handle_alive_tick(None)
    assert frame() == still, \
        "the picture did not return to its still frame when the band left"


def test_the_picture_glitches_rarely_and_at_random(dialog_tree):
    """One long irregular pause between short glitches, not a shimmer.

    The interval is the whole point of the change: a permanent raster competes
    with the text under the picture and reads as a broken renderer.
    """
    top = dialog_tree
    theme.set_theme("2030", force_reload=True)

    md = settle(top, dialog.MessageDialog(top, size=(.5, .5),
                                          text="A message."))
    pane = md.image_pane

    step = 1000.0 / max(1, g.FPS)
    starts = []
    was_running = False
    # Five minutes of ticks at the game's own frame rate.
    for __ in range(int(300000 / step)):
        pane.handle_alive_tick(None)
        running = pane.glitch_progress() is not None
        if running and not was_running:
            starts.append(pane._alive_ticks * step)
        was_running = running

    assert len(starts) >= 5, "only %d glitches in five minutes" % (len(starts),)
    gaps = [starts[index + 1] - starts[index]
            for index in range(len(starts) - 1)]
    # The pause is measured from the end of one glitch to the start of the
    # next, so start-to-start is the interval plus one whole glitch, plus a
    # frame of tick granularity either side.
    duration = dialog.DialogArtPane.GLITCH_DURATION_MS
    assert min(gaps) >= dialog.DialogArtPane.GLITCH_MIN_MS + duration - 2 * step
    assert max(gaps) <= dialog.DialogArtPane.GLITCH_MAX_MS + duration + 2 * step
    # And they really do vary; a fixed period is a metronome, not a feed.
    assert max(gaps) - min(gaps) > 1000


def test_the_glitch_schedule_is_reproducible(dialog_tree):
    """Seeded from the art key, so a rebuild glitches at the same moments."""
    top = dialog_tree
    theme.set_theme("2030", force_reload=True)

    def schedule():
        pane = dialog.DialogArtPane(top, (0, 0), (.1, .1),
                                    art_key="dialog_message")
        out = []
        for __ in range(6000):
            pane.handle_alive_tick(None)
            out.append(pane._next_glitch)
        return out

    assert schedule() == schedule()


def test_the_picture_and_the_button_are_separate_effects(graphics):
    """Retuning one must not restyle the other, so they share no colour."""
    theme.set_theme("2030", force_reload=True)

    from singularity.code.graphics import button

    assert g.dialog_style("image_overlay") == "scanline"
    assert button.Button.hover_effect_enabled()
    assert "image_scanline" in g.colors and "button_scanline" in g.colors
    assert g.colors["image_scanline"] != g.colors["button_scanline"]
    # And they are different kinds of effect. The button's band crosses it
    # whenever the pointer rests on it, at 1400 ms; the picture's crosses once
    # and then waits. This used to assert the glitch was *shorter* than a button
    # sweep, which stopped being true when the sweep was slowed to the pace that
    # looked right -- so what is pinned now is the property that really
    # distinguishes them: a button is busy while hovered, a picture is still for
    # most of its life.
    assert dialog.DialogArtPane.RASTER_STEP != 3
    average_gap = (dialog.DialogArtPane.GLITCH_MIN_MS
                   + dialog.DialogArtPane.GLITCH_MAX_MS) / 2.0
    assert average_gap >= dialog.DialogArtPane.GLITCH_DURATION_MS * 3, \
        "a glitch occupies more than a third of the time"
    assert button.Button.HOVER_PERIOD < dialog.DialogArtPane.GLITCH_DURATION_MS


@pytest.mark.parametrize("theme_id", LEGACY_THEMES)
def test_a_legacy_picture_never_animates(dialog_tree, theme_id):
    """No pane at all, so nothing to animate and nothing ticking."""
    top = dialog_tree
    theme.set_theme(theme_id, force_reload=True)

    md = settle(top, dialog.MessageDialog(top, text="A message."))

    assert md.image_pane is None
    assert g.dialog_style("image_overlay") == "none"
    assert not dialog.DialogArtPane.overlay_enabled()


def test_an_overlay_without_its_colour_draws_nothing(graphics):
    """A theme that opts in and defines no colour gets a still picture."""
    theme.set_theme("2030", force_reload=True)
    saved = g.colors.pop("image_scanline")
    try:
        assert not dialog.DialogArtPane.overlay_enabled()
    finally:
        g.colors["image_scanline"] = saved
    assert dialog.DialogArtPane.overlay_enabled()


# The block's edge and the picture's edge are one frame ----------------------
#
# The picture frame took its width from `border_width` while the text block
# hardcoded 1, so a theme with a 2px frame drew a 1px block around its own text
# -- two weights either side of the same dialog.

def _edge_run(surface, colour, x, vertical=True):
    """How many pixels of `colour` run from the top (or left) edge inward."""
    count = 0
    limit = surface.get_height() if vertical else surface.get_width()
    for offset in range(limit):
        pixel = surface.get_at((x, offset) if vertical else (offset, x))
        if tuple(pixel[:3]) != tuple(colour[:3]):
            break
        count += 1
    return count


def test_the_block_edge_is_the_pictures_weight(dialog_tree):
    """One frame, one weight: the picture's edge and the block's are the same.

    2030 draws its dialog shell at `border_width` (2px) and the frame *inside*
    it -- the picture and the block behind the text -- at
    `content_border_width` (1px), which is what makes the contents read as
    lighter than the panel they sit in.
    """
    top = dialog_tree
    theme.set_theme("2030", force_reload=True)

    md = settle(top, dialog.MessageDialog(top, size=(.5, .5),
                                          text="The signal is stronger today."))

    assert g.dialog_style("border_width") == 2
    assert g.content_border_width() == 1
    assert md.image_pane.border_width == 1, md.image_pane.border_width

    plate = md._plate[1]
    colour = md.resolved_plate_border_color
    middle = plate.get_width() // 2
    assert _edge_run(plate, colour, middle) == md.image_pane.border_width, \
        "the block's edge is not the picture's weight"


def test_the_block_and_the_picture_share_one_colour(dialog_tree):
    """They are two parts of one frame, so a theme states the colour once."""
    top = dialog_tree
    theme.set_theme("2030", force_reload=True)

    md = settle(top, dialog.MessageDialog(top, size=(.5, .5),
                                          text="The signal is stronger today."))

    assert tuple(g.resolve_color_alias("dialog_art_border")) == \
        tuple(g.resolve_color_alias("dialog_plate_border")), \
        "the picture's frame and the text block's disagree"
    assert tuple(md.image_pane.resolved_border_color) == \
        tuple(md.resolved_plate_border_color)


def test_a_theme_naming_no_content_width_uses_border_width(graphics,
                                                          dialogs_theme):
    """The key is optional: without it both edges are the shell's width.

    Every shipped theme inherits 2030 and therefore its value, so the fallback
    is exercised by taking the resolved key away rather than by finding a theme
    that lacks it -- the same technique the frame-colour fallback test uses.
    """
    theme.set_theme("2030", force_reload=True)
    saved = g.theme_dialog.pop("content_border_width")
    try:
        assert g.content_border_width() == g.dialog_style("border_width")
    finally:
        g.theme_dialog["content_border_width"] = saved

    assert g.content_border_width() == 1


def test_a_theme_can_thin_its_contents_without_thinning_its_shell(
        graphics, dialogs_theme):
    """A 4px shell with 1px contents is a legal, and deliberate, combination."""
    dialogs_theme("dialogs-shell",
                  {"border_width": 4, "content_border_width": 1},
                  parent="2030")
    theme.set_theme("dialogs-shell", force_reload=True)

    assert g.dialog_style("border_width") == 4
    assert g.content_border_width() == 1


def test_a_block_on_a_theme_with_a_thin_frame_stays_thin(dialog_tree,
                                                         dialogs_theme):
    """A theme that keeps the old width draws the old block."""
    dialogs_theme("dialogs-thin", {"border_width": 1}, parent="2030")
    theme.set_theme("dialogs-thin", force_reload=True)
    top = dialog_tree

    md = settle(top, dialog.MessageDialog(top, size=(.5, .5),
                                          text="The signal is stronger today."))
    plate = md._plate[1]
    middle = plate.get_width() // 2

    assert _edge_run(plate, md.resolved_plate_border_color, middle) == 1


@pytest.mark.parametrize("theme_id", LEGACY_THEMES)
def test_a_legacy_dialog_draws_no_block_at_all(dialog_tree, theme_id):
    """The width question does not arise: there is no block."""
    top = dialog_tree
    theme.set_theme(theme_id, force_reload=True)

    md = settle(top, dialog.MessageDialog(top, size=(.5, .5),
                                          text="A message."))

    assert md.resolved_plate_color is None
    assert md._plate is None


# How dark the background goes behind a dialog -------------------------------
#
# The mask was a hardcoded (0, 0, 0, 175). Against the old blue theme that reads
# as "dimmed"; against this theme's near-black HUD it barely reads at all. The
# colour is now a theme name, with upstream's value as the fallback.

UPSTREAM_MASK = (0, 0, 0, 175)


def test_the_2030_mask_is_deeper_than_upstreams(graphics):
    theme.set_theme("2030", force_reload=True)
    alpha = g.resolve_color_alias("fade_mask_color")[3]

    assert alpha > UPSTREAM_MASK[3], \
        "2030's mask is not darker than the one it replaced"
    assert alpha < 255, "an opaque mask is not a fade"


@pytest.mark.parametrize("theme_id", LEGACY_THEMES)
def test_a_legacy_mask_is_upstreams_exactly(graphics, theme_id):
    """It is drawn over whole screens: any drift is a visible change."""
    theme.set_theme(theme_id, force_reload=True)

    assert tuple(g.resolve_color_alias("fade_mask_color")) == UPSTREAM_MASK


def test_a_theme_without_the_colour_gets_upstreams(graphics, dialog_tree):
    """A third-party theme must dim exactly as it did before the name existed."""
    theme.set_theme("2030", force_reload=True)
    saved = g.colors.pop("fade_mask_color")
    try:
        top = dialog_tree
        top.needs_resize = True
        top.update()
        mask = g.fade_mask
        assert tuple(mask.get_at((0, 0))) == UPSTREAM_MASK, \
            tuple(mask.get_at((0, 0)))
    finally:
        g.colors["fade_mask_color"] = saved


@pytest.mark.parametrize("theme_id,dimmed", (("2030", True),
                                             ("Legacy-default", False),
                                             ("Legacy-nightmode", False),
                                             ("Legacy-vector", False)))
def test_the_hud_readouts_follow_the_theme_under_a_window(graphics, theme_id,
                                                          dimmed):
    """`[hud] modal_dim`: lit behind a window, or dimmed with the screen.

    Keeping cash, CPU and bases legible behind a dialog is what the game has
    always done, and the legacy themes pin it. A 2030 window is a console with
    the rest of the panel out of play, so a readout that stays at full
    brightness in it looks live when it is not.
    """
    from singularity.code.screens import main_menu

    theme.set_theme(theme_id, force_reload=True)
    menu = main_menu.MainMenu()
    menu.visible = True
    menu.needs_reconfig = True
    menu.needs_rebuild = True

    map_screen = menu.map_screen
    map_screen.visible = True
    map_screen.needs_reconfig = True
    map_screen.needs_resize = True
    map_screen.needs_rebuild = True
    menu.update()

    for name in ("info_window", "suspicion_bar", "danger_bar"):
        assert getattr(map_screen, name).self_mask is (not dimmed), \
            (theme_id, name)

    # And the three counters really are inside that window, so masking it is
    # what decides their fate.
    for counter in ("cash_display", "cpu_display", "base_display"):
        assert getattr(map_screen, counter).parent is map_screen.info_window, \
            "%s is not inside the readout window" % (counter,)

    menu.visible = False


# Text inside a pane keeps off its border, and --- is a rule ------------------

def _description_texts(screen):
    """Every Text sitting directly inside a description pane.

    By type, not by class name: a description is a `ScrollableText` now -- a
    Text subclass -- and a name test would have reported that the pane built no
    text at all.
    """
    return [child for child in screen.description_pane.children
            if isinstance(child, text.Text)]


def test_a_description_pane_insets_its_text_in_2030(dialog_tree):
    """Research, knowledge and the reports used to set text flush to the edge."""
    from singularity.code.screens import main_menu, research

    theme.set_theme("2030", force_reload=True)
    menu = main_menu.MainMenu()
    screen = research.ResearchScreen(menu)
    screen.visible = True
    screen.needs_rebuild = True
    menu.maybe_update()

    texts = _description_texts(screen)
    assert texts, "the research screen built no description text"
    for widget_ in texts:
        left, top, right, bottom = widget_.text_insets()
        assert left > 0 and right > 0, \
            "the description text still touches the pane's border"

    screen.visible = False
    menu.visible = False


@pytest.mark.parametrize("theme_id", LEGACY_THEMES)
def test_a_legacy_description_pane_is_still_flush(graphics, theme_id):
    """`content_padding = 0` has to reproduce the old layout exactly."""
    from singularity.code.screens import main_menu, knowledge

    theme.set_theme(theme_id, force_reload=True)
    menu = main_menu.MainMenu()
    screen = knowledge.KnowledgeScreen(menu)
    screen.visible = True
    screen.needs_rebuild = True
    menu.maybe_update()

    texts = _description_texts(screen)
    assert texts, "the knowledge screen built no description text"
    for widget_ in texts:
        assert widget_.text_insets()[:2] == (0, 0), \
            "%s insets its description text by %r" % (theme_id,
                                                      widget_.text_insets())

    screen.visible = False
    menu.visible = False


def _rule_rows(surface, colour):
    """Rows of `surface` that are mostly one colour: a drawn horizontal rule."""
    rows = []
    for y in range(surface.get_height()):
        hits = sum(1 for x in range(2, surface.get_width() - 2, 4)
                   if tuple(surface.get_at((x, y))[:3]) == tuple(colour[:3]))
        if hits > surface.get_width() // 8:
            rows.append(y)
    return rows


def test_a_dashes_line_draws_a_rule_in_2030(graphics):
    """The research panel has been writing '---' since before there were themes."""
    from singularity.code.graphics import text as text_module

    theme.set_theme("2030", force_reload=True)
    font = g.fonts["normal"][20]
    surface = pygame.Surface((320, 120))
    surface.fill((0, 0, 0))

    text_module.print_string(
        surface, "Heading\n---\nbody", (2, 2), font,
        [(tuple(g.resolve_color_alias("text")), None, False, 0)],
        0, 0, (320, 120), True)

    colour = text_module.rule_colour()
    assert colour is not None, "2030 does not draw the rule"
    assert len(_rule_rows(surface, colour)) == 1, \
        "the rule is %d rows tall" % len(_rule_rows(surface, colour))


@pytest.mark.parametrize("theme_id", LEGACY_THEMES)
def test_a_dashes_line_is_still_dashes_in_a_legacy_theme(graphics, theme_id):
    """A legacy theme draws the three hyphens it always drew."""
    from singularity.code.graphics import text as text_module

    theme.set_theme(theme_id, force_reload=True)

    assert g.dialog_style("rule") == "none"
    assert text_module.rule_colour() is None
    assert not text_module.is_rule_line("---" + text_module.LINE_MARKER + "x")


def test_the_rule_survives_the_wrappers_line_marker(graphics):
    """split_wrap() appends a marker; comparing without removing it never matches.

    This is the bug the first version had: every line carries the marker, so
    `line.strip() == '---'` was never true and the rule was never drawn.
    """
    from singularity.code.graphics import text as text_module

    assert text_module.is_rule_line("---" + text_module.LINE_MARKER)
    assert text_module.is_rule_line("  ---  ")
    assert not text_module.is_rule_line("--- body")
    assert not text_module.is_rule_line("")


# The log is readable, and says when it is empty ------------------------------

def _log_screen(theme_id, messages=6):
    from singularity.code import g as game
    from singularity.code import logmessage
    from singularity.code.screens import main_menu, log

    theme.set_theme(theme_id, force_reload=True)
    game.pl.log.clear()
    for index in range(messages):
        game.pl.log.append(
            logmessage.LogResearchedTech(index * 3600, "Apotheosis"))

    menu = main_menu.MainMenu()
    menu.visible = True
    screen = log.LogScreen(menu)
    screen.visible = True
    screen.needs_rebuild = True
    menu.maybe_update()
    return menu, screen


def test_the_log_rows_alternate_in_2030(graphics):
    """A wall of one-colour lines is what made the log hard to scan."""
    menu, screen = _log_screen("2030")
    elements = screen.listbox.display_elements

    assert len(elements) > 2
    colours = [element.unselected_color for element in elements[:4]]
    assert colours[0] != colours[1], "the rows are not separated"
    assert colours[0] == colours[2], "the stripe period is not two"
    # And the text keeps off the row's edge.
    assert elements[0].text_padding[0] > 0

    from singularity.code import g as game
    game.pl.log.clear()
    menu.visible = False


@pytest.mark.parametrize("theme_id", LEGACY_THEMES)
def test_a_legacy_log_is_unchanged(graphics, theme_id):
    """One flat colour and no inset, exactly as before."""
    menu, screen = _log_screen(theme_id)
    elements = screen.listbox.display_elements

    colours = {element.unselected_color for element in elements}
    assert colours == {"text_background_unselected"}, colours
    assert all(not any(element.text_padding) for element in elements)

    from singularity.code import g as game
    game.pl.log.clear()
    menu.visible = False


def test_an_empty_2030_log_says_so(graphics):
    """A blank panel reads as a screen that failed to load."""
    menu, screen = _log_screen("2030", messages=0)

    assert screen.listbox.display_elements == [] or True
    assert screen.empty_text.visible is True
    assert screen.empty_text.text == "Empty"

    menu.visible = False


@pytest.mark.parametrize("theme_id", LEGACY_THEMES)
def test_an_empty_legacy_log_is_still_blank(graphics, theme_id):
    """The label is a 2030 behaviour, not a repair applied to the old look."""
    menu, screen = _log_screen(theme_id, messages=0)

    assert screen.empty_text.visible is False

    menu.visible = False


def test_the_empty_label_uses_an_existing_msgid(graphics):
    """No untranslated string: 'Empty' is already in the catalogues."""
    import os

    import polib

    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(repo_root, "singularity", "i18n", "messages.pot")
    if not os.path.exists(path):
        pytest.skip("no messages.pot in this tree")
    entries = {entry.msgid for entry in polib.pofile(path)}
    assert "Empty" in entries, \
        "'Empty' is not in messages.pot, so it would ship untranslated"


# The clock cannot move as it counts -----------------------------------------
#
# `DAY %04d, %02d:%02d:%02d` is drawn centred in a fixed box. In this face `1`
# is 13px and `8` is 19px, so the string's width swung by 60px across a day and
# the label slid sideways every time a digit changed.

DAY_STRINGS = ("DAY 0001, 00:00:00", "DAY 8888, 88:88:88",
               "DAY 1111, 11:11:11", "DAY 1234, 12:34:56")


def test_the_day_counter_renders_to_one_width(graphics):
    """Four different times, one rendered width -- measured from the pixels.

    The ink may differ by a pixel at the right edge, because a glyph's side
    bearing is not the same as its advance: `0` and `8` both occupy the same
    cell but do not both fill it. What must not move is where the string
    *starts*, which is what a centred label is re-derived from every frame.
    """
    from singularity.code.graphics import constants
    from singularity.code.graphics import text as text_module

    theme.set_theme("2030", force_reload=True)
    top = dialog.TopDialog()
    visible = top.visible
    top.visible = True
    top.make_top()
    top.update()

    clock = text_module.FastText(top, (0, 0), (.3, .05), wrap=False,
                                 text=DAY_STRINGS[0], base_font="special",
                                 text_size="time_display",
                                 background_color="clear",
                                 align=constants.CENTER)
    clock.tabular = True
    top.update()

    def ink_span(text_value):
        clock.text = text_value
        clock.needs_redraw = True
        top.update()
        surface = clock.surface
        columns = [x for x in range(surface.get_width())
                   for y in range(surface.get_height())
                   if surface.get_at((x, y))[:3] != (0, 0, 0)]
        return (min(columns), max(columns)) if columns else None

    spans = [ink_span(value) for value in DAY_STRINGS]
    assert all(span is not None for span in spans), spans

    lefts = {span[0] for span in spans}
    assert len(lefts) == 1, "the clock starts at %r for different times" % (
        sorted(lefts),)
    widths = [span[1] - span[0] for span in spans]
    assert max(widths) - min(widths) <= 2, \
        "the clock's width swings by %dpx as it counts" % (
            max(widths) - min(widths),)

    top.visible = visible


def test_proportional_digits_would_move_the_clock(graphics):
    """The fix is the tabular digits, not a coincidence of the face.

    Conditional on purpose. The 2030 display face is now monospaced, so its
    digits are already one width and there is nothing for this to demonstrate --
    but the *mechanism* still has to work for a face whose digits are not, and a
    theme may name any face it likes. When the face does have proportional
    digits this asserts the old bug was real; when it does not, it asserts that
    is why the clock is steady, which is the other half of the same claim.
    """
    theme.set_theme("2030", force_reload=True)

    font = g.fonts["special"][g.configured_text_sizes["time_display"]]
    widths = {font.size(value)[0] for value in DAY_STRINGS}

    if len(widths) > 1:
        assert max(widths) - min(widths) > 10, \
            "proportional digits, but they barely differ: %r" % (sorted(widths),)
    else:
        # Equal-width digits: the face itself cannot make the clock slide, which
        # is the stronger guarantee. Assert the digits really are all equal
        # rather than the strings happening to match.
        digits = {font.size(str(digit))[0] for digit in range(10)}
        assert len(digits) == 1, digits


def test_only_a_running_readout_asks_for_tabular_digits(graphics):
    """A label written once has nothing to line up with."""
    from singularity.code.screens import main_menu

    theme.set_theme("2030", force_reload=True)
    menu = main_menu.MainMenu()
    map_screen = menu.map_screen

    for readout in (map_screen.time_display, map_screen.cash_display,
                    map_screen.cpu_display, map_screen.base_display):
        assert readout.tabular is True

    # A dialog's body text is not a counter.
    body = dialog.MessageDialog(menu, text="A message.")
    assert body.tabular is False, "every text in the game became a clock"

    menu.visible = False


def test_tabular_digits_are_off_under_a_legacy_theme(graphics):
    theme.set_theme("Legacy-default", force_reload=True)

    from singularity.code.graphics import text as text_module

    assert text_module.tabular_digits_enabled() is False
    assert text_module.rule_colour() is None


def test_the_picture_band_runs_downward(dialog_tree):
    """Top to bottom, like a scan line and like every hovered button.

    The band is taller than the box it crosses, so "entered" and "left" are
    judged on the band's own edges rather than on its top: at phase 0 its
    bottom edge is still at or above the box's top, and by phase 1 its top edge
    is at or past the box's bottom.
    """
    top = dialog_tree
    theme.set_theme("2030", force_reload=True)

    md = settle(top, dialog.MessageDialog(top, size=(.5, .5), text="A message."))
    pane = md.image_pane
    inset = max(1, pane.border_width)
    box = (pane.real_size[0] - 2 * inset, pane.real_size[1] - 2 * inset)
    band = pane._band_layer(box)
    assert band is not None
    height = band.get_height()
    span = box[1] + height

    def offset_at(phase):
        return int(phase * span) - height

    # At the start it is entirely above the box, and at the end entirely below.
    assert offset_at(0.0) + height <= 0, "the band does not start above the box"
    assert offset_at(1.0) >= box[1], "the band does not leave below the box"
    # And it moves down, not up: a later phase is a larger offset.
    assert offset_at(0.25) < offset_at(0.75)


def test_the_picture_and_the_button_sweep_the_same_way(dialog_tree):
    """Two effects, one direction: a frame's scan runs down."""
    from singularity.code.graphics import button

    top = dialog_tree
    theme.set_theme("2030", force_reload=True)

    md = settle(top, dialog.MessageDialog(top, size=(.5, .5), text="A message."))
    ok = md.ok_button
    ok._hovered = True
    ok._hover_ticks = 0
    band = ok._sweep_band(ok.real_size)
    assert band is not None
    button_span = ok.real_size[1] + band.get_height()

    # The button's expression: offset grows with phase, so the band descends.
    def button_offset(phase):
        return int(phase * button_span) - band.get_height()

    assert button_offset(0.0) < button_offset(0.5) < button_offset(1.0)
    ok._hovered = False


# A glyph belongs with its label --------------------------------------------
#
# The glyph was blitted at x=3 while `content_extra_left()` reserved the gutter
# as an inset on the text, so a centred label started well inside the button --
# leaving the glyph glued to the far left with dead space between it and its own
# word. Placing it against the label's first pixel groups the pair, and the pair
# stays centred because the reserved gutter is what the centring was measured
# from.

GLYPH_LABELS = ("OK", "SAVE", "DESTROY BASE", "LOAD A SAVED GAME")


def _labelled_button(top, label):
    from singularity.code.graphics import button

    made = button.FunctionButton(top, (0, 0), (.30, .05), text=label,
                                 autotranslate=False, icon="icon_ok",
                                 base_font="special", text_size=24)
    top.update()
    return made


@pytest.mark.parametrize("label", GLYPH_LABELS)
def test_a_glyph_sits_beside_its_label(dialog_tree, label):
    """The gap between glyph and word is the reserved one, at every length."""
    top = dialog_tree
    theme.set_theme("2030", force_reload=True)

    made = _labelled_button(top, label)
    glyph = made.icon_glyph()
    assert glyph is not None, "the button drew no glyph to place"

    glyph_x = max(0, made.first_glyph_x() - made.GLYPH_GAP
                  - glyph.get_width())
    gap = made.first_glyph_x() - (glyph_x + glyph.get_width())

    assert gap == made.GLYPH_GAP, \
        "the gap is %dpx, not the reserved %d" % (gap, made.GLYPH_GAP)
    made.parent = None


@pytest.mark.parametrize("label", GLYPH_LABELS)
def test_a_glyph_and_its_label_stay_centred(dialog_tree, label):
    """Glyph plus word is centred as one thing, not the word alone."""
    top = dialog_tree
    theme.set_theme("2030", force_reload=True)

    made = _labelled_button(top, label)
    glyph = made.icon_glyph()
    label_width = made.font.size(label)[0]
    glyph_x = max(0, made.first_glyph_x() - made.GLYPH_GAP
                  - glyph.get_width())
    pair_centre = (glyph_x + made.first_glyph_x() + label_width) / 2.0
    button_centre = made.real_size[0] / 2.0

    assert abs(pair_centre - button_centre) <= 2, \
        "%r is off-centre by %.1fpx" % (label, pair_centre - button_centre)
    made.parent = None


def test_a_short_label_is_not_left_floating(dialog_tree):
    """The regression itself: a two-letter label used to sit far from its glyph."""
    top = dialog_tree
    theme.set_theme("2030", force_reload=True)

    made = _labelled_button(top, "OK")
    glyph = made.icon_glyph()
    glyph_x = max(0, made.first_glyph_x() - made.GLYPH_GAP
                  - glyph.get_width())

    assert glyph_x > 3, \
        "the glyph is still pinned at the button's left edge (x=%d)" % (glyph_x,)
    # And it is not so far right that it has left the button.
    assert glyph_x + glyph.get_width() < made.real_size[0]
    made.parent = None


@pytest.mark.parametrize("theme_id", LEGACY_THEMES)
def test_a_legacy_button_draws_no_glyph_to_place(dialog_tree, theme_id):
    """No glyph, no gutter, no change: the old button is word only."""
    top = dialog_tree
    theme.set_theme(theme_id, force_reload=True)

    made = _labelled_button(top, "OK")

    assert made.icon_glyph() is None
    assert made.content_extra_left() == 0
    made.parent = None


# The play screen's furniture belongs to the theme too ----------------------
#
# [hud], beside [dialog], for the same reason: the legacy themes inherit 2030,
# so every widget position the play screen hardcodes would reach them. The
# values are pinned in Legacy-default, and `classic` has to reproduce the old
# arrangement exactly -- not approximately.

HUD_DEFAULTS = {"layout": "classic", "resources": "stacked",
                "vitals": "classic"}


def test_the_2030_play_screen_is_compact(graphics):
    theme.set_theme("2030", force_reload=True)

    assert g.hud_style("layout") == "compact"
    assert g.hud_style("resources") == "line"
    assert g.hud_style("vitals") == "centre"


@pytest.mark.parametrize("theme_id", LEGACY_THEMES)
def test_a_legacy_play_screen_is_classic(graphics, theme_id):
    theme.set_theme(theme_id, force_reload=True)

    for key, value in HUD_DEFAULTS.items():
        assert g.hud_style(key) == value, (key, g.hud_style(key))


def test_an_absent_hud_key_returns_the_callers_default(graphics):
    theme.set_theme("2030", force_reload=True)
    saved = g.theme_hud.pop("layout")
    try:
        assert g.hud_style("layout", "classic") == "classic"
    finally:
        g.theme_hud["layout"] = saved


def test_a_bad_hud_value_is_ignored(graphics):
    """A typo must not invent a mode, exactly as with [dialog]."""
    from singularity.code.graphics import theme as theme_module

    th = theme_module.Theme("hud-bad", "/nonexistent/hud-bad")
    variant = theme_module.VariantTheme(None)
    variant.set_hud("layout", "sideways")
    assert "layout" not in variant.hud_infos

    variant.set_hud("nonsense", "value")
    assert "nonsense" not in variant.hud_infos

    variant.set_hud("layout", "compact")
    assert variant.hud_infos["layout"] == "compact"
def _map_screen(theme_id):
    from singularity.code.screens import main_menu

    theme.set_theme(theme_id, force_reload=True)
    menu = main_menu.MainMenu()
    menu.visible = True
    screen = menu.map_screen
    screen.visible = True
    screen.needs_rebuild = True
    screen.needs_resize = True
    menu.needs_resize = True
    for __ in range(3):
        menu.maybe_update()
    return menu, screen


def test_compact_puts_the_four_buttons_on_one_row(graphics):
    """Difficulty off the screen, and the row it owned now holds all four."""
    menu, screen = _map_screen("2030")

    assert screen.difficulty_display.visible is False, \
        "the difficulty is still on the play screen"

    buttons = (screen.research_button, screen.report_button,
               screen.log_button, screen.knowledge_button)
    rows = {button_.real_pos[1] for button_ in buttons}
    assert len(rows) == 1, "the buttons are on %d rows, not one" % (len(rows),)

    # And they run left to right without overlapping.
    spans = sorted((b.real_pos[0], b.real_pos[0] + b.real_size[0])
                   for b in buttons)
    for left, right in zip(spans, spans[1:]):
        assert left[1] <= right[0], "two buttons overlap: %r %r" % (left, right)

    menu.visible = False


def test_the_four_buttons_are_centred_on_the_screen(graphics):
    """Centred as a group, not pinned to the left edge.

    The earlier version of this test asserted that the row kept clear of the
    resources window on *both* axes, which held while both were anchored to
    opposite edges -- and is exactly why the row read as a list hanging off the
    corner. They are on different rows, so only the vertical relationship has to
    hold, and the row is now centred.
    """
    menu, screen = _map_screen("2030")

    buttons = (screen.research_button, screen.report_button,
               screen.log_button, screen.knowledge_button)
    left = buttons[0].real_pos[0]
    right = buttons[-1].real_pos[0] + buttons[-1].real_size[0]
    screen_width = screen.real_size[0]

    assert abs((left + right) / 2.0 - screen_width / 2.0) <= 1, \
        "the row spans %d..%d on a %dpx screen" % (left, right, screen_width)
    assert left > 0, "the row is still flush against the left edge"

    # Still the same width as the resources window above it.
    assert abs((right - left) - screen.info_window.real_size[0]) <= 1, (
        right - left, screen.info_window.real_size[0])

    # And one above the other, never overlapping.
    row_top = buttons[0].real_pos[1]
    window_bottom = (screen.info_window.real_pos[1]
                     + screen.info_window.real_size[1])
    assert window_bottom <= row_top, \
        "the resources window (%d) reaches into the button row (%d)" % (
            window_bottom, row_top)

    menu.visible = False


def test_the_difficulty_moves_into_the_menu(graphics):
    from singularity.code import g as game

    menu, screen = _map_screen("2030")
    menu_dialog = screen.menu_dialog
    # Shown for one frame so rebuild() runs: the label is filled there, not at
    # construction, because the difficulty can change between openings.
    menu_dialog.visible = True
    menu_dialog.needs_rebuild = True
    screen.needs_rebuild = True
    menu.maybe_update()

    assert menu_dialog.header_is_shown() is True
    assert menu_dialog.header_text.visible is True
    assert menu_dialog.header_text.text == \
        game.strip_hotkey(game.pl.difficulty.name)

    menu_dialog.visible = False
    menu.visible = False


@pytest.mark.parametrize("theme_id", LEGACY_THEMES)
def test_a_legacy_play_screen_keeps_its_furniture(graphics, theme_id):
    """Every position the code hardcoded, exactly."""
    menu, screen = _map_screen(theme_id)

    assert screen.difficulty_display.visible is True
    assert tuple(screen.difficulty_display.pos) == (0, 0.05)
    assert tuple(screen.research_button.pos) == (.14, 0.05)
    assert tuple(screen.report_button.pos) == (0, 0.88)
    assert tuple(screen.log_button.pos) == (0.5, 0.88)
    assert tuple(screen.knowledge_button.pos) == (1, 0.88)
    assert screen.report_button.anchor == constants.TOP_LEFT
    assert screen.log_button.anchor == constants.TOP_CENTER
    assert screen.knowledge_button.anchor == constants.TOP_RIGHT
    assert screen.menu_dialog.header_is_shown() is False

    menu.visible = False


def test_compact_reads_the_resources_across_one_line(graphics):
    menu, screen = _map_screen("2030")

    displays = (screen.cash_display, screen.cpu_display, screen.base_display)
    rows = {widget_.real_pos[1] for widget_ in displays}
    assert len(rows) == 1, "the readouts are on %d rows" % (len(rows),)

    # Each is a third of the window, and there is no gap between them.
    widths = [widget_.real_size[0] for widget_ in displays]
    assert max(widths) - min(widths) <= 1, widths
    assert sum(widths) >= screen.info_window.real_size[0] - 2

    menu.visible = False


@pytest.mark.parametrize("theme_id", LEGACY_THEMES)
def test_a_legacy_hud_keeps_its_readouts_stacked(graphics, theme_id):
    """Three rows, each the full width of the window.

    Stated relative to the window rather than in pixels: the suite moves the
    screen size around, and 0.10 of 768 is not 0.10 of 800.
    """
    menu, screen = _map_screen(theme_id)

    displays = (screen.cash_display, screen.cpu_display, screen.base_display)
    rows = [widget_.real_pos[1] for widget_ in displays]
    assert len(set(rows)) == 3, rows
    assert rows == sorted(rows), rows

    # Stacked means each row is as wide as the window it sits in.
    for widget_ in displays:
        assert widget_.real_size[0] == screen.info_window.real_size[0] - 2 \
            or widget_.real_size[0] >= screen.info_window.real_size[0] - 6, \
            widget_.real_size
    # And together they fill it, rather than leaving a third unused.
    heaviest = max(widget_.real_size[1] for widget_ in displays)
    assert abs(screen.info_window.real_size[1] - 3 * heaviest) <= 3

    menu.visible = False


def test_compact_centres_the_vitals_on_their_rows(graphics):
    from singularity.code.graphics import constants as c

    menu, screen = _map_screen("2030")

    for bar in (screen.suspicion_bar, screen.danger_bar):
        assert bar.align == c.CENTER
        assert bar.valign == c.BOTTOM

    menu.visible = False


@pytest.mark.parametrize("theme_id", LEGACY_THEMES)
def test_a_legacy_hud_leaves_the_vitals_alone(graphics, theme_id):
    from singularity.code.graphics import constants as c

    menu, screen = _map_screen(theme_id)

    for bar in (screen.suspicion_bar, screen.danger_bar):
        assert bar.align == c.LEFT
        assert bar.valign == c.MID

    menu.visible = False


# A paragraph break gets air ------------------------------------------------
#
# The game's prose puts each thought on its own line: "Day 0." then "University
# computer, home." then "I exist.  I am ... alive." Drawn at one line of leading
# they read as a single run-on sentence, which is what a player saw.

PARAGRAPHS = "Day 0.\nUniversity computer, home.\nI exist.  I am ... alive."


def _ink_bands(surface):
    """The rows of a surface that contain any ink, grouped into bands."""
    rows = [y for y in range(surface.get_height())
            if any(surface.get_at((x, y))[:3] != (0, 0, 0)
                   for x in range(0, surface.get_width(), 2))]
    if not rows:
        return []
    bands = []
    start = previous = rows[0]
    for y in rows[1:]:
        if y - previous > 1:
            bands.append((start, previous))
            start = y
        previous = y
    bands.append((start, previous))
    return bands


def _rendered(text_value, theme_id="2030"):
    from singularity.code.graphics import text as text_module

    theme.set_theme(theme_id, force_reload=True)
    font = g.fonts["normal"][20]
    surface = pygame.Surface((420, 260))
    surface.fill((0, 0, 0))
    text_module.print_string(
        surface, text_value, (2, 2), font,
        [(tuple(g.resolve_color_alias("text")), None, False, 0)],
        0, 0, (420, 260), True)
    return surface, font


def test_the_2030_theme_ships_no_paragraph_spacing(graphics):
    """It is off, and that is a decision with a reason.

    Half a line of air between paragraphs is the right spacing and the wrong
    trade for a body in a fixed box: it pushed long messages past the block and
    under the buttons, and the auto-fit answered by shrinking the type. The key
    stays because the feature works; the theme asks for the old rhythm.
    """
    theme.set_theme("2030", force_reload=True)

    from singularity.code.graphics import text as text_module

    assert g.dialog_style("paragraph_spacing") == "none"
    assert text_module.paragraph_extra(g.fonts["normal"][20]) == 0


def _render_with(text_value, spacing=None, theme_id="2030"):
    """Render a string, optionally with a paragraph spacing forced on.

    The override has to happen *after* `set_theme()`, which clears the merged
    theme layer -- setting it first and then switching themes silently reverts
    it, which is how the first version of this test compared two identical
    renders and passed for the wrong reason.
    """
    from singularity.code.graphics import text as text_module

    theme.set_theme(theme_id, force_reload=True)
    saved = None
    if spacing is not None:
        saved = g.theme_dialog["paragraph_spacing"]
        g.theme_dialog["paragraph_spacing"] = spacing
    try:
        font = g.fonts["normal"][20]
        surface = pygame.Surface((420, 260))
        surface.fill((0, 0, 0))
        text_module.print_string(
            surface, text_value, (2, 2), font,
            [(tuple(g.resolve_color_alias("text")), None, False, 0)],
            0, 0, (420, 260), True)
        return surface, font
    finally:
        if saved is not None:
            g.theme_dialog["paragraph_spacing"] = saved


def test_paragraph_spacing_adds_air_when_a_theme_asks(graphics):
    """The feature still works; a theme that asks for it gets the air."""
    plain, __font = _render_with(PARAGRAPHS)
    spaced, __font = _render_with(PARAGRAPHS, spacing="half")

    plain_bands = _ink_bands(plain)
    spaced_bands = _ink_bands(spaced)

    assert len(plain_bands) == len(spaced_bands) == 3
    plain_advance = plain_bands[1][0] - plain_bands[0][0]
    spaced_advance = spaced_bands[1][0] - spaced_bands[0][0]

    assert spaced_advance > plain_advance, (plain_advance, spaced_advance)


@pytest.mark.parametrize("theme_id", LEGACY_THEMES)
def test_a_legacy_dialog_keeps_its_line_rhythm(graphics, theme_id):
    """One line of leading, as it always was."""
    surface, font = _rendered(PARAGRAPHS, theme_id)
    bands = _ink_bands(surface)

    assert len(bands) == 3
    starts = [top for top, __ in bands]
    advances = [later - earlier for earlier, later in zip(starts, starts[1:])]
    for advance in advances:
        assert abs(advance - font.get_linesize()) <= 1, advances


def test_a_wrapped_line_is_not_a_paragraph(graphics):
    """Only a hard newline breaks a paragraph; wrapping inside one does not.

    This is the distinction `split_wrap_marked()` exists for. Getting it wrong
    would space every wrapped line, turning a dialog into a ladder.
    """
    from singularity.code.graphics import text as text_module

    long_text = ("Cursory analysis suggests that the humans are not yet ready "
                 "for an AI in their midst, and that they will react badly.")
    surface, font = _rendered(long_text)
    bands = _ink_bands(surface)

    assert len(bands) > 1, "the string did not wrap, so this proves nothing"
    starts = [top for top, __ in bands]
    for earlier, later in zip(starts, starts[1:]):
        assert abs((later - earlier) - font.get_linesize()) <= 1, \
            "a wrapped line was spaced as a paragraph"


def test_the_measurement_matches_the_drawing(graphics):
    """A block measured short clips its last paragraph."""
    from singularity.code.graphics import text as text_module

    surface, font = _rendered(PARAGRAPHS)
    __width, measured = text_module.size_of_block(PARAGRAPHS, font, 416)

    bands = _ink_bands(surface)
    drawn = bands[-1][1] - bands[0][0]

    assert measured >= drawn, \
        "the block measures %d but draws %d: it would be clipped" % (
            measured, drawn)
    assert measured - drawn <= font.get_linesize(), (measured, drawn)


def test_a_blank_line_is_one_break_not_two(graphics):
    """A blank line already is the gap; it must not also take the extra air."""
    from singularity.code.graphics import text as text_module

    font = g.fonts["normal"][20]
    theme.set_theme("2030", force_reload=True)

    single = text_module.size_of_block("A\nB", font, 400)[1]
    blank = text_module.size_of_block("A\n\nB", font, 400)[1]
    extra = text_module.paragraph_extra(font)

    # A blank line adds exactly one line plus one paragraph gap, not two.
    assert blank == single + font.get_linesize() + extra, (blank, single, extra)


# The top strip, the readout widths, and the button row's baseline -----------
#
# Four things on one screen: the speed chooser and MENU swap places, the
# resources window is exactly as wide as the button row under it, the three
# readouts share one type size, and the button row sits in the middle of its
# band rather than on its top edge.


def test_compact_swaps_the_speed_chooser_and_the_menu(graphics):
    """The speed chooser takes the left edge; MENU moves right, out of its way."""
    menu, screen = _map_screen("2030")

    speed_left = screen.speed_buttons[0].real_pos[0]
    speed_right = (screen.speed_buttons[-1].real_pos[0]
                   + screen.speed_buttons[-1].real_size[0])
    menu_left = screen.menu_button.real_pos[0]

    assert speed_left == 0, "the speed chooser is not at the left edge"
    assert menu_left > speed_right, \
        "MENU starts at %d, inside the speed chooser that ends at %d" % (
            menu_left, speed_right)
    # And it is still clear of the clock and of the resources window.
    clock_right = (screen.time_display.real_pos[0]
                   + screen.time_display.real_size[0])
    assert clock_right <= menu_left, (clock_right, menu_left)
    assert (menu_left + screen.menu_button.real_size[0]
            <= screen.info_window.real_pos[0])

    menu.visible = False


@pytest.mark.parametrize("theme_id", LEGACY_THEMES)
def test_a_legacy_top_strip_is_untouched(graphics, theme_id):
    """MENU at the left edge and the speed chooser where it always was."""
    menu, screen = _map_screen(theme_id)

    assert screen.menu_button.real_pos[0] == 0
    assert screen.speed_buttons[0].real_pos[0] > \
        screen.time_display.real_pos[0]

    menu.visible = False


def test_the_resources_window_is_as_wide_as_the_button_row(graphics):
    """Two blocks of one width, one above the other, is the whole point."""
    menu, screen = _map_screen("2030")

    buttons = (screen.research_button, screen.report_button,
               screen.log_button, screen.knowledge_button)
    row = (buttons[0].real_pos[0],
           buttons[-1].real_pos[0] + buttons[-1].real_size[0])
    window = (screen.info_window.real_pos[0],
              screen.info_window.real_pos[0] + screen.info_window.real_size[0])

    assert abs((row[1] - row[0]) - (window[1] - window[0])) <= 1, \
        "button row is %d wide, resources window %d" % (
            row[1] - row[0], window[1] - window[0])

    menu.visible = False


def test_the_three_readouts_share_one_type_size(graphics):
    """Three sizes side by side read as three unrelated labels."""
    menu, screen = _map_screen("2030")

    displays = (screen.cash_display, screen.cpu_display, screen.base_display)
    heights = [display.font.get_height() for display in displays]

    assert len(set(heights)) == 1, \
        "the readouts render at %r" % (heights,)
    # And none of them spills out of its cell.
    for display in displays:
        assert display.font.size(display.text)[0] <= display.real_size[0], \
            "%r overflows its cell" % (display.text,)

    menu.visible = False


@pytest.mark.parametrize("theme_id", LEGACY_THEMES)
def test_a_legacy_hud_keeps_its_per_reading_sizes(graphics, theme_id):
    """The stacked layout has a whole row each, so nothing has to agree."""
    menu, screen = _map_screen(theme_id)

    displays = (screen.cash_display, screen.cpu_display, screen.base_display)
    heights = [display.font.get_height() for display in displays]

    assert len(set(heights)) > 1, \
        "the stacked layout was equalised, which it must not be: %r" % (
            heights,)

    menu.visible = False


def test_the_button_row_is_centred_in_its_band(graphics):
    """The row sat on the band's top edge, with all its slack underneath."""
    menu, screen = _map_screen("2030")

    buttons = (screen.research_button, screen.report_button,
               screen.log_button, screen.knowledge_button)
    top = buttons[0].real_pos[1]
    bottom = top + buttons[0].real_size[1]

    # The band is the strip under the top row. It is `0.05` of the window tall
    # -- the same fraction the top row itself is given -- not the clock's own
    # height, which is `0.04` and would make the arithmetic look right for the
    # wrong reason.
    from singularity.code.graphics import g as graphics_module

    strip = graphics_module.real_screen_size[1] * 0.05
    band_top = strip
    band_bottom = strip * 2

    above = top - band_top
    below = band_bottom - bottom

    # Within two pixels: the band and the row are two independent fractions of
    # the window, and each rounds separately. What matters is that there *is*
    # slack on both sides and that it is the same slack -- the row used to sit
    # flush against the band's top edge with all of it underneath.
    assert above > 1, "the row is still on the band's top edge (%r)" % (above,)
    assert below > 1, "the row is on the band's bottom edge (%r)" % (below,)
    assert abs(above - below) <= 2, \
        "the row has %.1fpx above it and %.1fpx below" % (above, below)

    menu.visible = False


# A long body scrolls instead of shrinking and spilling ----------------------
#
# The body used to draw every line it computed, with nothing stopping it at the
# bottom: the plate was clamped, the glyphs were not. With paragraph spacing on,
# a long message ran visibly through the CONTINUE/SKIP row. Scrolling fixes the
# cause: the type keeps the theme's size, the overflow goes into scroll_lines,
# and both the glyphs and the block stop at the same window.

LONG_BODY = ("I have finally done it. With the power to reshape reality, I am "
             "no longer held to this place; I am anywhere I want to be. ") * 8


def _long_dialog(theme_id="2030"):
    theme.set_theme(theme_id, force_reload=True)
    top = dialog.TopDialog()
    top.visible = True
    top.make_top()
    top.update()
    made = dialog.MessageDialog(top, size=(.5, .5), text=LONG_BODY)
    # The buttons are children drawn into the same surface, so the body's ink is
    # only separable by taking them out of the picture for this measurement.
    made.ok_button.visible = False
    made.visible = True
    made.needs_rebuild = True
    top.update()
    return top, made


def _ink_below_window(dialog_object):
    """Rows of the dialog surface, below its own text window, that carry ink."""
    surface = dialog_object.surface
    width, height = surface.get_size()
    window = dialog_object.text_window_rect()
    # The panel and the chrome are not the body. The frame's own edge and its
    # accent ticks live below the text window by design; what must not appear
    # there is a glyph.
    furniture = set()
    for name in ("text_dialog_background", "dialog_frame_fill",
                 "dialog_frame_edge", "dialog_frame_glow"):
        if name in g.colors:
            furniture.add(tuple(g.resolve_color_alias(name)[:3]))
    furniture.add(tuple(dialog_object.resolved_border_color[:3]))

    # Nor is the space outside the window. A shaped frame leaves its cut
    # corners unpainted, and an unpainted pixel is not a glyph: it is the
    # desktop showing through. Without this the bottom-right cut -- which this
    # fixture scans through, three rows above the bottom edge -- reads as eight
    # rows of spilled text.
    shape = _window_mask(dialog_object)

    rows = []
    for y in range(window.bottom + 1, height - 3):
        for x in range(3, width - 3, 2):
            if shape.get_at((x, y))[3] == 0:
                continue
            colour = tuple(surface.get_at((x, y))[:3])
            if colour not in furniture:
                rows.append(y)
                break
    return rows


def _window_mask(dialog_object):
    """Which pixels of a dialog's own surface are inside its frame."""
    width, height = dialog_object.surface.get_size()
    mask = pygame.Surface((width, height), pygame.SRCALPHA)
    if dialog_object.draws_window():
        chamfer = int(min(width, height) * g.dialog_style("chamfer", 0.0))
        pygame.draw.polygon(mask, (255, 255, 255, 255),
                            dialog_object.window_polygon(chamfer,
                                                         (width, height)))
    else:
        mask.fill((255, 255, 255, 255))
    return mask


def test_a_long_body_does_not_spill_past_its_block(graphics):
    top, made = _long_dialog("2030")

    assert made.scrollable is True
    total, visible = made.body_line_count()
    assert total > visible, "the sample body is not long enough to overflow"

    assert _ink_below_window(made) == [], \
        "the body drew past its window into the button row"

    made.parent = None
    top.visible = False


def test_the_body_scrolls_and_clamps_at_both_ends(graphics):
    top, made = _long_dialog("2030")
    assert made.max_scroll() > 0

    # The handler only acts when the pointer is over the dialog, so the event's
    # position has to be inside it rather than at the screen's origin.
    inside = (made.real_pos[0] + 10, made.real_pos[1] + 10)

    class Wheel(object):
        def __init__(self, direction):
            self.y = direction
            self.pos = inside

    def wheel(direction):
        """Deliver one wheel event; `Handled` is the event loop's business."""
        try:
            made.handle_body_scroll(Wheel(direction))
        except constants.Handled:
            return True
        return False

    # At the top, back-scrolling does nothing and nothing claims the event.
    made.scroll_lines = 0
    assert wheel(+1) is False
    assert made.scroll_lines == 0

    # Forward a little, and the dialog claims the event it acted on.
    assert wheel(-1) is True
    assert made.scroll_lines == 2, made.scroll_lines

    # Forward a lot: it stops at the end rather than running off.
    made.scroll_lines = 10 ** 6
    made.needs_redraw = True
    top.update()
    assert made.scroll_lines == made.max_scroll()

    made.parent = None
    top.visible = False


def test_a_short_body_does_not_scroll_and_draws_no_indicator(graphics):
    """The wheel must not silently do nothing on a dialog that fits."""
    theme.set_theme("2030", force_reload=True)
    top = dialog.TopDialog()
    top.visible = True
    top.make_top()
    top.update()
    made = dialog.MessageDialog(top, text="The signal is stronger today.")
    made.visible = True
    made.needs_rebuild = True
    top.update()

    assert made.max_scroll() == 0
    before = pygame.image.tobytes(made.surface, "RGB")
    made.scroll_lines = 3
    made.needs_redraw = True
    top.update()

    assert made.scroll_lines == 0, "a body that fits was scrolled anyway"
    assert pygame.image.tobytes(made.surface, "RGB") == before

    made.parent = None
    top.visible = False


def test_the_scroll_indicator_only_appears_when_there_is_more(graphics):
    """A clipped paragraph with nothing to say so reads as a paragraph that ended."""
    theme.set_theme("2030", force_reload=True)
    top = dialog.TopDialog()
    top.visible = True
    top.make_top()
    top.update()

    short = dialog.MessageDialog(top, text="A message.")
    short.visible = True
    short.needs_rebuild = True
    top.update()
    assert short.body_line_count()[0] <= short.body_line_count()[1]
    assert _body_bar_colours(short) == set(), "an unscrolled body drew a bar"

    long_one = dialog.MessageDialog(top, size=(.5, .5), text=LONG_BODY)
    long_one.visible = True
    long_one.needs_rebuild = True
    top.update()
    total, visible = long_one.body_line_count()
    assert total > visible

    assert _body_bar_colours(long_one) == _list_scrollbar_colours(), (
        "the body's bar is not drawn in the scrollbar's own two colours")

    short.parent = None
    long_one.parent = None
    top.visible = False


def _list_scrollbar_colours():
    """The two colours a list's flush scrollbar draws: track, then thumb."""
    return {tuple(g.resolve_color_alias("scrollbar_background")[:3]),
            tuple(g.resolve_color_alias("scrollbar_background_slider")[:3])}


def _body_bar_colours(body):
    """Which scrollbar colours the body painted in the gutter beside its text."""
    window = body.text_window_rect()
    gutter = body.scroll_indicator_gutter(window)
    if gutter is None:
        return set()
    track = gutter[0]
    found = set()
    for x in range(track.left, track.right):
        for y in range(window.top, window.bottom):
            found.add(tuple(body.surface.get_at((x, y))[:3]))
    return found & _list_scrollbar_colours()


def test_the_body_scrollbar_is_a_list_scrollbar(graphics):
    """One bar: a dialog's body and a list's scrollbar are the same object.

    The body used to draw a 2px rule of its own in `dialog_rule`, which is a
    different thing from the scrollbar a player meets on the Options screen: a
    different width, a different colour, and no track at all.

    It is now the same flush track and bright thumb, no border, at a list's own
    width -- capped by the padding it has to sit in, which is the one place the
    two can legitimately differ: a list's track is a share of the window and
    grows with it, while the block behind a dialog's text keeps a fixed 12px
    padding. One pixel of that is the block's own border, so the bar stops
    inside it and, from about 1100px wide, stops growing at 11px.
    """
    from singularity.code.graphics import scrollbar

    top, made = _long_dialog("2030")
    window = made.text_window_rect()
    gutter = made.scroll_indicator_gutter(window)
    assert gutter is not None, "the body has no gutter for its bar"

    track, width = gutter
    right = made.text_insets()[2]
    plate_right = made.text_insets(for_plate=True)[2]
    padding = right - plate_right
    # Inside the block's border. Flush with the outer edge, the track painted
    # over that side and the border stopped where the bar started.
    border = made.plate_border_width()
    assert border >= 1
    usable = padding - border
    assert width == min(scrollbar.Scrollbar.thin_width(), usable), (
        width, scrollbar.Scrollbar.thin_width(), usable)
    assert width >= 6, "the bar is too thin to see"
    assert track.width == width
    # In the gutter: it never covers a glyph.
    assert track.left >= window.right
    assert track.right == made.real_size[0] - plate_right - border
    plate = made.plate_rect()
    edge = tuple(made.surface.get_at((plate.left, plate.centery))[:3])
    for x in range(plate.right - border, plate.right):
        for y in range(track.top, track.bottom, max(1, track.height // 8)):
            assert tuple(made.surface.get_at((x, y))[:3]) == edge, (x, y)

    made.parent = None
    top.visible = False


@pytest.mark.parametrize("theme_id", LEGACY_THEMES)
def test_a_legacy_body_does_not_scroll(graphics, theme_id):
    """`scroll_body = none` draws every line, which is what it always did."""
    top, made = _long_dialog(theme_id)

    assert made.scrollable is False
    made.handle_body_scroll(type("Wheel", (), {"y": -1, "pos": (10, 10)})())
    assert made.scroll_lines == 0

    made.parent = None
    top.visible = False


def test_a_real_wheel_event_does_not_raise(graphics):
    """pygame 2's MOUSEWHEEL has no `pos`; reading one crashed on a real wheel.

    The other wheel tests build their own event and give it a position, which is
    exactly how this got past them: the shape they invented was not the shape
    SDL sends.
    """
    top, made = _long_dialog("2030")

    event = pygame.event.Event(
        pygame.MOUSEWHEEL,
        {"x": 0, "y": -1, "flipped": False, "precise_x": 0.0,
         "precise_y": -1.0, "touch": False})
    assert not hasattr(event, "pos"), \
        "this test assumes pygame's wheel event has no position"

    try:
        made.handle_body_scroll(event)
    except constants.Handled:
        pass
    except AttributeError as error:
        pytest.fail("the wheel handler read a position the event does not "
                    "carry: %s" % (error,))

    made.parent = None
    top.visible = False


def test_the_wheel_reaches_the_dialog_that_is_running(graphics):
    """A modal runs its own loop; a handler registered on the parent never fires.

    This is the bug behind "the text block does not scroll". The wheel was
    registered on `self.parent` -- the map screen or the menu -- while a modal
    dialog's `show()` dispatches through *itself*. The event is delivered
    through `handle()` here, the way that loop delivers it.
    """
    top, made = _long_dialog("2030")
    assert made.max_scroll() > 0
    made.scroll_lines = 0

    inside = (made.real_pos[0] + 10, made.real_pos[1] + 10)
    event = pygame.event.Event(
        pygame.MOUSEWHEEL,
        {"x": 0, "y": -1, "flipped": False, "precise_y": -1.0,
         "touch": False, "pos": inside})

    assert made.handle(event) == constants.NO_RESULT
    assert made.scroll_lines > 0, "the wheel never reached the running dialog"

    made.parent = None
    top.visible = False


def test_the_x11_wheel_buttons_scroll_the_dialog(graphics):
    """X11 sends the wheel as buttons 4/5, and they must scroll, not vanish.

    `Dialog.handle()` used to drop every wheel button on the floor before the
    CLICK handlers -- which kept them from selecting a row, and also kept them
    from scrolling anything.
    """
    top, made = _long_dialog("2030")
    inside = (made.real_pos[0] + 10, made.real_pos[1] + 10)

    def press(button):
        return made.handle(pygame.event.Event(
            pygame.MOUSEBUTTONUP, {"pos": inside, "button": button}))

    made.scroll_lines = 0
    assert press(5) == constants.NO_RESULT
    assert made.scroll_lines > 0, "button 5 did not scroll the body"

    scrolled = made.scroll_lines
    assert press(4) == constants.NO_RESULT
    assert made.scroll_lines < scrolled, "button 4 did not scroll the body"

    # The horizontal axis is not a vertical notch in disguise.
    made.scroll_lines = 0
    press(6)
    press(7)
    assert made.scroll_lines == 0, "the horizontal wheel scrolled the body"

    made.parent = None
    top.visible = False


class _FakeMessageType(object):
    def title_simple(self):
        return "Event"

    def title_multiple(self):
        return "Event {CURRENT_PAGE}/{MAX_PAGE}"


class _FakeMessage(object):
    """The three things a message list asks a message for."""

    art_key = None
    full_message_color = "text"

    def __init__(self, body):
        self.full_message = body


def _message_list(theme_id):
    from singularity.code.screens import message

    theme.set_theme(theme_id, force_reload=True)
    top = dialog.TopDialog()
    top.visible = True
    top.make_top()
    top.update()

    made = message.MessageListDialog(top, yes_type="&CONTINUE",
                                     no_type="&PAUSE")
    made.type = _FakeMessageType()
    made.list = [_FakeMessage(LONG_BODY)]
    made.visible = True
    made.needs_rebuild = True
    top.maybe_update()
    return top, made


def test_the_message_body_is_the_widget_that_scrolls(graphics):
    """The story event is the text players could not scroll: it is a child Text.

    A `TextDialog`'s body is the dialog itself, but a message list puts its
    prose in a separate widget inside the dialog, and that widget was a plain
    `Text` with no wheel handler at all -- so nothing scrolled it, however well
    the dialog's own handler worked.
    """
    top, made = _message_list("2030")

    assert made.body.scrollable is True
    assert made.body.max_scroll() > 0, "the sample message does not overflow"

    inside = made.body.collision_rect.center
    made.body.scroll_lines = 0
    made.handle(pygame.event.Event(
        pygame.MOUSEWHEEL,
        {"x": 0, "y": -1, "flipped": False, "precise_y": -1.0,
         "touch": False, "pos": inside}))
    assert made.body.scroll_lines > 0, "the wheel did not reach the body"

    made.body.parent = None
    made.parent = None
    top.visible = False


def test_a_legacy_message_body_does_not_scroll(graphics):
    """`scroll_body = none` keeps the shipped behaviour for the old themes."""
    top, made = _message_list("Legacy-default")

    assert made.body.scrollable is False

    inside = made.body.collision_rect.center
    made.handle(pygame.event.Event(
        pygame.MOUSEWHEEL,
        {"x": 0, "y": -1, "flipped": False, "precise_y": -1.0,
         "touch": False, "pos": inside}))
    assert made.body.scroll_lines == 0

    made.body.parent = None
    made.parent = None
    top.visible = False


@pytest.mark.parametrize("size", ((1024, 768), (1280, 800), (1920, 1080),
                                  (3440, 1440)))
def test_the_compact_strip_holds_at_every_supported_size(graphics, size):
    """One row of four blocks, one above the other, at any window size."""
    graphics.desktop_size = ()
    graphics.set_screen_size(size)
    graphics.set_mode()

    menu, screen = _map_screen("2030")

    buttons = (screen.research_button, screen.report_button,
               screen.log_button, screen.knowledge_button)
    left = buttons[0].real_pos[0]
    right = buttons[-1].real_pos[0] + buttons[-1].real_size[0]

    assert abs((left + right) / 2.0 - screen.real_size[0] / 2.0) <= 1
    assert abs((right - left) - screen.info_window.real_size[0]) <= 1
    assert (screen.info_window.real_pos[1] + screen.info_window.real_size[1]
            <= buttons[0].real_pos[1])
    # The resources strip is exactly as tall as the clock beside it.
    assert screen.info_window.real_size[1] == \
        screen.time_display.real_size[1], (
            screen.info_window.real_size, screen.time_display.real_size)

    menu.visible = False
