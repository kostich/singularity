"""The load screen: its title, the filter row, and the Delete key.

Three separate faults, all of them in the 2030 layout except the key:

- the window said SAVE GAMES although the screen only ever loads;
- the filter row and the list were laid out from two different bases, so the
  first saved game sat underneath the filter field;
- `K_DELETE` was taken by the Delete-button shortcut before the text field saw
  it, so holding Delete in the filter deleted one character and then nothing.
"""

import pygame

from singularity.code.graphics import constants, theme


def _screen(theme_id):
    from singularity.code.screens import main_menu, savegame

    theme.set_theme(theme_id, force_reload=True)
    menu = main_menu.MainMenu()
    menu.visible = True
    map_screen = menu.map_screen
    map_screen.visible = True
    map_screen.needs_rebuild = True
    map_screen.needs_resize = True
    menu.needs_resize = True
    for __ in range(3):
        menu.maybe_update()

    screen = savegame.SavegameScreen(map_screen)
    screen.visible = True
    screen.needs_reconfig = True
    screen.needs_rebuild = True
    for __ in range(2):
        menu.maybe_update()
    return menu, map_screen, screen


def _delete_key():
    return pygame.event.Event(pygame.KEYDOWN,
                              {"key": pygame.K_DELETE, "unicode": None})


def _press(screen, event):
    """Deliver one key the way the dialog's handler loop does."""
    try:
        screen._got_key(event)
    except constants.Handled:
        pass


class _Save(object):
    """As much of a savegame as the selection code reads."""

    def __init__(self):
        from singularity.code import savegame as sv
        self.name = "A save"
        self.savegame_format = sv.current_save_format


def test_the_load_screen_says_what_it_does(graphics):
    _, map_screen, screen = _screen("2030")
    assert screen.window_title == "SAVED GAMES"


def test_the_save_list_starts_below_the_filter(graphics):
    """The first row was behind the field: unreadable, and unclickable."""
    _, map_screen, screen = _screen("2030")

    filter_bottom = max(
        screen.label.real_pos[1] + screen.label.real_size[1],
        screen.text_field.real_pos[1] + screen.text_field.real_size[1])
    assert screen.listbox.real_pos[1] >= filter_bottom, (
        "the list starts at %d, the filter ends at %d"
        % (screen.listbox.real_pos[1], filter_bottom))

    # The bottom is where it always was: above the button row.
    row_top = screen.yes_button.real_pos[1]
    assert screen.listbox.real_pos[1] + screen.listbox.real_size[1] <= row_top

    screen.visible = False
    map_screen.visible = False


def test_a_legacy_load_screen_keeps_its_geometry(graphics):
    """The shipped numbers, unchanged -- overlap and all."""
    _, map_screen, screen = _screen("Legacy-default")

    assert screen.listbox.pos == (0, -.10)
    assert screen.listbox.size == (-1, -.77)

    screen.visible = False
    map_screen.visible = False


def test_the_load_screens_own_four_button_row_is_left_alone(graphics):
    """LOAD, Upgrade, Delete and BACK are not a pair, under any theme.

    The theme groups a *pair* of answers in the bottom-right corner. This screen
    has four buttons across the width on two different anchors, so grouping them
    would put LOAD on top of Delete.
    """
    _, map_screen, screen = _screen("2030")

    assert screen.owns_button_row is True
    assert screen.yes_button.pos == (-.03, -.99)
    assert screen.no_button.pos == (-.97, -.99)
    assert screen.convert_button.pos == (-.27, -.99)
    assert screen.delete_button.pos == (-.51, -.99)

    screen.visible = False
    map_screen.visible = False


def test_delete_edits_the_filter_while_the_field_has_focus(graphics):
    """Holding Delete has to keep deleting: the repeat is a KEYDOWN each time."""
    _, map_screen, screen = _screen("2030")

    deleted = []
    screen.delete_button.activated = deleted.append

    # Delete removes the character *after* the cursor, as it does in every text
    # field; the player's long filter had the cursor somewhere inside it.
    screen.text_field.text = "abcdef"
    screen.text_field.cursor_pos = 2
    screen.text_field.has_focus = True
    # The filter has just emptied itself through _search_for_savegame(), so the
    # row the shortcut would delete is set after the text, not before.
    screen.listbox.list = [_Save()]
    screen.listbox.list_pos = 0

    key = _delete_key()
    _press(screen, key)
    assert screen.text_field.text == "abdef", "Delete did not edit the field"
    assert deleted == [], "Delete also asked to delete a saved game"

    # A second press is what a held key delivers, and it has to do the same.
    _press(screen, _delete_key())
    assert screen.text_field.text == "abef", (
        "the second press did not delete another character")

    # Out of the field, Delete is the button's shortcut again.
    screen.text_field.has_focus = False
    screen.text_field.text = "abef"
    screen.text_field.cursor_pos = 3
    screen.listbox.list = [_Save()]
    screen.listbox.list_pos = 0
    _press(screen, key)
    assert deleted == [key], deleted
    assert screen.text_field.text == "abef"

    screen.visible = False
    map_screen.visible = False
