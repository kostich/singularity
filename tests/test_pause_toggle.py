"""Space pauses, and unpauses to the speed level that was last chosen.

Pause is a state, not a speed level, so ``g.last_speed`` never holds 0.  That
is what makes a single key work both ways, including after an explicit pause
(the PAUSE button on a message list, or ``Player.pause_game()``).  A notice
does not pause: the dialog is modal, and dismissing it leaves the speed.
"""

import io
import os

import pygame
import pytest

from singularity.code import g, savegame, warning
from singularity.code.graphics import constants, theme
from singularity.code.screens import main_menu


def press_space(map_screen):
    """Deliver a real space KEYDOWN, the way the event loop would."""
    return map_screen.handle(
        pygame.event.Event(pygame.KEYDOWN,
                           {"key": pygame.K_SPACE, "unicode": " "}))


def press_tick(map_screen):
    """Run the game tick the timer would run."""
    return map_screen.on_tick(pygame.event.Event(pygame.USEREVENT))


def press_pause_button(map_screen):
    """Click the two-bar pause control, the way a mouse click would."""
    try:
        map_screen.speed_buttons[0].activate_with_sound(None)
    except constants.Handled:
        pass


def record_warnings(map_screen):
    """Run for real, but collect the warning dialogs instead of opening them.

    A modal dialog would block the test, so the two things that can open one
    -- the message list and show_message() -- are replaced, and the warning
    dialogs are recorded instead.  The night mask is exercised by
    test_night_mask.py; here it only costs layout.
    """
    shown = []

    def show_list(message_type, messages):
        # show_list() itself ignores an empty list; log messages are not
        # warnings and arrive through the same call.
        if messages and message_type is warning.Warning:
            shown.append([message.id for message in messages])
        return False

    map_screen.messages.show_list = show_list
    map_screen.show_message = lambda *args, **kwargs: None
    map_screen.map.on_tick = lambda event: None
    return shown


@pytest.fixture
def map_screen(graphics):
    saved = (g.map_screen, g.last_speed, g.curr_speed)

    menu = main_menu.MainMenu()
    screen = menu.map_screen
    g.map_screen = screen
    g.curr_speed = 0
    g.last_speed = 1

    yield screen

    screen.set_speed(0)
    g.map_screen, g.last_speed, g.curr_speed = saved
    menu.visible = False


def test_a_new_game_has_a_level_to_resume_at(map_screen):
    assert g.curr_speed == 0
    assert g.last_speed == 1, "a paused new game must still know what to run at"

    press_space(map_screen)

    assert g.curr_speed == 1


def test_space_pauses_and_resumes_the_last_level(map_screen):
    map_screen.set_speed(7200)
    assert g.curr_speed == 7200
    assert g.last_speed == 7200

    for _ in range(3):
        press_space(map_screen)
        assert g.curr_speed == 0
        assert g.last_speed == 7200, "pausing must not overwrite the level"

        press_space(map_screen)
        assert g.curr_speed == 7200


def test_pausing_by_any_route_keeps_the_level(map_screen):
    map_screen.set_speed(60)
    map_screen.set_speed(0)
    assert (g.curr_speed, g.last_speed) == (0, 60)

    map_screen.set_speed(1)
    map_screen.adjust_speed(faster=False)
    assert (g.curr_speed, g.last_speed) == (0, 1)

    press_space(map_screen)
    assert g.curr_speed == 1


def test_an_internal_pause_resumes_at_the_running_level(map_screen):
    map_screen.set_speed(432000)

    # What the PAUSE button on a message list does.
    g.pl.pause_game()
    assert g.curr_speed == 0
    assert g.last_speed == 432000

    press_space(map_screen)
    assert g.curr_speed == 432000


def test_the_map_screen_binds_space_and_no_button_claims_it(map_screen):
    assert pygame.K_SPACE in map_screen.key_handlers

    for speed_button in map_screen.speed_buttons:
        assert speed_button.hotkey not in (" ", pygame.K_SPACE), (
            "speed button %r already owns the space key"
            % (speed_button.text,))


def test_a_new_game_resets_the_level(graphics):
    g.last_speed = 432000
    g.curr_speed = 0

    g.new_game("easy", initial_speed=0)
    assert g.last_speed == 1

    g.new_game("easy", initial_speed=60)
    assert (g.curr_speed, g.last_speed) == (60, 60)

    # Leave the module's player the way the fixtures expect it.
    g.new_game("easy", initial_speed=0)
    g.pl.intro_shown = True


def test_loading_a_savegame_starts_paused_at_the_default_level(map_screen):
    path = os.path.join(os.path.dirname(__file__), "savegames",
                        "savegame-test-01.s2")
    g.last_speed = 432000

    try:
        with open(path, "rb") as fd:
            savegame.load_savegame_fd(savegame.load_savegame_by_json,
                                      io.BufferedReader(fd))

        assert g.curr_speed == 0
        assert g.last_speed == 1, (
            "the level is not stored in the save; a load starts at 1")
    finally:
        g.new_game("easy", initial_speed=0)
        g.pl.intro_shown = True


