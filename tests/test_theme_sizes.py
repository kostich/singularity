"""A theme's [sizes] section, and the guarantee that it cannot leak.

The type scale is the one part of the theme format that a widget does not read
until it is *resized*: reconfig() re-resolves a size name, but a font is only
measured in resize(). That makes it the easiest thing in the engine to get
subtly wrong -- switch theme and every widget keeps the old size until
something else happens to resize it -- so both halves are pinned here.
"""

import pytest

from singularity.code.graphics import dialog, g, text
from singularity.code.graphics import theme


@pytest.fixture
def scaled_theme(graphics):
    """Register throwaway themes for one test, then leave the shipped set.

    A Theme needs no directory for this: init_cache() only reads images and
    fonts from disk when the theme declares some.
    """
    created = []

    def make(theme_id, sizes=None, parent=None):
        th = theme.Theme(theme_id, "/nonexistent/" + theme_id)
        variant = theme.VariantTheme(None)
        variant.name = theme_id
        for name, value in (sizes or {}).items():
            variant.set_size(name, value)
        th.set_variant(variant)
        # A theme with neither fonts nor a parent has no 'normal' face at all,
        # which the widget tree needs as soon as anything reconfigures.
        th.inherit(parent or theme.default_theme)
        theme.themes[theme_id] = th
        created.append(theme_id)
        return th

    yield make

    for theme_id in created:
        theme.themes.pop(theme_id, None)
    theme.set_theme(theme.default_theme, force_reload=True)


@pytest.fixture(autouse=True)
def _shipped_size_layers(graphics, scaled_theme):
    """Every test starts from the shipped layers, whoever ran before it."""
    g.user_text_sizes.clear()
    g.rebuild_text_sizes()
    theme.set_theme(theme.default_theme, force_reload=True)
    yield
    g.user_text_sizes.clear()
    g.rebuild_text_sizes()
    theme.set_theme(theme.default_theme, force_reload=True)


def test_a_theme_with_no_sizes_leaves_the_shipped_scale(graphics):
    """The legacy themes pin the shipped scale, so 2030 cannot reach them."""
    for theme_id in ("Legacy-default", "Legacy-nightmode", "Legacy-vector"):
        theme.set_theme(theme_id, force_reload=True)
        assert g.configured_text_sizes == g.default_text_sizes, theme_id
        assert g.theme_text_sizes == g.default_text_sizes, theme_id

    theme.set_theme(None, force_reload=True)


def test_the_2030_theme_sets_the_scale(graphics):
    theme.set_theme("2030", force_reload=True)

    assert g.configured_text_sizes == {
        "default": 20,
        "dialog_text": 15,
        "button": 30,
        "suspicion_bar": 36,
        "time_display": 30,
        "resource_display": 30,
        "report_content": 18,
    }


def test_switching_back_to_a_legacy_theme_restores_every_size(graphics,
                                                             scaled_theme):
    """A size set by one theme must not survive into the next one."""
    theme.set_theme("2030", force_reload=True)
    assert g.configured_text_sizes["button"] == 30

    theme.set_theme("Legacy-default", force_reload=True)
    assert g.configured_text_sizes == g.default_text_sizes

    theme.set_theme(None, force_reload=True)
    assert g.configured_text_sizes["button"] == 30


def test_a_theme_without_sizes_inherits_its_parents(graphics, scaled_theme):
    """Same rule as colours: what a theme does not say, its parent does."""
    scaled_theme("sizes-child", parent="2030")

    theme.set_theme("sizes-child", force_reload=True)
    assert g.configured_text_sizes["time_display"] == 30


def test_a_child_overrides_its_parent(graphics, scaled_theme):
    scaled_theme("sizes-child", {"time_display": 40}, parent="2030")

    theme.set_theme("sizes-child", force_reload=True)
    assert g.configured_text_sizes["time_display"] == 40
    assert g.configured_text_sizes["button"] == 30  # still from the parent


def test_the_players_choice_wins_over_the_theme(graphics):
    """A hand-edited preference is applied on top of whatever the theme says."""
    g.user_text_sizes["button"] = 44
    try:
        g.rebuild_text_sizes()
        theme.set_theme("2030", force_reload=True)
        assert g.configured_text_sizes["button"] == 44
        assert g.configured_text_sizes["time_display"] == 30
    finally:
        g.user_text_sizes.pop("button", None)
        g.rebuild_text_sizes()


@pytest.mark.parametrize("name,value", [
    ("nonsense", 12),      # no widget reads it, so it must not be stored
    ("default", "abc"),    # not a number
    ("default", "0"),      # a zero-point face measures nothing
    ("default", "-4"),
    ("default", None),
])
def test_a_bad_size_is_ignored(graphics, name, value):
    variant = theme.VariantTheme(None)
    variant.set_size(name, value)
    assert variant.size_infos == {}


def test_a_size_change_makes_the_tree_measure_again(graphics):
    """Without this flag the new scale would not take effect until a resize."""
    top = dialog.TopDialog()
    top.visible = True
    top.make_top()
    top.update()

    label = text.Text(top, (0, 0), (.5, .5), text="VESSEL", text_size="button")
    top.update()
    before = label.max_size
    assert not top.needs_resize

    fake = theme.Theme("sizes-bigger", "/nonexistent/sizes-bigger")
    variant = theme.VariantTheme(None)
    variant.set_size("button", 60)
    fake.set_variant(variant)
    fake.inherit(theme.default_theme)  # for its fonts
    theme.themes["sizes-bigger"] = fake
    try:
        theme.set_theme("sizes-bigger", force_reload=True)

        assert top.needs_resize, "a bigger button size must be measured"
        assert top.needs_reconfig

        top.update()
        assert label.max_size > before
    finally:
        theme.themes.pop("sizes-bigger", None)
        theme.set_theme(theme.default_theme, force_reload=True)


def test_an_unknown_name_never_reaches_the_live_dict(graphics):
    """A typo must not invent a setting that save_options() then persists."""
    g.theme_text_sizes["typo_size"] = 99
    try:
        g.rebuild_text_sizes()
        assert "typo_size" not in g.configured_text_sizes
    finally:
        g.theme_text_sizes.pop("typo_size", None)
        g.rebuild_text_sizes()
