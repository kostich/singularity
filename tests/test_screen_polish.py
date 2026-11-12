"""2030-only polish for the base, research, log and dialog frame.

Legacy themes keep the layout and the colours they had. Each test below
checks both.
"""

import pytest

from singularity.code import g
from singularity.code.graphics import dialog, theme
from singularity.code.graphics import g as gg


LEGACY = ("Legacy-default", "Legacy-nightmode", "Legacy-vector")


def settle(top, dialog_object):
    dialog_object.visible = True
    dialog_object.needs_rebuild = True
    top.needs_rebuild = True
    top.update()
    return dialog_object


@pytest.fixture
def top(graphics):
    made = dialog.TopDialog()
    made.visible = True
    made.make_top()
    made.update()
    yield made
    made.visible = False


def _base(top):
    from singularity.code.screens.base import BaseScreen

    base = next(g.all_bases())
    return settle(top, BaseScreen(top, base=base))


def test_a_2030_base_uses_chevrons_and_one_title_row(top):
    theme.set_theme("2030", force_reload=True)
    screen = _base(top)

    assert screen.prev_base_button.icon == "icon_back"
    assert screen.next_base_button.icon == "icon_forward"
    assert screen.prev_base_button.text == ""
    assert screen.next_base_button.text == ""
    assert screen.prev_base_button.icon_glyph() is not None
    width, height = screen.prev_base_button.real_size
    assert width == height
    assert width >= 16

    assert screen.name_display.size[1] == -1
    assert screen.state_display.parent is screen.name_display
    assert screen.state_display.pos[1] == 0
    assert screen.state_display.text
    assert screen.info_frame.pos[1] < .09

    screen.visible = False


@pytest.mark.parametrize("theme_id", LEGACY)
def test_a_legacy_base_keeps_its_two_rows_and_text_arrows(top, theme_id):
    theme.set_theme(theme_id, force_reload=True)
    screen = _base(top)

    assert screen.prev_base_button.text == "<"
    assert screen.next_base_button.text == ">"
    assert screen.prev_base_button.icon is None
    assert screen.prev_base_button.size == (.03, -1)
    assert screen.state_display.parent is screen.header
    assert screen.state_display.pos == (-.5, -.5)
    assert screen.state_display.size == (-1, -.5)
    assert screen.name_display.size == (-1, -.5)
    assert screen.info_frame.pos[1] == .09

    screen.visible = False


def test_research_descriptions_show_their_plate_in_2030(top):
    from singularity.code.graphics.dialog import DialogArtPane
    from singularity.code.logmessage import plate_key
    from singularity.code.screens.research import ResearchScreen

    theme.set_theme("2030", force_reload=True)
    screen = ResearchScreen(top)
    tech_id = next(iter(g.pl.techs))
    screen.key_list = ["cpu_pool", "jobs", tech_id]
    screen.list = ["CPU", "Jobs", "Tech"]
    screen.listbox.key_list = screen.key_list
    screen.listbox.list = screen.list

    def art_for(index):
        screen.listbox.list_pos = index
        screen._update_desc_pane()
        panes = [child for child in screen.description_pane.children
                 if isinstance(child, DialogArtPane)]
        assert len(panes) == 1
        text_widget = next(child for child in screen.description_pane.children
                           if not isinstance(child, DialogArtPane))
        assert text_widget.pos[1] == -screen.ART_STRIP
        return panes[0].art_key

    assert art_for(0) == "dialog_knowledge_processors"
    assert art_for(1) == "dialog_knowledge_jobs"
    assert art_for(2) == plate_key("dialog_tech_", tech_id)

    screen.visible = False


@pytest.mark.parametrize("theme_id", LEGACY)
def test_a_legacy_research_description_is_still_text(top, theme_id):
    from singularity.code.graphics.dialog import DialogArtPane
    from singularity.code.screens.research import ResearchScreen

    theme.set_theme(theme_id, force_reload=True)
    screen = ResearchScreen(top)
    tech_id = next(iter(g.pl.techs))
    screen.key_list = [tech_id]
    screen.list = ["Tech"]
    screen.listbox.key_list = screen.key_list
    screen.listbox.list = screen.list
    screen.listbox.list_pos = 0
    screen._update_desc_pane()

    assert not any(isinstance(child, DialogArtPane)
                   for child in screen.description_pane.children)
    body = screen.description_pane.children[0]
    assert body.pos == (0, 0)
    assert body.size == (-1, -1)

    screen.visible = False


class _Entry(object):
    art_key = None
    art_fallbacks = ()
    full_message_color = "text"

    def __init__(self, line):
        self.log_line = line
        self.log_emit_time = (1, 2, 3, 4)
        self.full_message = line


def _log(top, lines):
    from singularity.code.screens.log import LogScreen

    saved = list(g.pl.log)
    g.pl.log.clear()
    g.pl.log.extend(_Entry(line) for line in lines)
    screen = settle(top, LogScreen(top))
    return screen, saved