def test_entering_the_map_still_shows_the_warnings(map_screen):
    shown = record_warnings(map_screen)

    map_screen.force_update()
    press_tick(map_screen)

    assert shown, ("the warnings must not be lost: they are the only way the "
                   "game tells the player the processor is idle")


def test_an_unchanged_warning_is_not_repeated(map_screen):
    shown = record_warnings(map_screen)
    map_screen.force_update()
    press_tick(map_screen)
    assert shown
    shown.clear()

    for _ in range(3):
        press_space(map_screen)           # resume
        press_tick(map_screen)
        press_space(map_screen)           # pause again
        press_tick(map_screen)

    map_screen.set_speed(7200)            # an explicit speed choice
    press_tick(map_screen)
    map_screen.set_speed(0)

    assert shown == [], (
        "a warning that did not change was shown again: %r. One dialog per "
        "keypress is the behaviour the space key must not have." % (shown,))


def test_a_changed_warning_set_is_shown_again(map_screen):
    shown = record_warnings(map_screen)
    map_screen.force_update()
    press_tick(map_screen)
    assert shown
    shown.clear()

    # The real cause: the player gives the idle CPU to jobs, so the "I didn't
    # use all the available processor power" warning stops applying.
    player = g.pl
    was_jobs = player.get_allocated_cpu_for("jobs", 0)
    player.set_allocated_cpu_for("jobs", player.available_cpus[0])
    try:
        map_screen.set_speed(1)
        press_tick(map_screen)

        assert shown, ("a changed set of warnings must be shown: it is how the "
                       "player learns that something started going wrong")
        assert "cpu_usage" not in shown[0], (
            "the dialog showed a warning that no longer applies: %r" % (shown,))
        shown.clear()

        map_screen.set_speed(0)
        map_screen.set_speed(1)
        press_tick(map_screen)

        assert shown == [], (
            "and showing it once is enough: %r" % (shown,))
    finally:
        player.set_allocated_cpu_for("jobs", was_jobs)


def test_a_notice_leaves_the_speed_alone(map_screen, monkeypatch):
    """Grace, an event and a lost base open a dialog. They do not pause."""
    from singularity.code import base as base_module
    from singularity.code import chance

    monkeypatch.setattr(map_screen, "show_story_section", lambda name: None)
    monkeypatch.setattr(map_screen, "show_message", lambda *args, **kwargs: None)
    monkeypatch.setattr(chance, "roll_interval", lambda *args, **kwargs: False)

    try:
        map_screen.set_speed(7200)
        player = g.pl
        player.had_grace = True
        player.raw_sec = 23 * g.seconds_per_day
        player.update_times()
        player.give_time(1)
        assert player.had_grace is False, "day 23 must end the grace period"
        assert (g.curr_speed, g.last_speed) == (7200, 7200)

        player.events.pop("scandal", None)
        player.trigger_event(g.events["scandal"])
        assert (g.curr_speed, g.last_speed) == (7200, 7200)

        loc = next(iter(player.locations.values()))
        extra = base_module.Base("Temp", g.base_type["Stolen Computer Time"],
                                 built=True)
        loc.add_base(extra)
        player.remove_bases([(extra, "maint")])
        assert extra not in loc.bases
        assert (g.curr_speed, g.last_speed) == (7200, 7200)
    finally:
        g.new_game("easy", initial_speed=0)
        g.pl.intro_shown = True


def test_the_2030_pause_button_toggles(map_screen):
    """In 2030 the two-bar button pauses, and the next click resumes."""
    theme.set_theme("2030", force_reload=True)
    try:
        map_screen.set_speed(7200)
        press_pause_button(map_screen)
        assert g.curr_speed == 0
        assert g.last_speed == 7200

        press_pause_button(map_screen)
        assert g.curr_speed == 7200
        assert g.last_speed == 7200
    finally:
        map_screen.set_speed(0)


def test_a_legacy_pause_button_sets_speed_zero(map_screen):
    """A legacy theme's pause button means speed 0, so a second click stays."""
    theme.set_theme("Legacy-default", force_reload=True)
    try:
        map_screen.set_speed(7200)
        press_pause_button(map_screen)
        assert g.curr_speed == 0
        assert g.last_speed == 7200

        press_pause_button(map_screen)
        assert g.curr_speed == 0
        assert g.last_speed == 7200, "a second click must not resume"
    finally:
        map_screen.set_speed(0)
        theme.set_theme("2030", force_reload=True)


def test_a_new_save_is_named_for_the_day_and_the_difficulty(map_screen):
    saved_name = savegame.last_savegame_name
    saved_day = g.pl.time_day
    try:
        savegame.last_savegame_name = None
        g.pl.time_day = 18
        assert map_screen.menu_dialog.suggested_save_name() == "DAY 0018 EASY"

        g.pl.time_day = 3
        assert map_screen.menu_dialog.suggested_save_name() == "DAY 0003 EASY"

        savegame.last_savegame_name = "before the moon"
        assert (map_screen.menu_dialog.suggested_save_name()
                == "before the moon")
    finally:
        savegame.last_savegame_name = saved_name
        g.pl.time_day = saved_day
