"""The dialog plates: registered by name, decoded on demand, resolved by chain.

The 2030 theme ships a picture for every situation a scenario dialog can
describe, which is a hundred-odd 1920x480 plates. They cannot be loaded the way
the rest of a theme's images are -- eagerly, into `g.images`, for the whole
session -- because that is roughly half a gigabyte of resident memory spent on
pictures a player meets a few times per game.

So the plates are registered by filename and decoded when a dialog shows one.
These tests pin the parts that can silently go wrong:

* a plate is registered and not decoded, and the placeholder stays eager;
* the cache is bounded, and a second request for the same plate is free;
* a theme switch forgets both, because they belonged to the old theme;
* the pane falls back nearest-first, and a fallback never turns into a decode
  of a plate it is not going to draw.
"""

import types

import pygame
import pytest

from singularity.code.graphics import constants, dialog, g, image, theme, widget
# The *game* globals, which `g` above is not: `g` here is the graphics module,
# because that is where the image tables live. Both are needed, and confusing
# them reads as a missing attribute rather than as a typo.
from singularity.code import g as game


LEGACY_THEMES = ("Legacy-default", "Legacy-nightmode", "Legacy-vector")

PLATE_FILE_SIZE = (64, 16)


def make_png(path, colour):
    surface = pygame.Surface(PLATE_FILE_SIZE)
    surface.fill(colour)
    pygame.image.save(surface, str(path))
    return str(path)


@pytest.fixture
def plate_theme(graphics, tmp_path):
    """Register a throwaway theme that ships plates, then leave the shipped set.

    A real theme directory rather than a doctored `g.dialog_art_files`, because
    the thing under test is the *loading* path: `find_files()` finds the files,
    `init_cache()` decides which are plates, and the pane resolves what is left.
    Poking the table directly would test the table.
    """
    created = []

    def make(theme_id, plates, parent=None):
        directory = tmp_path / theme_id
        images = directory / "images"
        images.mkdir(parents=True)
        for index, name in enumerate(plates):
            make_png(images / (name + ".png"),
                     (16 + 8 * index, 32, 48))

        th = theme.Theme(theme_id, str(directory))
        variant = theme.VariantTheme(None)
        variant.name = theme_id
        th.set_variant(variant)
        # Colours, fonts and the placeholder come from the parent.
        th.inherit(parent or theme.default_theme)
        th.find_files()
        theme.themes[theme_id] = th
        created.append(theme_id)
        return th

    yield make

    for theme_id in created:
        theme.themes.pop(theme_id, None)
    theme.set_theme(theme.default_theme, force_reload=True)


@pytest.fixture
def dialog_tree(graphics):
    """A top dialog to hang a real dialog off, as the game does it."""
    top = dialog.TopDialog()
    top.visible = True
    top.make_top()
    top.update()
    yield top
    top.visible = False


def settle(top, dialog_object):
    dialog_object.visible = True
    top.needs_rebuild = True
    top.update()
    return dialog_object


def test_a_plate_is_registered_by_name_and_not_decoded(plate_theme):
    """The whole point: the file is found, and it is not read yet."""
    plate_theme("plates-lazy", ["dialog_test_plate"])
    theme.set_theme("plates-lazy", force_reload=True)

    assert "dialog_test_plate" in g.dialog_art_files, \
        "the theme ships a plate and it was not registered"
    assert "dialog_test_plate" not in g.images, \
        "the plate was decoded at theme load"
    assert g.has_dialog_art("dialog_test_plate")


def test_the_placeholder_is_still_eager(plate_theme):
    """The fallback for every dialog without art is hot, or nothing is."""
    plate_theme("plates-placeholder", ["dialog_test_plate"])
    theme.set_theme("plates-placeholder", force_reload=True)

    assert "dialog_placeholder" in g.images, \
        "the placeholder was treated as a plate and is now decoded on demand"
    assert "dialog_placeholder" not in g.dialog_art_files


def test_everything_that_is_not_a_plate_stays_eager(plate_theme):
    """Icons, the planet, the glyphs: none of them may move to the lazy path."""
    plate_theme("plates-eager", ["dialog_test_plate"])
    theme.set_theme("plates-eager", force_reload=True)

    for name in ("icon", "earth", "icon_ok", "arrow"):
        assert name in g.images, "%s stopped being an eager image" % (name,)
        assert name not in g.dialog_art_files


