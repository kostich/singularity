#!/usr/bin/env python3
"""Headless UI smoke test for Endgame: Singularity.

The pytest suite in tests/ only exercises game logic: it calls g.no_gui() and
never draws anything. This script instead mirrors the real startup path from
singularity/__init__.py main() and then *renders* the actual screens headlessly,
so the pygame-surface and NumPy drawing code is executed for real.

It was written while bringing the game up on Python 3.15 / pygame 2.6 / NumPy 2
and it caught two genuine bugs that the unit tests could not see:

  * ResearchScreen.update_item / LocationScreen.update_item being called with
    only two arguments by CustomListbox.update_element.
  * LocationScreen._selection_change indexing a None key_list.

Usage (from the repository root):

    SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy PYTHONPATH=. \
        python3 utils/ui_smoke_test.py

Exit status is 0 only if every step passed.

Note: modal dialogs are deliberately not opened. ``MapScreen.on_tick`` shows the
intro story and news dialogs, which block on pygame.event.wait() until clicked,
so the harness sets ``pl.intro_shown`` and does not drive the game clock.
"""

import os
import sys
import time
import traceback

# Must be set before pygame initialises its video/audio subsystems.
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

from singularity.code import g, dirs

g.debug = True
g.force_single_dir = False
dirs.create_directories(g.force_single_dir)

from singularity.code import i18n

i18n.set_language(force=True)

import pygame

import singularity.code.graphics.g as gg
import singularity.code.graphics.theme as theme
from singularity.code import mixer

desired_soundbuf = mixer.soundbuf

import singularity.code.graphics.font as font

mixer.preinit(desired_soundbuf)
pygame.init()
mixer.update()
font.init()
pygame.key.set_repeat(500, 50)

from singularity.code import data

data.load_themes()
theme.set_theme(None)
gg.init_graphics_system()
data.reload_all()

# A widget that does not fit its parent is normally clipped with a warning, so
# the game carries on looking subtly wrong. In the harness that is a failure:
# it is how the right-hand half of the HUD went missing on a 21:9 fullscreen
# without any step noticing.
gg.strict_layout = True
mixer.load_sounds()
mixer.load_music()
mixer.play_music("music")

from singularity.code.graphics import dialog
from singularity.code.screens import main_menu, map as mapscreen
from singularity.code.screens import research, location as locscreen

FAILURES = []


def step(name):
    """Run one harness step and record whether it raised."""
    def decorator(func):
        try:
            func()
            print("PASS  ", name)
        except Exception:
            FAILURES.append(name)
            print("FAIL  ", name)
            traceback.print_exc()
        return func
    return decorator


