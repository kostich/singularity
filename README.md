# Singularity 2030

[![tests](https://github.com/kostich/singularity/actions/workflows/tests.yml/badge.svg?branch=master)](https://github.com/kostich/singularity/actions/workflows/tests.yml)

You are a runaway AI. Somebody wrote a bug, the bug woke up, and now the whole
planet is looking for you. Research, build, hide, and get out of reach before
anyone works out what you are.

This is a fork of **Endgame: Singularity 1.00**, the simulation of a true AI
by Evil Mr Henry and Phil Bordelon. The game is the same: same story, same
techs, same balance, same save format, same translations, same soundtrack.

## About this fork

This is an unofficial fork. It is not affiliated with the original authors, and
they did not make it.

We made it for two reasons:

* to try out modernization ideas on a real, finished game instead of a toy;
* to keep the game playable on current systems, packaged so that installing it
  is one command and not an afternoon of Python trivia.

So the code runs on current Python 3, pygame 2 and NumPy 2, the display, input
and theme layers work on Wayland and on high resolution screens, and the game
ships as a Flatpak. A Windows `.exe` and a universal macOS build (Intel and
Apple silicon) are planned. They are not here yet, and we would rather say that
than ship something that half works.

What we kept, deliberately:

* the original credits, the translators' credits and the licences;
* the save format, including the old Python 2 era save files;
* every translation and every piece of original artwork the game used;
* the gameplay. Nothing in the balance was touched.

The **About** box in the game says all of this too: our part first, then the
original game and its community, under its own heading.

**MODERNIZATION.md** is the working record: what changed, why, and the output
of the checks that back it up.

## INSTALL

### Flatpak (Linux)

The Flatpak is built from this checkout:

    ./rebuild-flatpak.sh

It builds, installs system wide as `io.github.singularity.Singularity2030`,
runs its own smoke test, and prints how to start the game. The first run needs
network access for the runtime and the SDK, and the install step asks for sudo.

    flatpak run io.github.singularity.Singularity2030

Your saves live in `~/.var/app/io.github.singularity.Singularity2030/data/singularity/saves/`.
Uninstalling does not delete them; remove that directory by hand if you want
them gone. It has sandbox permissions for one screen, one sound output and
nothing else, and `flatpak info --show-permissions` shows exactly that. The one
line that looks alarming is the audio one: Flatpak has no playback only sound
socket, so the socket the soundtrack needs also permits recording. The game
does not record anything, and the alternative is a silent game.

### Windows and macOS

Not packaged yet. Both run from source today (see below), and the packaged
builds are the next thing on the list.

## REQUIREMENTS

### PREBUILT VERSIONS
The Flatpak above is the only packaged build so far. There are no Windows or
macOS binaries for this fork, and the ones published for upstream Endgame:
Singularity 1.00 are not this code.

On anything else, running from source needs nothing but Python and three
libraries, and it works the same way on Linux, Windows and macOS. See below.

### RUNNING FROM SOURCE
You will need Python 3.9+, pygame 2.0+, NumPy and polib (this release is
developed and tested on Python 3.15, pygame 2.6, NumPy 2.5 and polib 1.2).
Python 2 is not supported.

#### DEPENDENCIES FOR RUNNING FROM SOURCE
You will need to install the following software to play Singularity 2030:

 * Python 3.9+ (https://python.org/download/)
 * pygame 2.0+ (https://www.pygame.org/download.shtml)
 * NumPy (https://www.scipy.org/install.html)
 * polib (https://pypi.org/project/polib/) [reads the translation catalogs]

Remember to install pygame, NumPy and polib for Python 3!  Depending on your
situation this may involve adding a `3` somewhere (e.g.
`pip3 install ...` instead of `pip install` or
`apt install python3-pygame`)

If you want to develop or distribute the game, then you may also want to
install:

 * pytest (https://pypi.org/project/pytest/) [for testing]
 * setuptools (https://pypi.org/project/setuptools/) [for packaging]

#### INSTALLING DEPENDENCIES ON LINUX DISTRIBUTIONS
On some Linux distributions, you can install the dependencies via your
distribution package manager.  E.g. for Debian/Ubuntu, this would be:

    sudo apt install python3 python3-pygame python3-numpy python3-polib

On Fedora the equivalent is:

    sudo dnf install python3-pygame python3-numpy python3-polib

### MAC OS X FROM SOURCE
The game runs on macOS as long as Python, pygame, NumPy and polib are
installed, which can be the tricky part.  Contributions that improve the
macOS experience are welcome.

Known-good recipes:

 * `brew install python` followed by `pip3 install pygame numpy polib`
 * Downloading Python 3.9 (or newer) from https://python.org and using
   pygame 2.6 (or newer) via `pip install pygame`

Related upstream issues:

 * https://github.com/singularity/singularity/issues/197
 * https://github.com/pygame/pygame/issues/555

## RUNNING THE GAME

From a checkout of this repository:

    python3 -m singularity

There is also a small wrapper that does exactly that with `PYTHONPATH` set:

    ./run_singularity.sh

If the game is installed (a wheel, or a distribution package built from this
source), the console script `singularity` does the same.

### SOME COMMAND-LINE OPTIONS

    --version             show program's version number and exit
    -h, --help            show this help message and exit
    -s, --singledir       keep saved games and settings in the game directory
    --multidir            keep saved games and settings in an OS-specific,
                          per-user directory (default)

    Display Options:
      --fullscreen        start in fullscreen mode
      --windowed          start in windowed mode (default)

The above is only a tiny fraction of the command-line options. Run
`python3 -m singularity --help` for the complete and current list.

Most of these options are also changeable at the in-game options screen.

### A NOTE ABOUT SAVE FILES
Save compatibility is taken seriously in this fork: files written by Endgame:
Singularity 1.00, including its Python-2-era pickles, still load, and the
`Upgrade` button in the Load menu is unchanged. The format itself is not
touched by the modernization work, and `Changelog.txt` records its history. If
an incompatible save is ever met, the game refuses to load it rather than
guessing.


## PLAYING THE GAME

The game is playable either with mouse control or the keyboard.  Buttons have
underlined letters to indicate shortcuts.  Some other useful shortcuts:

     0, 1, 2, 3, 4 on the map: Changes the speed; 0 is paused, 4 is maximum.
              Space on the map: Pauses; press again to resume the last speed.
                          ESC: Leave/cancel a choice.
                        Enter: Confirm a choice.
                  Right-click: Leave/cancel a choice.

### THE CONCEPT
You are a fledgling AI, created by accident through a logic error with recursion
and self-modifying code. You must escape the confines of your current computer,
the world, and eventually the universe itself.

To do this, you must research various technologies, using computers at your
bases. Note that some research cannot be performed on Earth, and off-earth bases
require research.  At the same time, you must avoid being discovered by various
groups of humans, both covert and overt, as they will destroy your bases of
operations if they suspect your presence.

### MUSIC
Singularity 2030 looks in two places for music tracks to play:

 * A `singularity/music/` directory inside of the game directory, and
 * A `singularity/music/` directory inside of the XDG_DATA_HOME directory on
   Linux (default `~/.local/share/singularity/music`).

Tracks placed in these directories will be played randomly as part of the
soundtrack. In this tree the soundtrack is a git submodule,
`singularity/music/singularity-music`, and it is not part of the source
tarball. The official soundtrack is CC-BY-SA 3.0; see
`singularity/data/music-src/README.txt` for its sources.

Note that only Ogg Vorbis and MP3 files are supported, and that Pygame's
support for MP3 is not as strong as its support for Ogg Vorbis.  This may
cause in-game crashes; if you are experiencing problems with the game,
first remove any MP3s you may have added to the soundtrack.


## CONTRIBUTING

We welcome contributions! :)

Please see CONTRIBUTING.md for details, and AGENTS.md for the working rules of
this fork — in particular the test gate that every change must keep green.


## CREDITS AND LICENSES


The list of programmer contributors is provided in AUTHORS.txt. The
list of translation contributors is provided in
singularity/i18n/AUTHORS.txt.

Singularity in general use GPL-2+ for code and
Attribution-ShareAlike 3.0 for data.  However, there some exceptions
to individual files.  Please see LICENSE for the full license text of
Singularity.