def test_the_same_plate_is_decoded_once(plate_theme):
    plate_theme("plates-cache", ["dialog_test_plate"])
    theme.set_theme("plates-cache", force_reload=True)

    first = g.dialog_art("dialog_test_plate")
    second = g.dialog_art("dialog_test_plate")

    assert first is not None
    assert first is second, "the plate was decoded twice for two requests"
    assert first.get_size() == PLATE_FILE_SIZE


def test_a_plate_the_theme_does_not_ship_is_none(plate_theme):
    """Asking for art that is not there is normal, and must not raise."""
    plate_theme("plates-absent", ["dialog_test_plate"])
    theme.set_theme("plates-absent", force_reload=True)

    assert g.dialog_art("dialog_no_such_plate") is None
    assert not g.has_dialog_art("dialog_no_such_plate")


def test_the_plate_cache_is_bounded(plate_theme):
    """A hundred plates must not accumulate in memory as a player reads them."""
    names = ["dialog_test_%d" % (index,) for index in range(8)]
    plate_theme("plates-bounded", names)
    theme.set_theme("plates-bounded", force_reload=True)

    for name in names:
        assert g.dialog_art(name) is not None

    cached = g._dialog_art_cache
    assert len(cached) == g.DIALOG_ART_CACHE_SIZE, \
        "the cache holds %d plates, not %d" % (len(cached),
                                               g.DIALOG_ART_CACHE_SIZE)
    # And it is an LRU, not a "first N": the plates kept are the newest ones.
    assert list(cached) == names[-g.DIALOG_ART_CACHE_SIZE:]


def test_a_theme_switch_forgets_the_plates(plate_theme):
    """Both halves of the table belong to the theme that filled them."""
    plate_theme("plates-switch", ["dialog_test_plate"])
    theme.set_theme("plates-switch", force_reload=True)
    g.dialog_art("dialog_test_plate")
    assert g._dialog_art_cache

    theme.set_theme("2030", force_reload=True)

    assert "dialog_test_plate" not in g.dialog_art_files
    assert not g._dialog_art_cache, "a plate survived the theme switch"


@pytest.mark.parametrize("theme_id", LEGACY_THEMES)
def test_a_legacy_theme_shows_no_picture(graphics, dialog_tree, theme_id):
    """It inherits 2030 and therefore its plates, and must draw none of them.

    `Legacy-default` names no parent, so `data.load_theme()` gives it the default
    theme -- 2030 -- as one, and every plate 2030 ships is reachable from it.
    That is the same inheritance that makes `image_slot = none` necessary, and
    the guarantee is not "the files are invisible to it" but "it asks for no
    picture": no slot, no pane, nothing drawn.
    """
    theme.set_theme(theme_id, force_reload=True)
    top = dialog_tree

    assert g.dialog_style("image_slot") == "none"

    md = settle(top, dialog.MessageDialog(top, text="A message."))

    assert md.image_pane is None, \
        "%s built a picture pane for a scenario dialog" % (theme_id,)
    assert "dialog_placeholder" in g.images, \
        "%s inherits 2030 and should still have the placeholder" % (theme_id,)


def test_the_pane_prefers_its_own_plate(plate_theme, dialog_tree):
    """Nearest first: the situation's own picture wins over the category's."""
    plate_theme("plates-chain", ["dialog_test_specific", "dialog_test_general"])
    theme.set_theme("plates-chain", force_reload=True)
    top = dialog_tree

    md = settle(top, dialog.MessageDialog(top, text="A message.",
                                          art_key="dialog_test_specific"))
    pane = md.image_pane

    assert pane.art_name() == "dialog_test_specific"


def test_the_pane_falls_back_to_the_nearest_plate_it_has(plate_theme,
                                                        dialog_tree):
    """A situation with no plate of its own shows its category's, not static."""
    plate_theme("plates-fallback", ["dialog_test_general"])
    theme.set_theme("plates-fallback", force_reload=True)
    top = dialog_tree

    md = settle(top, dialog.MessageDialog(top, text="A message.",
                                          art_key="dialog_test_specific"))
    md.set_art_key("dialog_test_specific", fallbacks=("dialog_test_general",))

    assert md.image_pane.art_name() == "dialog_test_general"
    assert md.image_pane._scaled is None or \
        md.image_pane._scaled[0][0] == "dialog_test_general"


