#file: test_menu_backdrop.py
#Copyright (C) 2026
#This file is part of Endgame: Singularity.

#Endgame: Singularity is free software; you can redistribute it and/or modify
#it under the terms of the GNU General Public License as published by
#the Free Software Foundation; either version 2 of the License, or
#(at your option) any later version.

#Endgame: Singularity is distributed in the hope that it will be useful,
#but WITHOUT ANY WARRANTY; without even the implied warranty of
#MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#GNU General Public License for more details.

#You should have received a copy of the GNU General Public License
#along with Endgame: Singularity; if not, write to the Free Software
#Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

"""The 2030 main menu's backdrop, and the guarantee it stays off the old themes.

The picture is a function of the tick count. Two menus stepped the same number
of times must match, a legacy menu must not move, and the columns must stay in
the gutters: the title has no fill of its own, so a column under it would show
through the letters.
"""

import hashlib

import pygame
import pytest

from singularity.code.graphics import constants, g, theme
from singularity.code.graphics.menu_backdrop import MenuBackdrop


SIZE = (1280, 800)

MENU_COLOURS = MenuBackdrop.COLOURS


def _show(gg, theme_id):
    """One main menu, laid out at a fixed size under one theme."""
    from singularity.code.screens import main_menu

    theme.set_theme(theme_id, force_reload=True)
    gg.desktop_size = ()
    gg.set_screen_size(SIZE)
    gg.set_mode()

    menu = main_menu.MainMenu()
    menu.visible = True
    menu.needs_reconfig = True
    menu.needs_rebuild = True
    menu.update()
    return menu


def _digest(menu):
    return hashlib.sha256(pygame.image.tobytes(menu.surface, "RGB")).hexdigest()


def _pump(menu, ticks):
    """The dialog's own tick handlers, then a redraw. No wall clock."""
    for _ in range(ticks):
        for _priority, handler in list(menu.handlers.get(constants.TICK, ())):
            handler(None)
        menu.maybe_update()


def test_two_menus_agree_after_the_same_ticks(graphics):
    """Seeded columns, so the snapshot and a second run are the same picture."""
    first = _show(graphics, "2030")
    _pump(first, 12)
    first_digest = _digest(first)

    second = _show(graphics, "2030")
    _pump(second, 12)

    assert _digest(second) == first_digest


def test_ticking_moves_the_2030_menu_and_not_a_legacy_one(graphics):
    live = _show(graphics, "2030")
    assert live.backdrop.enabled()
    before = _digest(live)
    _pump(live, 12)
    assert _digest(live) != before

    legacy = _show(graphics, "Legacy-default")
    assert not legacy.backdrop.enabled()
    assert g.dialog_style("menu_backdrop") == "none"
    still = _digest(legacy)
    _pump(legacy, 12)
    assert _digest(legacy) == still


def test_the_columns_stay_in_the_gutters(graphics):
    """Rain in the outer fifth, and nowhere under the title.

    The raster is a line every fourth row across the whole menu, so the quiet
    pixel is taken between those lines. Anything else there -- a column or the
    frame -- would be the effect in the wrong place.
    """
    menu = _show(graphics, "2030")
    width, height = menu.real_size
    void = tuple(g.resolve_color_alias("main_menu_background"))[:3]
    gutter = int(width * MenuBackdrop.GUTTER)

    found = False
    for y in range(0, int(height * 0.85), 2):
        if y % MenuBackdrop.RASTER_STEP == 0:
            continue
        for x in range(2, gutter, 2):
            if menu.surface.get_at((x, y))[:3] != void:
                found = True
                break
        if found:
            break
    assert found, "no column in the left gutter at tick 0"

    # Inside the title's horizontal span (0.225..0.775), outside the button
    # column (0.375..0.625), and off a raster row.
    x = int(width * 0.30)
    y = int(height * 0.32)
    if y % MenuBackdrop.RASTER_STEP == 0:
        y += 1
    assert menu.surface.get_at((x, y))[:3] == void

    frame = tuple(g.resolve_color_alias("menu_frame"))[:3]
    left = int(width * MenuBackdrop.FRAME[0])
    top = int(height * MenuBackdrop.FRAME[1])
    bottom = int(height * MenuBackdrop.FRAME[3])
    mid = (top + bottom) // 2
    assert any(menu.surface.get_at((left + dx, mid))[:3] == frame
               for dx in range(-2, 4)), "the frame is not drawn"


def test_rain_without_its_colours_does_not_raise(graphics):
    """Opting in without the colours is a plain fill, not a KeyError."""
    theme.set_theme("2030", force_reload=True)
    saved = {name: g.colors.pop(name) for name in MENU_COLOURS}
    try:
        assert not MenuBackdrop.enabled()
        menu = _show(graphics, "2030")
        # set_theme reloaded the colours. Drop them again, on the live menu.
        for name in MENU_COLOURS:
            g.colors.pop(name, None)
        assert not menu.backdrop.enabled()
        menu.backdrop.handle_tick(None)
        # The menu paints again. With the colours gone the backdrop draws
        # nothing, so the gutters are the fill.
        menu.needs_redraw = True
        menu.update()
        void = tuple(g.resolve_color_alias("main_menu_background"))[:3]
        assert menu.surface.get_at((40, 101))[:3] == void
        before = _digest(menu)
        _pump(menu, 8)
        assert _digest(menu) == before
    finally:
        g.colors.update(saved)


def test_a_theme_switch_hooks_and_unhooks_the_tick(graphics):
    menu = _show(graphics, "2030")
    try:
        assert any(handler == menu.backdrop.handle_tick
                   for _priority, handler in menu.handlers.get(constants.TICK, ()))

        theme.set_theme("Legacy-default", force_reload=True)
        menu.needs_reconfig = True
        menu.update()
        assert not menu.backdrop.enabled()
        assert all(handler != menu.backdrop.handle_tick
                   for _priority, handler in menu.handlers.get(constants.TICK, ()))

        theme.set_theme("2030", force_reload=True)
        menu.needs_reconfig = True
        menu.update()
        assert menu.backdrop.enabled()
        assert any(handler == menu.backdrop.handle_tick
                   for _priority, handler in menu.handlers.get(constants.TICK, ()))
    finally:
        menu.stop_timer()


def test_the_backdrop_is_the_first_child(graphics):
    """Drawn first, so the buttons and the title cover it."""
    menu = _show(graphics, "2030")
    assert menu.children[0] is menu.backdrop
    assert menu.backdrop.pos == (0, 0)
    assert menu.backdrop.size == (1, 1)
