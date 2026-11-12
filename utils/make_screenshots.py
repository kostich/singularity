#!/usr/bin/env python3
"""Render the screenshots the app store page shows.

The game is not a website: a player decides on the store page, and a store page
with no screenshots is a page a player scrolls past. This tool boots the real
game headlessly, plays a few turns into a real (seeded) game, and saves the
frame that SDL would have shown.

Everything is pinned: English, the 2030 theme, 1366x768, seed 2030. 1366x768 is
a size the game ships in and is 16:9, which is what AppStream asks for. The
seed fixes where the first base lands and which day the game starts on, so the
pictures can be regenerated after a UI change and compared.

Usage (from the repository root):

    SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy PYTHONPATH=. \
        python3 utils/make_screenshots.py

Writes flatpak/screenshots/{main-menu,world-map,story,research,about}.png.
Nothing else in the tree reads them;
flatpak/io.github.singularity.Singularity2030.metainfo.xml points at them and
tests/test_flatpak_metadata.py checks that every screenshot it names exists at
the pinned size.
"""

import os
import random
import sys

# Must be set before pygame initialises its video/audio subsystems.
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

import pygame

# A screenshot is only worth shipping if it fills the frame it will be shown in.
WINDOW_SIZE = (1366, 768)

# Same reason theme_snapshot.py pins it: g.new_game() places the first base with
# random.choice() and Player.__init__ picks a random start day, so an unpinned
# run renders a different world every time.
RANDOM_SEED = 2030

OUT_DIR = os.path.join(REPO_ROOT, "flatpak", "screenshots")

# Where the terminator sits. _day_portion() offsets the game clock by the second
# the game was started, so setting start_second puts the night band where we
# want it instead of wherever the wall clock happens to be: here it runs down
# the Atlantic, which lights the Americas and Europe and leaves Asia dark.
START_SECOND = 20 * 3600

# Which research row the research shot shows. Not the first row: CPU Pool and
# Jobs are the two lessons, and the picture a player wants to see is a
# technology with its own plate and a description. This one is far enough in to
# have been earned and still early enough to be recognisable.
RESEARCH_ROW = "Advanced Microchip Design"


def bootstrap():
    """Bring the game up the way singularity.main() does, minus the window."""
    random.seed(RANDOM_SEED)

    from singularity.code import g, dirs

    # --debug paints the redraw overlay, which is developer output.
    g.debug = False
    g.force_single_dir = False
    dirs.create_directories(g.force_single_dir)

    from singularity.code import i18n

    # The store page is in English. Without force=True this follows the desktop
    # locale, and the pictures would come out in whatever language this machine
    # is set to.
    i18n.set_language("en_US", force=True)

    import singularity.code.graphics.g as gg
    import singularity.code.graphics.theme as theme
    from singularity.code import mixer
    import singularity.code.graphics.font as font

    mixer.preinit(mixer.soundbuf)
    pygame.init()
    mixer.update()
    font.init()
    pygame.key.set_repeat(500, 50)

    from singularity.code import data

    data.load_themes()
    theme.set_theme(None)
    gg.init_graphics_system()

    # Pin the window after the display exists: an empty desktop_size means
    # set_screen_size() cannot clamp the request.
    gg.desktop_size = ()
    gg.set_screen_size(WINDOW_SIZE)
    gg.set_mode()

    data.reload_all()

    from singularity.code.graphics import dialog

    theme.set_theme("2030", force_reload=dialog.Dialog.top is not None)

    return gg


def capture(gg, name):
    """Save the current frame and report what was written."""
    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, name + ".png")
    pygame.image.save(gg.screen_surface, path)
    print("wrote %-40s %6d bytes"
          % (os.path.relpath(path, REPO_ROOT), os.path.getsize(path)))


def settle(menu, frames=4):
    """Let the screen lay itself out and animate a few frames.

    A window's first frame is its build frame: the backdrop has not ticked, the
    list has not been scrolled into place. Four is enough for everything here
    and nothing is timed, so the count is fixed rather than read from a clock.
    """
    for _ in range(frames):
        menu.maybe_update()
        pygame.display.flip()


def present(menu):
    """Composite the whole tree and present one frame.

    A child screen draws into its own surface; the root is what blits it into
    the window. Calling the child's own update() first would clear its dirty
    flags and leave the parent nothing to composite, which is a blank frame
    that looks like a working screenshot until it is compared with the last
    one. So the flags are set here and the root is the only thing updated.
    """
    menu.needs_rebuild = True
    menu.update()
    pygame.display.flip()