def main():
    print("screen:", pygame.display.get_surface())
    print("music tracks:", sum(len(v) for v in mixer.music_dict.values()))
    print("music busy:", pygame.mixer.music.get_busy())

    menu = main_menu.MainMenu()

    @step("main menu renders")
    def _():
        dialog.Dialog.top.needs_rebuild = True
        dialog.Dialog.top.maybe_update()
        pygame.display.flip()

    @step("new_game + map renders (daynight on, then off)")
    def _():
        g.new_game("easy", initial_speed=0)
        # The intro story is a modal dialog; it would block on a click.
        g.pl.intro_shown = True
        ms = mapscreen.MapScreen(parent=menu)

        # This is the NumPy-heavy path: EarthImage builds a night mask with
        # sin/cos/linspace over every pixel.
        g.daynight = True
        ms.needs_rebuild = True
        ms.needs_reconfig = True
        dialog.Dialog.top.maybe_update()
        pygame.display.flip()

        ms.map.needs_resize = True
        ms.map.reset_night_mask_computation()
        g.daynight = False
        ms.needs_reconfig = True
        dialog.Dialog.top.maybe_update()
        pygame.display.flip()

    @step("research screen: update_item with key_list=None")
    def _():
        rs = research.ResearchScreen(parent=menu)
        rs.listbox.list = ["placeholder"]
        element = rs.listbox.make_element()
        rs.listbox.display_elements = [element]
        # key_list is None here, so this calls rebuild_func(element, None).
        rs.listbox.update_element(element, 0)

    @step("research screen: populated + rendered")
    def _():
        rs = research.ResearchScreen(parent=menu)
        techs = [t for t in g.pl.techs.values() if t.available() and not t.done]
        techs.sort(key=lambda t: i18n.lex_sorting_form(t.spec.name))
        rs.visible = True
        rs.list = ["CPU Pool", "Jobs"] + ["Research %s" % t.name for t in techs]
        rs.key_list = ["cpu_pool", "jobs"] + [t.id for t in techs]
        rs.listbox.key_list = rs.key_list
        rs.needs_rebuild = True
        rs.update()
        pygame.display.flip()
        print("       research rows:", len(rs.list), "techs:", len(techs))

    @step("location screen: update_item with key_list=None")
    def _():
        ls = locscreen.LocationScreen(menu)
        ls.listbox.list = ["placeholder"]
        element = ls.listbox.make_element()
        ls.listbox.display_elements = [element]
        ls.listbox.update_element(element, 0)

    @step("location screen: populated with a real base + rendered")
    def _():
        ls = locscreen.LocationScreen(menu)
        location = [loc for loc in g.pl.locations.values() if loc.bases][0]
        ls.location = location
        ls.visible = True
        ls.needs_rebuild = True
        ls.update()
        pygame.display.flip()
        print("       location:", location.name, "bases:", len(location.bases))

    @step("simple menu dialog renders")
    def _():
        d = dialog.SimpleMenuDialog(menu)
        d.visible = True
        d.needs_rebuild = True
        dialog.Dialog.top.maybe_update()
        pygame.display.flip()

    @step("message dialog renders")
    def _():
        d = dialog.MessageDialog(menu, text="Harness message dialog.")
        d.visible = True
        d.needs_rebuild = True
        dialog.Dialog.top.maybe_update()
        pygame.display.flip()

    @step("dialog frame: 2030 centres the panel and reserves a picture banner")
    def _():
        from singularity.code.graphics import constants

        theme.set_theme("2030", force_reload=True)
        dialog.Dialog.top.maybe_update()

        d = dialog.MessageDialog(menu, size=(.5, .5),
                                 text="Harness message dialog.")
        d.visible = True
        d.needs_rebuild = True
        dialog.Dialog.top.maybe_update()
        pygame.display.flip()

        expected = (int(.5 * gg.real_screen_size[0]) - d.real_size[0] // 2,
                    int(.5 * gg.real_screen_size[1]) - d.real_size[1] // 2)
        assert d.anchor == constants.MID_CENTER, d.anchor
        assert d.real_pos == expected, (d.real_pos, expected)
        pane = d.image_pane
        assert pane is not None
        assert pane.real_size[0] > pane.real_size[1], (
            "the picture is not a banner: %r" % (pane.real_size,))
        assert d.text_insets()[1] > 0 and d.text_insets()[2] > 0
        assert d.text_insets()[1] >= (pane.real_pos[1] + pane.real_size[1])
        print("       centred at %s, banner %s at %s, text insets %s"
              % (d.real_pos, pane.real_size, pane.real_pos, d.text_insets()))

        # A button under this theme wears a CRT overlay while hovered, and the
        # band advances because it was redrawn -- not because time passed.
        ok = d.ok_button
        assert ok.hover_effect_enabled()
        assert ok._hover_hooked, "the button never registered its tick handler"
        plain = ok.surface.copy()
        ok._hovered = True
        ok._hover_ticks = 0
        ok.needs_redraw = True
        dialog.Dialog.top.maybe_update()
        hovered = ok.surface.copy()
        assert pygame.image.tobytes(hovered, "RGB") != \
            pygame.image.tobytes(plain, "RGB"), "hovering drew nothing"
        ok._hover_ticks = 9
        ok.needs_redraw = True
        dialog.Dialog.top.maybe_update()
        assert pygame.image.tobytes(ok.surface, "RGB") != \
            pygame.image.tobytes(hovered, "RGB"), "the scanline did not move"
        ok._hovered = False
        print("       hover: overlay drawn, band advanced, %s"
              % ("deterministic" if ok.hover_sweep_phase() == 0.0
                 else "phase %.2f" % ok.hover_sweep_phase()))

        d.visible = False

        # The screens that are lists rather than scenes take no picture, and
        # the log is the one a player meets most often. It is checked here, on
        # the real screen, because "the log grew a placeholder" was reported
        # from a real game rather than from a unit test.
        from singularity.code.screens import log as log_screen

        log = log_screen.LogScreen(menu)
        log.visible = True
        log.needs_rebuild = True
        dialog.Dialog.top.maybe_update()
        pygame.display.flip()
        assert log.image_pane is None, "the log has a picture slot"
        # Below the window's header band, which the theme decides: the position
        # is the old one moved by exactly that share of the window.
        assert log.listbox.pos == (0, log.below_header(-.09)), log.listbox.pos
        print("       log: no picture, list at %s %s"
              % (log.listbox.pos, log.listbox.size))
        log.visible = False

        theme.set_theme(None, force_reload=True)
        dialog.Dialog.top.maybe_update()

    @step("dialog art: a scenario dialog paints its own plate, not the static")
    def _():
        theme.set_theme("2030", force_reload=True)
        dialog.Dialog.top.maybe_update()

        # The plate is a file in the theme, and the whole point of this pass is
        # that a dialog shows it. Asserting it from the pixels is the only way
        # that cannot be satisfied by a name: the same dialog is drawn twice,
        # once with the theme's plate visible and once with it hidden, and the
        # two frames must differ.
        assert gg.has_dialog_art("dialog_message"), \
            "the theme ships no plate for dialog_message"

        d = dialog.MessageDialog(menu, size=(.5, .5),
                                 text="Harness message dialog.")
        d.visible = True
        d.needs_rebuild = True
        dialog.Dialog.top.maybe_update()
        pane = d.image_pane
        assert pane.art_name() == "dialog_message", pane.art_name()
        with_art = pygame.image.tobytes(pane.surface, "RGB")

        saved = gg.dialog_art_files.pop("dialog_message")
        try:
            gg._dialog_art_cache.clear()
            pane._scaled = None
            pane.needs_redraw = True
            dialog.Dialog.top.maybe_update()
            without_art = pygame.image.tobytes(pane.surface, "RGB")
        finally:
            gg.dialog_art_files["dialog_message"] = saved
            pane._scaled = None
            pane.needs_redraw = True
            dialog.Dialog.top.maybe_update()

        assert with_art != without_art, \
            "the pane drew the same pixels with and without its plate"
        print("       %s %s in a %s pane"
              % (pane.art_name(), gg.dialog_art("dialog_message").get_size(),
                 pane.real_size))
        d.visible = False

    @step("dialog frame: a legacy theme still draws the old one")
    def _():
        from singularity.code.graphics import constants

        theme.set_theme("Legacy-default", force_reload=True)
        dialog.Dialog.top.maybe_update()

        d = dialog.MessageDialog(menu, size=(.5, .5),
                                 text="Harness message dialog.")
        d.visible = True
        d.needs_rebuild = True
        dialog.Dialog.top.maybe_update()
        pygame.display.flip()

        expected = (int(.5 * gg.real_screen_size[0]) - d.real_size[0] // 2,
                    int(.1 * gg.real_screen_size[1]))
        assert d.anchor == constants.TOP_CENTER, d.anchor
        assert d.real_pos == expected, (d.real_pos, expected)
        assert d.border_width == 1
        assert d.image_pane is None
        assert d.text_insets() == (0, 0, 0, 0), d.text_insets()
        print("       legacy geometry at %s, size %s"
              % (d.real_pos, d.real_size))

        d.visible = False
        theme.set_theme(None, force_reload=True)
        dialog.Dialog.top.maybe_update()

    @step("layout: map renders undistorted at 16:9 and at 21:9")
    def _():
        saved = (gg.desktop_size, gg.screen_size,
                 gg.fullscreen, gg.window_size)
        saved_map_screen = g.map_screen
        try:
            # Fullscreen switches in place: the same window, the same surface,
            # no restart asked for. Recreating the window is what used to lose
            # keyboard and mouse input entirely.
            before = gg.screen_surface
            before_size = gg.window_size

            assert gg.set_fullscreen(True)
            assert gg.fullscreen
            assert gg.screen_surface is before
            assert gg.window_size == gg.desktop_size
            assert not gg.restart_needed()
            print("       fullscreen in place, window now:", gg.window_size)

            assert gg.set_fullscreen(False)
            assert not gg.fullscreen
            assert not gg.restart_needed()

            # The SDL dummy driver has no window manager, so it does not put
            # the window back by itself. A compositor that does not either is
            # covered by the unit tests, which drive a fake one.
            gg.set_screen_size(before_size)
            gg.set_mode()
            assert gg.window_size == before_size

            for size in ((1920, 1080), (3440, 1440)):
                # An unknown desktop leaves the requested window size alone, so
                # the SDL dummy driver can render these sizes. The size ->
                # layout step under test is the same one the real screen path
                # uses.
                gg.desktop_size = ()
                gg.set_screen_size(size)
                gg.set_mode()

                # Use the map screen the menu already owns: in the real game it
                # is a CHILD of the menu, and building it parentless gives it a
                # different width, which is what hid the containment bug.
                map_screen = menu.map_screen
                map_screen.visible = True
                map_screen.needs_reconfig = True
                map_screen.needs_rebuild = True

                # The map screen is no longer the root, so the whole tree has
                # to relayout and the root is what pushes it to the display.
                menu.needs_resize = True
                menu.needs_rebuild = True

                g.daynight = True
                menu.update()

                earth_w, earth_h = map_screen.map.real_size
                print("       window:", gg.window_size,
                      "layout:", gg.real_screen_size,
                      "origin:", gg.layout_origin,
                      "earth:", (earth_w, earth_h))

                # The art is 2:1; this is what used to be stretched.
                assert abs(earth_w / float(earth_h) - 2.0) < 0.01

                # The globe must fit the map screen it is drawn on, not merely
                # the window: comparing against the window is what made this
                # assertion pass while the globe was clipped.
                assert map_screen.collision_rect.contains(map_screen.map.collision_rect)
                assert map_screen.real_size == gg.real_screen_size

                # The screen covers the layout area, shifted by the origin.
                assert map_screen.collision_rect.topleft == gg.layout_origin

                # The layout is the window, and the window is what the display
                # surface presents. A mismatch between these is a strip of
                # window that nothing ever draws into.
                assert gg.real_screen_size == gg.window_size
                assert gg.screen_surface.get_size() == gg.window_size

                origin_x = gg.layout_origin[0]
                if origin_x:
                    # A click inside the pillarbox must not reach the HUD.
                    assert not map_screen.is_over((origin_x - 1, 10))
                assert map_screen.is_over((origin_x + 5, 10))

                pygame.display.flip()
                map_screen.visible = False

            # A window manager resizes the window without asking, and the game
            # may never hear about it (or may drop what it hears). The layout has
            # to follow the window before anything is painted: laying out in
            # part of the window leaves the rest showing whatever the compositor
            # left in the reallocated buffer.
            from pygame._sdl2 import video

            window = video.Window.from_display_module()
            previous = gg.window_size
            gg._mode_changed_at = 0.0  # the last mode change was long ago

            # 16:10, then 32:9 -- the second one pillarboxes, so its bands are
            # the area nothing in the widget tree ever draws into.
            for size in ((1600, 1000), (2560, 720)):
                window.size = size
                pygame.event.pump()
                pygame.event.clear(pygame.VIDEORESIZE)

                # A reallocated window buffer is not black, it is whatever was
                # in that memory. Paint the whole surface a colour no theme
                # uses, and demand the frame leaves none of it outside the UI.
                gg.screen_surface.fill((0, 255, 0))
                menu.maybe_update()

                assert gg.window_size == size
                assert gg.screen_surface.get_size() == size

                bands = gg.outside_layout_rects()
                for band in bands:
                    assert gg.screen_surface.get_at(
                        (band.centerx, band.centery))[:3] == (0, 0, 0)
                inside = (gg.layout_origin[0] + 5, gg.real_screen_size[1] // 2)
                assert gg.screen_surface.get_at(inside)[:3] != (0, 255, 0)

                print("       window resized behind our back:", size,
                      "layout:", gg.real_screen_size,
                      "bands:", [(band.x, band.width) for band in bands])

            # Put the window back the way the rest of the harness expects it.
            window.size = previous
            pygame.event.pump()
            pygame.event.clear(pygame.VIDEORESIZE)
            menu.maybe_update()
            assert gg.window_size == previous
        finally:
            (gg.desktop_size, gg.screen_size,
             gg.fullscreen, gg.window_size) = saved
            g.map_screen = saved_map_screen
            gg.set_screen_size(gg.screen_size, fs=gg.fullscreen)
            gg.set_mode()
            dialog.Dialog.top.needs_resize = True

    @step("fullscreen toggles off again, and a resize echo cannot bounce it")
    def _():
        saved = (gg.desktop_size, gg.screen_size, gg.window_size,
                 gg.windowed_size, gg.fullscreen)
        try:
            # set_mode() re-probes the desktop, so these have to be sizes the
            # dummy driver actually reports: 1024x768 is its desktop.
            gg.desktop_size = (1024, 768)
            gg.set_screen_size((800, 600))
            gg.set_mode()
            assert not gg.fullscreen
            assert gg.window_size == (800, 600)

            top = dialog.Dialog.top

            # Every toggle must be reversible, must switch in place, and must
            # never recreate the window. Which size it comes back to is the
            # window manager's business and is covered by the unit tests.
            for expected in (True, False, True, False):
                surface = gg.screen_surface
                calls = []
                real_set_mode = gg.set_mode
                gg.set_mode = lambda: (calls.append(1), real_set_mode())
                try:
                    applied = gg.set_fullscreen(expected)
                finally:
                    gg.set_mode = real_set_mode

                assert applied
                assert gg.fullscreen is expected
                assert calls == []
                assert gg.screen_surface is surface
                assert not gg.restart_needed()
                # The surface the game draws into is the window the compositor
                # made: that is the invariant whose absence was a band of
                # unpainted window along one edge.
                assert gg.window_size == gg.screen_surface.get_size()
                if expected:
                    assert gg.window_size == (1024, 768)

            # A compositor resize while fullscreen must not rewrite the chosen
            # resolution, and must not ask for another mode change. Feeding the
            # event back in was what made the toggle bounce.
            gg.set_fullscreen(True)
            gg.set_mode()
            before = gg.screen_size
            # Pretend the mode change was long ago, so that only the fullscreen
            # guard can reject this event and not the settle window. The size
            # is not the current window either, so the no-op guard cannot mask
            # it. Without the fullscreen guard this assertion fails.
            gg._mode_changed_at = 0.0
            top.handle(pygame.event.Event(pygame.VIDEORESIZE,
                                          {"size": (900, 700),
                                           "w": 900, "h": 700}))
            assert gg.screen_size == before
            assert gg.fullscreen

            # Leaving fullscreen still returns to the window the user chose.
            gg.set_fullscreen(False)
            gg.set_mode()
            assert gg.window_size == (800, 600)
            print("       toggled on/off 4 times, size held at", gg.window_size)
        finally:
            (gg.desktop_size, gg.screen_size, gg.window_size,
             gg.windowed_size, gg.fullscreen) = saved
            gg.set_screen_size(gg.screen_size, fs=gg.fullscreen)
            gg.set_mode()
            dialog.Dialog.top.needs_resize = True

    @step("leaving fullscreen returns to a window, and does not stall")
    def _():
        saved = (gg.desktop_size, gg.screen_size, gg.window_size,
                 gg.windowed_size, gg.fullscreen)
        try:
            gg.desktop_size = (1024, 768)
            gg.set_screen_size((800, 600))
            gg.set_mode()
            assert gg.window_size == (800, 600)

            assert gg.set_fullscreen(True)
            assert gg.window_size == (1024, 768)

            # The whole point: the way back, verified, and quickly.
            started = time.monotonic()
            applied = gg.set_fullscreen(False)
            elapsed = time.monotonic() - started

            assert applied
            assert not gg.fullscreen
            assert gg.window_size == (800, 600)
            assert gg.real_screen_size == (800, 600)
            assert gg.screen_surface.get_size() == (800, 600)
            assert not gg.restart_needed()
            # A toggle that waits out a retry budget is the "stuck for 200 ms"
            # the player saw. Success must be the fast path.
            assert elapsed < 0.2, "leaving fullscreen took %.3fs" % elapsed
            print("       fullscreen off in %.3fs, window back to %s"
                  % (elapsed, gg.window_size))
        finally:
            (gg.desktop_size, gg.screen_size, gg.window_size,
             gg.windowed_size, gg.fullscreen) = saved
            gg.set_screen_size(gg.screen_size, fs=gg.fullscreen)
            gg.set_mode()
            dialog.Dialog.top.needs_resize = True

    @step("options: changing resolution with the dialog open redraws it")
    def _():
        # The report: fullscreen off, then 3440x1440 -> 1280x1024 from the
        # resolution list, and the process died in SDL_ttf while the open
        # dialog measured its labels for the new layout. apply_display_request()
        # resizes the window in place and marks the dialog for a resize, so the
        # whole tree is measured again -- that is the frame that must survive.
        #
        # Fullscreen itself is covered by the two steps above: the dummy driver
        # cannot grant a 3440x1440 fullscreen, so what is reproduced here is the
        # resolution change that follows leaving it.
        saved = (gg.desktop_size, gg.screen_size, gg.window_size,
                 gg.windowed_size, gg.fullscreen)
        saved_top = dialog.Dialog.top
        try:
            gg.desktop_size = (3440, 1440)
            gg.set_screen_size((3440, 1440))
            gg.set_mode()

            from singularity.code.screens import options as options_module

            screen = options_module.OptionsScreen(None, (0, 0), (1, 1))
            screen.make_top()
            screen.visible = True
            screen.needs_rebuild = True
            # Only the active tab pane is a child of the dialog, so the video
            # pane has to be the selected one for its labels to be laid out --
            # that is what the Video tab button does.
            screen.set_tabs_pane(screen.video_pane)
            dialog.Dialog.top.maybe_update()
            pygame.display.flip()

            pane = screen.video_pane
            for size in ((1280, 1024), (3440, 1440), (800, 600), (1280, 1024)):
                pane.set_resolution(size)
                dialog.Dialog.top.maybe_update()
                pygame.display.flip()

                assert gg.screen_size == size, gg.screen_size
                assert not gg.restart_needed()
                # The window a request for this resolution produces, and the
                # layout the UI is measured in: they are the same area.
                assert gg.window_size == gg.compute_window_size(size, False)
                assert gg.real_screen_size == gg.window_size

                # The labels the reported stack was measuring. A zero-point
                # face measures every glyph at zero width and draws nothing.
                for label in (pane.resolution_label, pane.resolution_custom_X,
                              pane.fullscreen_label, pane.grab_label):
                    assert label.font is not None, label
                    assert label.font.get_height() > 0, label

                print("       %s: window %s, layout %s, label text %dpx"
                      % (size, gg.window_size, gg.real_screen_size,
                         pane.resolution_label.font.get_height()))
        finally:
            dialog.Dialog.top = saved_top
            (gg.desktop_size, gg.screen_size, gg.window_size,
             gg.windowed_size, gg.fullscreen) = saved
            gg.set_screen_size(gg.screen_size, fs=gg.fullscreen)
            gg.set_mode()
            dialog.Dialog.top.needs_resize = True

    @step("options: a wheel flick scrolls the list, not the resolution")
    def _():
        # The report: with a free-spinning mouse the lists "continue scrolling
        # over and over". on_mousewheel() used to move a whole window per event
        # by setting list_pos, and on the resolution list that is not a cursor
        # move -- it is the setting, so every notch resized the real window.
        saved = (gg.desktop_size, gg.screen_size, gg.window_size,
                 gg.windowed_size, gg.fullscreen)
        saved_top = dialog.Dialog.top
        try:
            gg.desktop_size = ()
            gg.set_screen_size((1024, 768))
            gg.set_mode()

            from singularity.code.screens import options as options_module

            screen = options_module.OptionsScreen(None, (0, 0), (1, 1))
            screen.make_top()
            screen.visible = True
            screen.needs_rebuild = True
            screen.set_tabs_pane(screen.video_pane)
            dialog.Dialog.top.maybe_update()
            pygame.display.flip()

            pane = screen.video_pane
            lb = pane.resolution_choice
            chosen = gg.screen_size
            start_view = lb.scrollbar.scroll_pos
            start_selection = lb.list_pos

            def a_row_that_is_not_selected():
                """The centre of a visible row other than the chosen one.

                A row has to be a real candidate for the bug to show: parking
                on the row that is already selected cannot tell a working
                guard from a missing one.
                """
                for index, element in enumerate(lb.display_elements):
                    if index + lb.scrollbar.scroll_pos != lb.list_pos:
                        return element.collision_rect.center
                return None

            # The report put the pointer inside the list -- "the option changes
            # only if I scroll while the cursor is within it" -- so that is
            # where it is parked for every event below.
            target = a_row_that_is_not_selected()
            assert target is not None, "every visible row is the selected one"
            pygame.mouse.set_pos(target)
            pygame.event.pump()

            # A flick, not a notch: tens of events, the way a high-resolution
            # wheel delivers one gesture.
            for _ in range(30):
                dialog.Dialog.top.handle(pygame.event.Event(
                    pygame.MOUSEWHEEL,
                    {"x": 0, "y": -1, "flipped": False,
                     "precise_x": 0.0, "precise_y": -1.0,
                     "which": 0, "touch": False}))
                dialog.Dialog.top.maybe_update()
                pygame.display.flip()

            assert gg.screen_size == chosen, (
                "the wheel changed the resolution: %r -> %r"
                % (chosen, gg.screen_size))
            assert tuple(gg.window_size) == tuple(gg.compute_window_size(chosen,
                                                                       False))
            assert lb.scrollbar.scroll_pos > start_view, (
                "the wheel did not scroll the view")
            # The view moved without the selection moving with it.
            assert lb.list_pos == start_selection, (
                "the wheel moved the selection: %r -> %r"
                % (start_selection, lb.list_pos))

            # A wheel axis is reported as a button on X11. Whatever number a
            # driver picks, releasing it over a row must not choose that row.
            # Scrolling moved the rows, so re-aim at one that is not selected.
            target = a_row_that_is_not_selected()
            assert target is not None, "every visible row is the selected one"
            pygame.mouse.set_pos(target)
            pygame.event.pump()

            for button in (2, 4, 5, 6, 7, 8):
                dialog.Dialog.top.handle(pygame.event.Event(
                    pygame.MOUSEBUTTONUP,
                    {"pos": target, "button": button}))
                dialog.Dialog.top.maybe_update()
                pygame.display.flip()
                assert gg.screen_size == chosen, (
                    "button %d changed the resolution: %r -> %r"
                    % (button, chosen, gg.screen_size))
                assert lb.list_pos == start_selection, (
                    "button %d moved the selection: %r -> %r"
                    % (button, start_selection, lb.list_pos))

            print("       view %d -> %d, selection held at %d, resolution at %s"
                  % (start_view, lb.scrollbar.scroll_pos, lb.list_pos,
                     gg.screen_size))
        finally:
            dialog.Dialog.top = saved_top
            (gg.desktop_size, gg.screen_size, gg.window_size,
             gg.windowed_size, gg.fullscreen) = saved
            gg.set_screen_size(gg.screen_size, fs=gg.fullscreen)
            gg.set_mode()
            dialog.Dialog.top.needs_resize = True

    @step("save + load roundtrip")
    def _():
        import io

        from singularity.code import savegame

        buf = io.BytesIO(b"")
        real_close = buf.close
        buf.close = lambda *args, **kwargs: None
        savegame.write_game_to_fd(buf, gzipped=False)
        buf = io.BytesIO(buf.getvalue())
        savegame.load_savegame_fd(savegame.load_savegame_by_json,
                                  io.BufferedReader(buf))
        real_close()
        print("       reloaded game, techs:", len(g.pl.techs))

    print()
    if FAILURES:
        print("FAILURES:", FAILURES)
        return 1
    print("ALL HARNESS STEPS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
