"""The suspicion row claimed more precision than it had (upstream #233).

With `discovery display = partial` the percentage is rounded to the nearest
5%, and was then formatted with two decimals anyway: 5.23% became "5.00%",
which reads as a precise measurement of something the game is only guessing
at.
"""

import locale

from singularity.code import g

DECIMAL_POINT = locale.localeconv()["decimal_point"]


def _map_screen(theme_id="2030"):
    from singularity.code.graphics import theme
    from singularity.code.screens import main_menu

    theme.set_theme(theme_id, force_reload=True)
    menu = main_menu.MainMenu()
    menu.visible = True
    screen = menu.map_screen
    screen.visible = True
    screen.needs_rebuild = True
    screen.needs_resize = True
    menu.needs_resize = True
    for _ in range(3):
        menu.maybe_update()
    return menu, screen


def _suspicion_chunks(screen, discover):
    """Show one group at 5.23% and return the suspicion row's chunks."""
    g.pl.display_discover = discover
    g.pl.had_grace = False
    for group in g.pl.groups.values():
        group.suspicion = 0
    next(iter(g.pl.groups.values())).suspicion = 523

    screen.rebuild()
    return list(screen.suspicion_bar.chunks)


def test_partial_display_shows_a_whole_percent(graphics):
    menu, screen = _map_screen()

    chunks = _suspicion_chunks(screen, "partial")

    assert g.to_percent(g.nearest_percent(523, 500)) in chunks
    shown = [c for c in chunks if c.endswith("%")]
    assert shown, chunks
    for text in shown:
        assert DECIMAL_POINT not in text, (
            "%r shows a decimal place the rounded number does not have" % text)

    menu.visible = False


def test_full_display_keeps_two_decimals(graphics):
    """The precise view is precise: 5.23% really is 5.23%."""
    menu, screen = _map_screen()

    chunks = _suspicion_chunks(screen, "full")

    assert g.to_percent(523, True) in chunks
    assert any(DECIMAL_POINT in c and c.endswith("%") for c in chunks), chunks

    menu.visible = False


def test_minimal_display_still_shows_a_word(graphics):
    menu, screen = _map_screen()

    chunks = _suspicion_chunks(screen, "minimal")

    assert g.suspicion_to_detect_str(523) in chunks
    assert not any(c.endswith("%") for c in chunks), chunks

    menu.visible = False