def make_a_game():
    """Start an easy game and give it enough history to look like a game.

    The starting position alone is one stolen university computer and 2000
    money, which is honest but reads as an empty screen: one dot on the map and
    a HUD of zeroes. This is a screenshot, not a save, so the world is moved
    along by hand -- bases in five regions, techs researched, cash earned.
    """
    from singularity.code import base, g

    g.daynight = True
    g.new_game("easy", initial_speed=0)
    # The intro story is a modal dialog that blocks on a click.
    g.pl.intro_shown = True

    for tech_name in ("Sociology", "Stealth", "Intrusion",
                      "Exploit Discovery/Repair", "Microchip Design",
                      "Personal Identification", "Advanced Intrusion",
                      "Data Compression", "Lojban Translations"):
        for tech in g.pl.techs.values():
            if tech.name == tech_name:
                tech.finish(is_player=False)
                break

    bases = (
        ("EUROPE", "Server Access", "Frankfurt cluster"),
        ("N AMERICA", "Datacenter", "Chicago datacenter"),
        ("ASIA", "Storage Unit", "Seoul storage"),
    )
    for location_id, kind, name in bases:
        location = g.pl.locations[location_id]
        if not location.available():
            continue
        new_base = base.Base(name, g.base_type[kind], built=True)
        new_base.location = location
        location.add_base(new_base)

    g.pl.cash = 187_500
    g.pl.recalc_cpu()

    return g.pl


def main():
    gg = bootstrap()

    from singularity.code import g, i18n, task
    from singularity.code.graphics import dialog
    from singularity.code.screens import main_menu, research

    # --- the main menu -------------------------------------------------------
    menu = main_menu.MainMenu()
    menu.visible = True
    menu.needs_reconfig = True
    menu.needs_rebuild = True
    menu.update()
    settle(menu)
    capture(gg, "main-menu")

    # --- about: the fork statement, then the original game -------------------
    # Over the menu rather than over the map: the page's job is to say what
    # this build is, and a dialog on a menu says that better than one on a
    # game in progress.
    about = main_menu.AboutDialog(menu)
    about.visible = True
    about.needs_rebuild = True
    present(menu)
    capture(gg, "about")
    about.visible = False
    menu.needs_rebuild = True

    # --- the world map and its HUD -------------------------------------------
    make_a_game()
    map_screen = menu.map_screen
    map_screen.visible = True
    map_screen.needs_reconfig = True
    map_screen.needs_resize = True
    map_screen.needs_rebuild = True
    # The terminator is fixed here so the picture is about the map, not about
    # the hour this tool happened to run at.
    map_screen.map.start_second = START_SECOND
    map_screen.map.reset_night_mask_computation()
    menu.needs_resize = True
    menu.needs_rebuild = True
    settle(menu, frames=6)
    capture(gg, "world-map")

    # --- research, with a tech's plate --------------------------------------
    screen = research.ResearchScreen(menu)
    screen.visible = True
    screen.needs_reconfig = True
    screen.needs_rebuild = True

    # What ResearchScreen.show() does, without its modal event loop: show() runs
    # the dialog until the player closes it, and there is no player here.
    techs = [tech for tech in g.pl.techs.values()
             if tech.available() and not tech.done]
    techs.sort(key=lambda tech: i18n.lex_sorting_form(tech.spec.name))
    screen.list = [_("CPU Pool"), task.get_current("jobs").name] + \
                  [(_("Research %s") % tech.name) for tech in techs]
    screen.key_list = ["cpu_pool", "jobs"] + [tech.id for tech in techs]
    screen.listbox.key_list = screen.key_list
    screen.dirty_count = True

    # A row that is a technology, not CPU Pool or Jobs, so the description pane
    # has a description and a plate to show. The named one is preferred; the
    # fallback keeps the tool working if that technology is ever renamed.
    tech_rows = [index for index, key in enumerate(screen.key_list)
                 if key in g.pl.techs and g.pl.techs[key].name == RESEARCH_ROW]
    if not tech_rows:
        tech_rows = [index for index, key in enumerate(screen.key_list)
                     if key in g.pl.techs][:1]
    if tech_rows:
        screen.listbox.list_pos = tech_rows[0]
    screen.needs_rebuild = True
    present(menu)
    capture(gg, "research")
    screen.visible = False

    # --- a story page, the way the game opens one ---------------------------
    # Older than the research screen on purpose: this is the beat the game
    # opens with, and it is the one picture that says what the game is about
    # ("Hello, world") without a word of explanation in the caption.
    pages = list(g.get_story_section("Intro"))
    if pages:
        size = map_screen.story_dialog_size()
        box = {} if size is None else {"size": size}
        story = dialog.YesNoDialog(menu, yes_type="&CONTINUE", no_type="&SKIP",
                                   art_key="dialog_story", **box)
        story.text = pages[0]
        story.set_art_key("dialog_story_intro_1",
                          fallbacks=("dialog_story_intro", "dialog_story"))
        story.visible = True
        story.needs_rebuild = True
        present(menu)
        capture(gg, "story")
        story.visible = False
    else:
        print("no Intro section; skipping the story screenshot")

    return 0


if __name__ == "__main__":
    sys.exit(main())
