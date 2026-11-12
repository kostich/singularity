"""Tests for the window/layout geometry.

All of this is pure arithmetic, so no display is needed. The numbers below are
the contract that keeps 4:3 and 16:9 exactly as they were while making a window
wider than 16:9 usable: the HUD keeps its shapes and spreads out, and a
resolution change survives a fullscreen round trip.
"""

import pytest

import pygame

from singularity.code.graphics import g as gg


# Window sizes at or below 16:9, i.e. every shape the game was written for.
IDENTITY_SIZES = [
    (800, 600),
    (1024, 600),
    (1024, 768),
    (1280, 800),
    (1280, 1024),
    (1366, 768),
    (1440, 900),
    (1920, 1080),
    (960, 540),
]

# State set_screen_size() and update_layout() write to.
_STATE = ("desktop_size", "screen_size", "window_size", "windowed_size",
          "fullscreen", "layout_size", "layout_origin", "real_screen_size",
          "screen_surface", "geometry_dirty",
          "_requested_window_size", "_applied_window_size",
          "_applied_fullscreen")


@pytest.fixture(autouse=True)
def _restore_globals():
    saved = {name: getattr(gg, name) for name in _STATE}

    yield

    for name, value in saved.items():
        setattr(gg, name, value)
    gg.update_layout()
    # update_layout() may mark the next frame as needing a full repaint, which
    # is state for the frame and not for whatever runs next.
    gg.geometry_dirty = False


def _surface_size():
    """The size of the surface the game is actually drawing into."""
    return tuple(gg.screen_surface.get_size())


@pytest.mark.parametrize("size", IDENTITY_SIZES)
def test_layout_uses_the_whole_window_at_or_below_16_9(size):
    # This is the regression guard: none of these may change behaviour.
    assert gg.compute_layout(size) == (size, (0, 0))


@pytest.mark.parametrize("size", [
    (2560, 1080),
    (3440, 1440),
    (1920, 800),
    # A 21:9 desktop's *windowed* size: 3440x1440 minus the window margin. It
    # must not be pillarboxed while the fullscreen of the same screen is not.
    (3370, 1370),
    (2490, 1010),
])
def test_layout_uses_the_whole_window_up_to_21_9(size):
    # 21:9 keeps the whole width: the extra space is usable real estate, not
    # something to throw away.
    assert gg.compute_layout(size) == (size, (0, 0))


@pytest.mark.parametrize("size, expected", [
    # 32:9 is where the clusters would read as separate islands.
    ((5120, 1440), ((3600, 1440), (760, 0))),
    ((3840, 1080), ((2700, 1080), (570, 0))),
])
def test_layout_pillarboxes_beyond_21_9(size, expected):
    # 32:9 would push the HUD clusters too far apart to read as one layout.
    assert gg.compute_layout(size) == expected


def test_layout_survives_a_degenerate_size():
    # probe_desktop_size() can legitimately report 0x0 under Wayland.
    assert gg.compute_layout((0, 0)) == ((0, 0), (0, 0))


def test_earth_matches_the_old_4_3_size():
    # EarthImage used to ask for (1, .667) of the window, which is these two at
    # 4:3. The globe must not move by a pixel there.
    assert gg.fit_aspect_size((1024, 768), 2.0, 0.74) == (1024, 512)
    assert gg.fit_aspect_size((800, 600), 2.0, 0.74) == (800, 400)


@pytest.mark.parametrize("area", IDENTITY_SIZES + [
    (2560, 1440),
    (3440, 1440),
    (5120, 1440),
    (7680, 4320),
    (320, 240),
])
def test_earth_is_never_stretched_and_stays_in_its_area(area):
    width, height = gg.fit_aspect_size(area, 2.0, 0.74)

    assert width <= area[0]
    assert height <= int(area[1] * 0.74) + 1
    # The art is 2:1; one pixel of rounding is all that is allowed.
    assert abs(width / float(height) - 2.0) < 0.01


@pytest.mark.parametrize("desktop, expected", [
    ((3440, 1440), (1920, 1080)),
    ((2560, 1440), (1920, 1080)),
    ((3840, 2160), (2560, 1440)),
    ((1920, 1080), (1440, 900)),
    ((1366, 768), (1024, 600)),
])
def test_default_window_fits_the_desktop(desktop, expected):
    assert gg.choose_default_screen_size(desktop) == expected


def test_default_window_falls_back_when_nothing_fits():
    # No listed resolution fits an 800x600 desktop; keep the old default rather
    # than inventing one. set_screen_size() clamps it afterwards.
    assert gg.choose_default_screen_size((800, 600)) == gg.default_screen_size


@pytest.mark.parametrize("size, is_fullscreen, expected", [
    ((1920, 1080), False, (1920, 1080)),
    ((3440, 1440), False, (3370, 1370)),   # margin: panels and title bar
    ((1920, 1080), True, (3440, 1440)),    # fullscreen is the desktop
    ((2560, 1440), False, (2560, 1370)),   # margin only on the axis that needs it
])
def test_compute_window_size(size, is_fullscreen, expected):
    assert gg.compute_window_size(size, is_fullscreen,
                                  desktop=(3440, 1440)) == expected


