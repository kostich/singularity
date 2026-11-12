"""At the top speed the globe sweeps instead of strobing.

The clock is useless for the map's day/night at 432000 game-seconds a second:
the tick moves it 432000/30 = 14400 seconds, a sixth of a day, so the
terminator jumps a sixth of the way round the globe every frame. Meanwhile the
season changes five times a second and the night mask is rebuilt that often.

So above HIGH_SPEED the *picture* runs on its own clock: one full sweep per
HIGH_SPEED_SWEEP_SECONDS, which is 3x the level below it (7200 sweeps once per
12 s), with the season held for the length of the sweep. Gameplay time is
untouched, and dropping below the threshold puts the band straight back where
the real clock has it.
"""

import pytest

import pygame

from singularity.code import g
from singularity.code.graphics import dialog
from singularity.code.graphics import g as gg


DAY = 24 * 60 * 60


@pytest.fixture
def earth(graphics):
    """A live map screen with day/night on, and a counter on the build steps."""
    from singularity.code.screens import main_menu, map as mapscreen

    saved = (g.daynight, g.curr_speed, g.last_speed, g.pl.raw_min,
             g.pl.time_day, g.map_screen)

    menu = main_menu.MainMenu()
    menu.visible = True
    menu.needs_rebuild = True
    dialog.Dialog.top.maybe_update()

    map_screen = mapscreen.MapScreen(parent=menu)
    g.map_screen = map_screen
    g.daynight = True
    map_screen.visible = True
    map_screen.needs_reconfig = True
    map_screen.needs_rebuild = True
    dialog.Dialog.top.maybe_update()

    globe = map_screen.map
    # The band is also offset by the second the game started. Pin it, so a
    # terminator position is a number this file can predict.
    globe.start_second = 0

    counts = {"steps": 0}
    real = globe._compute_night_mask_step

    def counted(width, height, day_of_year):
        counts["steps"] += 1
        return real(width, height, day_of_year)

    globe._compute_night_mask_step = counted

    # One redraw to build the mask, so the counts below start from a built one.
    globe.needs_redraw = True
    dialog.Dialog.top.maybe_update()
    counts["steps"] = 0

    yield globe, counts, menu, map_screen

    map_screen.stop_timer()
    (g.daynight, g.curr_speed, g.last_speed, g.pl.raw_min,
     g.pl.time_day, g.map_screen) = saved
    menu.visible = False


def _position(globe):
    return globe.compute_night_start()


def test_a_sweep_is_a_fraction_of_a_globe_per_frame_not_a_sixth(earth):
    globe, counts, menu, map_screen = earth
    width = globe.real_size[0]
    g.pl.raw_min = 144                 # a tenth of the day past midnight
    _position(globe)                   # the frame before the speed change
    g.curr_speed = 432000

    globe.advance_high_speed_phase()   # entering: continue from that frame
    seeded = _position(globe)
    assert seeded == int(width * 0.4)

    globe.advance_high_speed_phase()
    first = _position(globe)
    globe.advance_high_speed_phase()
    second = _position(globe)

    # One tick is 1/(30 * 4) of a day, i.e. a width/120 step -- and the band
    # moves in the same direction as the clock does at the speeds below.
    step = seeded - first
    assert step == pytest.approx(width / 120.0, abs=1.5)
    assert first - second == pytest.approx(step, abs=1.5)
    assert step < width / 6.0, (
        "a sixth of the globe in one frame is the strobing this replaces")


def test_one_sweep_lasts_the_configured_time(earth):
    globe, counts, menu, map_screen = earth
    g.pl.raw_min = 144
    _position(globe)
    g.curr_speed = 432000

    globe.advance_high_speed_phase()
    seeded = globe.high_speed_phase
    assert seeded == pytest.approx(0.1)

    steps = int(gg.FPS * 4.0)
    for _ in range(steps):
        globe.advance_high_speed_phase()

    assert steps == gg.FPS * int(4.0)
    assert globe.high_speed_phase == pytest.approx(seeded)


def test_the_sweep_is_three_times_the_level_below_it():
    """The whole point of the period: it should read as a faster 2h/s."""
    from singularity.code.screens import map as mapscreen

    level_below = mapscreen.speeds[3]
    assert mapscreen.speeds[4] >= mapscreen.HIGH_SPEED
    assert DAY / float(level_below) == \
        3 * mapscreen.HIGH_SPEED_SWEEP_SECONDS


def test_the_season_is_held_while_the_clock_races(earth):
    globe, counts, menu, map_screen = earth
    g.pl.raw_min = 144
    g.curr_speed = 432000
    globe.advance_high_speed_phase()
    held = globe.compute_day_of_year()

    for _ in range(30):
        globe.advance_high_speed_phase()
        # What the clock does at this speed: five days a second.
        g.pl.time_day += 1
        globe.needs_redraw = True
        dialog.Dialog.top.maybe_update()

    assert globe.compute_day_of_year() == held
    assert counts["steps"] == 0, (
        "%d mask rebuild steps while the season is held" % counts["steps"])
    assert globe.night_mask_day_of_year == held