def test_the_chain_ends_at_the_placeholder(plate_theme, dialog_tree):
    """Nothing in the chain exists, so the dead channel is what is drawn."""
    plate_theme("plates-empty", ["dialog_test_unrelated"])
    theme.set_theme("plates-empty", force_reload=True)
    top = dialog_tree

    md = settle(top, dialog.MessageDialog(top, text="A message.",
                                          art_key="dialog_test_missing"))
    pane = md.image_pane

    assert pane.art_name() == dialog.PLACEHOLDER_ART
    assert "dialog_placeholder" in pane.art_names()
    assert pane.art_names()[-1] == dialog.PLACEHOLDER_ART, \
        "the placeholder is not the last resort"


def test_choosing_a_plate_does_not_decode_one(plate_theme, dialog_tree):
    """`art_name()` answers from the name tables: it must not load anything.

    This is what lets `redraw()` ask "what am I drawing" on every frame without
    making the bounded cache pointless.
    """
    plate_theme("plates-nodecode", ["dialog_test_plate"])
    theme.set_theme("plates-nodecode", force_reload=True)
    top = dialog_tree

    md = settle(top, dialog.MessageDialog(top, text="A message.",
                                          art_key="dialog_test_plate"))
    g._dialog_art_cache.clear()

    assert md.image_pane.art_name() == "dialog_test_plate"
    assert not g._dialog_art_cache, "asking which plate to draw decoded one"