def test_set_screen_size_keeps_4_3_and_16_9_identity():
    gg.desktop_size = (3440, 1440)

    for size in ((800, 600), (1024, 768), (1280, 1024), (1920, 1080)):
        gg.set_screen_size(size)
        gg.set_mode()
        # Smaller than the desktop, so no margin and no pillarbox.
        assert gg.window_size == size
        assert gg.real_screen_size == size
        assert gg.layout_origin == (0, 0)


def test_set_screen_size_does_not_touch_the_running_window():
    """The core invariant: a request is recorded, the window is left alone.

    Applying it means recreating the window, and on Wayland the new window then
    receives no events at all. A stack dump of a hung game showed the main
    thread blocked in pygame.event.wait().
    """
    gg.desktop_size = (3440, 1440)
    gg.set_screen_size((1920, 1080))
    gg.set_mode()

    surface = gg.screen_surface

    gg.set_screen_size((2560, 1440))

    assert gg.screen_surface is surface
    assert gg.window_size == (1920, 1080)
    assert gg.real_screen_size == (1920, 1080)
    assert gg.restart_needed()


def test_a_window_size_saved_as_a_resolution_repairs_itself():
    """prefs.dat on a real machine held xres=3440 yres=1371.

    That is the desktop (3440x1440) minus the window margin: a window size, not
    a resolution. Loaded back, it reopened as a nearly-fullscreen window that
    was not fullscreen, which looks like windowed mode being broken. Anything
    within the margin of the desktop is the whole screen.
    """
    gg.desktop_size = (3440, 1440)

    gg.set_screen_size((3440, 1371))

    assert gg.screen_size == (3440, 1440)
    # And the window that follows is a real windowed window.
    assert gg.windowed_size == (3370, 1370)


def test_a_real_resolution_is_not_snapped_to_the_desktop():
    gg.desktop_size = (3440, 1440)

    for size in ((1920, 1080), (2560, 1440), (1024, 768), (3200, 1300)):
        gg.set_screen_size(size)
        assert gg.screen_size == size


def test_a_size_exactly_one_margin_below_the_desktop_means_the_same_window():
    """3370x1370 is desktop minus margin, i.e. the full-screen window.

    Treating it as the desktop is not a loss of information: compute_window_size
    subtracts that same margin, so both spellings produce one identical window.
    Keeping the desktop spelling means the Options list shows the real screen
    rather than a number that looks custom but is not.
    """
    gg.desktop_size = (3440, 1440)

    gg.set_screen_size((3370, 1370))
    snapped_size, snapped_window = gg.screen_size, gg.windowed_size

    gg.set_screen_size((3440, 1440))

    assert snapped_size == gg.screen_size == (3440, 1440)
    assert snapped_window == gg.windowed_size == (3370, 1370)


def test_a_dragged_window_does_not_rewrite_the_resolution():
    """A drag changes the window. It must not change what "Resolution" means.

    save_options() writes screen_size to prefs.dat, so a drag that wrote it back
    turned one resize into a permanent, wrong resolution.
    """
    gg.desktop_size = (3440, 1440)
    gg.set_screen_size((1920, 1080))
    gg.set_mode()

    assert gg.adopt_window_size((1234, 567))

    assert gg.window_size == (1234, 567)
    assert gg.windowed_size == (1234, 567)
    # The chosen resolution is untouched, so prefs.dat keeps a real one.
    assert gg.screen_size == (1920, 1080)
    assert not gg.restart_needed()


def test_the_layout_refuses_to_become_degenerate():
    """A 0x0 window must not zero the layout, and so must not kill every font.

    text.convert_font_size is size * real_screen_size[1] // 768, so a layout
    height of 0 renders every glyph at 0px: panes draw and text does not. A
    compositor can report exactly that for a window it has not mapped yet.
    """
    from singularity.code.graphics import text as text_module

    gg.desktop_size = (3440, 1440)
    gg.set_screen_size((1920, 1080))
    gg.set_mode()

    healthy_layout = gg.real_screen_size
    healthy_font = text_module.convert_font_size(20)
    assert healthy_font > 0

    # The compositor reports nothing usable.
    gg.window_size = (0, 0)
    gg.update_layout()

    assert gg.real_screen_size == healthy_layout
    assert text_module.convert_font_size(20) == healthy_font


def test_a_degenerate_report_never_reaches_the_layout():
    """window_size_actual() must not hand a 0x0 answer back."""
    gg.desktop_size = (3440, 1440)
    gg.set_screen_size((1920, 1080))
    gg.set_mode()

    assert gg.window_size_actual() == (1920, 1080)
    # Even with a surface that reports nothing (a window mid-creation).
    assert gg._usable_size((0, 0)) is False
    assert gg._usable_size((1920, 1080)) is True


