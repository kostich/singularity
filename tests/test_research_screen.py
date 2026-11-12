"""The research screen's ??? box and the message it opens.

The box is a standard button, so it took the theme's one button height -- 40px
in a 46px row, placed in the row's lower half, so it spilled out of its own row
and its label was clipped. The message it opens is a dialog placed at the centre
of the *screen*, which is not the centre of the window it is drawn in: its
surface was clipped and its OK button was never drawn.
"""

from singularity.code.graphics import theme


def _research_screen(theme_id):
    from singularity.code.screens import main_menu, research

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

    screen = research.ResearchScreen(map_screen)
    screen.visible = True
    screen.needs_reconfig = True
    screen.needs_rebuild = True
    for __ in range(2):
        menu.update()
    return menu, map_screen, screen


def test_the_help_box_fits_inside_its_row(graphics):
    menu, map_screen, screen = _research_screen("2030")

    row = screen.listbox.display_elements[0]
    box = row.help_button
    box.visible = True
    box.needs_resize = True
    menu.update()

    assert box.role == "chrome", "the box still takes the standard button height"
    assert box.real_pos[1] + box.real_size[1] <= row.real_size[1], (
        "the box ends at %d in a %d row"
        % (box.real_pos[1] + box.real_size[1], row.real_size[1]))
    assert box.real_pos[0] + box.real_size[0] <= row.real_size[0]

    screen.visible = False
    map_screen.visible = False


def test_a_legacy_research_screen_keeps_the_standard_box(graphics):
    """The old geometry is the old look, spill and all."""
    menu, map_screen, screen = _research_screen("Legacy-default")

    row = screen.listbox.display_elements[0]
    assert row.help_button.role == "standard"

    screen.visible = False
    map_screen.visible = False


def test_the_danger_message_shows_its_ok_button(graphics):
    """It was cut in half, with no way out but Escape."""
    menu, map_screen, screen = _research_screen("2030")

    help_dialog = screen.help_dialog
    help_dialog.text = ("This technology is too dangerous to research on any of "
                        "the computers I have. It needs a base under the sea.")
    help_dialog.set_art_key("dialog_danger_1",
                            fallbacks=("dialog_danger", "dialog_message"))
    help_dialog.visible = True
    help_dialog.needs_rebuild = True
    map_screen.update()

    # Inside the window it was opened from, and with its whole surface.
    assert help_dialog.real_pos[1] >= 0
    assert (help_dialog.real_pos[1] + help_dialog.real_size[1]
            <= screen.real_size[1])
    assert tuple(help_dialog.surface.get_size()) == tuple(help_dialog.real_size)

    ok = help_dialog.ok_button
    assert ok.visible
    assert ok.real_pos[1] + ok.real_size[1] <= help_dialog.real_size[1], (
        "the OK button is below the dialog's own surface")

    help_dialog.visible = False
    screen.visible = False
    map_screen.visible = False
