"""The location screen: button margins, the confirmations, and double-click.

The six buttons were placed at shares of the screen -- 0, .5 and 1 -- so the
outer two were flush with the window's border, and the two dialogs this screen
opens were anchored on the window's top edge rather than in the middle.
"""

import pygame

from singularity.code.graphics import constants, dialog, theme


def _location_screen(theme_id):
    from singularity.code import g
    from singularity.code.screens import main_menu

    theme.set_theme(theme_id, force_reload=True)
    menu = main_menu.MainMenu()
    menu.visible = True
    map_screen = menu.map_screen
    map_screen.visible = True
    map_screen.needs_rebuild = True
    map_screen.needs_resize = True
    menu.needs_resize = True
    menu.needs_rebuild = True
    for __ in range(3):
        menu.update()

    screen = map_screen.location_dialog
    screen.location = [loc for loc in g.pl.locations.values() if loc.bases][0]
    screen.visible = True
    screen.needs_reconfig = True
    screen.needs_rebuild = True
    screen.needs_resize = True
    for __ in range(2):
        menu.update()
    return menu, map_screen, screen


def test_the_location_buttons_keep_off_the_borders(graphics):
    _, map_screen, screen = _location_screen("2030")

    margin = int(round(graphics.dialog_style("margin", .02)
                       * screen.real_size[0]))
    width, height = screen.real_size

    for name in ("open_button", "rename_button", "power_button",
                 "new_button", "destroy_button", "back_button"):
        widget_ = getattr(screen, name)
        left = widget_.real_pos[0]
        right = left + widget_.real_size[0]
        assert left >= margin - 1, (name, left, margin)
        assert right <= width - margin + 1, (name, right, width - margin)
        # The rows keep the vertical position they shipped with; only the two
        # outer buttons were flush with the border, and that is the horizontal
        # margin below.
        assert widget_.real_pos[1] + widget_.real_size[1] <= height

    # Nothing overlaps: three columns on each row.
    row = [screen.open_button, screen.rename_button, screen.power_button]
    row.sort(key=lambda widget_: widget_.real_pos[0])
    for left_one, right_one in zip(row, row[1:]):
        assert left_one.real_pos[0] + left_one.real_size[0] <= right_one.real_pos[0]

    screen.visible = False
    map_screen.visible = False


def test_a_legacy_location_screen_keeps_its_geometry(graphics):
    _, map_screen, screen = _location_screen("Legacy-default")

    assert screen.open_button.pos == (0, -.8)
    assert screen.power_button.pos == (-1, -.8)
    # A theme that does not centre its dialogs anchors them at the top edge.
    assert screen.confirm_destroy.pos == (-.5, 0)
    assert screen.confirm_destroy.anchor == constants.TOP_CENTER

    screen.visible = False
    map_screen.visible = False


def test_the_destroy_confirmation_sits_in_the_middle(graphics):
    """`(-.5, 0)` with a middle anchor centres a dialog on the top edge."""
    _, map_screen, screen = _location_screen("2030")

    other = screen.confirm_destroy
    assert other.pos == (-.5, -.5)

    other.visible = True
    other.needs_rebuild = True
    map_screen.update()

    # The middle of the window, so its top is inside the frame.
    assert other.real_pos[1] > 0
    centre = other.real_pos[1] + other.real_size[1] // 2
    assert abs(centre - screen.real_size[1] // 2) <= 2

    other.visible = False
    screen.visible = False
    map_screen.visible = False


def test_a_double_click_opens_the_row_under_the_pointer(graphics, monkeypatch):
    """Not the selected row: whatever the player actually clicked, any base."""
    from singularity.code import base as base_module
    from singularity.code import g

    _, map_screen, screen = _location_screen("2030")

    location = screen.location
    # A warehouse, which is the case the player reported: a base with no CPU of
    # its own, finished, and openable like any other.
    extra = base_module.Base("Zzz Warehouse", g.base_type["Small Warehouse"])
    extra.done = True
    location.add_base(extra)
    screen.needs_rebuild = True
    map_screen.update()

    opened = []
    monkeypatch.setattr(dialog, "call_dialog",
                        lambda shown, parent=None: opened.append(shown))

    # The row the warehouse sits in, and a *different* row left selected: the
    # pointer decides what opens, not the selection.
    index = screen.listbox.key_list.index(extra)
    target = screen.listbox.display_elements[index]
    screen.listbox.list_pos = 1 - index

    # Six pixels right and six down between the two clicks, which is what a hand
    # does. The engine's own rule wanted them within ten pixels in total and
    # dropped the pair, which is why a base could not be opened this way.
    centre = target.collision_rect.center
    for offset in ((0, 0), (6, 6)):
        screen.handle(pygame.event.Event(
            pygame.MOUSEBUTTONUP,
            {"pos": (centre[0] + offset[0], centre[1] + offset[1]),
             "button": 1}))

    assert opened, "the double-click opened nothing"
    assert opened[0] is screen.base_dialog
    assert screen.base_dialog.base is extra

    screen.visible = False
    map_screen.visible = False
