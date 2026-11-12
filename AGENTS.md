# AGENTS.md — working notes for this repo

## What this is

An unofficial hard fork of **Endgame: Singularity 1.00** (a simulation about a
runaway AI), presented as **Singularity 2030** and nowhere else. Code is
GPL-2+; data (images, soundtrack) is CC-BY-SA 3.0.

It is a hard fork, not a patch set for upstream: these changes are not meant to
be merged back, the presentation is ours, and the original authors are not
involved. What the fork is for: try out modernization ideas and keep the game
playable on current systems by packaging it (Flatpak now, Windows and macOS
next). What it must keep: the original credits, the translators' credits, the
licences, the save format and every translation. See §39 of
`MODERNIZATION.md`.

All work happens on **`master`**. It is this fork's main branch, and it sits
directly on upstream `99729e8` (upstream's 1.1 plus the unreleased 1.1.1). The
fork's own work is six commits above that base, one per area: the Python 3
alignment, the display and dialog frame, the 2030 theme and its art, the
catalogs and tests, the fork's name, and the packaging. `MODERNIZATION.md` §13
names them and §40 explains how that history was built and what it costs. Use
`git log -1 --oneline` for the current HEAD; it is not pinned here because it
changes with every commit.

`origin` is this fork's own repository, `github.com:kostich/singularity`, a
public GitHub fork of `singularity/singularity`. Upstream's remote is not
configured, so a stray `git push` cannot reach `singularity/singularity`.
Re-add it as `upstream` if you ever need it.

**Commit to `master`.** It is this fork's only branch and every change lands
there. Do not cut a branch off it for new work, even a short-lived one: one
branch, `master`, and no second name for the same commit.

## Read this before you plan anything

**This was already a Python 3 codebase.** A 2020-era one, but Python 3. There was
never a python2→python3 port to do. If you are planning a rewrite, you have
misread the situation. The job is: delete dead shims, clear deprecations, keep
behaviour identical.

Every change here is behaviour-preserving. If a change alters gameplay, save
compatibility or a translation, it is a bug in the change.

## Non-negotiables

- **Keep the gate green.** Run both commands below after every change and quote
  the raw output. Red means stop and fix, not proceed.
- **Do not weaken tests.** If a test genuinely must change, justify it in the
  commit message. Never delete an assertion to make something pass.
- **Save compatibility is sacred.** `singularity/code/savegame.py` loads
  Python-2-era pickles and has an `Upgrade` button in the Load menu;
  `Changelog.txt` records the format history. Do not touch the format.
- **Do not touch the music submodule.** `singularity/music/singularity-music`
  (17 CC-BY-SA Ogg tracks) is a submodule, deliberately uncommitted and excluded
  from tarballs by `.gitattributes`. Leave it, `.gitmodules` and `.gitattributes`
  alone.
- **No reformatting, no re-architecting, no drive-by cleanup.** One item, one
  commit, minimal diff.
- **Small separate commits**, one item each, on `master`. Do not push or open a
  PR unless asked in the current message.
- **Keep `MODERNIZATION.md` in sync.** It is the authoritative record of the
  fork's changes. Every commit that changes behaviour, packaging, docs or
  tooling adds or amends its entry (what, why, and the verified output) in the
  same commit — not in a later "docs" commit.

## Environment

The versions the gate below was last run against. They are what this tree is
known to work with, not a floor it requires.

| Component | Version | Source |
|---|---|---|
| Distro | Fedora 45 Workstation, Wayland | — |
| Python | 3.15.0 (`/usr/bin/python3`) | — |
| pygame | 2.6.1 (SDL 2.32.74) | `python3-pygame` |
| NumPy | 2.5.4 | `python3-numpy` |
| polib | 1.2.0 (`python3-polib-1.2.0-16.fc45`) | `python3-polib` |
| pytest | 9.1.1 | `python3-pytest` |

**No virtualenv, and do not add one.** There is no pygame wheel on PyPI for
CPython 3.15, so the distro package is the only sane route. The game runs
straight from the checkout.

```sh
sudo dnf install -y python3-pygame python3-numpy python3-pytest python3-polib
```

`polib` is a **hard runtime dependency** — it parses the `.po` catalogs at
startup, so the game will not start without it.

## The gate

Run both after every change:

```sh
# from the root of this checkout

# unit tests — expect: 940 passed, 1 xpassed, and NO warnings line
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy PYTHONPATH=. \
    python3 -m pytest -q tests/

# headless UI harness, 17 steps — expect: ALL HARNESS STEPS PASSED
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy PYTHONPATH=. \
    python3 utils/ui_smoke_test.py

# the real game (opens a window)
./run_singularity.sh --debug
```

The dialog art has its own two commands. `--list` is what proves the generator
and the game agree: it prints one line per plate and flags any situation with no
brief, and any brief with no situation.

```sh
# the inventory: 156 plates, no MISSING BRIEF, no ORPHAN BRIEF
python3 utils/make_dialog_art.py --list

# every plate is 1920x480, below the body text, and unlike every other plate
python3 utils/make_dialog_art.py --check
```

`DESIGN.md` is the style contract for those plates, and it is the script that is
authoritative where the two disagree.

The type and the glyphs have a check each. The font one is the interesting one:
it asks the shipped catalogues which characters the game actually draws, and the
fonts' own cmaps whether they can draw them. "Supports Cyrillic" is a claim; this
is the measurement that found Exo 2 had no Greek.

```sh
# every character the translations use, in every shipped face
python3 utils/font_coverage.py

# the glyphs: 64x64, real ink, no two alike, sources and licence present
python3 utils/make_icon_set.py --check
```

`utils/make_icon_set.py` needs ImageMagick to rasterise the vendored SVGs into
`images/icon_*.png`. That is a build-time dependency only — the committed PNGs
are what the game loads — and the SVGs are committed so it works offline.

The counts above move when content or tests are added, so treat the number the
suite prints as the truth and fix this file when it drifts. `919` is what it
reports with upstream 1.1 and 1.1.1 merged in.

`1 xpassed` is **expected and correct**:
`tests/test_translations.py::test_root_collation` is marked `xfail` with the
comment "Fails in github actions"; it passes on this machine. Leave the marker
alone — "fixing" the xpass by deleting the marker is wrong.

The Flatpak is **outside** the gate and does not replace it:
`./rebuild-flatpak.sh` builds `flatpak/io.github.singularity.Singularity2030.yml`
and installs it system-wide (sudo for the install and the runtimes; no
`flatpak-builder` as root). It is the only thing that proves the sandboxed app
starts, so run it after touching anything the install depends on
(`__init__.py`, `dirs.py`, `i18n.py`, `mixer.py`). `build/` is gitignored;
`flatpak/` and `rebuild-flatpak.sh` are not.

## Deeper diagnostic recipes

Normal runs hide defects. Use these when touching anything resource- or
locale-related:

| Probe | Catches |
|---|---|
| `python3 -X dev -m pytest -q tests/` | `ResourceWarning` — unclosed files, leaked handles |
| `python3 -W error::DeprecationWarning -m pytest -q tests/` | deprecations as hard failures |
| `PYTHONWARNDEFAULTENCODING=1 … pytest -q tests/` | text `open()` with no `encoding=` |

All three are currently clean. Each one found a real bug the first time it was
run (see *Traps*).

## Codebase map

```
singularity/
  __init__.py          argparse CLI, prefs loading, pygame bootstrap, main()
  __main__.py          thin entry point for `python3 -m singularity`
  code/g.py            global mutable state (g.pl, g.story, g.data_strings…)
  code/data.py         loads the ConfigParser-format .dat content files
  code/savegame.py     .sav (py2 pickle) + .s2 (JSON) loading, format upgrades
  code/i18n.py         language selection, .po→.mo generation, gettext install
  code/mixer.py        sound/music; degrades gracefully with no audio device
  code/player.py       the AI itself: cash, cpu, suspicion, locations, techs
  code/buyable.py      shared cost/progress logic for techs, items and bases
  code/spec.py         declarative field definitions shared by the above
  code/safety.py       exception logging / crash dialog
  code/graphics/       widget toolkit: widget, dialog, button, text, listbox…
  code/screens/        the screens themselves (map, research, options…)
  data/                .dat content, theme images, one click sound
  i18n/                lang_*/ .po catalogs, languages.json
  music/               git submodule — do not touch
tests/                 pytest suite + savegame fixtures
utils/
  ui_smoke_test.py     REQUIRED headless UI harness (17 steps over real screens)
  data-translations.py dev tool: regenerates the .po catalogs
flatpak/               Flatpak manifest, AppStream data, icons, launcher
rebuild-flatpak.sh     builds the Flatpak and installs it system-wide
MODERNIZATION.md       authoritative change record + environment + evidence
```

`MODERNIZATION.md` is the authoritative record of what changed and why, with the
evidence for each change. Read it before editing; extend it in the same commit
as the change.

## Traps and gotchas

All of these cost real time. Read before editing.

**`README.md` is the real file; `README.txt` no longer exists.** It used to be a
symlink (git mode `120000`), which meant every edit went through the link and
`git status` only mentioned `README.txt`. Do not reintroduce the second name.

**The in-game About text is a translated `msgid`.** `about_message` in
`screens/main_menu.py` still says "Endgame: Singularity" because that exact
string is translated in all nine catalogs. Renaming it in the source would
silently drop the About box back to English everywhere; change the `.po`
catalogs too, or leave it.

**`.gitignore` used to hide new files under `.github/`.** Its `.*` rule ignored
every dotfile and only `.travis.yml`/`.codecov.yml` were whitelisted, so a new
workflow was ignored and then silently absent from the commit. It now
whitelists `!.github/`. If `git status` looks empty after you add a dotfile,
check `git check-ignore -v <path>`.

**The prefs-reading path in `main()` is untested.** Neither pytest nor the UI
harness exercises `singularity/__init__.py`'s prefs block, so a missing import
there ships silently. If you touch it, verify by hand with a real `prefs.dat`
(write it through the options screen, then read it through `main()`).

**The layout must match the window, and the whole window must be painted.**
`g.window_size` is what SDL reports for the window — read it back, never assume
it. `g.reconcile_window_size()` runs once a frame and adopts it, because a
resize event can be lost, coalesced or refused; `set_mode()` must not call
`note_mode_change()` (only a real fullscreen switch does), or the compositor's
answer to our own start-up call is thrown away as an echo. When the geometry
changes, `g.geometry_dirty` makes the root present the entire window once: SDL
reallocates the window surface on a resize, and nothing in the widget tree
draws outside the layout area, so anything else leaves a band of green/black
stripes down the side of the window.

**A `pygame.Surface` passed as the `depth` argument copies the pixel format,
not the `SRCALPHA` flag.** `g.ALPHA` is built with `convert_alpha()`, so
`pygame.Surface(size, 0, g.ALPHA)` gave `g.fade_mask` no `SRCALPHA`: the blit
ignored its 175 alpha and painted a solid black rectangle over every widget
behind an open dialog, erasing text and background alike. Use
`pygame.Surface(size, pygame.SRCALPHA)` whenever a surface must blend.
`tests/test_fade.py` pins this; a faded parent must stay multi-coloured and
merely darker.

**The `--debug` overlay must never feed rects back into the frame.**
`updated_rect` is not just a present list — `g.layout_blit_pairs()` turns each
rect into a *blit source region*. The overlay once kept its rings from the
previous frame and appended them to `updated_rect`, so the frame was assembled
from rectangles chosen in an earlier one: a whole-root rect replayed after a
dialog opened pasted a stale full-screen region over the UI, which is the black
bars and partial labels that appeared only under `--debug`. Draw the overlay on
`screen_surface` after the blit, never into a copy of the root.

**Leaving fullscreen needs `Window.set_windowed()`, not `set_fullscreen(False)`.**
Measured on the dummy driver: after `set_fullscreen(False)` the window stays at
the desktop size and every later resize request is silently dropped, for ever —
a window that looks fullscreen and cannot be made smaller without a restart.
`set_windowed()` (SDL_SetWindowFullscreen(window, 0)) clears the flag properly.
Also never record a display state before reading it back: the old code wrote the
size, waited out a 500 ms pump budget, then read the desktop size back and
stored it as `_applied_window_size`, so `restart_needed()` reported nothing to
do. `g._leave_fullscreen()` verifies the exit and returns False only when the
window did not move at all; `apply_display_request()` then leaves the state
unrecorded so the choice applies at the next start instead of pretending
success.

**There is no restart prompt, and nothing may re-add one.** Upstream's
`check_restart()` was hardcoded to `need_restart = False` ("Test all changes
that require a restart. Currently, none."). `d1cd8ec` wired it to
`restart_needed()` while the in-place switch was still believed impossible, so a
working toggle produced "You must restart for some of the changes to be fully
applied." Fullscreen and resolution now change the *running* window, so the
prompt was removed along with `offer_restart()` and `restart()` (the Alt+Enter
handler and the Options OK button were its only callers).
`tests/test_fullscreen.py::test_the_restart_prompt_is_gone` keeps it out. Note
that success must not be judged on the window reaching an exact size: a
maximized or tiled window refuses to be resized and is still out of fullscreen,
and treating that as a failure is exactly what armed the prompt.

**`argparse` flag pairs must keep `default=None`.** `--sound/--nosound`,
`--daynight/--nodaynight`, `-g/--nograb`, `-s/--multidir` and
`--fullscreen/--windowed` all write one dest, and the code below tests
`if options.X is not None`. argparse defaults `store_true` to `False`, which
would silently overrule the preferences file.

**Hidden options stay hidden via `argparse.SUPPRESS`.** `-p`, `-d/--debug` and
`--cheater` must parse but must not appear in `--help`, because old scripts pass
`-p`. Historically this worked because an *unregistered* optparse `OptionGroup`
still registers its options. Keep both properties.

**Save-format invariants.** Keep `encoding='bytes'` on the unpickler — that is
precisely what lets Python-2 pickles load. Leave `savefile_translation`,
`find_class`, `recursive_fix_pickle` and the `unpickle_instance` logic alone. The
safety net is `tests/savegames/`: two py2 pickles and one `.s2`, compared
field-by-field against reference `.json`. Prove changes by digesting loaded state
(cash, time, done techs, triggered events, bases) before and after — and make the
digest deterministic (no `str()` of objects with memory addresses).

**Text encoding must be explicit.** `prefs.dat` is written by
`screens/options.py` and read by `__init__.py`; both must say `encoding='utf-8'`
or the round-trip breaks on non-UTF-8 locales. `languages.json` is UTF-8 by
RFC 8259. The `.sha1` translation cache too.

**Delete `build/` and `*.egg-info/` before grepping.** They are gitignored but
hold full copies of the source, doubling every search hit with stale results.

**`find_packages(include=["singularity", "singularity.*"])`** — a bare
`find_packages()` also ships `utils/` (it has an `__init__.py`) as a second
top-level package into site-packages.

**`setup.py` must insert the source dir on `sys.path`.** It does
`import singularity` to reuse `__version__`, and PEP 517 build hooks exec it in a
subprocess without the source tree on the path.

**The music submodule uses SSH URLs.** With no SSH key, fetch via:
```sh
git -c url."https://github.com/".insteadOf="git@github.com:" \
    submodule update --init --depth 1 singularity/music/singularity-music
```

**`error.log` absence is the health check.** It lives at
`~/.local/share/singularity/log/error.log` and is created lazily; no file after a
run means nothing was logged, which is what you want.

**No audio device is not a failure.** `mixer.py` guards on `not init`; you get
`WARNING: Sound is requested, but mixer is not initialized!` and the game keeps
running.

**`test_translations.py` needs `data.load_story_defs()` in `setup_module()`.** It
reads `g.story` and used to pass only as a side effect of another module loading
the data. It is self-sufficient now — keep it that way.

## Commit conventions

Imperative subject, prefixed by area when it helps:

```
i18n: replace deprecated locale.getdefaultlocale()
savegame: drop the Python 2 loader scaffolding
polib: remove the last Python 2 conditionals
data: close story.dat instead of leaking the handle
tests: drop the IS_PY2 skips and make the module order-independent
Remove the no-op 'from __future__' imports
```

Body: what changed, why, and **what you verified, with real command output**.
Call out any behaviour change explicitly. Justify any test change.

## State of this work

Done: `pycompat.py` deleted; `optparse`→`argparse`; `codecs.open`→`open` (this is
what removed all 120 warnings); `pygame.surfarray.use_arraytype()` removed; the
dead pygame-1 `HAS_FUNCTIONAL_BLITS` branch removed; the vendored `polib`
**un-vendored** (1568 lines deleted, real package now required);
`locale.getdefaultlocale()` replaced; explicit UTF-8 on cross-process files; the
`story.dat` handle leak fixed; `PY2`/`PY3`/`cPickle`/`__builtin__`/`TextWrapper`
removed; 40 `from __future__` imports removed; `pyproject.toml` added with
`python_requires=">=3.9"` and Python-3-only classifiers; READMEs at real floors;
the display and widget layer rebuilt around the window SDL actually gives us
(in-place fullscreen, resize echo, whole-window repaint, containment, wheel
delta); `u""` prefixes, the last Python-2 fallbacks and the dead
`i18n/utils/languages.py` removed; `README.txt` de-symlinked into a real
`README.md`; `release/` and its two gitlinks dropped; the fork presented as
**Singularity 2030**; upstream 1.1 and 1.1.1 merged in (§37); the fork
published on its own repository with Actions switched off (§38).
`MODERNIZATION.md` has the itemized version of all of it.

Deliberately left alone: the save-format code, the `xfail` marker, the music
submodule, the About `msgid` and its `.po` catalogs, the OLPC options, the
hidden `-p`, `Changelog.txt`'s history, and the structure of
`utils/data-translations.py`.

## Known remaining issues

- **CI is off, so the gate is the only check.** GitHub Actions is disabled on
  the fork's repository, and `.github/workflows/tests.yml` is disabled by hand
  on top of that. Nothing runs on a push. Before it was switched off, one run
  did happen and failed the two fullscreen round-trip tests in
  `tests/test_layout.py`, which pass here under the same dummy driver; the
  pygame and SDL build on that worker is the difference. Don't read a green
  local run as proof that a different environment would agree.
- **No CPython 3.15 wheel on PyPI.** pygame has no wheel for 3.15, so the
  environment here is distro packages only. Building a wheel works; installing
  one on 3.15 does not, yet.

## Reporting

After each item: what changed (file:line), why, and the verification output —
**quoted, not paraphrased**. At the end: a table of done/deferred with one-line
reasons, plus anything you found that was not on your list.