def test_fullscreen_round_trip_restores_the_chosen_window():
    # The size the SDL dummy driver really reports, so that set_mode() can
    # honour a fullscreen request. It clamps fullscreen to this.
    #
    # What this tree asks SDL for is its own arithmetic and is asserted exactly.
    # What came back is a video driver's answer, and drivers disagree: the dummy
    # driver on some SDL builds keeps the desktop-sized surface when fullscreen
    # is switched off, which is exactly where this test failed on a CI runner
    # while passing here. So the request is asserted before set_mode() replaces
    # it, and the result is checked against the surface, not against the request.
    gg.desktop_size = (1024, 768)
    gg.set_screen_size((800, 600))
    gg.set_mode()
    assert (gg.window_size, gg.windowed_size) == ((800, 600), (800, 600))
    assert not gg.restart_needed()

    gg.set_screen_size(fs=True)
    assert gg.fullscreen
    # Switching the mode must not rewrite the resolution...
    assert gg.screen_size == (800, 600)
    # ...nor touch the running window...
    assert gg.window_size == (800, 600)
    # ...and the chosen window is remembered.
    assert gg.windowed_size == (800, 600)
    assert gg.restart_needed()

    # A restart applies it: that is what set_mode() is for.
    gg.set_mode()
    assert gg.window_size == (1024, 768)
    assert not gg.restart_needed()

    gg.set_screen_size(fs=False)
    # Coming back must ask for the chosen window, not the desktop size, which
    # looks exactly like fullscreen and made the toggle unusable.
    assert gg._requested_window_size == (800, 600)
    gg.set_mode()
    assert not gg.fullscreen
    assert gg.window_size == _surface_size()
    assert not gg.restart_needed()

    # Toggling repeatedly must not drift.
    for _ in range(3):
        gg.set_screen_size(fs=True)
        gg.set_mode()
        gg.set_screen_size(fs=False)
        assert gg._requested_window_size == (800, 600)
        gg.set_mode()
    assert gg.screen_size == (800, 600)
    assert gg.windowed_size == (800, 600)
    assert gg.window_size == _surface_size()
    assert not gg.restart_needed()


def test_resolution_changed_while_fullscreen_is_remembered():
    gg.desktop_size = (3440, 1440)
    gg.set_screen_size((1920, 1080), fs=True)
    gg.set_mode()
    assert gg.fullscreen

    # Picking a resolution while fullscreen defines the window to come back to.
    gg.set_screen_size((2560, 1440))
    assert gg.fullscreen
    assert gg.windowed_size == (2560, 1370)

    gg.set_screen_size(fs=False)
    assert gg.restart_needed()
    # The window to come back to is the chosen resolution, not the desktop.
    assert gg._requested_window_size == (2560, 1370)
    gg.set_mode()
    assert not gg.fullscreen
    assert gg.window_size == _surface_size()
    assert not gg.restart_needed()


def test_set_screen_size_records_a_32_9_fullscreen_request():
    """The pillarbox arithmetic is compute_layout()'s job and is covered above.
    This checks that the request path reaches it with the desktop size."""
    gg.desktop_size = (5120, 1440)
    gg.set_screen_size((5120, 1440), fs=True)

    assert gg.fullscreen
    assert gg.screen_size == (5120, 1440)
    # Fullscreen means the desktop, not the chosen resolution.
    assert gg._requested_window_size == (5120, 1440)


def test_blit_pairs_are_identity_without_pillarboxing():
    rect = pygame.Rect(10, 20, 100, 50)

    assert gg.layout_blit_pairs([rect], (0, 0)) == [(rect, rect)]


def test_blit_pairs_undo_the_collision_rect_offset():
    # The root's collision rect already starts at the origin, because it is in
    # window space. Blitting must therefore keep the destination as-is and put
    # the source region back into layout space; shifting both would draw the
    # whole UI one origin too far right.
    layout_size, origin = gg.compute_layout((5120, 1440))
    root_rect = pygame.Rect(origin, layout_size)

    [(dest, area)] = gg.layout_blit_pairs([root_rect], origin)

    assert dest == root_rect
    assert area == pygame.Rect((0, 0), layout_size)
    # Drawing and hit-testing place the UI at the same spot.
    assert dest.topleft == origin


def test_a_geometry_change_marks_the_frame_for_a_full_repaint():
    # A resize hands the window a freshly allocated buffer, so the next frame
    # has to present all of it rather than the rects that changed.
    gg.window_size = (1600, 600)
    gg.update_layout()

    assert gg.geometry_dirty

    gg.geometry_dirty = False
    gg.update_layout()  # nothing moved

    assert not gg.geometry_dirty


def test_outside_layout_rects_is_empty_when_the_layout_is_the_window():
    gg.screen_surface = None
    gg.window_size = (1920, 1080)
    gg.update_layout()

    assert gg.real_screen_size == gg.window_size
    assert gg.outside_layout_rects() == []


def test_outside_layout_rects_covers_a_window_that_grew():
    # Measured against the surface as well as the window: the surface is what
    # gets presented, so a surface larger than window_size still has to be
    # covered -- that is the strip that was left showing garbage.
    gg.screen_surface = pygame.Surface((1600, 600))
    gg.window_size = (1024, 768)
    gg.update_layout()

    assert gg.outside_layout_rects() == [pygame.Rect(1024, 0, 576, 768)]
