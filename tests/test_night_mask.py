"""The night mask must be cached, not rebuilt from scratch every frame.

EarthImage.get_night_mask() decides whether to reuse the mask it already has
from two attributes, night_mask_day_of_year and night_mask_dim. Neither was
ever assigned, so both tests were dead: the day always looked changed and the
size never looked cached. Every single redraw therefore ran all five build
steps and allocated a fresh full-size surface plus its pixel array -- 1.7 MB a
frame at 1024x600, 8.6 MB at 3440x1440 -- which is a large heap block churned
once per frame for nothing.

The mask views also have to go when the mask is invalidated: pixels_alpha()
locks the surface it reads until the array is freed.
"""

import pytest

from singularity.code import g
from singularity.code.graphics import dialog


@pytest.fixture
def earth(graphics):
    """A live map screen with day/night on, and a counter on the build steps."""
    from singularity.code.screens import main_menu, map as mapscreen

    saved_daynight = g.daynight
    saved_time_day = g.pl.time_day
    saved_map_screen = g.map_screen

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

    g.daynight = saved_daynight
    g.pl.time_day = saved_time_day
    g.map_screen = saved_map_screen
    menu.visible = False


def _redraws(globe, count=5):
    for _ in range(count):
        globe.needs_redraw = True
        dialog.Dialog.top.maybe_update()


def test_an_unchanged_frame_reuses_the_mask(earth):
    globe, counts, menu, map_screen = earth

    _redraws(globe, 5)

    assert counts["steps"] == 0, (
        "%d build steps over 5 redraws: the mask is not being cached"
        % counts["steps"])


def test_the_mask_records_what_it_was_built_for(earth):
    globe, counts, menu, map_screen = earth

    assert globe.night_mask_day_of_year == globe.compute_day_of_year()
    assert globe.night_mask_dim == tuple(globe.real_size)


def test_a_new_day_rebuilds_the_mask_once(earth):
    globe, counts, menu, map_screen = earth
    g.pl.time_day += 1

    _redraws(globe, 5)

    # Five steps is one rebuild; the five redraws after it reuse the result.
    assert counts["steps"] == 5


def test_a_resize_rebuilds_the_mask_once(earth):
    globe, counts, menu, map_screen = earth

    map_screen.needs_resize = True
    map_screen.needs_rebuild = True
    counts["steps"] = 0

    _redraws(globe, 5)

    assert counts["steps"] == 5
    assert globe.night_mask_dim == tuple(globe.real_size)


def test_invalidating_the_mask_releases_the_pixel_views(earth):
    """A view keeps its surface locked, so it must not outlive the surface."""
    globe, counts, menu, map_screen = earth

    globe.get_night_mask()
    globe.night_mask_dim = None  # as if the size had changed
    globe.reset_night_mask_computation()

    assert globe.step_night_alphas is None
    assert globe.step_round_light is None