def test_a_2030_log_row_has_one_size_and_no_dash(top):
    theme.set_theme("2030", force_reload=True)
    short = "A short line."
    long = "word " * 40
    screen, saved = _log(top, [short, long])
    try:
        assert screen.hint.visible is True
        assert "Double-click" in screen.hint.text

        rows = [row for row in screen.listbox.display_elements if row.visible]
        assert len(rows) >= 2
        assert all(row.time_label.text.startswith("DAY ") for row in rows)
        assert all(" -- " not in (row.message_label.text or "") for row in rows)
        assert all(" -- " not in (row.time_label.text or "") for row in rows)

        sizes = {row.message_label.font.get_height() for row in rows}
        assert len(sizes) == 1, sizes
        assert rows[1].real_size[1] > rows[0].real_size[1]
    finally:
        g.pl.log.clear()
        g.pl.log.extend(saved)
        screen.visible = False


@pytest.mark.parametrize("theme_id", LEGACY)
def test_a_legacy_log_row_still_joins_with_a_dash(top, theme_id):
    theme.set_theme(theme_id, force_reload=True)
    screen, saved = _log(top, ["Something happened."])
    try:
        assert screen.hint.visible is False
        shown = [row.text for row in screen.listbox.display_elements
                 if row.text]
        assert shown
        assert all(" -- " in line for line in shown)
    finally:
        g.pl.log.clear()
        g.pl.log.extend(saved)
        screen.visible = False


def _edge_pixel(dialog_object):
    return tuple(dialog_object.surface.get_at(
        (1, dialog_object.real_size[1] // 2))[:3])


def _close(pixel, name):
    expected = tuple(gg.resolve_color_alias(name)[:3])
    assert all(abs(pixel[i] - expected[i]) <= 4 for i in range(3)), (
        pixel, expected, name)


def _hull_pixels(dialog_object):
    """A pixel of the header band, and one of the hull beside the content."""
    width, height = dialog_object.real_size
    band = tuple(dialog_object.surface.get_at((width // 2, 3))[:3])
    # The right margin is the frame's own fill: the picture and the text stop
    # short of it, and the buttons sit on the bottom row.
    hull = tuple(dialog_object.surface.get_at((width - 6, height // 2))[:3])
    return band, hull


def test_a_2030_warning_is_amber_and_titled(top):
    from singularity.code import warning
    from singularity.code.screens import message as message_screen

    theme.set_theme("2030", force_reload=True)
    made = message_screen.MessageListDialog(
        top, yes_type="&CONTINUE", no_type="&PAUSE")
    made.type = warning.Warning
    made.list = [warning.warnings["one_base"]]
    settle(top, made)

    assert made.window_title == "WARNING"
    assert made.title.visible is False
    assert made.chrome_tone == "warning"
    assert made.prev_button.visible is False
    _close(_edge_pixel(made), "dialog_warning_edge")
    band, hull = _hull_pixels(made)
    _close(band, "dialog_warning_header")
    _close(hull, "dialog_warning_fill")

    made.visible = False


def test_a_2030_loss_frame_is_red(top):
    from singularity.code.screens.map import MapScreen

    theme.set_theme("2030", force_reload=True)
    made = dialog.MessageDialog(top, text="The base is gone.")
    made.chrome_tone = "alert"
    made.window_title = "Base Discovered"
    made.needs_redraw = True
    settle(top, made)

    _close(_edge_pixel(made), "dialog_alert_edge")
    band, hull = _hull_pixels(made)
    _close(band, "dialog_alert_header")
    _close(hull, "dialog_alert_fill")
    assert made.window_title == "Base Discovered"

    story = dialog.YesNoDialog(top, text="Gone.")
    MapScreen._apply_story_chrome((story,), "Lost No Bases")
    assert story.chrome_tone == "alert"
    assert story.window_title == "DEFEAT"
    kept = dialog.YesNoDialog(top, text="Hello.")
    MapScreen._apply_story_chrome((kept,), "Intro")
    assert kept.chrome_tone is None
    assert kept.window_title == "CONFIRM"

    made.visible = False


def test_show_message_keeps_a_legacy_body_red(top, monkeypatch):
    from singularity.code.screens.map import MapScreen

    monkeypatch.setattr(dialog, "call_dialog", lambda shown, parent: None)
    theme.set_theme("Legacy-default", force_reload=True)
    shared = dialog.MessageDialog(top, text_size="dialog_text")
    screen = type("Screen", (), {})()
    screen.message_dialog = shared
    MapScreen.show_message(screen, "gone", color="red",
                           title="Base Discovered", tone="alert")
    assert shared.color == "red"
    assert shared.chrome_tone is None
    assert shared.window_title == "MESSAGE"


@pytest.mark.parametrize("theme_id", LEGACY)
def test_a_legacy_warning_keeps_its_caption(top, theme_id):
    from singularity.code import warning
    from singularity.code.screens import message as message_screen

    theme.set_theme(theme_id, force_reload=True)
    made = message_screen.MessageListDialog(
        top, yes_type="&CONTINUE", no_type="&PAUSE")
    made.type = warning.Warning
    made.list = [warning.warnings["one_base"], warning.warnings["cpu_usage"]]
    made.list_pos = 0
    settle(top, made)

    assert made.title.visible is True
    assert made.window_title is None
    assert made.chrome_tone is None
    assert made.title.text.startswith("WARNING")
    assert made.prev_button.visible is True

    made.visible = False
