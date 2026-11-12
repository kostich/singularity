"""The About box: this fork first, the original game after it, both intact.

Clicking About is how a player finds out what a build is. It has to say, in
plain words, that this is an unofficial fork -- and it has to keep showing what
it is a fork of: the original authors' names, the licence line, and upstream's
website, source tree, tracker and IRC room. Dropping any of those would be
taking credit for someone else's game.

The original paragraph is a gettext msgid translated in every catalog, so the
checks below read it from `main_menu.about_message` instead of carrying a copy
of the text. A copy would keep passing while the msgid was reworded, and a
reworded msgid is an English About box in all twenty-three languages.
"""

FORK_OPENING = "unofficial fork of Endgame: Singularity"
RULE = "---"
HEADING = "THE ORIGINAL GAME AND ITS COMMUNITY"
REPOSITORY = "https://github.com/kostich/singularity"


def about_text(graphics):
    """The text the About dialog would draw."""
    from singularity.code.screens import main_menu

    menu = main_menu.MainMenu()
    menu.visible = True
    menu.needs_reconfig = True
    menu.needs_rebuild = True
    menu.update()

    about = main_menu.AboutDialog(menu)
    about.visible = True
    about.needs_rebuild = True
    about.rebuild()

    return about.text


def test_the_first_thing_it_says_is_that_this_is_a_fork(graphics):
    text = about_text(graphics)

    assert text.startswith("Singularity 2030"), text[:120]
    assert FORK_OPENING in text
    assert "not affiliated with the original authors" in text


def test_the_fork_part_points_at_this_repository(graphics):
    """Our bugs are ours. Upstream's tracker is in the part below the rule."""
    fork_part = about_text(graphics).split(RULE)[0]

    assert REPOSITORY in fork_part
    assert "singularity/singularity" not in fork_part


def test_the_original_game_follows_the_rule_and_its_own_heading(graphics):
    lines = about_text(graphics).splitlines()

    assert RULE in lines, "the two halves need a separator"
    index = lines.index(RULE)
    assert lines[index + 1] == HEADING
    assert lines[index + 2] == "", "the heading needs a line of its own"


def test_every_line_of_the_original_msgid_is_still_there(graphics):
    """Not summarised, not reworded: the same lines, in the same order.

    The version block at the end is filled in from the running build, so its
    placeholder lines are excluded here and checked separately below.
    """
    from singularity.code.screens import main_menu

    text = about_text(graphics)
    source_lines = [_l for _l in _(main_menu.about_message).splitlines()
                    if _l and "{" not in _l]

    assert source_lines, "the original message has gone empty"
    position = -1
    for line in source_lines:
        found = text.find(line, position + 1)
        assert found > position, "missing or out of order: %r" % line
        position = found


def test_the_original_game_comes_after_the_fork(graphics):
    text = about_text(graphics)

    first = text.index(FORK_OPENING)
    heading = text.index(HEADING)
    original = text.index("Endgame: Singularity is a simulation of a true AI.")

    assert first < heading < original


def test_the_original_msgid_was_not_reworded(graphics):
    """Translations are keyed on this exact string, whitespace included.

    Editing it -- even to add our fork's name to the first line -- would have
    silently replaced the About box with English everywhere. The fork says its
    own thing in its own msgid instead.
    """
    from singularity.code.screens import main_menu

    source = main_menu.about_message

    assert source.startswith(
        "Endgame: Singularity is a simulation of a true AI.")
    for line in ("A game by Evil Mr Henry and Phil Bordelon",
                 "released under the GPL",
                 "Website: http://www.emhsoft.com/singularity/",
                 "Source code: https://github.com/singularity/singularity",
                 "Bug tracker: https://github.com/singularity/singularity/issues",
                 "IRC Room: #singularity on irc.oftc.net (port 6667)",
                 "Game Version: {VERSION}",
                 "Pygame version: {PG_VERSION}",
                 "SDL version: {SDL_VERSION}"):
        assert line in source, line