def test_entering_the_top_speed_starts_where_the_clock_was(earth):
    globe, counts, menu, map_screen = earth
    g.pl.raw_min = 700
    g.curr_speed = 7200
    before = _position(globe)

    g.curr_speed = 432000
    globe.advance_high_speed_phase()

    assert _position(globe) == before, (
        "changing speed must not jump the band: it starts from the clock")


def test_entering_the_top_speed_ignores_the_first_tick_that_got_us_there(earth):
    """The tick that switches to 432000 moves the clock a sixth of a day.

    That is the point of the speed, and following it on the frame the player
    pressed the button is a jump of exactly the size the sweep exists to
    avoid, so the sweep starts from the last frame that was drawn instead.
    """
    globe, counts, menu, map_screen = earth
    width = globe.real_size[0]
    g.pl.raw_min = 600
    g.curr_speed = 7200
    before = _position(globe)

    # What give_time() really does on the first tick at the top speed: 14400
    # seconds, a sixth of a day.
    g.pl.raw_min = (600 + 14400 // 60) % 1440
    g.curr_speed = 432000
    globe.advance_high_speed_phase()

    moved = abs(_position(globe) - before)
    assert moved <= 1, (
        "the band followed the clock's %d px jump into the frame: moved %d px"
        % (width // 6, moved))


def test_leaving_the_top_speed_does_not_move_the_band(earth):
    """The sweep and the clock have drifted apart; the handover must hide it."""
    globe, counts, menu, map_screen = earth
    g.pl.raw_min = 144
    g.curr_speed = 432000
    for _ in range(10):
        globe.advance_high_speed_phase()
    before = _position(globe)

    # Down to 1 min/s. Nothing has moved the clock since, so the two now
    # disagree by a long way -- which used to be drawn as a jump.
    g.curr_speed = 1
    globe.end_high_speed_animation()

    assert abs(_position(globe) - before) <= 1, (
        "the band jumped when the top speed ended: %d -> %d"
        % (before, _position(globe)))
    assert globe.sweep_residual != 0.0, (
        "there was nothing to hand over, so this proves nothing -- the sweep "
        "must have moved the band away from the clock by now")


def test_the_band_glides_home_to_the_clock(earth):
    globe, counts, menu, map_screen = earth
    width = globe.real_size[0]
    g.pl.raw_min = 144
    g.curr_speed = 432000
    for _ in range(10):
        globe.advance_high_speed_phase()

    g.curr_speed = 7200
    globe.end_high_speed_animation()

    positions = [_position(globe)]
    for _ in range(4 * gg.FPS):        # more than the slowest glide can take
        if not globe.advance_sweep_blend():
            break
        positions.append(_position(globe))

    # Every frame of the glide is a small step, never a leap across the globe,
    # and never a bigger one than the sweep itself was taking: a globe per
    # HIGH_SPEED_SWEEP_SECONDS at 30 fps is width/120.
    steps = []
    for previous, current in zip(positions, positions[1:]):
        delta = abs(current - previous)
        steps.append(min(delta, width - delta))
    assert max(steps) <= width // 120 + 2, (
        "the glide stepped %d px on a %d px globe, faster than the sweep's %d"
        % (max(steps), width, width // 120))

    assert globe.sweep_blend == 0.0
    assert globe.sweep_residual == 0.0
    assert _position(globe) == int(width * (0.5 - 144 / 1440.0)) % width


def test_the_glide_only_ever_runs_the_day_night_forward(earth):
    """A periodic picture has one direction that keeps time advancing.

    The gap between where the sweep left the band and where the clock has it
    can be read two ways, and only one of them is forward: a fifth of a day
    ahead is four fifths behind. Reading it as "ahead" -- which is what taking
    the gap the short way round does whenever the sweep is in front -- made the
    band glide backwards, at random, depending on where the sweep happened to
    be when the speed changed.
    """
    globe, counts, menu, map_screen = earth
    width = globe.real_size[0]
    g.pl.raw_min = 600                 # the clock the sweep is measured against
    g.curr_speed = 432000
    globe.advance_high_speed_phase()   # enter the level ...

    cases = 0
    glided_backwards_before = 0
    for index in range(24):
        # ... then put the sweep at each twenty-fourth of a day in turn, so
        # every relationship between the band and the clock gets a glide.
        globe.high_speed_phase = index / 24.0
        if 0.0 < (globe.high_speed_phase - globe._day_portion()) % 1.0 < 0.5:
            glided_backwards_before += 1

        globe.end_high_speed_animation()

        positions = [_position(globe)]
        for _ in range(4 * gg.FPS):
            if not globe.advance_sweep_blend():
                break
            positions.append(_position(globe))

        for previous, current in zip(positions, positions[1:]):
            forward = (previous - current) % width
            assert 0 <= forward < width // 2, (
                "the band ran backwards: %d -> %d px, which is %d px the "
                "wrong way round the globe" % (previous, current,
                                               width - forward))
        cases += 1

        g.curr_speed = 432000          # back into a sweep for the next case
        globe.advance_high_speed_phase()

    assert cases == 24
    assert glided_backwards_before >= 4, (
        "no case had the sweep in front of the clock, so the bug this test is "
        "for was not covered: %d of 24" % glided_backwards_before)


def test_the_glide_runs_even_at_speed_one(earth, monkeypatch):
    """on_tick() returns early until a whole game second has passed.

    That is most ticks at 1 s/s, so a glide advanced after the return would
    step the band three times instead of thirty -- as visible as the strobing
    this replaces.
    """
    globe, counts, menu, map_screen = earth
    map_screen.needs_warning = False
    monkeypatch.setattr(g.pl, "give_time", lambda secs: 0)
    monkeypatch.setattr(g.pl, "lost_game", lambda: 0)
    monkeypatch.setattr(map_screen.messages, "show_list",
                        lambda *args, **kwargs: False)
    tick = pygame.event.Event(pygame.USEREVENT)

    g.pl.raw_min = 144
    g.curr_speed = 432000
    for _ in range(10):
        globe.advance_high_speed_phase()

    map_screen.set_speed(1)
    map_screen.leftovers = 0.0         # a game second is far away

    blends = []
    for _ in range(5):
        globe.needs_redraw = False
        map_screen.on_tick(tick)
        assert globe.needs_redraw, (
            "a glide frame has to be drawn, or the band is not gliding")
        blends.append(globe.sweep_blend)

    assert blends[0] < 1.0, "the glide did not advance at all at 1 s/s"
    assert blends == sorted(blends, reverse=True)
    assert globe.sweep_residual != 0.0


def test_going_back_up_mid_glide_picks_up_where_the_band_is(earth):
    globe, counts, menu, map_screen = earth
    g.pl.raw_min = 144
    g.curr_speed = 432000
    for _ in range(10):
        globe.advance_high_speed_phase()

    g.curr_speed = 60
    globe.end_high_speed_animation()
    for _ in range(5):
        globe.advance_sweep_blend()
    mid_glide = _position(globe)

    g.curr_speed = 432000
    globe.advance_high_speed_phase()

    assert abs(_position(globe) - mid_glide) <= 1, (
        "going back up to the top speed snapped the band: %d -> %d"
        % (mid_glide, _position(globe)))
    assert globe.sweep_blend == 0.0


def test_changing_speed_forgets_the_sweep(earth):
    globe, counts, menu, map_screen = earth
    g.curr_speed = 432000
    globe.advance_high_speed_phase()
    assert globe.high_speed_phase is not None

    map_screen.set_speed(7200)

    assert globe.high_speed_phase is None
    assert globe.high_speed_day is None
    # Forgotten as a sweep, kept as a glide: the band does not move.
    assert globe.sweep_blend == 1.0


def test_low_speeds_still_follow_the_clock(earth):
    globe, counts, menu, map_screen = earth
    width = globe.real_size[0]
    g.curr_speed = 7200

    for raw_min in (0, 360, 900):
        g.pl.raw_min = raw_min
        assert _position(globe) == \
            int(width * (0.5 - raw_min / 1440.0)) % width
    assert globe.high_speed_phase is None


def test_the_map_screen_animates_the_globe_every_tick_at_the_top_speed(
        earth, monkeypatch):
    globe, counts, menu, map_screen = earth
    map_screen.needs_warning = False
    monkeypatch.setattr(g.pl, "give_time", lambda secs: 0)
    monkeypatch.setattr(g.pl, "lost_game", lambda: 0)
    monkeypatch.setattr(map_screen.messages, "show_list",
                        lambda *args, **kwargs: False)
    tick = pygame.event.Event(pygame.USEREVENT)

    g.curr_speed = 432000
    phases = []
    for _ in range(5):
        globe.needs_redraw = False
        map_screen.on_tick(tick)
        assert globe.needs_redraw, (
            "the sweep has to be drawn every frame, or it is not a sweep")
        phases.append(globe.high_speed_phase)

    assert phases[0] is not None
    assert len(set(phases)) == len(phases), "the band did not move"

    # One level down the band is still gliding onto the clock, so the tick
    # after the change is a frame even though no game minute passed.
    g.curr_speed = 7200
    globe.needs_redraw = False
    map_screen.on_tick(tick)
    assert globe.high_speed_phase is None
    assert globe.needs_redraw

    # Once it has settled, the map is redrawn once a minute of game time again,
    # not on every tick -- the cost the top speed pays deliberately.
    while globe.advance_sweep_blend():
        pass
    globe.needs_redraw = False
    map_screen.on_tick(tick)
    assert not globe.needs_redraw