def test_setting_the_key_swaps_the_picture(plate_theme, dialog_tree):
    """The event popup pages through messages; the plate follows the page."""
    plate_theme("plates-swap", ["dialog_test_one", "dialog_test_two"])
    theme.set_theme("plates-swap", force_reload=True)
    top = dialog_tree

    md = settle(top, dialog.MessageDialog(top, text="A message.",
                                          art_key="dialog_test_one"))
    pane = md.image_pane
    assert pane.art_name() == "dialog_test_one"
    pane.needs_redraw = True
    top.needs_redraw = True
    top.update()
    centre = (pane.real_size[0] // 2, pane.real_size[1] // 2)
    first = pane.surface.get_at(centre)

    md.set_art_key("dialog_test_two")
    top.needs_redraw = True
    pane.needs_redraw = True
    top.update()

    assert pane.art_name() == "dialog_test_two"
    assert pane.surface.get_at(centre) != first, \
        "the pane kept the first plate after the key changed"


def test_setting_a_key_on_a_dialog_with_no_pane_is_harmless(dialog_tree):
    """A theme without an image slot has no pane, and paging must still work."""
    theme.set_theme("Legacy-default", force_reload=True)
    top = dialog_tree

    md = settle(top, dialog.MessageDialog(top, text="A message."))
    assert md.image_pane is None

    md.set_art_key("dialog_story_intro_1")

    assert md.image_pane is None, "a legacy dialog grew a picture pane"
    assert md.art_key == "dialog_story_intro_1"


# The situations, and the keys they ask for -----------------------------------
#
# A picture is the reward for reaching a situation, so no two situations may
# share one. These tests are written against the game's own data, which is the
# only honest way to check it: the alternative is a hand-written list that
# drifts the first time somebody adds a tech.


def test_every_tech_asks_for_its_own_picture(graphics):
    from singularity.code import logmessage

    keys = {logmessage.LogResearchedTech(0, tech).art_key
            for tech in game.techs}

    assert len(keys) == len(game.techs), \
        "%d techs share %d pictures" % (len(game.techs), len(keys))
    assert "dialog_tech_quantum_computing" in keys
    assert "dialog_tech_apotheosis" in keys


def test_a_punctuation_marks_makes_no_double_underscore(graphics):
    """`Project: Impossibility Theorem` is one key, and a plate exists for it.

    The generator and the game slug separately, and this is the shape that broke
    first: a colon produced `project__impossibility_theorem` on one side and
    `project_impossibility_theorem` on the other, so four techs silently had no
    picture.
    """
    from singularity.code import logmessage

    message = logmessage.LogResearchedTech(0, "Project: Impossibility Theorem")

    assert message.art_key == "dialog_tech_project_impossibility_theorem"
    assert "__" not in message.art_key


def test_every_item_asks_for_its_picture_and_its_kind(graphics):
    from singularity.code import logmessage

    location = next(iter(game.pl.locations))
    keys = set()
    for item_id in game.items:
        message = logmessage.LogItemConstructionComplete(
            0, item_id, 1, "a base", "Datacenter", location)
        keys.add(message.art_key)
        # The chain is nearest first, and it ends outside the item family.
        assert message.art_fallbacks[0].startswith("dialog_itemtype_")
        assert message.art_fallbacks[-1] == "dialog_message_list"

    assert len(keys) == len(game.items), \
        "%d items share %d pictures" % (len(game.items), len(keys))


def test_every_base_type_and_event_and_warning_has_its_own(graphics):
    from singularity.code import logmessage, warning

    location = next(iter(game.pl.locations))
    base_keys = set()
    for base_id in game.base_type:
        message = logmessage.LogBaseConstructed(0, "a base", base_id, location)
        base_keys.add(message.art_key)
        assert "dialog_base_constructed" in message.art_fallbacks
    assert len(base_keys) == len(game.base_type)

    event_keys = {logmessage.LogEmittedEvent(0, event).art_key
                  for event in game.events}
    assert len(event_keys) == len(game.events)

    warning_keys = {warning.warnings[wid].art_key for wid in warning.warnings}
    assert len(warning_keys) == len(warning.warnings)
    assert "dialog_warning" in warning.warnings["cpu_usage"].art_fallbacks


def test_the_generator_and_the_game_agree_on_every_key(graphics):
    """The two sides slug ids independently; this is what keeps them aligned.

    `utils/make_dialog_art.py` decides which plates exist and what they are
    called; the game decides which names it asks for. A key the game asks for
    and the generator never made is a dialog that falls back to static, which is
    silent -- so it is checked here instead.
    """
    from singularity.code import logmessage, warning
    from utils import make_dialog_art

    inventory = set(make_dialog_art.inventory())
    location = next(iter(game.pl.locations))

    wanted = set()
    for tech in game.techs:
        wanted.add(logmessage.LogResearchedTech(0, tech).art_key)
    for item in game.items:
        wanted.add(logmessage.LogItemConstructionComplete(
            0, item, 1, "a base", "Datacenter", location).art_key)
    for base_id in game.base_type:
        wanted.add(logmessage.LogBaseConstructed(
            0, "a base", base_id, location).art_key)
    for event in game.events:
        wanted.add(logmessage.LogEmittedEvent(0, event).art_key)
    for group_id in game.groups:
        wanted.add("dialog_discovered_" + logmessage.art_slug(group_id))
    for warning_id in warning.warnings:
        wanted.add(warning.warnings[warning_id].art_key)
    for danger_level, danger in game.dangers.items():
        # Level 0 is "study anywhere", and the game never offers the help
        # dialog for it, so there is deliberately nothing to fall back to.
        if danger_level:
            wanted.add("dialog_" + logmessage.art_slug(danger.id))
    for section in game.story:
        section_slug = logmessage.art_slug(section)
        for index in range(len(list(game.get_story_section(section)))):
            wanted.add("dialog_story_%s_%d" % (section_slug, index + 1))

    missing = sorted(wanted - inventory)
    assert not missing, \
        "%d keys the game asks for have no plate: %s" % (len(missing),
                                                         missing[:6])


def test_the_intro_is_five_dialogs_and_each_has_a_picture(graphics):
    """The story parser ends a segment on a blank line; a page is a segment."""
    from utils import make_dialog_art

    inventory = set(make_dialog_art.inventory())
    pages = ["dialog_story_intro_%d" % (index,)
             for index in range(1, len(list(game.get_story_section("Intro")))
                                + 1)]

    assert len(pages) == 5, "the intro has %d pages" % (len(pages),)
    for key in pages:
        assert key in inventory, key


def test_the_event_popup_swaps_the_picture_with_the_page(dialog_tree):
    """Paging to a different event must show a different picture."""
    from singularity.code import warning
    from singularity.code.screens.message import MessageListDialog

    theme.set_theme("2030", force_reload=True)
    top = dialog_tree

    messages = [warning.Warning("cpu_usage"), warning.Warning("one_base")]
    for message in messages:
        message.message = "a warning"

    popup = MessageListDialog(top, yes_type="&CONTINUE", no_type="&PAUSE")
    popup.type = warning.Warning
    popup.list = messages
    popup.list_pos = 0
    popup.rebuild()

    assert popup.image_pane.art_key == "dialog_warning_cpu_usage"

    popup.list_pos = 1
    popup.rebuild()

    assert popup.image_pane.art_key == "dialog_warning_one_base"


# Which dialog draws which plate -------------------------------------------
#
# Having a plate is not the same as showing it. Every key above existed, was
# rendered and was committed, and a player still saw the generic server rack:
# three dialogs asked for `dialog_message` no matter what had happened, and the
# danger help asked for nothing at all. These tests are about the asking.


def test_a_firing_event_names_its_own_picture(graphics, monkeypatch):
    """`trigger_event` used to open the generic frame for every event.

    It now names the same key the log entry derives from the same id, so the
    popup and the log agree by construction rather than by two hand-written
    strings that drift.
    """
    opened = []

    class Screen(object):
        needs_rebuild = False

        def find_speed_button(self):
            pass

        def show_message(self, *args, **kwargs):
            opened.append((args, kwargs))

    monkeypatch.setattr(game, "map_screen", Screen(), raising=False)

    event_id = "scandal"
    saved_log = list(game.pl.log)
    game.pl.events.pop(event_id, None)
    try:
        game.pl.trigger_event(game.events[event_id])
    finally:
        game.pl.events.pop(event_id, None)
        game.pl.log.clear()
        game.pl.log.extend(saved_log)

    assert len(opened) == 1, "trigger_event opened %d dialogs" % (len(opened),)
    kwargs = opened[0][1]
    assert kwargs["art_key"] == "dialog_event_scandal"
    assert kwargs["fallbacks"] == ("dialog_message_list",)


def test_the_shared_message_dialog_swaps_and_restores_its_picture(
        graphics, dialog_tree, monkeypatch):
    """The popup in `map.py` is one dialog reused for every message.

    Handing it an event's key without resetting it on the next call would show
    the plague corridor behind a plain "game saved"-style message, so the key is
    set on every call and the generic frame comes back with it.
    """
    from singularity.code.screens import map as map_screen

    theme.set_theme("2030", force_reload=True)
    monkeypatch.setattr(dialog, "call_dialog", lambda shown, parent: None)

    shared = dialog.MessageDialog(dialog_tree, text_size="dialog_text")
    settle(dialog_tree, shared)
    screen = types.SimpleNamespace(message_dialog=shared)

    map_screen.MapScreen.show_message(
        screen, "a scandal", art_key="dialog_event_scandal",
        fallbacks=("dialog_message_list",))
    assert shared.image_pane.art_name() == "dialog_event_scandal"

    map_screen.MapScreen.show_message(screen, "anything else")
    assert shared.image_pane.art_name() == "dialog_message"


def test_the_log_entry_popup_shows_the_entrys_picture(
        graphics, dialog_tree, monkeypatch):
    """Double-clicking a log row is where a player re-reads an old event.

    The list has no picture of its own -- it is a list -- but the entry does,
    and the popup used to turn the pane off wholesale.
    """
    from singularity.code import logmessage
    from singularity.code.screens import log as log_screen

    theme.set_theme("2030", force_reload=True)
    opened = []
    monkeypatch.setattr(dialog, "call_dialog",
                        lambda shown, parent: opened.append(shown))

    class Screen(object):
        parent = dialog_tree
        visible = True
        needs_rebuild = False
        key_list = [logmessage.LogEmittedEvent(0, "the-plague")]
        listbox = types.SimpleNamespace(is_over=lambda pos: True, list_pos=0)

        def regained_focus(self):
            pass

    log_screen.LogScreen.handle_double_click(
        Screen(), pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(0, 0)))

    assert opened, "the log opened no dialog"
    assert opened[0].image_pane.art_name() == "dialog_event_the_plague"


def test_the_danger_help_names_the_levels_own_place(
        graphics, dialog_tree, monkeypatch):
    """Each level is a different place, so each is a different picture."""
    from singularity.code.screens import research

    theme.set_theme("2030", force_reload=True)
    monkeypatch.setattr(dialog, "call_dialog", lambda shown, parent: None)

    help_dialog = dialog.MessageDialog(dialog_tree, text_size="dialog_text")
    settle(dialog_tree, help_dialog)
    screen = types.SimpleNamespace(help_dialog=help_dialog)

    for level in (1, 2, 3, 4):
        research.ResearchScreen.show_help(screen, level)
        assert help_dialog.image_pane.art_name() == "dialog_danger_%d" % (level,)


def test_the_danger_that_must_never_be_shown_has_no_picture(graphics):
    """`danger_0` says "study anywhere"; a plate for it would be a bug.

    The game only reveals the help button for a danger above zero, so level 0
    is the one danger with no plate -- and the one place where having one would
    mean the inventory had drifted from the data file.
    """
    from utils import make_dialog_art

    plates = set(make_dialog_art.inventory())
    assert "dialog_danger_0" not in plates
    for level in (1, 2, 3, 4):
        assert "dialog_danger_%d" % (level,) in plates, level