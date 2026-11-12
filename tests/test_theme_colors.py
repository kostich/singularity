"""The pane edge has its own colour, and the old themes keep the old one.

The screens used to pass `pane_background` as the *border* colour of every
panel, so a theme could give a panel a fill but never an edge: the frame was
always the fill colour. `pane_border` fixes that for the 2030 theme without
touching how the legacy themes look, and these tests pin both halves.
"""

import glob
import os

import pytest

from singularity.code.graphics import g, theme


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHIPPED_THEMES = ("2030", "Legacy-default", "Legacy-nightmode", "Legacy-vector")


def resolved(colors, name):
    return g.resolve_color_alias(name)


@pytest.mark.parametrize("theme_id", SHIPPED_THEMES)
def test_every_shipped_theme_defines_the_pane_edge(graphics, theme_id):
    """A theme that cannot answer would raise KeyError while drawing."""
    theme.set_theme(theme_id, force_reload=True)

    assert "pane_border" in g.colors
    assert len(resolved(g.colors, "pane_border")) == 4


@pytest.mark.parametrize("theme_id",
                         ["Legacy-default", "Legacy-nightmode",
                          "Legacy-vector"])
def test_the_legacy_themes_keep_exactly_the_old_edge(graphics, theme_id):
    """Their panels used to be edged in pane_background; they still are."""
    theme.set_theme(theme_id, force_reload=True)

    assert resolved(g.colors, "pane_border") == \
        resolved(g.colors, "pane_background")


def test_the_2030_edge_is_deliberately_different(graphics):
    """Otherwise the change would be invisible and not worth the new name."""
    theme.set_theme("2030", force_reload=True)

    assert resolved(g.colors, "pane_border") != \
        resolved(g.colors, "pane_background")


def test_no_screen_paints_a_panel_border_in_the_fill_colour():
    """The choke point: the screens must ask for the edge, not the fill."""
    offenders = []
    screens = os.path.join(REPO_ROOT, "singularity", "code", "screens")
    for path in sorted(glob.glob(os.path.join(screens, "*.py"))):
        with open(path, encoding="utf-8") as fd:
            for lineno, line in enumerate(fd, 1):
                if 'border_color="pane_background"' in line:
                    offenders.append("%s:%d" % (os.path.basename(path), lineno))

    assert not offenders, ("panels still edged in the fill colour: %s"
                           % ", ".join(offenders))
