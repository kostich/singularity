"""Fixtures shared by the tests that need a real graphics stack.

Most of the suite never touches pygame. Widgets, layout and display modes do,
and they need exactly what singularity.main() sets up: a display surface, a
theme (which is where fonts and colours come from) and the game data.

Requested explicitly rather than autouse, so the pure-logic tests stay fast and
independent of pygame.
"""

import pytest

from singularity.code import g, data, dirs, i18n


@pytest.fixture(scope="module")
def graphics():
    """Bring the graphics system up once, as singularity.main() does."""
    g.no_gui()
    dirs.create_directories(False)
    # These tests assert English copy and the widths of English labels.
    # set_language() otherwise follows the desktop locale, so a machine
    # whose locale matches a shipped catalog would translate the fixtures.
    i18n.set_language("en_US", force=True)

    import pygame

    import singularity.code.graphics.g as gg
    import singularity.code.graphics.theme as theme
    import singularity.code.graphics.font as font
    from singularity.code import mixer

    mixer.preinit(mixer.soundbuf)
    pygame.init()
    font.init()

    data.load_themes()
    theme.set_theme(None)
    gg.init_graphics_system()
    data.reload_all()

    g.daynight = False
    g.new_game("easy", initial_speed=0)
    # The intro is a modal dialog; there is nothing to click in a test.
    g.pl.intro_shown = True

    yield gg

    # Leave the globals as they were found: these tests move the screen size
    # around, and other modules read the same globals.
    gg.desktop_size = ()
    gg.set_screen_size(gg.default_screen_size, fs=False)
    # set_screen_size() only records the request now; set_mode() is what
    # actually sizes the window.
    gg.set_mode()
    g.daynight = True
