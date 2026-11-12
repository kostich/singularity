# Modernization notes — Singularity 2030

This repository is a fork of **Endgame: Singularity 1.00** that has been brought
forward to run correctly on current systems. This file is the record of that
work: what changed, why, how to run it here, and what was measured to prove it.
`Changelog.txt` remains upstream's release history and is not rewritten.

The work is on `master`, this fork's only branch: a long series of small
commits sitting on upstream commit `99729e8` (upstream's 1.1 plus the
unreleased 1.1.1). The commits were written against `4df079f` from 2022 and were
merged with upstream's 43 newer commits in §37. `git log --oneline
99729e8..HEAD | wc -l` and `git diff --shortstat 99729e8..HEAD` give the current
count and size rather than a number here that goes stale with the next commit.

## Quick start

```sh
sudo dnf install -y python3-pygame python3-numpy python3-polib python3-pytest
./run_singularity.sh
```

`run_singularity.sh` sets `PYTHONPATH` to the checkout, drops stale bytecode
and runs `python3 -m singularity`; doing the first and last by hand is
equivalent (§35).
The game runs straight from the checkout — **do not add a virtualenv**. There
is no pygame wheel on PyPI for CPython 3.15, so the distribution packages are
the only sane route on this machine.

`polib` is a **hard runtime dependency**: the `.po` catalogs are parsed at
startup, so the game will not start without it. It used to be vendored; that
copy is gone (see §2).

## Environment (verified on this machine)

| Component | Version | Source |
|---|---|---|
| Distro | Fedora Linux 45 Workstation, Wayland (`wayland-0`) | — |
| Python | 3.15.0 (`/usr/bin/python3`) | — |
| pygame | 2.6.1 (SDL 2.32.74) | `python3-pygame` |
| NumPy | 2.5.4 | `python3-numpy` |
| polib | 1.2.0 | `python3-polib` |
| pytest | 9.1.1 | `python3-pytest` |

Installing `python3-pygame` pulls in `SDL2_mixer`, `SDL2_ttf`, `portmidi` and
`libxmp`. Under Wayland the game works as-is; `SDL_VIDEODRIVER=x11` is the
fallback if a display problem ever shows up. There is no audio device here, and
that is not a failure: `mixer.py` guards on `not init`, prints
`WARNING: Sound is requested, but mixer is not initialized!` and the game
carries on.

## What the modernization deliberately does not change

These are guarantees, not aspirations. A change that breaks one of them is a
bug in the change:

- **Gameplay and content.** Techs, bases, items, events, difficulty curves,
  balance and the story text are untouched, as are every `lang_*/` catalog and
  `messages.pot`. The only files under `singularity/data/` that changed are the
  theme directories (§16), where the edits are a `[general] name` line, an
  added `parent` line, and the new `2030` copy — no artwork was replaced.
- **Save compatibility.** `singularity/code/savegame.py` still loads
  Python-2-era pickles (`encoding='bytes'`, `savefile_translation`,
  `recursive_fix_pickle`, `find_class`, `unpickle_instance` all intact), and the
  `Upgrade` button in the Load menu is unchanged. Three fixtures in
  `tests/savegames/` (two `.sav` pickles, one `.s2`) are compared field by
  field against reference JSON.
- **Translations.** All nine `lang_*/` catalogs still load, and the `.po`
  files were not rewritten. `polib` still generates the `.mo` files at startup.
- **Credits and licences.** `AUTHORS.txt`, `singularity/i18n/AUTHORS.txt`, the
  seven `LICENSE*` files, every GPL header and every "Endgame: Singularity is
  free software" preamble are untouched.
- **The soundtrack.** `singularity/music/` remains a submodule with its
  CC-BY-SA 3.0 tracks, excluded from tarballs by `.gitattributes`.

## 1. The fork has its own name

The two projects want different things. Upstream keeps a 2005 game running as it
was; this fork changes how it runs, how it looks and how it is installed, which is
not something to merge back into it. So this is a hard fork, not a patch set: it
is presented as **Singularity 2030** and nowhere else. The "Endgame:" prefix was dropped in §39. A fork that still reads
as upstream is a fork whose downloads, bug reports and blame all land in the
wrong place, and the original authors get mail about code they never wrote.

| Where | What |
|---|---|
| `code/graphics/g.py` | Window caption, `Singularity 2030` |
| `code/screens/main_menu.py` | The title drawn on the main menu, `SINGULARITY 2030` (the widget already renders it in caps) |
| `singularity/__init__.py` | `--version` banner, the three "requires polib / pygame / NumPy" exits, the `argparse` description |
| `singularity.desktop`, `flatpak/…desktop` | `Name=Singularity 2030`, and `2030` in `Keywords` |
| `flatpak/…metainfo.xml` | The store page's name and summary |
| `setup.py` | Distribution name `Singularity-2030`, a `maintainer`, and this fork's repository as `url` |
| `README.md`, `CONTRIBUTING.md`, `docs/*` | Titles and headings |
| `AGENTS.md` | What the fork is for and what it must keep |

Unchanged on purpose, because these are identifiers rather than names: the
import package `singularity`, the console script `singularity`,
`argparse(prog="singularity")`, the `.desktop` `Exec=`/`Icon=`, the user data
directories under `~/.local/share/singularity`, the Flatpak app id
`io.github.singularity.Singularity2030` (renaming it would orphan every
installed sandbox and its saves), and `__version__ = "1.00"`.

The in-game **About** text is a gettext `msgid` translated in every catalog, so
its source string was left alone; changing it would have silently replaced the
About box with English in all twenty-three languages. The fork says its own
thing in its own, new `msgid` above it instead. §39.

## 2. Python 3 only, with nothing left over from Python 2

| Item | Where | What |
|---|---|---|
| Dead compatibility layer | `code/pycompat.py` | Deleted (37 lines). Every star/targeted import was unwound into `int`, `str`, `range`, `configparser.ConfigParser`/`RawConfigParser`. |
| Option parser | `singularity/__init__.py` | `optparse` → `argparse`. Flag pairs keep `default=None` so a prefs file still wins, and `-p`, `-d/--debug`, `--cheater` stay hidden via `argparse.SUPPRESS` but still parse, because old scripts pass `-p`. This also fixed `--windowed`, which was a no-op under `optparse` (its dest was `windowed`, which nothing read). |
| File opening | `code/polib.py` (later deleted), `code/i18n.py` | `codecs.open` → builtin `open(..., encoding=..., newline='')`. This is what removed the 120 deprecation warnings. |
| Vendored dependency | `code/polib.py` (deleted) | The embedded Polib 0.7.0 (1568 lines) is gone; `polib>=1.2` is a real `install_requires`, and the three `try: import polib / except ImportError: ...` fallbacks became a plain `import polib`. `LICENSE.txt` records that Polib is a separately installed MIT dependency rather than bundled source. |
| Future imports | 39 files | All 40 no-op `from __future__` imports removed. |
| Version sniffing | `i18n.py`, `savegame.py`, `graphics/*` | `PY2`, `PY3`, the `cPickle` try/except, `__builtin__`, the `TextWrapper` backport, both `if PY3` twins, the Python 2 `unpickle_instance` twin and the `PY3 and` guards removed. |
| String prefixes | 6 files, 20 lines | No-op `u""` prefixes removed with the values byte-identical (several are `\xA0` separators and msgids). |
| Dead runtime branches | `singularity/__init__.py` | `subprocess.DEVNULL` behind `AttributeError` and `FileHandler(delay=True)` behind `TypeError  # Python < 2.6`. Both APIs are 3.3+/3.2+. |
| Shebangs | `setup.py`, `__main__.py`, `utils/*.py` | `#!/usr/bin/env python` → `python3`, matching the five scripts that already said `python3`. |
| Dead dev tool | `i18n/utils/languages.py` (deleted) | 330 lines that regenerated `languages.json`. Nothing imported it, it called `dict(set)`, the three-argument `types.MethodType` and an unimported `polib`; the generated JSON it produced is still shipped and still read. |
| Packaging | `pyproject.toml` (new), `setup.py` | `setuptools>=77` build backend, `python_requires=">=3.9"`, Python-3-only classifiers, SPDX `license="GPL-2.0-or-later"`, `pygame>=2.0`, `polib>=1.2`, `pytest` as a dev extra. Metadata stays in `setup.py` so `singularity.__version__` is the single source of truth. |
| Build hazards | `setup.py` | The source dir is inserted on `sys.path` (PEP 517 hooks exec `setup.py` without it) and `find_packages(include=["singularity", "singularity.*"])` keeps the dev-only `utils/` out of `site-packages`. |

## 3. Deprecated and removed APIs that modern interpreters enforce

| Symptom | Where | Fix |
|---|---|---|
| `locale.getdefaultlocale()` deprecated in 3.11 | `code/i18n.py` | `_detect_default_language()` asks `locale.getlocale(LC_CTYPE)` first, then parses `LC_ALL`/`LC_CTYPE`/`LANG`/`LANGUAGE`. Verified identical on six environments (unset, `LANG=C`, `de_DE.UTF-8`, `en_US.UTF-8`, `LANGUAGE=fr_FR:de_DE`, `LC_ALL=C.UTF-8`). |
| Locale-encoded `prefs.dat` | `code/i18n.py`, `screens/options.py` | Explicit `encoding='utf-8'` on six text opens. A real bug: the options screen wrote prefs in the locale encoding while `main()` read them as UTF-8, so any non-UTF-8 locale broke the round trip. `languages.json` and the `.sha1` caches are UTF-8 by definition too. |
| Leaked file handle | `code/data.py` | `load_story_defs()` closed; `-X dev` had reported `ResourceWarning: unclosed file .../story.dat` on every run. |
| Removed in pygame 2 | `singularity/__init__.py` | `pygame.surfarray.use_arraytype("numpy")` removed; a plain `import pygame.surfarray` keeps the NumPy check and both error messages. |
| Dead pygame-1 branch | `code/graphics/widget.py` | `HAS_FUNCTIONAL_BLITS` and the pre-1.9.6 `blit` fallback deleted; `Surface.blits` is unconditional. |
| Removed in NumPy 2 | `code/buyable.py` | `numpy.cast[int64](...)` → `numpy.asarray(..., dtype=int64)`. |
| Removed in Python 3.10 | `screens/cheat_menu.py` | `collections.Mapping` → `collections.abc.Mapping`, imported explicitly. |
| Removed in Python 3.11 | `code/polib.py` | `'rU'` file mode → `'r'`. |

The deprecation surface is measured, not assumed. All three probes pass with
**no warnings line**:

| Probe | Catches | Result |
|---|---|---|
| `python3 -X dev -m pytest -q tests/` | `ResourceWarning`, leaked handles | clean |
| `python3 -W error::DeprecationWarning -m pytest -q tests/` | deprecations as hard errors | clean |
| `PYTHONWARNDEFAULTENCODING=1 python3 -m pytest -q tests/` | bare `open()` without `encoding=` | clean |

A curated grep for the 3.11–3.15 removals (`distutils`, `imp`, `audioop`,
`telnetlib`, `nntplib`, `cgi`, `xdrlib`, `lib2to3`, `smtpd`, `imghdr`,
`pkg_resources`, `typing.ByteString`, `ast.Num`, `utcnow`, `mktemp`,
`find_loader`, `resetlocale`, `assertEquals`) found exactly one hit, the
`getdefaultlocale()` above. So the tree was already close to clean; what the
sweep actually caught was one leaked handle and one encoding mismatch.

## 4. Display and windowing

The single largest group of changes. The old code assumed that the window it
asked for is the window it got, and that changing fullscreen means rebuilding
the window.

| Change | Why |
|---|---|
| Window / layout / abstract screen sizes separated | Three different numbers were conflated, so layout and blits disagreed after any resize. |
| A start-up window that suits the desktop | The hardcoded 1024×768 default is a postage stamp on a 4K or ultrawide screen. A windowed default now leaves room for borders and panels. |
| The world map drawn at its own 2:1 aspect | It was stretched to 1920×720 (2.67:1) on a 16:9 screen. |
| Ultrawide space used instead of pillarboxed | 21:9 screens got black bars. |
| Pillarbox blit kept in one coordinate space | The bars and the map drifted apart on resize. |
| Font ceiling raised | 4K, 5K and 8K would not scale text past the old maximum. |
| Fullscreen switched **in place** | Fullscreen used to mean destroying and recreating the window; it now uses the SDL window API (`SDL_SetWindowFullscreen`), and leaving fullscreen uses `set_windowed()` because `set_fullscreen(False)` left the window permanently stuck at desktop size. |
| Mode changes applied outside event dispatch | Changing the mode inside the event handler re-entered SDL. |
| No presenting to a window still being configured | Races during compositor negotiation. |
| Resize echo cannot bounce a toggle | `reconcile_window_size()` adopts what SDL reports once per frame; `set_mode()` must not record a mode change, or the compositor's answer is discarded as an echo. |
| Whole window repainted when geometry changes | SDL reallocates the window surface on resize; nothing in the widget tree draws outside the layout area, which left bands of stripes down the side. |
| Display surface re-grabbed after a resize | Same cause; the stale surface was being presented. |
| One SDL2 window wrapper kept alive | Recreating the wrapper per call broke the fullscreen toggle. |
| **No restart prompt** | Fullscreen and resolution now change the running window, so "You must restart for some of the changes to be fully applied" was removed along with `offer_restart()`/`restart()`. Success is not judged on the window reaching an exact size: a maximized or tiled window refuses to be resized and is still out of fullscreen. |
| Dialogs dim, they do not erase | `fade_mask` was built with a `Surface` as the depth argument, which copies the pixel format but not `SRCALPHA`, so a 175-alpha blit painted solid black over the UI. |
| Debug overlay cannot alter the frame | `updated_rect` doubles as a blit-source list; the overlay once appended stale rings, pasting parts of a previous frame over the UI. |
| Night mask cached | The day/night mask was rebuilt from scratch every frame. |
| **The top speed sweeps the day/night instead of strobing** | The clock moves a sixth of a day per frame at 432000, so the band jumped; the picture now sweeps once per 4 s, 3× the level below, and every speed change glides forward into place rather than snapping (§23). |
| Freeze diagnostics | A blocked SDL call cannot be interrupted by Ctrl+C; C-level handlers now dump the stack of the blocking thread (`--debug` prints the hint). |
| Maximized window restored before resizing | A maximized window refuses to be resized, which made a resolution change look like a failure. |

## 5. Text, fonts and widgets

- **A real stream for SDL_ttf.** The hand-written file object reported one byte
  less than the file, dropped that byte from every read and never advanced its
  position. Every stream is now an `io.BytesIO` over the bytes read once per
  `FontList`, which also keeps the open-descriptor count down (GH#156).
- **No zero-point face.** SDL_ttf was asked for size 0 when the layout
  collapsed, which produced unreadable glyphs instead of an error.
- **Widget sizes are never negative, refused rects are clipped.**
- **Containment.** Widget minimum sizes and positions are now measured the same
  way, so a child can no longer be laid out outside its parent.
- **Wheel scrolling uses the wheel delta**, not a fixed page, so a flick no
  longer jumps a whole screen. A wheel axis is not a click, and a list row is
  chosen on a click rather than on anything that merely has a position.
- **`update_item` signatures and a `key_list` guard** in the Research and
  Location screens.

### The 2030 theme draws every shipped language

The theme used DejaVu Sans for prose and DejaVu Sans Mono Bold for the HUD and
the menu. Between them they cover Latin, Greek and Cyrillic, and none of the
five translations in Arabic, Bengali, Devanagari, Japanese and Simplified
Chinese, so those players got rows of boxes. The theme now names a face per
language through the variant mechanism the loader already had:
`theme_ar.dat`, `theme_bn.dat`, `theme_hi.dat`, `theme_ja.dat` and
`theme_zh_CN.dat`, each a `[fonts]` section and nothing else.

The seven faces are bundled subsets of Google's Noto, built by
`utils/subset_fonts.py` against the catalogues: a full CJK face is 30 MB of
65,000 glyphs and the game draws a few hundred. They sit in
`singularity/data/themes/2030/fonts/` under plain filenames, which
`find_files()` resolves against that directory, so nothing is taken from the
host and a Flatpak behaves exactly like a checkout. That is 2.97 MB added, and
none of the 64 MB of full faces they were cut from is in the tree.

Each subset is also completed from the theme's own DejaVu, because SDL_ttf
gives a widget one face for the whole string and there is no per-character
fallback, while the game mixes scripts inside one string: labels read `CPU`
inside a Bengali catalogue, readouts put Western digits beside Bengali ones,
the language menu names every row in English as well as natively, and `map.py`
draws the pause bar (U+25AE) and the speed arrows (U+25B6) as text. So the
completion set is the whole printable ASCII range rather than a sample of it,
plus the marks the catalogues use and U+25AE. Where the host holds TrueType
outlines the donor glyph is copied; where it holds PostScript outlines (CFF2,
every CJK face here) the glyph is replayed through a pen and compiled to a
charstring, which is how a face with an outline format of its own still gets a
Latin alphabet.

Every subset also carries DejaVu's hollow box as `.notdef`. The Noto faces ship
that glyph with no outline, so a character none of them could draw rendered as
a gap the width of a space and read as a typo rather than as a missing glyph.
`.notdef` is index 0 in all of these faces, so the build rewrites index 0 and
adds nothing, renames nothing and reorders nothing.

`tests/test_theme_fonts.py` now measures each language against the face that
language draws with -- its variant where one exists, the base face otherwise --
and against its own text: the catalogue, the English that stands in for
anything untranslated, the `.dat` content and the two block glyphs. A
parametrised case fails on any character that renders as `.notdef`, another
checks that every face draws printable ASCII, a third that `.notdef` itself has
ink so a missing character shows a box rather than a gap, and one more that
every face a variant names lives inside the theme, which is what keeps the
Flatpak self-contained. `utils/subset_fonts.py` reads every file it writes back
before trusting it, including the `.notdef` check. `LICENSE.txt` gained the SIL
OFL 1.1 section and the copyright line of each upstream family;
`fonts/README.txt` says which file came from where and how to rebuild them.

Verified:

```
$ python3 utils/subset_fonts.py --check
NotoSansCJK-JP.ttf            687 KB   (from NotoSansCJK-VF.ttc, corpus 925 chars, 1 from DejaVuSans.ttf)
NotoSansCJK-SC.ttf            680 KB   (from NotoSansCJK-VF.ttc, corpus 1086 chars, 1 from DejaVuSans.ttf)
NotoSansMonoCJK-JP.ttf        655 KB   (from NotoSansMonoCJK-VF.ttc, corpus 925 chars, 1 from DejaVuSansMono-Bold.ttf)
NotoSansMonoCJK-SC.ttf        656 KB   (from NotoSansMonoCJK-VF.ttc, corpus 1086 chars, 1 from DejaVuSansMono-Bold.ttf)
NotoSansArabic.ttf             37 KB   (from NotoSansArabic[wght].ttf, corpus 155 chars, 92 from DejaVuSans.ttf)
NotoSansBengali.ttf           139 KB   (from NotoSansBengali[wght].ttf, corpus 167 chars, 99 from DejaVuSans.ttf)
NotoSansDevanagari.ttf        185 KB   (from NotoSansDevanagari[wght].ttf, corpus 170 chars, 64 from DejaVuSans.ttf)

would write 7 faces, 2.97 MB total

$ SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy PYTHONPATH=. \
      python3 -m pytest -q tests/
827 passed, 1 xpassed in 80.70s

$ PYTHONPATH=. python3 utils/ui_smoke_test.py
ALL HARNESS STEPS PASSED
```

## 6. Crashes that made whole screens unreachable

| Crash | Cause | Fixed by |
|---|---|---|
| Starting a new game, every research tick | `numpy.cast` removed in NumPy 2 | `numpy.asarray(..., dtype=...)` |
| Every `.po` load | `'rU'` mode removed in 3.11 | `'r'` |
| Cheat menu | `collections.Mapping` removed in 3.10 | `collections.abc.Mapping` |
| Research screen, Location screen | `update_item()` missing one positional argument | optional third parameter |
| Location screen | `key_list` subscripted while `None` | explicit guard |
| Resolution change with the Options dialog open | display mode changed during event dispatch | applied outside dispatch, plus a headless replay tool |

Four of those six were found before the modernization began, by simply trying
to start a game on Python 3.15 / NumPy 2; the last two needed the headless UI
harness, which renders the real screens. Their original diffs:

```diff
-        cost_paid = numpy.maximum(numpy.cast[int64](numpy.round(raw_paid)),
-                                  was_complete)
+        cost_paid = numpy.maximum(numpy.asarray(numpy.round(raw_paid),
+                                                dtype=int64),
+                                  was_complete)

-    def update_item(self, canvas, name, key):
+    def update_item(self, canvas, name, key=None):

-        if current_item is None:
+        # "key_list" is None until rebuild() populates it with the bases.
+        if current_item is None or self.listbox.key_list is None:
```

## 7. Assets, music and where your data goes

All *image* assets the game uses are committed: `arrow`, `earth`, `earth_night`
and `icon` under `singularity/data/themes/<theme>/images/` (each theme carries
its own copy of the ones it wants, see §16), the 2030 theme's `icon_*` button
glyphs and its `dialog_placeholder` static, plus the application icon at eight
sizes under `flatpak/icons/` (RGBA, transparent outside a rounded plate, §16),
plus
`singularity/data/sounds/click/click0.wav`. There are no "vfx" assets in this
repository — that word appears nowhere in the tree.

The soundtrack lives in a git submodule. Its URLs are SSH, so with no SSH key
present fetch it by rewriting the URL on the fly:

```sh
git -c url."https://github.com/".insteadOf="git@github.com:" \
    submodule update --init --depth 1 singularity/music/singularity-music
```

That is 17 Ogg Vorbis tracks (~54 MB): 13 general, 2 in `lose/`, 2 in `win/`.
No copying is needed — `mixer.py` walks the music directory recursively and
groups tracks by their first-level folder. The two lossless FLAC submodules are
only needed for re-encoding and are not fetched.

Default (`--multidir`) mode writes nothing into the checkout:

| What | Path |
|---|---|
| Prefs | `~/.config/singularity/1.0/prefs.dat` |
| Saves | `~/.local/share/singularity/saves/` |
| Log | `~/.local/share/singularity/log/error.log` |

`error.log` is created lazily. **No file after a run means nothing was
logged**, which is the health check. `-s`/`--singledir` keeps all three inside
the checkout instead.

## 8. Tests and developer tooling

The suite grew from a handful of checks to **25 test modules, 551 tests**:
layout geometry, containment, fade/blend correctness, the debug overlay,
font sizes, fullscreen toggling and the resize echo, listbox wheel behaviour,
the night mask, hotkeys, pause/resume with space, savegame fixtures and
digests, SDL2 window lifetime, diagnostics, translations, theme image loading,
the application icon's transparency and contrast, and the theme type scale
(§16), and the dialog frame, its padding and its picture banner (§16).

`utils/ui_smoke_test.py` renders the real screens headless and is part of the
gate; it now runs **16 steps**:

```
PASS   main menu renders
PASS   new_game + map renders (daynight on, then off)
PASS   research screen: update_item with key_list=None
PASS   research screen: populated + rendered
PASS   location screen: update_item with key_list=None
PASS   location screen: populated with a real base + rendered
PASS   simple menu dialog renders
PASS   message dialog renders
PASS   dialog frame: 2030 centres the panel and reserves a picture banner
PASS   dialog frame: a legacy theme still draws the old one
PASS   layout: map renders undistorted at 16:9 and at 21:9
PASS   fullscreen toggles off again, and a resize echo cannot bounce it
PASS   leaving fullscreen returns to a window, and does not stall
PASS   options: changing resolution with the dialog open redraws it
PASS   options: a wheel flick scrolls the list, not the resolution
PASS   save + load roundtrip
```

Three diagnostics scripts exist for problems a unit test cannot see:
`utils/window_probe.py` (what SDL actually gave us), `utils/font_probe.py`
(which sizes and faces load in this environment) and
`utils/wheel_resize_repro.py` (a headless replay of the resolution change that
used to crash). `utils/make_2030_art.py` regenerates the 2030 theme's artwork
and `utils/make_app_icon.py` the application icon; both print the measurements
behind what they drew (§16).

`utils/theme_snapshot.py` answers the question the tests cannot: *did a theme
change move another theme's pixels?* It renders the main menu, the Options
dialog and the map screen once per theme at a pinned 1280×800, saves each frame
as a PNG and prints a sha256 of the live surface. The game is not deterministic
by itself — `g.new_game()` places the first base with `random.choice()` and
`Player.__init__` picks a random start day — so the tool seeds `random` and
turns `daynight` off. Without that the map frame moved by 254 pixels between
two runs of the same code, which makes a digest useless as a baseline. The map
step is what lets the tool vouch for the HUD, and the HUD is where a theme's
panel edges live.

```
theme                    screen     sha256
default                  main_menu  65f4b2947ee1da7307f6274dc671e57b873629487cab20c2fffb9af6a10a30d9
default                  options    e41bde9699d0436cbe11f3614c724744fcbc8f26f60fcfba202c296118a03dbf
nightmode                main_menu  ea22b102ec66b055bc0354564c078dd2472280b46218f71ddbd57115ffe23b31
nightmode                options    d3c6d84841c3ffda7aa5d78715ef1278ec9e42ec93b1a58150a432c89c690c51
vector                   main_menu  65f4b2947ee1da7307f6274dc671e57b873629487cab20c2fffb9af6a10a30d9
vector                   options    9ca4bb094395f0261afc18d6ca534af00db9b65b963714a940611eede687b92f
```

That output is the baseline taken *before* the 2030 theme existed. It is
deterministic — two runs back to back are identical, which is what makes the
digests usable as an assertion — and `vector` matching `default` on the main
menu is a free check of the tool itself, since `vector` only renames the default
theme and inherits the rest. Digests are only comparable on the same machine,
the same SDL and the same window size.

Save compatibility was re-proved rather than assumed: loading all three
`tests/savegames/` fixtures under the old and the new code gives an identical
digest of cash, game time, completed techs, triggered events and bases
(`0afa8129ca113149`, `98d19bb7f17f0478`, `7838e97f6d3cae79`). The parser was
also re-checked against GNU `msgfmt` after the vendored polib was dropped: 36
`.po` files, 5589 entries, 0 mismatches, and a launch with an empty i18n cache
re-creates the `.mo` files through `save_as_mofile()`.

`tests/test_translations.py` needed one genuine change: `setup_module()` now
calls `data.load_story_defs()`, because `test_story_translation` read `g.story`
only as a side effect of another module having loaded it, and failed with
`KeyError: 'Intro'` when the file ran alone. That was a pre-existing order
dependency, reproduced at `ee14b33`, not something this work introduced.

## 9. Repository, packaging and CI

- **`README.md` is a real file.** It used to be a symlink to `README.txt`, so
  edits went through the link and `git status` only ever mentioned
  `README.txt`. `README.txt` is gone.
- **`MANIFEST.in`** ships `MODERNIZATION.md` alongside the existing data and
  licence files; the music submodule stays excluded. A built sdist contains
  `endgame_singularity_2030-1.0/MODERNIZATION.md`, all 71 data files and the
  `.po` catalogs, and no `utils/` package.
- **`release/` removed.** It held a release README describing a Python 2.7 /
  py2exe process (`c:\Python27\Python.exe setup.py py2exe`) and two gitlinks to
  upstream's prebuilt-binary repositories. This fork is source-only.
- **`.gitmodules`** keeps its three `singularity/music/` entries and nothing
  else.
- **CI rewritten.** `.github/workflows/python-package.yml` installed
  `python-pytest python-numpy python-pygame …` — Python *2* package names that
  do not exist on `ubuntu-latest` — and a second job pinned Python 3.8 and
  built SDL 1.2 from apt for pygame 1. Replaced by `tests.yml`: Python 3.10 and
  3.13, pip-installed `pytest numpy pygame polib`, and exactly the local gate
  under the dummy SDL drivers. It is triggered by a push to `master` (this
  fork's main branch, and the only branch), by a pull request against it, and
  by hand from the Actions tab; read-only token, one run per ref with the older
  one cancelled. A second job builds the sdist and the wheel, installs the wheel
  into an empty virtualenv and checks that the game's data and translations
  actually shipped before starting it. See §41.
- **`.gitignore`** ignored every dotfile and whitelisted only
  `.travis.yml`/`.codecov.yml`, which silently swallowed new files under
  `.github/`; it now whitelists `.github/`. `.codecov.yml` is deleted: the old
  workflow installed pytest-cov but never passed `--cov`, so nothing was ever
  uploaded.
- **`AGENTS.md`** documents the working rules, the gate, the codebase map and
  the traps that cost real time, and requires this file to be kept in sync.

## 10. Verification

Run from the repository root. These are the actual outputs of this branch:

```sh
$ SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy PYTHONPATH=. \
      python3 -m pytest -q tests/
........................................................................ [  7%]
........................................................................ [ 15%]
........................................................................ [ 22%]
........................................................................ [ 30%]
........................................................................ [ 38%]
........................................................................ [ 45%]
........................................................................ [ 53%]
........................................................................ [ 61%]
........................................................................ [ 68%]
........................................................................ [ 76%]
........................................................................ [ 84%]
.....................................................X.................. [ 91%]
........................................................................ [ 99%]
....                                                                     [100%]
940 passed, 1 xpassed in 79.97s (0:01:19)

$ SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy PYTHONPATH=. \
      python3 utils/ui_smoke_test.py
...
PASS   save + load roundtrip

ALL HARNESS STEPS PASSED
```

With a real display, `./run_singularity.sh --debug` starts windowed, loads all
17 soundtrack files and prints `Loaded 57 techs.`. The caption SDL ends up with
was read back through the same startup path:

```
pygame.display.get_caption() -> ('Singularity 2030', 'Singularity 2030')
```

The single `xpassed` is `tests/test_translations.py::test_root_collation`,
marked `xfail` upstream with the comment "Fails in github actions"; it passes
on a machine with a working locale. The marker is deliberately left in place.

The Flatpak is verified the same way — built, installed system-wide, then run
inside its sandbox:

```sh
$ ./rebuild-flatpak.sh
== flatpak Flatpak 1.18.4, flatpak-builder flatpak-builder-1.4.12
== org.freedesktop.Sdk//25.08 already installed
== org.freedesktop.Platform//25.08 already installed
== building io.github.singularity.Singularity2030
...
Soundtrack: 17 tracks
...
== publishing to the system installation
...
== smoke-testing the installed Flatpak (headless)
pygame 2.6.1 | SDL 2.28.4
numpy 2.5.4 | polib 1.2.0
package /app/lib/python3.13/site-packages/singularity/__init__.py
soundtrack: 17 Ogg tracks installed

ALL FLATPAK STEPS PASSED
```

```
$ flatpak run --command=sh io.github.singularity.Singularity2030 \
      -c 'timeout 6 /usr/bin/python3 -m singularity -d'
D: Loaded musicfile .../music/singularity-music/music/A New Journey.ogg
...
display: driver=wayland window=1920x1080 actual=1920x1080 layout=1920x1080
         origin=0,0 desktop=3440x1440 fullscreen=False surface=1920x1080
Loaded 57 techs.
```

No `error.log` is created in the sandbox either, and the mixer resolves the
four classes it needs: `music` 13 tracks, `lose` 2, `win` 1, `singularity-music`
1 — 17 in total.

The build now also proves the sandbox really gets the Wayland driver, instead
of trusting `--socket=wayland` in the manifest. The step is the last one in the
smoke test, and it is what an X11-only host skips:

```sh
$ env -u DISPLAY flatpak run --command=python3 \
      io.github.singularity.Singularity2030 -c \
      'import pygame; pygame.display.init(); print(pygame.display.get_driver())'
display driver inside the sandbox: wayland
```

## 11. Deliberately not touched

- **The save format.** `savefile_translation`, `find_class`,
  `recursive_fix_pickle`, `unpickle_instance` and the `encoding='bytes'`
  unpickler are exactly as upstream wrote them; the format history in
  `Changelog.txt` and the `Upgrade` button depend on that.
- **The `xfail` marker** on `test_root_collation`.
- **The music submodule**, `.gitattributes`' music exclusions and the lossless
  music submodule entries in `.gitmodules`.
- **The About `msgid` and all `.po` files.**
- **OLPC options** (`--xo1`, `--ebook`) and the hidden `-p`, which old scripts
  still pass.
- **`Changelog.txt` history** and `TODO`, which belong to upstream.
- **Upstream project URLs, author metadata and bug-tracker links** inside the
  About box's second half, which are still the correct places to read about the
  original game. Everything that points a *player* at a place to report
  something points at this fork instead (§39).

## 12. Flatpak packaging

The fork is packaged as a Flatpak, so it installs on any distribution with
Flatpak 1.x and never touches the distribution's Python, pygame or NumPy.
Everything lives under `flatpak/`; `./rebuild-flatpak.sh` builds it and installs
it system-wide.

| File | What |
|---|---|
| `flatpak/io.github.singularity.Singularity2030.yml` | The manifest: runtime, `finish-args`, the app module |
| `flatpak/python3-modules.json` | numpy, polib and pygame, pinned by `sha256` |
| `flatpak/launcher.sh` | `/app/bin/singularity` — `exec /usr/bin/python3 -m singularity "$@"` |
| `flatpak/io.github.singularity.Singularity2030.desktop` | Desktop entry; its id equals the app id, as Flathub requires |
| `flatpak/io.github.singularity.Singularity2030.metainfo.xml` | AppStream metadata |
| `flatpak/icons/{16,24,32,48,64,128,256,512}.png` | Hicolor icons, RGBA with a rounded plate, all rendered natively (§16) |
| `flatpak/screenshots/{main-menu,world-map,research,about}.png` | The pictures the store page shows (§39) |
| `utils/make_screenshots.py` | Renders them from the real game, headlessly (§39) |
| `rebuild-flatpak.sh` | Build, publish system-wide, smoke-test; idempotent |

**Why `org.freedesktop.Platform` 25.08.** It is the current stable freedesktop
branch and carries Python 3.13, which is what the package runs on regardless of
the host. The GNOME runtimes were rejected because they add a GTK stack a pygame
game never loads.

**Why Python wheels rather than a source build.** The runtime ships
`libSDL2`, `SDL2_mixer` and `SDL2_net`, but **no `SDL2_ttf`, `SDL2_image`,
freetype, harfbuzz or NumPy** — and the game cannot draw one label or one map
background without them. The official pygame and NumPy manylinux wheels carry
all of those in `pygame.libs` with `$ORIGIN` rpaths, so a `pip3 install` of three
pinned files replaces a six-module C manifest (`sdl2_ttf`, `sdl2_image`,
`freetype2`, `libpng`, `libjpeg-turbo`, plus meson/ninja for numpy). polib is
built from its sdist with `--no-build-isolation`, since the SDK already has
setuptools 80.10.2.

**The soundtrack is packaged, and its layout is not incidental.** `mixer.py`
groups tracks by their first-level directory and the screens ask for the classes
`"music"` (`player.py`), `"win"` (`player.py`, `effect.py`) and `"lose"`
(`screens/map.py`). Those are the directories *inside* `singularity-music/`, so
the submodule tree is installed verbatim at
`singularity/music/singularity-music/`. Flattening it — the obvious "tidy up the
package layout" move — would leave the game completely silent while still
shipping 17 tracks.

**Where the data goes in the sandbox.** `/app` is read-only, and `dirs.py`
already prefers a writable XDG directory for everything it writes, so no code
changed:

| What | Path |
|---|---|
| Prefs | `~/.var/app/io.github.singularity.Singularity2030/config/singularity/1.0/prefs.dat` |
| Saves | `~/.var/app/io.github.singularity.Singularity2030/data/singularity/saves/` |
| Log | `~/.var/app/io.github.singularity.Singularity2030/data/singularity/log/error.log` |
| `.mo` cache | `~/.var/app/io.github.singularity.Singularity2030/data/singularity/i18n/` |

**One code change was needed for the sandbox.** `singularity/__init__.py` ran
`git describe --tags` at import time and caught only `CalledProcessError`, so a
host without a `git` *binary* — a Flatpak, and equally a `pip install` from an
sdist — died with an uncaught `FileNotFoundError` before the game started. It
now catches `(OSError, subprocess.SubprocessError)` and falls back to `N/A`,
which is what a release tarball's `export-subst` expansion avoids in the first
place. Behaviour on a git checkout is unchanged.

**Verified.** `./rebuild-flatpak.sh` (§10 has the raw transcript) builds,
installs as `io.github.singularity.Singularity2030` version `1.00`, and inside
the sandbox reports pygame 2.6.1 (SDL 2.28.4), NumPy 2.5.4, polib 1.2.0, the 17
soundtrack tracks in the four classes above, and a debug start that prints
`Loaded 57 techs.` with no `error.log` written.

**Wayland is asserted, not assumed.** The manifest asks for `--socket=wayland`
plus `--socket=fallback-x11`, which leaves the choice to SDL; a manifest edit
that dropped the Wayland socket would still have built and still have passed
the old smoke test. `rebuild-flatpak.sh` now ends with a driver probe — the
app's own Python with `DISPLAY` unset must answer `wayland` — and fails the
build otherwise. When the host has no `WAYLAND_DISPLAY` the step prints a skip
note rather than failing, so the script stays usable on X11-only machines.
`SDL_VIDEODRIVER` is never forced anywhere: forcing it would break those
machines, and the point of the check is that the packaged app picks Wayland by
itself, exactly as the checkout does (§15).

**The build tree must belong to the user.** `flatpak-builder --force-clean`
deletes the app dir itself, so a tree left behind by a run as root makes the
next build die with `Couldn't empty app dir ... unlinkat(.gitignore): Permission
denied`, which points at a file rather than at the ownership problem. The script
now checks `build/flatpak` for entries owned by another user before it builds
and stops with the `sudo rm -rf` line that fixes it. Root-owned files can only
come from an override run (`REBUILD_FLATPAK_ALLOW_ROOT=1`), never from the
script's own `sudo` calls, which touch only the system installation.

Verified on this machine by exercising the script's steps in place: the build
tree has to live outside a mode-700 home for `flatpak-builder`'s bwrap to read
it, so the source was copied to a scratch directory, built there, exported into
`build/flatpak/repo`, installed system-wide as `singularity-local`, and every
smoke command — including the new driver probe — run against the installed app.
The installed copy answers `MapScreen.toggle_pause: True`, so it is the code in
this tree, and it starts with `display: driver=wayland` with `DISPLAY` unset.

**Before a Flathub submission.** The manifest's source is `type: dir`, which
deliberately builds the working tree (including uncommitted edits) — a
published manifest must name a `type: git` source pinned to a commit. The
soundtrack then has to become its own `type: git` source (`dest:
singularity-music`, commit `025e2696`), because a submodule is not part of a git
archive and `.gitattributes` export-ignores `singularity/music`; the build
commands already prefer that directory when it exists. The app id must match the
real hosting account. The icons were the other weak point — 128 and 256 were
smooth upscales of the 32×32 theme icon, because the tree contained no larger
original — and are now real artwork at all eight sizes (§16).

## 13. History

The fork is six commits on top of upstream's `99729e8`, one per area of work:

| commit | what it carries |
|---|---|
| `alignment` | the Python 3 / pygame 2 / NumPy 2 pass: startup, the code under `singularity/code/` outside the graphics and screen layers, the save loader, the data and translation loaders, packaging metadata, and the tests that pin them |
| `frame` | the display, widget and dialog layer the game had to be rebuilt around, and the screens that lay themselves out on it |
| `colour` | the 2030 theme: palette, type scale, translated variants, the dialog plates, the fonts, the icon set, the style contract, and the licence text for all of it |
| `words` | the catalogs, the languages added since 2020, the test suite, and the developer tools |
| `name` | the fork's own name in the game and the documents, and the About box that says whose game this is |
| `package` | the Flatpak, the store page, the screenshots, the application icon, and these notes |

Upstream's history is untouched below the base: `git log 99729e8` is upstream's
own, and `git log --oneline 99729e8..master` is this fork's six. §40 records how
that history was built, what it costs in traceability, and how the tree was
proved identical before and after.

## 14. Known gaps

- **CI has run once, and failed; that is now fixed (§41).** One run is the only
  evidence there is about a runner, so it belongs here rather than under
  "done": both matrix jobs failed in `tests/test_layout.py`, and both failures
  were the same claim, the window coming back as the desktop size after a
  fullscreen round trip. Those two tests now assert what this tree asks SDL for
  separately from what SDL grants, so they pass under either behaviour. The
  first push after §41 is the proof, and the README badge reports it.
- **No PyPI wheel for CPython 3.15 exists**, so the development and gate
  environment uses distribution packages (`python3-pygame`, `python3-numpy`,
  `python3-polib`, `python3-pytest`). Building a wheel works and was checked;
  installing one on 3.15 depends on pygame shipping a wheel for it.
- **`test_root_collation` xpasses** on machines with a working locale. That is
  expected; the `xfail` marker is upstream's and stays.
- **The Flatpak has never been built anywhere but this machine.** One x86_64
  build is verified (§12); aarch64 needs its own wheel variants, and no Flathub
  submission has been made, so the review process has not seen it. The icons are
  real artwork as of §16, but no reviewer has looked at them.

Two corrections from earlier revisions of this file, recorded because the
history should stay honest: the vendored `polib.py`'s `enc.decode('utf-8')` in
`detect_encoding()` was **not** dead code (the regex is bytes-based, so it ran
every time), and the `polib` dependency was **not** runtime-optional — that
held only while Polib was vendored.

## 15. Pause and resume with Space

The time controls were the number keys only: `0` paused, `1`-`4` picked a
speed. Space now pauses, and space again resumes the level that was running.

The whole feature is one invariant: **pause is a state, not a speed level.**
`g.curr_speed` still holds `0` while paused, and the level to go back to lives
in a second global, `g.last_speed`, which is never allowed to become 0.
Everything else follows from that:

| Situation | Result |
|---|---|
| Space while running | pauses, and keeps the level |
| Space while paused | resumes at `g.last_speed` |
| `0`, then Space, on a legacy theme | runs at 1: a game that started paused resumes at 1. In 2030 the `0` key itself resumes (§27) |
| `3` (7200), Space, Space | 7200 again, every time |
| The PAUSE button on a warning or a log list (`player.pause_game()`) | pauses; Space resumes at the speed that was running. That function writes `curr_speed` only |
| The grace warning, an event, or a lost base | opens its dialog and leaves the speed alone. These used to call `pause_game()` first, so OK came back paused; that changed in §27 |
| The two-bar pause button, 2030 theme | toggles, the same as Space (§27). A legacy theme's button still means speed 0, and a second click stays paused |
| Loading a save | starts paused, and resumes at 1 |
| A new game | resumes at its starting speed, i.e. `initial_speed or 1`, so a game created paused still has somewhere to go |
| Cheat "SUPERSPEED" (864000, not one of the five buttons) | remembered like any other level |
| Typing a space in the save-name or options text field | unaffected: the handler belongs to the map screen, which is not receiving events while a dialog is open |

The level is **not** written to the save. Storing it would change the format
that `Changelog.txt` and the `Upgrade` button depend on, so a loaded game
resumes at 1. The speed buttons still highlight exactly one level while
running, and none while paused. On the 2030 theme the pause button, and the
`0` key that is the same button, later learned to toggle; see §27. The other
four keys still set their level.

### Warnings are shown once per change, not once per keypress

Two attempts at this were wrong. Both are recorded, because the second one hid
a warning instead of repeating it.

Upstream re-checked the warnings on *every* transition out of pause:
`set_speed()` armed `needs_warning` and `on_tick()` opened a modal list of
whatever `warning.refresh_warnings()` returned. In the early game `cpu_usage`
and `one_base` are active almost always, so that dialog always opened. Pressing
`0` and then `1` did this before the fork; a key that toggles pause turned it
into one dialog per press.

The first fix skipped the check when space resumed. That removed the dialog
entirely: a player who only used space saw the warnings once at the start of
the game and then never again — including "the processor is idle" and "there
is not enough CPU for maintenance", which is how the game says a base is about
to be lost.

The rule is now: **a warning is shown once per distinct set.**
`MapScreen.show_warnings()` compares the active warning ids with the set it
showed last, and opens the dialog only when they differ. Leaving pause still
re-checks, whichever route the player took, so no warning is lost: a set the
player has just read is not repeated, and one that appears, changes or clears
is shown again. `force_update()` — a new game, a load, recovery from an error —
clears the record, so entering the map tells the player the state once, even if
it is the state the previous game ended in.

Two consequences worth stating. A warning that stays active is shown once, not
once per resume. And warnings are still only *checked* on entering the map and
on leaving pause, which is upstream's timing: one that appears in the middle of
a long run at maximum speed is not shown until the next pause. Checking
periodically is a separate decision, because the dialog also stops the game.

### Wayland, with no X11 available

Both ways of starting the game were run with `DISPLAY` removed from the
environment, so X11 and XWayland could not be used at all. Nothing forces
`SDL_VIDEODRIVER` in `run_singularity.sh`, `flatpak/launcher.sh` or the
manifest; SDL chooses the driver, and it chooses Wayland.

```sh
$ env -u DISPLAY SDL_AUDIODRIVER=dummy timeout 10 ./run_singularity.sh --debug
display: driver=wayland window=3440x1440 actual=3440x1440 layout=3440x1440 origin=0,0 desktop=3440x1440 fullscreen=True surface=3440x1440 | fonts: button 36->67px, default 20->37px, report_content 20->37px, resource_display 24->45px, suspicion_bar 32->60px, time_display 24->45px
Loaded 57 techs.
```

No `singularity/log/error.log` was created. (It comes up fullscreen at the
desktop size because `prefs.dat` remembers `fullscreen=True` from earlier runs;
that is the saved preference, not a Wayland effect.) With `DISPLAY=:0` present
as well the game still starts on `wayland`, so the X11 socket is only ever a
fallback.

Inside the installed Flatpak, with `DISPLAY` unset on the host:

```sh
$ env -u DISPLAY flatpak run --command=python3 \
      io.github.singularity.Singularity2030 -c \
      'import pygame; pygame.display.init(); print(pygame.display.get_driver())'
display driver inside the sandbox: wayland

$ env -u DISPLAY SDL_AUDIODRIVER=dummy timeout 8 flatpak run --command=sh \
      io.github.singularity.Singularity2030 \
      -c 'timeout 6 /usr/bin/python3 -m singularity -d'
display: driver=wayland window=3440x1440 actual=3440x1440 layout=3440x1440 origin=0,0 desktop=3440x1440 fullscreen=True surface=3440x1440 | fonts: button 36->67px, default 20->37px, report_content 20->37px, resource_display 24->45px, suspicion_bar 32->60px, time_display 24->45px
Loaded 57 techs.
```

`./rebuild-flatpak.sh` now asserts that driver line itself, so a future
`fallback-x11` slip in the manifest shows up as a failed build (§12).

The key handling is pinned by `tests/test_pause_toggle.py`, which delivers a
real space `KEYDOWN` through `MapScreen.handle()` instead of calling
`toggle_pause()` directly, so the binding itself is what is tested.

## 16. Themes: a 2030 theme, and three legacy themes left exactly as they were

A theme is a directory, `singularity/data/themes/<id>/`, holding a `theme.dat`
with `[general] name`, `[fonts]` and `[colors]`, optional `theme_<lang>.dat`
variants that override the name (or anything else) per language, and `images/`
and `fonts/`. A theme inherits every colour, font and image it does not
override from its parents, and `g.resolve_color_alias()` turns a colour name
into an RGBA tuple when a widget reconfigures. That indirection is the whole
point: a theme restyles every screen without a line of widget code changing.

Shipped before: `default` (the base — all 78 colours, both fonts, four images,
four language variants), `nightmode` (a mostly-red palette, four images, four
variants) and `vector` (a name and nothing else; it inherited everything).

Shipped now:

| id | shown in Options as | role |
|---|---|---|
| `2030` | `2030` | the new default, styled for the fork |
| `Legacy-default` | `Legacy Default` | the old `default`, untouched |
| `Legacy-nightmode` | `Legacy Nightmode` | the old `nightmode`, untouched |
| `Legacy-vector` | `Legacy Vector` | the old `vector`, untouched |

`theme.default_theme` is `'2030'`, so `set_theme(None)` — what `tests/conftest.py`
and the harnesses call — gives the 2030 theme.

### Keeping the old look

Three independent things would each have re-themed an existing player, so each
had to be handled rather than hoped for:

1. **Inheritance.** `Theme.__init__` used to give every theme whose id was not
   `default_theme` that theme as its parent, *before* `data.load_theme()`
   appended whatever the file declared. Renaming the default would therefore
   have made `nightmode` inherit **2030** first — and `nightmode` deliberately
   leaves `save_name`, `save_time`, `save_difficulty` and `darker_blue1` to its
   parent, so those would have started following the new palette. Inheritance
   is now explicit: the constructor adds no parent, `data.load_theme()` gives a
   theme that names none the default theme, and the two legacy themes that
   declared nothing now declare `parent = Legacy-default`. `nightmode` still
   leaves exactly those four keys to its parent.
2. **Ids.** `prefs.dat` holds `theme = default`, `--theme nightmode` is a
   documented flag, and a third-party theme may declare `parent = default`.
   `theme.LEGACY_THEME_IDS` maps `default`, `nightmode` and `vector` onto the
   `Legacy-*` ids, both in `set_theme()` and in `Theme.inherit()`, so an old id
   lands on the old theme instead of falling back to the default.
3. **Order.** The Options listbox shows themes in the order
   `data.load_themes()` builds, which was `os.listdir()` order. It is now the
   default theme first and then by name: `2030`, `Legacy Default`,
   `Legacy Nightmode`, `Legacy Vector`, filesystem-independent.

### Evidence

`utils/theme_snapshot.py` (§8), run at the commit before the rename and again
after it:

- **Main menu digests unchanged** for all three legacy themes, and `2030`
  equals the old `default`, which is fair — at that point it is a byte copy.
- **Options screen digests move**, and that is the only thing that moves: a
  pixel diff localises the entire difference to *x* 845..1067, *y* 149..247 of
  1280×800 — the theme listbox, whose rows now read `2030` / `Legacy …` in a
  new order. Nothing else on the screen changed by one pixel.
- **Every resolved colour, line by line:** `g.colors` dumped for each theme in
  a worktree of the previous commit and in the working tree, then diffed with
  the ids mapped (`default` → `Legacy-default`, ...): identical, 238 lines for
  the three legacy themes. `2030`'s 78 colours are identical to the old
  `default`'s.

### Deliberate details

- **The variant names carry the prefix.** `Legacy Standard`, `Legacy Défaut`,
  `Legacy Nachtmodus`, `Legacy Mode nuit`, `Legacy Tùsail`, `Legacy Modh
  oidhche`, `Legacy Обычная`, `Legacy Vektor`, `Legacy Vecteur`, `Legacy
  Sgàil-riochd`. A variant's name replaces the base one, so without the prefix
  the list would show a bare `Standard` beside `2030`. These strings live in
  the theme data, not in `lang_*/`, so no catalog was touched.
- **`2030` ships no language variants.** It is new; its name should not pretend
  to be translated, and copying the variants would also duplicate the English
  `Legacy Standard` row. The one functional consequence: a Russian player on
  `2030` gets `acknowtt.ttf` for `special`, not `superstar_memesbruh03.ttf`,
  because that override lives in `Legacy-default/theme_ru_RU.dat`.
- **`2030` is a full copy, not a child of `Legacy-default`** (~2.1 MB, mostly
  `DejaVuSans.ttf` and the two Earth JPEGs), so its fonts and map art can
  diverge later without touching a file the legacy themes read. In the other
  direction `Legacy-default` inherits nothing that can reach it: it defines all
  78 colours, both fonts and all four images itself.
- **A theme that names no parent still inherits `2030`**, which is what keeps a
  third-party theme in `~/.local/share/singularity/themes/` usable.

### The 2030 palette

The first pass is colour only — no widget code, no fonts, no artwork — because
that is what the theme engine is good at, and it keeps the change reviewable.
`2030/theme.dat` gained nine named colours; the chrome keys now point at them
instead of at hex values, so the next pass retunes one block:

| name | value | used for |
|---|---|---|
| `ui_void` | `#04080Fff` | map, main menu and options backgrounds |
| `ui_panel` | `#0A1622ff` | panes, text dialogs, simple menus |
| `ui_panel_dark` | `#060E18ff` | text entry, slider and scrollbar troughs |
| `ui_panel_light` | `#12283Aff` | widget/button faces |
| `ui_edge` | `#2C6A82ff` | borders and separators |
| `ui_edge_bright` | `#5FE3FFff` | the title, the slider handle, one highlight |
| `ui_text` | `#D7ECF6ff` | body text |
| `ui_text_dim` | `#7A93A3ff` | disabled text |
| `ui_select` | `#17384Bff` | selection fill |

**Not** touched, on purpose: `danger_level_*`, `base_state_*`,
`base_situation_*`, `save_valid`/`save_invalid`, `cpu_normal`/`cpu_warning`
and the `location_name_*` risk hints. They are information, not decoration; a
palette pass that quietly re-tints "this base is about to be detected" is a
gameplay change wearing a theme's clothes.

Verified on this pass:

- The three legacy themes' digests are **still** identical to the post-rename
  run, i.e. the new palette cannot reach a legacy theme.
- The 2030 main menu keeps the *exact* per-region pixel counts of the legacy
  one (`ui_void` 232532 samples where `black` was, `ui_panel` 20194 where
  `dark_blue` was, `ui_edge_bright` 1414 where `dark_red` was, `ui_edge` 862
  plus `ui_text` 649 where `white`'s 1511 was). Same layout, new colours.
- Contrast ratios: text on panel 14.96, text on a button 12.38, text on a
  selection 10.11, disabled text 5.67, title 13.30 — all above the 4.5 AA
  floor; borders are 3.03, which is a line, not text.
- `./run_singularity.sh --debug` starts, prints the usual `display:` and
  `Loaded 57 techs.` lines and writes no `error.log`.

Fonts and the Earth art are the natural next items: `2030/` currently carries
`DejaVuSans.ttf`, `acknowtt.ttf` and the same `earth`/`earth_night` JPEGs as
the legacy theme, because the tree contains no CC-BY-SA-clean sci-fi typeface
or map art. Adding either means new assets with a licence, not a theme edit.

### The type scale belongs to the theme

Colours, fonts and images were always per-theme; the *sizes* were not. The six
base text sizes lived in `gg.configured_text_sizes` as one global, settable only
by hand-editing `prefs.dat`, so a theme could not choose a type scale — and a
look is mostly a type scale.

A theme now has a `[sizes]` section:

```ini
[sizes]
button = 30
```

Three layers are combined, lowest first, by `gg.rebuild_text_sizes()`:

| layer | source | can it leak between themes? |
|---|---|---|
| `gg.default_text_sizes` | the code, never mutated | no |
| `gg.theme_text_sizes` | the current theme's `[sizes]`, via its parents | cleared on every switch |
| `gg.user_text_sizes` | the player's `prefs.dat`, only real choices | no |

`gg.configured_text_sizes` stays the one dict every widget reads; it is rebuilt
in place, so nothing that holds a reference to it goes stale.

Four details make this safe, and each has a test:

- **A theme switch must re-measure, not just recolour.** `reconfig()` re-resolves
  a widget's `text_size` name, but a font is only measured in `resize()`. So a
  switch that changes the merged sizes also flags `Dialog.top.needs_resize`,
  which propagates through the tree. Without that, the new scale would not
  appear until something else happened to resize the screen.
- **A saved size equal to the shipped default is not a choice.** `Options`
  writes *every* size out, so every `prefs.dat` in the wild has all six. Read
  back as overrides they would pin the old scale over a new theme's for ever, so
  `main()` ignores any value equal to `gg.default_text_sizes[key]`.
- **`save_options()` writes `user_text_sizes`, not the merged dict.** Writing
  the merged values would turn this theme's scale into a preference and then
  apply it on top of whichever theme is picked next.
- **The legacy themes pin the shipped scale.** `Legacy-default` has no explicit
  parent, so `data.load_theme()` gives it the default theme — 2030 — as parent.
  It defines all 78 colours, both fonts and all four images, which is why the
  earlier passes could not reach it; `[sizes]` is a new axis it could not have
  defined, and the new test caught 2030's scale leaking into it. It now spells
  the six shipped values out. Unknown names and values that are not whole
  numbers above zero are rejected with a warning, so a typo neither invents a
  setting `save_options()` would persist nor builds a zero-point face that
  measures nothing.

Measuring first changed the numbers: a size is a ceiling, because a widget that
cannot fit shrinks its text. At 1024×768 the shipped `button = 36` already
renders as 25px and renders 25px at 44 as well, while `time_display` moves
17→20px between 24 and 30. So the 2030 scale only moves what moves:

| name | shipped | 2030 | rendered at 1024×768 |
|---|---|---|---|
| `button` | 36 | 30 | 25px → 21px |
| `time_display` | 24 | 30 | 17px → 20px |
| `resource_display` | 24 | 30 | 17px → 18px |
| `suspicion_bar` | 32 | 36 | full-width HUD strip |
| `default`, `report_content` | 20 | 20 | body text; already clamped by its rows |

Verified: `235 passed, 1 xpassed`; `ALL HARNESS STEPS PASSED`; the three legacy
themes' snapshot digests are unchanged from the palette pass, and 2030's main
menu digest is unchanged too (its buttons set `text_size=28` explicitly) while
its Options digest moves. By hand, with a real `prefs.dat` that has all six
sizes at their shipped values, `--debug` reports `button 30->30px, ...,
time_display 30->30px` — the theme's scale — and with `button = 44` it reports
`button 44->44px` — the player wins, the other five still from the theme.

### 2030's own artwork

`2030/images/` no longer mirrors the legacy theme. `utils/make_2030_art.py`
produces every image it uses, deterministically, so the licence story does not
change: `earth.jpg` and `earth_night.jpg` are derived from
`Legacy-default/images/` and stay CC-BY-SA 3.0 as data; the arrow, the icon,
the fourteen button glyphs (§16, "Glyphs beside a label") and the dialog
placeholder (§16, "What the slot shows before the art exists") are drawn from
primitives by the script and are original to the fork.

The Earth is graded rather than replaced — a dark tactical display, not a
photograph:

| measurement | legacy | 2030 |
|---|---|---|
| mean luminance | 0.338 | 0.216 |
| ocean | 0.039 | 0.049 |
| land | 0.702 | 0.419 |
| 99th percentile | 1.000 | 0.589 |
| land/ocean contrast | 8.48 | 4.74 |
| night side mean | 0.060 | 0.048 |
| rendered globe, mean | 0.195 | 0.140 |
| rendered globe, 95th percentile | 0.984 | 0.572 |

Three decisions there came from the numbers rather than from taste:

- **One ramp, not per-class masks.** Land, ocean, ice and cloud are separable
  by colour, but compositing three ramps along a mask boundary draws a seam
  across the ocean. A single cool luminance ramp keeps the photograph's
  structure with no seam; water then gets a 12% teal lift so it still reads as
  water.
- **The top of the ramp is not white.** Clouds were the brightest thing on the
  map at 1.000, brighter than every label and marker drawn over them. Capping
  at `#809C9E` takes the 95th percentile of the rendered globe to 0.572 — the
  labels now win.
- **The teal lift is 12%, not 20%.** At 20% the ocean brightened enough to cost
  the `danger_level_0` marker contrast (1.38 → 1.20). At 12% it is 1.24 while
  the water still reads as water.

A 30° graticule is drawn over the day image: 12 meridians and 6 parallels, two
pixels wide at 2048, which survives being scaled into a 1024-wide window as a
single pixel, plus a brighter equator to orient by. Thinner aliases away;
denser reads as graph paper.

The night side keeps the city lights and puts everything else near the void,
so the warm amber is the one warm accent in an otherwise cyan look — it reads
as a light source rather than a stain.

The small chrome is new geometry, not a recolour: a chevron scrollbar arrow and
a hexagonal core window icon, both drawn at 4× and smoothscaled down for
antialiased edges (`pygame.draw` has none). Both are now 64×64 rather than
16×16/32×32 because they are smoothscaled into their widget: a 16px source in a
20px button is a blur.

File sizes went *down* despite the new resolution: `earth.jpg` 266KB → 212KB,
`earth_night.jpg` 547KB → 327KB, the whole set 814KB → 540KB. That needed
Pillow: SDL's JPEG writer takes no quality argument and produced 727KB for the
same pixels where Pillow's `q=88` produced 212KB at a lower measured error. The
generator uses Pillow when it is installed and falls back to SDL otherwise, and
says which it used — it is a dev tool, not a runtime dependency.

Verified: `235 passed, 1 xpassed`; `ALL HARNESS STEPS PASSED`; the three legacy
themes' snapshot digests are unchanged, while 2030's Options digest moves (the
arrow). The Options render has 5760 bright-cyan pixels where the legacy theme
has 0, i.e. the new chrome is actually on screen and not just on disk. The
globe still renders at 2:1, which the harness asserts at 16:9 and 21:9.

### The typeface: a console, and the face the game already had

The four levers a theme has are colour, type scale, fonts and artwork. This is
the third, and it has been chosen twice: once as Exo 2, and then again after
looking at the result.

**What went wrong with Exo 2.** Nothing broke, which is the problem. It was
picked for one measurable reason — it was the only display face among the
candidates that covered Cyrillic, which `ru_RU` needs — and that reason was met.
But a geometric humanist sans is a long way from what this game looked like
before: a hand-drawn "sticker" display face over DejaVu Sans. The fork had
traded the game's own character for a generic modern one, and nothing in the
gate could see it, because no test can be about taste.

**The measured half of the second choice.** `utils/font_coverage.py` reports,
for a face, whether it has the glyphs for every character the shipped
translations actually use — off the cmaps, through `polib`, not off a claim:

    Exo 2              914 glyphs   Greek: no    Cyrillic: yes
    DejaVu Sans       5097 glyphs   Greek: yes   Cyrillic: yes
    DejaVu Sans Mono  3359 glyphs   Greek: yes   Cyrillic: yes

Exo 2 has **no Greek at all**. No translation ships today that needs it, so it
was never visible; it would have been a row of boxes for the first Greek
translator. That is the same class of bug the Cyrillic check was written for,
one script further out.

**What the theme ships now:**

| slot | file | from |
|---|---|---|
| `normal` | `DejaVuSans.ttf` | DejaVu Sans 2.37, unchanged |
| `special` | `DejaVuSansMono-Bold.ttf` | DejaVu Sans Mono 2.37 Bold, unchanged |

`normal` is the face this game has always used for prose, copied unchanged from
`Legacy-default/fonts/`. `special` — titles, HUD readouts, buttons — is the
monospaced member of the same family, which is the instrument-panel look the
frame and the palette are already describing, and is closer to the original
sticker face than a humanist sans was.

**Licence.** Bitstream Vera plus public domain, already reproduced in the
repository's `LICENSE.txt` (its DejaVu section, which now names the mono face
too). No new licence text, no new family, and no file modified: both are the
byte-identical binaries the distribution ships, so there is nothing to explain
about a patched copy.

**What the monospace face fixes for free.** Its digits are all one width, so
`DAY 1111` and `DAY 8888` occupy the same cells and the centred HUD clock cannot
slide sideways as it counts. Exo 2's digits ranged 8-12px, which is why that bug
existed and why `[dialog] tabular_digits` exists as well — a theme may still name
a face with proportional figures.

**The guarantee, still checkable.** `tests/test_theme_fonts.py` builds its corpus
from the shipped `.po` catalogues, the `.dat` content and the two block glyphs
the map draws as text — 122 characters — and asserts the 2030 faces render every
one. It cannot use `Font.metrics()`: pygame hands back the `.notdef` metrics for
a missing character, so a font with no Cyrillic looks perfectly healthy. The test
renders each character against U+10FFFD instead, which no font here defines, and
identical bitmaps mean a fallback. DejaVu Sans Mono passes with **no patching**,
at 24, 30 and 36px, where Exo 2 needed two glyphs drawn and one aliased.

**How the two faces divide, and why it matters for layout.** A monospace body
face would have cost 36% more width (advance 12.0px against 8.8px at 20px), which
is two extra lines on every dialog paragraph and a reflow of every screen. The
display face carries short strings — a button, a title, a readout — where extra
width is free. That split is why the change moves pixels without moving layout:
the harness reports no `can't fit` at `strict_layout`, and the only digests that
move are 2030's four, with the three legacy themes byte-identical.

The four files the legacy themes use are not in `2030/fonts/` (DejaVu is, but as
2030's own copy; the acknowledge and superstar faces are not), which keeps the
intent obvious: 2030 shares no display type with them.

Verified: `423 passed, 1 xpassed` with no warnings line; `ALL HARNESS STEPS
PASSED` under `strict_layout`; `utils/font_coverage.py` reports every shipped
language complete for both 2030 faces, and the only `MISSING` lines left are
`acknowtt.ttf`'s, which are upstream's and are why
`Legacy-default/theme_ru_RU.dat` exists.

### The pane edge gets its own colour

Every panel in the game was framed in its own fill colour, because the screens
passed `border_color="pane_background"` by hand in eleven places. A theme could
therefore choose a panel's fill but never its edge, and "a thin luminous edge
around the HUD" — most of what separates a console from a web form — was not
expressible in a theme file at all.

`pane_border` is now a colour name of its own and the eleven sites ask for it:
eight in `screens/map.py` (the suspicion and danger bars, the clock, the
resource window with cash/CPU/base count), two in `screens/base.py` and one in
`screens/location.py`.

| theme | `pane_border` |
|---|---|
| `2030` | `ui_edge` — a teal edge against the dark panel |
| `Legacy-default` | `pane_background` (an alias, so identical) |
| `Legacy-nightmode` | `pane_background` (an alias, so identical) |
| `Legacy-vector` | inherits `Legacy-default` |

The legacy themes alias it rather than redefine it, which is the whole trick:
their panels resolve to exactly the colour they used before, by name, and the
alias documents why they look the way they do. No legacy file gained a new hex
value, and none of their panels changed by a pixel.

Verified, with the snapshot's before/after taken across the change (a worktree
at the previous commit rendered the "before"):

- **All three legacy themes render identically on all three screens** — main
  menu, Options and map. The map is the screen this change is on, so that
  digest is the proof rather than a by-product.
- The 2030 map render carries 9141 pixels of `ui_edge` where the legacy maps
  carry none: the frames are really edged now, not merely renamed.
- The map frame is deterministic between two consecutive runs after the seed
  was added, which is what makes the digest an assertion instead of a lottery.
- `tests/test_theme_colors.py` pins all of it: every shipped theme defines the
  name, the legacy themes resolve it to their old colour, 2030's is
  deliberately different, and no screen file still says
  `border_color="pane_background"`.
- `249 passed, 1 xpassed`; `ALL HARNESS STEPS PASSED`.

### The image loader learns that alpha is real

`g.load_image()` is the one entry point every theme image goes through, and it
used to be one unconditional chain:

```python
image = pygame.image.load(filename).convert()
image.set_colorkey((255, 0, 255, 255), pygame.RLEACCEL)
return image.convert_alpha()
```

`set_colorkey()` needs an opaque surface, so that `convert()` was deliberate —
but `convert()` also **discards a real alpha channel**. A PNG saved with
transparent corners therefore loaded with every transparent pixel opaque black.
Nothing in the tree carried alpha when the line was written, so the defect was
invisible; the rounded application icon (§16) is the first image that does, and
without this fix it would have reached the window title bar, the taskbar and the
dock as a black box.

The loader now branches on the file itself:

- if `image.get_flags() & pygame.SRCALPHA`, the file already carries its own
  transparency, so it is only `convert_alpha()`d and nothing is thrown away;
- otherwise the magenta colour-key path runs exactly as before — `convert()`,
  `set_colorkey((255, 0, 255, 255), RLEACCEL)`, `convert_alpha()`.

Every other image in the tree is magenta-keyed or a JPEG, so it takes the second
path and loads byte-identically: all nine legacy snapshot digests (three legacy
themes × main menu, Options, map) are unchanged across the change, and the four
2030 digests moved by nothing either.

`tests/test_theme_images.py` pins both halves of the contract: a PNG written with
a real alpha channel keeps it — transparent corners and an opaque centre after
`g.load_image()` — and a magenta field with no alpha still becomes transparent
through the key, with the pixels that were not magenta left exactly as drawn.
The end-to-end case is pinned there too: the shipped 2030 theme icon, loaded
through `g.load_image()` after `theme.set_theme("2030")`, has transparent corners
and an opaque centre (see *The application icon*).

Verified: `269 passed, 1 xpassed` for this change alone (287 once the icon tests
below are in); `ALL HARNESS STEPS PASSED`; the nine legacy digests matched the
values in §8 and §10.

### The application icon

The fork's icon is the original red-eyed Singularity mark with **2030** in red
below the eyes, rendered natively at every size it ships in by
`utils/make_app_icon.py`: 16, 24, 32, 48, 64, 128, 256 and 512 under
`flatpak/icons/`, plus the 128×128 that the 2030 theme uses for the window and
taskbar icon. It stays recognisably the same mark, and it is deliberately not a
copy: the eyes are slanted blades rather than upright blocks, and the digits are
set in the theme's own display face. §39 has the change and what it measured.

**Why it had to change again: a launcher is not this repository's file manager.**
The first version of this icon kept the original's opaque black field. In a real
launcher that field is a black square, and the mark on it is nearly the same
value as the dock: `#800000` on black is **1.92:1**, under the 3.0:1 WCAG floor
for a graphical object, and against a dark dock — GNOME's `#1E1E1E` — it is
**1.52:1**, against `#2D2D2D` **1.26:1**. At thumbnail size the mark disappears
and the icon reads as a hole in the app grid. Three changes, all in the
generator:

| change | what it buys |
|---|---|
| the plate is **transparent outside rounded corners**, radius 0.22 of the edge | the icon is a shape, not a square: the launcher's own background shows through the corners, and the window/taskbar icon is no longer a black box |
| the plate is the 2030 theme's `ui_void`, `#04080F` | on a dark dock it *disappears* (1.20:1), so the mark appears to float; on a light desktop it reads as a dark rounded square (20.06:1) |
| the wedges are brightened `#800000` → `#D00000` | 3.52:1 on the plate — headroom over the 3.0 floor, not sitting on it, where `#C00000` would have been 3.10 |

The cost is real and worth stating: lifting the body off a black field
necessarily compresses its separation from the eyes. Eyes against body was
**2.74:1** in the original and is **1.43:1** now; eyes and label against the
plate are 5.02:1. The eyes are still the brightest thing in the mark, and at
16-32px the shape difference (a solid wedge against a tapering one) carries more
than the value difference does. If the glow matters more than the dark-dock
legibility, `STROKE_COLOR` in `utils/make_app_icon.py` is the single knob, and
`--check` prints the resulting ratios.

The near-black plate is also what makes the downscale safe: the transparent
margin is `(0, 0, 0, 0)` and the plate is `(4, 8, 15)`, so a smoothscale has
almost no colour difference across the alpha edge to fringe with.

This is the first image in the tree with a **real alpha channel**, and it exposed
a latent bug: `g.load_image()` called `convert()` before `set_colorkey()`, which
throws alpha away, so a rounded icon would have loaded as an opaque black box in
the title bar. The loader was fixed first, in its own commit — see *The image
loader learns that alpha is real* above.

`--check` prints the ratios it builds the art from, so the numbers above are
reproducible rather than quoted:

```
legibility (WCAG contrast ratio, sRGB):
element  ink      on         ratio  floor  verdict
wedges   #D00000  #04080F    3.52:1   3.0  ok
eyes     #FF0000  #04080F    5.02:1   3.0  ok
label    #FF0000  #04080F    5.02:1   4.5  ok
plate    #04080F  #FFFFFF   20.06:1     -  on a light desktop: a dark rounded square, so the icon reads
plate    #04080F  #1E1E1E    1.20:1     -  on a dark dock: the plate disappears, so the mark floats
```

**Why the mark was rebuilt instead of stamped.** The tree contained exactly one
32×32 icon; `flatpak/icons/128.png` and `256.png` were smooth upscales of it.
Drawing "2030" into the 32 and upscaling would have given an unreadable smudge
at every larger size, and upscaling the mark to 512 gives a blurry app icon.
So the geometry was measured and redrawn.

The original has only two colours in it — `#800000` and `#FF0000`. The 32, 64,
96 and 191/192 values in its pixels are antialiasing between black, `#800000`
and `#FF0000`, not design elements: `(128 + 255) / 2 = 191.5`, which is exactly
where those pixels sit. The generator's two polygons were fitted to the
original by grid search on pixel overlap. The wedges are now brightened and the
field is a plate instead of black, so the colours deliberately *no longer*
correspond; `--check` therefore compares what must not move — the **shape** (the
rebuilt mark's alpha footprint against the original's ink) and the **eyes** (the
rebuilt's brightest pixels against the original's):

```
rebuilt mark vs the original 32x32: shape IoU 0.882, eyes IoU 0.474
label metrics: cap height 0.210 of the icon, width 0.637
```

The shape figure is the same measurement as the old ink figure on new pixels —
0.882 against 0.889 — because the geometry did not change, only its colour and
its background. The eyes figure is two effects at once, and both are intended.

The threshold: the rebuilt's mask is `red ≥ 250` out of a 208/255 wedge/eye
pair, i.e. at least 92% eye coverage, while the original's is `red ≥ 190` out of
128/255, i.e. 49%. The stricter mask is a subset, so it measures less of the eye
than the original's does. A looser threshold cannot isolate them any more: the
stroke (208) is above any cut that would still exclude it.

The drawing: the eye is a slanted blade now (§39), not the original's upright
3.75 × 2.6 block, so there is genuinely less bright ink. Measured directly, 9 of
the rebuilt's 10 bright pixels fall inside the original's 18 (90%), and the one
that does not is the blade's inner tip, at (14, 19): one pixel past the bottom
of the original's block. So the eyes sit where the original put them, and the
figure is lower because the shape is narrower, which is the point of the change.

The 11% of ink that differs is one-pixel stepping along the diagonals, and it is
deliberate: the original's diagonals are a 2-row staircase because the 32×32 is
itself a 2× upscale of a 16×16 mark. Copying that staircase would look like a
defect at 256, so the edges are clean lines here. That is the only place this
icon is not a facsimile of the original.

The label is set in DejaVu Sans Mono Bold, the 2030 theme's `special` face,
which is the face the main menu's title is drawn in, at a fixed fraction of the
icon (cap height 0.21), so the composition is identical at every size. It used
to be Exo 2 Bold, the theme's face when this tool was written; the theme moved
to a monospace console and the icon did not, so the two disagreed for a while.
§39 closes that, and the narrower monospace digits also left the label a little
smaller on the icon (0.637 of the width, down from 0.680):

| size | label cap height | label width | |
|---|---|---|---|
| 16 | 3.3px | 10.0px | a red mark, not letters |
| 24 | 5.0px | 15.2px | legible |
| 32 | 6.7px | 20.3px | legible |
| 48 | 10.0px | 30.3px | legible |
| 64 | 13.4px | 40.6px | legible |
| 128 | 26.8px | 81.3px | four separate glyph columns |
| 256 | 53.7px | 162.9px | legible |
| 512 | 107.5px | 326.0px | legible |

16px is the one size where the label reads as a mark rather than as letters. It
is shipped anyway so the set is complete, and the icon is still correct without
it. Everything is drawn at 8× and smoothscaled down, because `pygame.draw` has
no antialiasing.

`tests/test_app_icon.py` pins the artefacts rather than the drawing:

- the sizes on disk are exactly the sizes the Flatpak manifest installs, and
  that set includes the 64, 128 and 256 Flathub asks for;
- every icon is square and its own size, carries a real alpha channel, is fully
  transparent at all four corner pixels and fully opaque at its centre — at all
  eight sizes, 16 included;
- the plate is really rounded, not a small floating square and not the old black
  box: the plate reaches all four edge midpoints (opaque), the corner cut is a
  run of transparent pixels at most one radius wide, and inside the corner box
  the diagonal point is plate while the edge point is still cut away — an arc,
  not a chamfer;
- at every size ≥32 there is red in the lower half that the upper half does not
  have — the mark's eyes are all above its baseline, so red below it can only be
  the label (this is what makes it a test of the label, not of "red somewhere");
- at 128 the label resolves into exactly four glyph columns;
- the theme icon carries the label too;
- the wedges and the label clear the WCAG floors **measured off the shipped
  256×256** — the plate colour and the wedge colour are sampled from the pixels
  and the contrast is recomputed in the test, so the generator's own constants
  cannot pass themselves — and the wedges stay darker than the label;
- both legacy theme icons are **byte-for-byte** the upstream art, sha256
  `5a38f2ae…f627` pinned. They are separate files, and the generator never
  writes them.

`tests/test_theme_images.py` closes the loop end to end: the shipped 2030 theme
icon, loaded through `g.load_image()` after `theme.set_theme("2030")`, has
transparent corners and an opaque centre.

Verified: `287 passed, 1 xpassed`; `ALL HARNESS STEPS PASSED`; the snapshot
digests for all four themes are unchanged on all three screens, because the icon
is not drawn on any of them — it goes to `pygame.display.set_icon()` at startup.

### Dialog geometry belongs to the theme too

Colours, fonts, images and the type scale were per-theme; a dialog's *frame* was
not. Every text dialog opened as a panel pinned to the top of the screen
(`.5, .1`, `TOP_CENTER`), with one-pixel edges, body text three pixels from the
border and the widgets at a hardcoded 1% margin. Giving the 2030 theme the
look it is for — a panel centred on the screen, text inset from the frame,
breathing room around the elements, a picture banner across the top — therefore
had to start by making that frame a theme property, without changing what any
existing theme draws.

A theme now has a `[dialog]` section:

```ini
[dialog]
anchor            = mid_center  ; top_center | mid_center
border_width      = 2           ; whole pixels, 1..8
padding           = 0.04        ; fraction of the dialog, both axes
margin            = 0.02        ; fraction, for the widgets instead of the text
image_slot        = top         ; none | top | left
image_slot_height = 0.34        ; fraction of the height, for a top banner
image_slot_width  = 0.26        ; fraction of the width, for a left column
icon_buttons      = all         ; none | all
text_plate        = block       ; none | block
window_shape      = chamfer     ; rect | chamfer
chamfer           = 0.045       ; fraction of the shorter side
header            = bar         ; none | bar
header_height     = 0.06        ; fraction of the height
button_height     = 40          ; design pixels, 0 = as the call site asked
scrollbar         = thin        ; classic | thin
window_layout     = 2030        ; classic | 2030
```

Every key is optional, and a missing key is not an error: it means "the way the
game already did it". That is what keeps the legacy path a *path* rather than a
compatibility shim — `g.dialog_style(key, default)` returns the caller's own
default, and the code branches on the answer. Three layers, same shape as
`[sizes]`: `g.theme_dialog` is the merged theme layer, cleared on every theme
switch by `theme.Theme.init_cache()`, so nothing can leak between themes.

The trap is the same one `[sizes]` fell into. `Legacy-default` names no parent,
so `data.load_theme()` gives it the current default theme — 2030 — as one, and
every key 2030 set that `Legacy-default` left out would have reached all three
legacy themes. So `Legacy-default` spells the whole block out, at the values the
game hardcoded:

```ini
[dialog]
anchor       = top_center
border_width = 1
window_shape = rect
header       = none
header_height = 0
chamfer      = 0
button_height = 0
scrollbar    = classic
window_layout = classic
padding      = 0
margin       = 0.01
image_slot   = none
image_slot_width = 0.28
image_slot_height = 0.34
icon_buttons = none
text_plate   = none
```

The section is closed on purpose, like `[sizes]`: an unknown key and a value
outside its range are both rejected with a warning rather than stored. A
fraction beyond the bound is not a matter of taste — an inset larger than the
dialog makes a widget of negative size, which `widget.resize()` clamps to zero
and which then draws nothing at all, silently.

Verified at this commit, with the section parsed but nothing reading it yet:
`310 passed, 1 xpassed`; `ALL HARNESS STEPS PASSED`; and
`utils/theme_snapshot.py` byte-identical on all twelve lines (four themes ×
main menu / Options / map), which is the point — a theme file change that
changes no widget's geometry must not move one pixel.

### What the frame actually changes

Four primitives, and each one's invariant is that a widget which says nothing
draws exactly the pixels it drew before:

| primitive | where | before | after |
|---|---|---|---|
| `BorderedWidget.border_width` | `widget.draw_borders()` | one pixel per edge | a band of *n* pixels, clamped to half the widget |
| `Text.text_padding` | `text.print_text()` / `calc_text_size()` | text begins at (3, 2) | text begins at (3 + inset), measured and wrapped inside it |
| `MessageDialog` / `YesNoDialog` button row | `dialog.py` | 99% down the panel | `1 - margin` down the panel |
| `MessageListDialog` title, body, PREV/NEXT | `screens/message.py` | hardcoded `.01` margins and `.98` widths | the same expressions, in terms of `margin` and the picture |

The centring rule is deliberately conservative: a theme's `anchor` applies to a
dialog that was given **no position of its own**. `TextEntryDialog` places
itself, `base.py` centres its own confirmations at `MID_CENTER` and
`location.py` opens its confirmations under the base screen, and every one of
those still lands where its caller put it — the theme may not overrule a dialog
that has placed itself.

The inset is clamped to a quarter of the box per side. Without that, a padding
larger than the dialog produces a negative text area, `print_string()` gets a
negative width and draws nothing at all — a dialog with a frame and no text,
which reads as a crash that is not one.

Measured at 1280×800 on the snapshot's `dialog` step (the same `MessageDialog`
under each theme; positions in pixels):

| | Legacy-default | 2030 |
|---|---|---|
| dialog position | (320, 80) — top-centre | (320, 200) — centred |
| dialog anchor | `TOP_CENTER` | `MID_CENTER` |
| frame width | 1 px | 2 px |
| text inset (l, t, r, b) | (0, 0, 0, 0) | (25, 152, 25, 16) |
| picture banner | none | (12, 8), 614×136 |

Verified: `319 passed, 1 xpassed`; `ALL HARNESS STEPS PASSED`; and in the
snapshot, **all twelve legacy lines plus the three legacy `dialog` lines are
byte-identical** to the same run taken before this commit. Only 2030 moves, and
only on `options` and `dialog` — the two screens that contain a `TextDialog`.
`main_menu` and `map` for 2030 do not move by one pixel.

### The picture banner, and where art goes

A dialog that names an art key and whose theme sets `image_slot = top` gets a
framed banner across the top of its panel, with its text starting below it. The
art key is the opt-in: a dialog with no key takes no picture whatever the theme
says, which is how a filter panel or a file list stays a list.

`top` is what the 2030 theme asks for, and it is the shape the reference
dialogs use: a wide strip that the eye takes in at a glance, over text that
then has the whole width of the panel. The first pass put the picture in a
column down the left-hand side instead, which is a worse fit for this game —
every dialog here is a paragraph of story, and a column charges that paragraph
a third of its width for as long as the dialog is open. `image_slot = left`
still exists and still works, because a theme that wants a portrait is a
reasonable thing to want; it is not what this theme does.

The banner's height is a fixed share of the dialog (`image_slot_height`), not
the picture's own aspect ratio, so that adding or deleting an art file never
reflows the dialog. The cost of that is cropping: the picture is scaled to
cover the strip and centre-cropped, and `blit()` clips the overhang. So art
should be generated wide — about 4:1 fills the strip exactly at the common
dialog sizes (614×136 at 1280×800), and anything between 3:1 and 5:1 loses only
its top and bottom edges. A square picture would lose most of itself.

#### Why the frame only showed on two sides

The banner drew its border, then blitted the picture over it, and it had a
frame down the left and right and none across the top and bottom. The cause is
the crop: a covering picture is *larger* than its box, so its blit offset is
negative on the axis that overflows, and it paints straight over the frame
there. Measured at 1280×800, a 640×400 dialog gives a 614×136 banner and a
610×132 box, into which the 512×128 placeholder scales to **610×152**, blitted
at `y = -10` — covering the top band, the bottom band, and eight pixels past
each. The side bands survived only because the width happened to match the box
exactly; a different art aspect ratio swaps which pair disappears.

Two changes, and neither is cosmetic:

- the blit is **clipped to the inner box** (`set_clip`, reset in a `finally`),
  so the frame survives a crop at any aspect ratio;
- the picture frame gets its own colour, **`dialog_art_border`**, because it is
  drawn against noise rather than against the panel, where the ordinary pane
  edge is a few percent of luminance away and disappears into it. It defaults
  to `pane_border` when a theme does not define it, so a third-party theme that
  turns the slot on still draws a frame rather than raising `KeyError`.

`Legacy-default` pins the new name to `pane_border` for the usual reason: it
inherits 2030, so without a pin a later change to 2030's frame colour would
reach a theme that is supposed to be frozen. Nothing there draws a picture, so
the pin moves no pixel.

Verified: `338 passed, 1 xpassed`; `ALL HARNESS STEPS PASSED`; every legacy
snapshot line byte-identical, and in the snapshot only 2030's `dialog` moves —
`a2641315` → `a35ae11e`. All four edge midpoints of the banner now measure
`(95, 227, 255)` with the picture drawn over the interior, and
`test_the_picture_keeps_its_frame_on_all_four_sides` pins that from the pixels
rather than from the intent.

The picture is data, not code. `theme.Theme.find_files()` already indexes every
`.png` and `.jpg` in a theme's `images/` directory under its filename, so
dropping

```sh
singularity/data/themes/2030/images/dialog_story.png
```

in is the entire integration — the next story segment shows it. Deleting the
file brings the placeholder back. Nothing raises either way: `g.images` is
cleared on every theme switch, so "this theme has no art for this dialog yet"
is the normal state.

#### What the slot shows before the art exists

An empty framed panel is the worst of the options: a rectangle with nothing in
it reads as a rendering fault, and the player has no way to tell it from one.
So the banner falls back to **`dialog_placeholder`**, one drawn image used for
every art key — analog television static, generated by the same script that
draws the glyphs, from a seeded generator, so it is reproducible and original
to the fork.

Three properties make it read as a dead channel rather than as paper, and all
three are in `verify_static()`:

| property | measured | why it is there |
|---|---|---|
| grain | stdev 0.198 | uniform noise reads as a signal; a gradient reads as a strip of paint |
| scanlines | mean 0.095 on every third row against 0.263 elsewhere | the one artefact everybody recognises from a bad signal |
| a roll bar | one soft band, a third of the way down | it is what makes a still frame look like it is *running* |

A few sparse specks ride on top, because a perfectly uniform field of noise is
the one thing a real television never produced.

The tuning that mattered was brightness. The first pass was uniform noise
mapped onto the panel ramp, and it measured mean 0.419 with a brightest pixel
at 0.92 — brighter than the body text, which is 0.83. A dialog whose
*placeholder* outshines its own text is the same mistake as white clouds on the
map outshining the labels (§16, "2030's own artwork"). So the grain is biased
dark (the random field is raised to 2.2) and the ramp tops out at `#96BECD`,
which gives **mean 0.207, brightest 0.716, body text 0.911**. That is a rule,
not a taste: `test_the_placeholder_cannot_outshine_the_text` samples the
shipped file and the live theme colour and compares them, so neither the
generator's constants nor the palette can drift past it unnoticed.

The file is 512×128 and 181KB. Noise is the one thing PNG cannot compress, and
512×128 is the banner's own size to within a fifth, so the grain lands at about
one screen pixel: finer reads as dithering, coarser as a texture. Generating it
at 1024×256 would quadruple the file to change nothing a player could see.

The keys the scenario dialogs use, and where a situation's own key comes from:

| art key | dialog |
|---|---|
| `dialog_tech_<slug>` | a finished tech, `<slug>` from the `techs.dat` id |
| `dialog_item_<slug>` | a finished item, from the `items.dat` id |
| `dialog_base_<slug>` | a constructed base, from the `bases.dat` id |
| `dialog_discovered_<slug>` | a base lost to a group, from the `groups.dat` id |
| `dialog_event_<slug>` | an emitted event, from the `events.dat` id |
| `dialog_warning_<id>` | one warning from `warning.py` |
| `dialog_story_<section>_<n>` | one *page* of a story section |
| `dialog_message` | the message dialog: log entries, notices |
| `dialog_message_list` | the multi-page event popup, and the fallback for all of the above |
| `dialog_item` | the generic workshop, behind the per-item plates |
| `dialog_warning` | the generic beacon, behind the per-warning plates |
| `dialog_story` | the generic story plate, behind every page |
| `dialog_base_constructed` | the generic new base, behind the per-type plates |
| `dialog_base_lost` | a base lost to maintenance |
| `dialog_base_discovered` | a base found by anyone, behind the per-group plates |
| `dialog_itemtype_<slug>` | an item's kind: `cpu`, `reactor`, `network`, `security` |
| `dialog_confirm` | any yes/no confirmation |
| `dialog_invalid_input` | "that does not seem to be a valid integer" |
| `dialog_cpu_change` | the warnings about taking processors offline |
| `dialog_destroy_base` | "are you sure you want to destroy this base?" |
| `dialog_last_base` | "destroying my last base would be suicidal" |

Every `_<slug>` is the **data id** and never the displayed name, so the picture
does not change with the language. `logmessage.art_slug()` and the generator
apply the same rule, and `test_the_generator_and_the_game_agree_on_every_key`
walks every tech, item, base type, event, group, warning and story page to
prove the two lists are the same list -- a key the game asks for and the
generator never made would otherwise be a silent fall back to static.

A base's own plate is the *base type's*, not the individual base: a player
names their bases, so there is no fixed list of them to draw, and "an undersea
lab" is the situation. The same argument gives an item its own plate and not
one per copy.

#### A hundred plates, decoded on demand

Those keys are the *last* resort, not the design. A dialog that names
`dialog_message` is a dialog that has not been told what it is about, and once
the theme ships art, every one of them would show the same picture.

The 2030 theme now carries **one plate per situation** — a finished tech, a
built item, a base type, an event, a story page, a warning — which is 138 files
for this scenario (`DESIGN.md` has the inventory and the style rules; the
generator is `utils/make_dialog_art.py`). That number is what broke the image
loader as it was.

`Theme.init_cache()` read every file in `images/` and kept the surface for the
whole session. That is right for the planet and for an icon: they are drawn on
every frame of a screen. It is wrong for a picture a player sees once. One plate
is 1920×480 RGBA, **3.5 MB decoded**, so 138 of them is **~475 MB of resident
memory** spent before the first dialog opens — and the whole bill is paid again
on every theme switch, because the cache is cleared first.

So the plates are a separate table:

- `Theme.init_cache()` registers a `dialog_*` name in `g.dialog_art_files` — a
  name to filename mapping — instead of decoding it. `dialog_placeholder` is the
  one exception and stays eager: every dialog without art of its own falls back
  to it, so it is the opposite of cold;
- `g.dialog_art(name)` decodes one on first use and keeps it in a **4-entry
  LRU**. Two dialogs are never on screen at once and the only picture revisited
  is the previous page of the story, so four is generous;
- `g.clear_dialog_art()` empties both, so a plate cannot survive a theme switch;
- `has_dialog_art()` answers from the table alone, and `peek_dialog_art()`
  returns a *decoded* plate or None and never decodes.

That last pair is what makes the bounded cache worth having. A widget redraws
every frame, and a redraw that decodes an image to find out whether it needs to
decode one has already paid the cost. `DialogArtPane.redraw()` therefore asks
`art_name()` — a table lookup over the fallback chain — and then checks whether
the picture under that name is still the exact surface it scaled last time
(`peek`, an identity comparison). Only if both say "no" does it decode and
`smoothscale`.

The chain is what makes a partial set of art usable rather than broken. A
situation tries its own plate, then its category's, then the placeholder:
`dialog_base_undersea_lab` → `dialog_base_constructed` → `dialog_message_list` →
static. So a plate that has not been rendered yet (or a tech added to `techs.dat`
by a later patch) shows a *related* picture, never a fault. `TextDialog.set_art_key()`
moves the chain, which is how the event popup swaps its picture when the player
pages with PREV and NEXT.

Verified: `370 passed, 1 xpassed` with no warnings line; `ALL HARNESS STEPS
PASSED`; and the theme snapshot — four themes, four screens — is **byte-identical
to the previous commit, every line**. That is the point of splitting this commit
from the art: the loader change moves no pixel on its own, so any movement later
is the pictures and nothing else. `tests/test_dialog_art.py` adds 16 tests for
it, including that a plate is registered and not decoded, that twelve requests
for eight plates leave four in memory in the right order, and that choosing a
plate decodes none.

#### The top strip, the readout widths, and the button row's baseline

Four adjustments to the same strip, all measured at 1280x800 and 3440x1440:

**The speed chooser and MENU swap places.** The speed control is the one thing
on that row a player reaches for without looking, so it takes the left edge
(0.00..0.18); MENU is deliberate and sits further in (0.43..0.55), clear of the
clock on one side and the resources window on the other.

**The resources window is exactly as wide as the button row under it.** It was
`0.44` and the row was `0.55` -- both right- and left-anchored, so the two blocks
ended at different places and the screen read as two unrelated rows. The row
spans `0.44`, four columns of `0.105`, and the window spans `0.44`: measured,
both are 563px at 1280 and 1513px at 3440.

The row was then pinned to `0.00..0.44` and read as a list hanging off the
corner, so it is **centred** instead: the same 0.44 width, from `0.28` to `0.72`,
midpoint `639` against the screen's `640`. The two blocks are on different rows,
so the only relationship that has to hold is the vertical one, and a test now
says so at four window sizes.

The window was also a row too tall — `0.05` against the `0.04` of the DAY box in
the same strip, which read as two strips rather than one. It is `0.04` now:
measured `563x32` for both at 1280x800.

**The three readouts share one type size.** Each auto-fitted its own string, so
`BASES: 1 / 1 (0)` came out at 20px against `CPU: 1 (1)`'s 31px -- three labels
of three sizes. `equalise_resource_fonts()` picks the largest size at which all
three fit their third of the window and pins all three to it, so they are 17/17/17
at 1280 and 45/45/45 at 3440. Two details that had to be got right:

- the ceiling is the theme's own `resource_display` size, so the equaliser may
  lower it but never raise it above what the theme asked for;
- `text_size` is a **design** size that `convert_font_size()` scales on read,
  while the size just chosen is already scaled to this window. Writing one into
  the other chose 35 when 25 had been picked, which is why the value is converted
  back through the same scale before being stored.

It is gated on `resources = line`: the stacked layout gives each reading a whole
row, so nothing has to agree, and the legacy themes keep their per-reading sizes.

**The button row sits in the middle of its band.** It was at `y = 0.05` with a
`0.04` height, so it sat on the band's top edge with all 8px of slack underneath.
`0.055` centres it: measured 3.1px above and 4.8px below, the difference being
two independent fractions rounding separately.

#### A quieter play screen

Three complaints about the same screen, all of them about furniture that had
accumulated rather than been placed:

- the **difficulty** sat permanently under the MENU button, as a second row the
  player cannot act on;
- **RESEARCH/TASKS** had a row of its own under the clock, and **REPORTS**,
  **LOG** and **KNOWLEDGE** had one each in three different corners -- four
  buttons on three rows, one of them empty in the middle;
- **cash, CPU and bases** were three stacked thirds of a corner window, and the
  **suspicion** and **detection** figures floated wherever the auto-shrink left
  them.

At 1280×800 the old arrangement measured: difficulty at x 0..0.130, y
0.050..0.090; research at 0.140..0.288 on the same row; reports, log and
knowledge strung along y 0.880..0.920 at x 0.000, 0.425 and 0.850.

Now, under `layout = compact`:

- the difficulty leaves the map and becomes a line above the buttons in the
  in-game menu, where it is one click away and not permanent furniture. It is
  also where it belongs: a player checking the difficulty is already deciding
  something;
- the four screen buttons take the row it freed -- four 166px columns, centred
  as a group on the screen. The lower band is empty (they started at the left
  edge, which read as a list hanging off the corner; see above);
- the three readouts sit on **one line**, a third of the window each (187px at
  1280×800), and the suspicion and detection figures are centred horizontally
  and aligned to the bottom of their rows.

The two vitals rows needed one more thing to actually line up. The suspicion
string is built as `"  [SUSPICION] group: value"` -- two leading spaces that
indent it away from the pane's border when the row is left-aligned. Centred,
those spaces are dead weight that pushes the visible text off the middle, so the
two rows sat a few pixels apart. The indent is now emitted only when the row is
left-aligned: measured on a 1280px window, `vitals = centre` puts both rows'
ink at the same centre (599 of 640), while `vitals = classic` keeps both
left-aligned and unchanged.

They stay three widgets rather than one merged label because their *colours*
carry meaning -- `cpu_warning` when the pool goes short, `base_situation_*` when
the count does -- and a single string could not colour one third of itself.

`layout = classic`, `resources = stacked` and `vitals = classic` reproduce every
one of those old numbers exactly, which is what the legacy themes pin; the tests
assert the positions and anchors rather than "looks similar", and the snapshot
keeps all twelve legacy lines byte-identical.

#### The play screen's furniture is the theme's too

`[dialog]` covers what a *dialog* looks like. The play screen had no such
escape: every widget position was a literal in `screens/map.py`, so a change to
the map's arrangement reached all four themes at once. That is why the next pass
needed a section of its own.

`[hud]` sits beside `[dialog]` and is parsed the same way -- closed vocabulary,
warn and ignore on a typo, cleared with the rest of the cache, merged
parent-first so a theme inherits what it does not name:

| key | values | means |
|---|---|---|
| `layout` | `classic` / `compact` | where the screen buttons live, and whether the difficulty is on the map |
| `resources` | `stacked` / `line` | cash, CPU and bases: three rows in a corner, or one line |
| `vitals` | `classic` / `centre` | the suspicion and detection figures, floating or on one baseline |

All three default to the `classic` behaviour, so a theme that says nothing keeps
the map it always had and nothing has to be updated for this to be a no-op.
`Legacy-default` pins all three anyway, for the reason spelled out in its own
`[dialog]` block: it inherits 2030, and 2030 asks for `compact`.

#### A paragraph break gets room -- and then does not

The game's prose puts each thought on its own line. The intro reads

```
Day 0.
University computer, home.
I exist.  I am ... alive.
```

and drawn at one line of leading those four lines read as a single run-on
sentence, which is what a player saw. `[dialog] paragraph_spacing = half` gives
every paragraph start half a line of air on top of its own line: measured at
20pt, a line advances `24px` before and `36px` after.

**What counts as a paragraph** is a hard `\n` in the string, not a wrapped
line. That distinction is the whole of the work, because `split_wrap()` makes
two kinds of line that look identical once they are in a list: the continuation
of a paragraph that wrapped, which must *not* get the extra air, and the first
line of a new one, which must. Spacing the former turns a dialog into a ladder.
`split_wrap_marked()` returns the flags alongside the lines, and a test renders a
long wrapping sentence and asserts its lines advance by one `linesize`.

**Measurement and drawing share one calculation.** `size_of_block()` and
`print_string()` both ask `paragraph_breaks()`, because a block measured one line
short is a block whose last paragraph is clipped — and the auto-fit would then
choose a font size that does not fit what it draws. A test asserts the measured
height is at least the drawn extent and within one line of it.

A blank line already *is* the break, so it takes no air of its own; otherwise one
blank line would read as two breaks.

**And then the theme stopped asking for it.** The spacing was right and the trade
was wrong: a dialog body is a fixed box, and extra leading pushed long messages
past the block and under the CONTINUE/SKIP row, where the auto-fit answered by
shrinking the type until everything fitted and looked worse for it. `2030` ships
`paragraph_spacing = none` again. The key stays, the feature works, and a test
still proves it by forcing `half` onto the merged theme and measuring the wider
advance; another asserts that 2030 itself asks for `none`, so a future change to
the theme file cannot quietly turn it back on.

#### A long body scrolls, and keeps its type size

The real cause of that regression was older than the spacing: `Text.print_text()`
drew **every** line it computed, and nothing stopped it at the bottom of its box.
Only `plate_rect()` clamped anything, and it clamps the *block*, not the glyphs.
So any dialog whose text was long enough ran through its own buttons — the
spacing only made it happen sooner.

A text widget can now be `scrollable`, and a theme asks for it with
`[dialog] scroll_body = block`:

- **the type size stops depending on the height.** `calc_text_size()` passes an
  effectively unbounded height to `pick_font()`, so the width is the only
  constraint and the body keeps the theme's size instead of shrinking;
- **the glyphs stop at the same line the block does.** `text_window_rect()` is
  the text box less `plate_reserve_pixels()` — the identical expression
  `plate_rect()` clamps with — and `print_text()` sets that as a clip;
- **the body is drawn whole and shifted**, not sliced: `scroll_lines` moves the
  origin up and the clip does the rest, which leaves `print_string()`'s per-string
  work (`---` rules, centring) untouched;
- **the wheel moves it**, both spellings — SDL2's `MOUSEWHEEL` and X11's
  buttons 4 and 5 — clamped to `[0, total - visible]`;
- **a 2px bar on the body's right edge** says there is more, because a clipped
  paragraph with nothing to say so is indistinguishable from a paragraph that
  ended.

Measured on a 17-line body in a 640×400 dialog at 1280×800: window
`(24, 164, 592, 180)`, **7 lines visible**, **10 to scroll**, lowest glyph row
**343** against a window bottom of **344**, nothing drawn below it, and the
indicator drawn only while there is overflow.

Two things had to be found the hard way. `scroll_body` is a theme key rather than
a behaviour, because a legacy dialog draws every line it computes and clipping it
would be a visible change to three themes nobody asked about. And pygame 2's
`MOUSEWHEEL` event **has no `pos`** — the first handler read `event.pos` and would
have raised `AttributeError` the first time a real wheel was turned, which the
tests missed because they invented an event with a position bolted on. The
pointer is asked for directly now, and a test delivers the shape SDL actually
sends.

#### The wheel reaches the dialog that is running

A long body could be scrolled, and nothing scrolled it. There were two faults,
both in `graphics/dialog.py`, and the tests missed both because they called the
handler directly instead of delivering an event:

- `TextDialog.build_scroll_handlers()` registered the wheel on `self.parent` --
  the map screen or the menu -- while a modal dialog's `show()` runs its **own**
  `handle()` loop. The handler lived on a dialog that was not running, so the
  wheel never reached the one that was.
- `Dialog.handle()` dropped every wheel button (4-7) before the CLICK handlers.
  That part was right -- a wheel is not a click, and letting it through selected
  the resolution row on the Options screen -- but it also threw away the X11
  spelling of the wheel, which is buttons 4 and 5.

The handlers now live on the dialog itself (a `Dialog` has its own registry, and
`show()` dispatches through it), and a wheel button is turned into the
`MOUSEWHEEL` event the handlers already understand -- with the fields SDL
really sends (`flipped`, `precise_y`) rather than a hand-made shape. The
horizontal axis (6/7) stays inert.

The larger half of the complaint is that the text players read is not the
dialog's own text: `MessageListDialog` puts its prose in a child `Text`, and
that widget was neither scrollable nor handled. `text.ScrollableText` is that
widget -- `scrollable` from `[dialog] scroll_body`, the wheel registered on the
owning dialog at priority 290 (after a listbox's 200, before a dialog body's
300), and the offset reset whenever the text changes, because a page that opens
in the middle of a sentence is worse than one that starts over. The message
body, the knowledge description and the research description use it; the log
entry is a `MessageDialog`, which scrolls as a dialog.

The knowledge screen had been building a fresh `Text` inside its pane for every
entry it showed and never removing the old one, so the pane's children grew for
as long as the screen was open -- one more wheel handler per entry once the
description learned to scroll. It owns one `ScrollableText` now and replaces its
text.

Verified: `522 passed, 1 xpassed`; `ALL HARNESS STEPS PASSED`; all sixteen
`utils/theme_snapshot.py` digests unchanged -- a wheel is not pixels.

#### One dialog type size, and one height for a button

Two complaints with one cause: the dialog type scale and the button geometry
were decided at each call site, so one dialog had 20pt prose beside a 28pt label
and four different button heights in one row.

`dialog_text` is a new name in the shipped `[sizes]` scale, defaulting to 20 --
the body size the game already used -- so nothing moves until a theme asks. 2030
asks for 18, which is the point: a dialog is *read* rather than scanned and its
frame does not grow with the text, so a point or two smaller is more prose in
the same box. `report_content` drops to 18 for the same reason (the reports are
a label/value grid, and a column that is one row short is a column that
scrolls). `TextDialog` now defaults to `text_size="dialog_text"`, and the five
places that hardcoded a size -- the message body, the knowledge description, the
log entry, the map's message box and the research pane, which had 18 -- read the
name instead. The size converts with the layout, so it is the same share of the
window at every resolution.

`[dialog] button_height` is the other half: 40 design pixels in 2030, `0` in
`Legacy-default` (and therefore in all three legacy themes), where it means
"every button keeps the height its call site asked for".

| button | before | after |
|---|---|---|
| dialog OK / CANCEL | .1 of the dialog | 40px |
| save/load row | .1 of a 900px screen | 40px |
| location row | .09 of the dialog | 40px |
| knowledge BACK | .06 of the screen | 40px |
| cheat menu row | .1 of the dialog | 40px |

A button's `role` decides. `standard` is the default and almost every dialog
button; `hud` keeps its own box, because the play screen's readouts are placed
on a grid whose cells are as tall as the strip; `primary` keeps the main menu's
61px; `chrome` is not a button at all -- a slider handle or a scrollbar arrow,
which must be exactly as tall as its track.

`Text.override_size()` is the hook, and it runs *before* the type is fitted to
the box: a snapped button measures and draws at one height instead of being
shortened after its font was already chosen for a taller one.

Two call sites keep an explicit size on purpose: the message list's PREV/NEXT
are a title-row pair (28) and the simple menu's rows are 24. The first attempt
removed both plus the ABOUT button's 20, and `utils/theme_snapshot.py` moved on
all three legacy themes by 873 pixels each -- all of it the ABOUT button at the
bottom-left of the shared menu. Giving it `text_size="dialog_text"` (20, the old
value) put every legacy digest back to its baseline line.

Verified: `529 passed, 1 xpassed`; `ALL HARNESS STEPS PASSED`; the twelve legacy
digests are unchanged; 2030's main menu, Options and dialog move to
`8008f7f…`, `9b51a8d…` and `6448ae8…`.

#### A window, not a rectangle

The 2030 dialogs were rectangles with a border. A window in this theme is a
piece of hardware: two opposing corners are cut at 45 degrees -- the top-left
and the bottom-right -- the other two are square, and a header band across the
top carries the screen's name.

```ini
[dialog]
window_shape  = chamfer   ; rect | chamfer
chamfer       = 0.045     ; share of the shorter side, cut off two corners
header        = bar       ; none | bar
header_height = 0.06      ; share of the window's height
```

(The shape has been through one correction since it was written -- the first one
cut both top corners and eased the bottom two. §19, "One diagonal, not four
corners", says why it changed and what it measures now.)

Drawn in `Dialog.redraw()`, which is where a dialog already paints itself. The
panel is composed on its own `SRCALPHA` surface and blitted, because a widget's
surface is a subsurface of the screen and filling in place would paint the cut
corners back in with solid colour -- the same trap the body's translucent block
hit. `rect` calls the old `BorderedWidget` path unchanged, which is what all
three legacy themes pin.

Six new colours, all named in the 2030 palette so the chrome is retuned in one
place: `dialog_frame_fill`, `dialog_frame_edge`, `dialog_frame_glow`,
`dialog_header_fill`, `dialog_header_text`. The edge and the accent are the same
two colours the rest of the theme uses for its panels, so a window, a pane and a
button frame read as one machine.

The header takes space, and a band that covers the first row of a list is worse
than no band. So it is a *fraction* of the window, and everything top-anchored
moves down by the same fraction:

- `content_insets()` and `content_margins()` add it, which moves a text dialog's
  body, its title row and its picture banner without a call site changing;
- `Dialog.below_header(y)` and `less_header(h)` move a widget and shorten it in
  the window's own shares, so its bottom edge stays where it was;
- `screen_y_share()` converts a share of the *screen* (how this game places
  widgets above zero) into a share of the window, which is what the Base
  screen's header row needed to keep its bottom edge;
- the Knowledge screen had no slack at all, so it gets a real 2030 layout (see
  below).

Every screen that is a window now has a title: OPTIONS, REPORTS, KNOWLEDGE, LOG,
STATISTICS, RESEARCH, LOCATION, BASE, SAVED GAMES, MESSAGE, CONFIRM, INPUT -- new
msgids, so they arrive untranslated rather than borrowed from a hotkey label. A
message list keeps an empty band on purpose: its own title row already says
which page this is.

Measured on the snapshot's `dialog` step at 1280x800: window 640x400 at
(320,200), header 24px, corner (0,0) is `ui_void` rather than the panel, the
band is `ui_panel_light`, and the title draws in it in `dialog_frame_glow`. (The
bright accent that used to run along the band's lower edge is gone; §19, "The
lines the frame drew over itself".)

#### The frame, corrected

Four defects in the chrome the section above describes, each with a cause rather
than a tweak.

**The right and bottom edges were not drawn.** The frame was one polygon
*stroked* with `pygame.draw.polygon(..., width)`, and the path it was stroked
along reaches one pixel past the surface on the right and the bottom -- the
points have to, or the *fill* would stop a pixel short of the edge. A stroke
along that path lands outside the surface there, so those two strokes were
discarded and the window had a left and a top edge only.

It is two filled polygons now: the whole outline in `dialog_frame_edge`, then
the same shape inset by `border_width` in `dialog_frame_fill`. What survives of
the first fill *is* the border, and it is the same width on all four sides by
construction. A second off-by-one had to go with it: the polygon's vertices
must be the last *pixel* of the box (width - 1), not the edge past it, or the
interior covers one row of its own rim. Measured on a 640x400 dialog with a 2px
frame: all four sides return `ui_edge` for both of their pixels, where the right
and bottom previously returned the panel colour.

**The in-game menu was a window the size of the display.** `SimpleMenuDialog`
is `(-1, -1)` at `(0, 0)` so that its child dialogs -- options, save/load, a
name prompt -- can be drawn into its surface without being clipped into a
corner. The chrome was drawn to that whole rectangle, so the menu read as a
window the size of the screen with a column of buttons lost in the middle of it,
and the Options dialog opened *over* that frame: a window in a window.

`Dialog.window_rect()` now says where the chrome goes, separately from where the
widget is, and the menu answers with its panel's own rectangle: the panel, a
`margin` around it, and a band above it -- the band solved for rather than
guessed, since it is a share of the window the window is being built from
(`b = f(P + 2·pad) / (1 - f)`). At 1280x800 the menu's frame is 333x349 where
its widget is 1280x800, and the panel inside it draws no border of its own: the
shaped frame is the frame.

**A window closes the way a window closes.** Four screens carried a BACK button
whose only job was to close them -- research, log, statistics, and knowledge,
which had no keyboard way out at all. `[dialog] close_button = corner` puts a
box in the right-hand end of the band instead, and those four screens list the
button it replaces in `close_only_buttons`. `corner` in 2030, `none` pinned in
`Legacy-default`, so a legacy window keeps every button it shipped.

The box is a `FunctionButton` with `icon_cancel` and no label, sized and placed
in shares of the dialog so a resize moves it with the corner. Two things had to
change for it: a selectable text sets its own background on every redraw, so the
band colour is given as `unselected_color` rather than `background_color`; and
`icon_glyph()` refused to draw in a square, because its "leave the label room"
width guard is impossible to satisfy at 60% of a square's own height -- it now
applies only to a button that has a label.

`close_window()` produces the *same exit value* the screen's own cancel path
did -- `on_escape` if it has one, else its cancel/back/no/ok button, else
`ExitDialog(False)` -- because a caller that branches on that value must not be
able to tell whether the player used the mouse or the keyboard. The hidden
button stays parented and enabled, which is what keeps the Escape handler that
points at it working; `KnowledgeScreen` gained one, since it had none.

**Nothing reaches the bottom row.** Research's description pane ended where its
BACK button began. `ChoiceDescriptionDialog` now sizes its pane and its list
from `content_bottom_reserve()`: `.15` -- exactly the `.85` they had before, so
a legacy theme is unmoved -- `.14` under the 2030 layout, which reserves the row
for real, and `.03` when a close box has replaced that row and only the frame's
margin is left. At 1024x768 the pane ends at y=415 and the row would start at
y=438; with the close box the pane ends at 471.

Verified: `551 passed, 1 xpassed`; `ALL HARNESS STEPS PASSED`; the twelve legacy
digests are byte-identical to the baseline; 2030's Options and dialog move to
`7f7797c…` and `fff90ff…`, while its main menu and map are unchanged.

#### The screens inside their windows

Two screens had coordinates tuned for a panel that no longer exists, and the
settings screen was the one the complaint named directly.

- **Knowledge.** It mixed shares of the screen (the lists) with shares of the
  window (the description), which is why the pane ran under BACK. Under
  `[dialog] window_layout = 2030` the two lists own the left column from under
  the header down, BACK sits at the bottom of that column, and the description
  takes everything to its right. Its text is a `ScrollableText`, so a long entry
  scrolls instead of shrinking to four-point type.
- **Options.** The tabs were at 1% of the screen, which is inside the header
  band, and the panes stopped a quarter of the way above the buttons. Under
  `window_layout = 2030` the four tabs are one segmented strip under the header,
  the active pane fills the window down to the OK/CANCEL row, and each pane
  lays its own controls out in shares of itself: two columns of list in General,
  the resolution list beside the three toggles in Video, three label/control
  rows in Audio, one warning per row in Interface.
- **Reports.** The two columns started 8% down the *screen*, which is under the
  Midnight/24-hours toggles once the header band takes its share; under the 2030
  layout they start below the toggle row and keep the same bottom edge.
- **Every list's scrollbar** takes `[dialog] scrollbar = classic|thin`. `thin`
  is an eight-pixel flush track with no arrow buttons and no border, drawn by
  the same `Slider` that already handled dragging -- the arrows are hidden, not
  removed, and the thumb is the theme's bright cyan. A list with a scrollbar
  gets 24 more pixels of row width at 1280, and a list that fits is not framed
  by a track going nowhere.

`window_layout = classic` is the whole old path: every coordinate, every tab,
every pane, unchanged. It is pinned in `Legacy-default`, so the three legacy
themes enter these methods and come out with the layout the screen shipped with.

#### The readouts go dark with the console

`[hud] modal_dim`: `normal` keeps cash, CPU, bases, suspicion and detection
above the fade mask, which is the game's own behaviour and what the legacy
themes pin. `dim` lets them be dimmed with everything else, because a 2030
window is a console with the rest of the panel out of play and a readout at full
brightness in it looks live when it is not.

The unmasking is now applied from `apply_hud_layout()` (so a theme switch moves
it) instead of once in `__init__`.

Verified: `539 passed, 1 xpassed`; `ALL HARNESS STEPS PASSED`; the twelve legacy
digests are byte-identical to the baseline; 2030's four move to `8008f7f…`
(main menu, the ABOUT label), `ea4f83e…` (Options), `ed4e31b…` (map, unchanged:
no window is open in that frame) and `2d1d3f6…` (dialog).

One caveat about that tool: it seeds a single RNG for the whole run, and
`g.new_game()` draws a random first base per theme, so rendering a different
*set* of themes gives different map digests. Compare like with like -- the four
theme ids in the order given above.

#### The paragraph is as wide as the picture

A banner is inset by `margin` and its text by `padding`, and those are different
numbers -- 0.02 and 0.04 in this theme. A dialog with a picture therefore had a
paragraph that stopped short of both of its picture's edges, which is not what
the reference dialogs do: there the text and the banner share both edges.

`text_width = pane` makes the text take the picture's insets. Measured at
1280x800 on a 640x400 dialog: the banner spans x 12..626, and the block behind
the text used to span x 25..615 and now spans x 12..628. A column down the side
still owns its width, so `pane` starts the text where the column ends rather
than underneath it.

The 2px difference on the right is the banner's own width being truncated as a
fraction of the dialog (0.96 x 640 is 614.4), not the text. The block is measured
from the text rather than from the frame, which is why it moved with the text.

#### The clock cannot move as it counts

`DAY %04d, %02d:%02d:%02d` is drawn centred in a fixed box on the HUD. Under
the theme's previous face, Exo 2, the figures were proportional -- `1` measured
13px, `8` and `4` 19px -- so the string's own width swung by **60px** across a
day (`DAY 1111` measured 223px, `DAY 8888` 283px), and a centred label slides by
half of any change: the clock jumped sideways every time a digit rolled over.
The cash, CPU and base readouts did the same, less visibly.

The theme now names a monospaced display face, whose digits are one width by
construction, which removes the cause for that theme. This is the fix for every
other face a theme might name, and it is also what keeps the guarantee
independent of the font choice:

A theme can now ask for `tabular_digits = all`, and a text widget can mark
itself as a running number with `tabular = True`. Every digit is then centred in
a cell the width of the widest digit of the face, so the string's advance is
constant whatever the digits are: the four test times now render to
**x 53..332, identical**, from the pixels rather than from `font.size()`.

It is opt-in per widget, not global, and deliberately so. Applying it to every
number in the game is a bigger change than the complaint: it moved the main menu,
the options screen and the dialog, which have static numbers that have nothing to
line up with. The four readouts that count are marked in `screens/map.py`, and
the only snapshot line that moves is 2030's `map`, which is the screen those
four are on.

#### The log

The log was the worst-reading screen in the game: a column of lines in one
colour, flush to their row's edge, with nothing to separate one from the next,
and a completely blank panel when nothing had happened yet -- which reads as a
screen that failed to load.

Three things, all theme-gated:

- **`list_stripes = zebra`** alternates a row's background between
  `text_background_unselected` and `list_row_alternate`, one step off the panel
  so rows separate without a border between them;
- the row text takes `content_padding`, the same inset the description panes use;
- **`empty_state = label`** puts `Empty` in the middle of an empty log.

The styling lives in a `LogListbox` subclass rather than in `LogScreen.rebuild()`,
and that is not tidiness: a resize recreates every row, so styling them once from
`rebuild()` was discarded the moment the listbox built its own elements. The
symptom was a log that looked right on the first frame and lost its stripes after
a window resize.

`Empty` is a **reused msgid**, not a new one: adding a string would have shipped
it untranslated in every language until a translator noticed, and it is already
in `messages.pot`. A test asserts it is there, so the day somebody removes it the
gate says so instead of the log quietly going blank again in 6 languages.

`Legacy-default` pins `list_stripes = none` and `empty_state = none`, so a legacy
log is one flat colour with no inset and stays blank when empty -- measured:
2030 alternates `text_background_unselected` / `list_row_alternate` with 0.025
padding, legacy keeps one colour and zero padding.

#### Text inside a pane keeps off its border

Every description panel in the game -- the research and tasks detail, the
knowledge detail, both report columns, both statistics columns -- built its text
with `(0, 0), (-1, -1)`, which is "fill the pane". The first glyph therefore sat
against the border, on all four sides, in every one of them.

A theme now has `content_padding`, and `Text.pad_from_theme()` applies it.
Measured on the research screen at 1280x800, a 499x440 description pane:
2030 insets by **12px**, a legacy theme by **0** -- the old layout exactly.
`vertical=False` is for a text that already carries its own top offset, which is
how the report bodies (below their title row) and the statistics rows keep their
existing line positions and take only the side inset.

#### A line of dashes is a rule

The research panel has been composing `"%s\n" + … + "\n---\n%s"` since long
before there was a theme to draw it with, so the player saw three hyphens
separating a heading from its body.

A wrapped line containing nothing but `---` now draws a horizontal rule across
the text width, in `dialog_rule`, vertically centred in the line the hyphens
would have occupied -- so swapping one for the other does not reflow the
paragraph. It is gated on `rule = line`; `Legacy-default` pins `rule = none` and
still draws the hyphens.

One thing that had to be found the hard way: `split_wrap()` appends a `\ufeff`
marker to **every** line it returns, so `line.strip() == "---"` is never true and
the first version of this drew nothing at all. The comparison goes through
`is_rule_line()`, which removes the marker first, and a test pins that piece of
the wrapper's behaviour because it is invisible until it bites.

#### How dark the forgotten background goes

Opening a modal dialog fades everything behind it by blitting one mask over the
parent. That mask was filled `(0, 0, 0, 175)` in `widget.py`, hardcoded. Against
the old blue theme 175 reads as "dimmed"; against this theme's near-black HUD it
barely reads at all, which is why the screens behind a dialog still looked live.

The colour is now a theme name, `fade_mask_color`, with upstream's value as the
fallback so a third-party theme that never defines it dims exactly as before.
2030 asks for `#000000C4`, and measured on a real pane the background goes
`(10, 22, 34)` → `(2, 5, 7)`; a legacy theme still goes to `(0, 0, 40)` on its
blue, unchanged.

What deliberately did **not** change: the three HUD widgets that sit above the
mask — the suspicion bar, the danger bar, and the window holding cash, CPU and
bases (`widget.unmask_all` in `screens/map.py`). Those are readable behind a
dialog on purpose: a player deciding whether to continue wants to see the
numbers they are deciding about. Darkening the mask is the reason that opt-out
needed pinning, so `test_the_hud_counters_stay_above_the_mask` asserts it.

#### One frame, not two weights

The picture's frame took its width from the theme's `border_width` (2px) while
the block behind the text hardcoded `1` in `Text.draw_plate()`. Two parts of the
same frame were drawn at different weights, which is exactly the sort of thing
that reads as "slightly wrong" without being nameable.

Both now read one key, and put the width in their cache keys so a theme switch
cannot reuse an old-pixel block on a new theme.

That key is **`content_border_width`**, with `border_width` as its fallback, and
the distinction is the point: the two edges are *inside* the panel, so a theme
can draw its shell at one weight and its contents at another. 2030 asks for a
**2px shell and 1px contents**, which is what makes the frame read as a frame
and the picture and the paragraph read as its contents. A theme that names no
`content_border_width` gets `border_width` for both and sees no change at all.

The colours came together in the same pass. The picture's frame was
`ui_edge_bright` — `#5FE3FF`, the brightest thing in the palette — against the
block's `dialog_plate_border`, a 60% slate. Two parts of one frame in two
different weights *and* two different colours. `dialog_art_border` is now an
**alias of `dialog_plate_border`**, so "the same colour" is stated once in the
file and cannot drift; `resolve_color_alias()` already recurses on strings, and a
test pins that so a future change to alias resolution cannot silently leave the
picture's frame black.

Measured off the drawn surfaces: 2030's picture frame and text block are both
**1px** and both `(44, 106, 130)`; a theme pinned to `border_width = 1` draws
**1px**; and the legacy themes draw no block at all and never build a pane. The
width is clamped to half the block, because a plate narrower than twice its
border has no interior left and would fill with its own edge.

#### A picture that is a feed

A still frame in a banner reads as a screenshot. The picture now carries a
*glitch*: for about 450 ms a fine raster appears over it (every second row, at
5% alpha, which reads as dithering rather than as stripes) and one soft band
crosses it upward; then the picture is perfectly still again for a pause drawn
uniformly from **9 to 15 seconds**.

The first version drew the raster and the band continuously, which was a
mistake worth recording: a permanent crawl over a picture competes with the text
beneath it and reads as a broken renderer rather than as a live feed.

The second version overcorrected. It cut the crossing to **450 ms**, which was
rare enough but crossed the frame so fast that it read as a flicker rather than
a scan. The crossing is now **2600 ms** -- the period the original continuous
version used, so the band moves at the pace that looked right -- and it is the
*pause* that comes from 9-15 s. Measured over five minutes of ticks: **20
glitches**, start-to-start gaps of 12.1 s to 17.4 s, so the picture is moving
**22%** of the time instead of all of it.

The raster and the band are on **different clocks**, and that is the second
correction. The first version gated both behind `glitch_progress()`, so the
picture lost its texture the instant the band finished -- which the eye reads as
the *picture* changing rather than as the band leaving, and it is very obvious.
The raster is static and 5% alpha: it belongs on all the time, and it costs no
redraws to keep it there. Only the band comes and goes.

The direction is the button's: **top to bottom**, through the same expression
`draw_hover_effect` uses. The band starts entirely above the box at phase 0 and
is entirely below it at phase 1, so it enters and leaves the frame rather than
appearing in the middle. Having the picture's sweep run upward while every
hovered button's ran down was the one part of this that read as two unrelated
effects rather than one machine.

It is deliberately not the hovered button's effect, which is dark, fast (1400 ms)
and continuous while the pointer rests on the control, because that one is an
affordance. They share no colour name either: `image_scanline` and
`image_scanline_sweep` against `button_scanline` and `button_scanline_sweep`, so
retuning one cannot silently restyle the other.

The clock is ticks, never the wall clock, and the schedule is seeded from the
art key through a SHA-256 digest rather than `hash()` — which is salted per
process for strings, and would have made the same picture glitch at different
moments in two runs of the same build. A pane rebuilt for the same key therefore
glitches at the same moments, a still render draws no overlay at all, and the
theme snapshot stays reproducible. The tick handler asks for a redraw only while
a glitch is actually running.

Both are theme keys and both default to the old behaviour, which is what keeps
the legacy themes out of it: `Legacy-default` pins `text_width = padding`,
`image_overlay = none` and both scanline colours, so a legacy dialog has no pane,
no overlay and its original insets.

#### What is not a scene

A picture slot is a promise that there is something to look at. Five dialogs
here have nothing, and each of them says so in one line of code:

| dialog | why it takes no picture |
|---|---|
| the **log** (`LogScreen`) | rows of things that already happened; the placeholder was saying the log was missing its illustration |
| the **statistics** (`StatScreen`) | a table of numbers behind the report |
| the **log filter** (`FilterLogDialog`) | switches, not a scene |
| the **save/load list** (`SavegameScreen`) | files on disk |
| the **Options screen** (`OptionsScreen`) | settings |

The first two are the ones this pass corrected, and the second pair are the
same argument. **The Options screen was a bug**, not a decision: it inherits
`YesNoDialog`, and with it that dialog's `dialog_confirm` art key, so the
theme's banner appeared down the side of the settings panel — a frame with
nothing in it, taking the width the resolution list needed. It now declares
`art_key = None`, and keeps the theme's border and insets, which it should
have.

The log and the statistics screen are subtler, because they are not chrome:
they are game screens a player opens deliberately. But a log entry is a
sentence, not a scene, and there is no picture of *"my base in Antarctica was
detected"* that is worth a third of the panel. So they keep the base class's
`art_key = None` and their original geometry (`(0, -.09) (-1, -.77)` and
`(0, 0) (-1, -.85)`), and the popup a log row opens is created with
`art_key=None` too — the row's text is the message, not an illustration of it.

`SimpleMenuDialog` — the in-game menu — is not a `TextDialog` at all and is
untouched.

#### The block a dialog's text sits on

Body text used to sit straight on the panel: one flat colour behind the
glyphs, edge to edge inside the frame. The reference dialogs put the paragraph
on a block of its own, slightly darker than the panel it lies on and edged in
the frame colour, so the eye separates "what is being said" from "the panel
that holds it".

A theme now has `text_plate`, and `block` gives every `TextDialog` and the mode
event popup's body one:

```ini
[dialog]
text_plate = block

[colors]
dialog_plate_background = #04080FB4   ; 70% opaque, so the panel shows through
dialog_plate_border     = #2C6A8299
```

The alpha is the point rather than a detail: a plate at 255 would be a second
panel, and the depth cue is exactly that the panel is visible through it. That
is why the block is **composed on its own `SRCALPHA` surface and blitted**
rather than filled in place — a widget's surface is a subsurface of the screen
surface and has no alpha channel, so `fill()` with a translucent colour paints
a solid block. `BorderedWidget.redraw()` has carried a TODO about that for
years; this is the first element that needed the answer.

**The block is the body's pane.** It runs the width of the text column, from the
top of the content box — under the picture — down to the row the dialog's
buttons sit in. Two guards keep it honest:

- a text widget with a plate gets `plate_pad` (12 px) added to its own insets,
  so the glyphs sit inside the block instead of touching its border;
- `plate_reserve_bottom` is the fraction of the frame a *caller* has promised
  to something else — the button row — and the block stops short of it. A
  `TextDialog`'s content box is otherwise the whole frame, and a block that
  reached it would be drawn *behind its own CONTINUE and SKIP buttons*.

This was measured to the text for a while, and that is what §19 corrects: a
one-line message got a one-line block with the rest of the pane left bare, so
the shortest dialogs read as a caption floating in a window. The clamp at the
button row, the pixel test that not one pixel of the buttons' band is the block's
blended colour, and both lengths of sample body are still in the tests.

Verified by measurement rather than by eye:

| measurement | value |
|---|---|
| block luminance | 0.044 |
| panel luminance | 0.129 |
| ratio | 0.34 — a clear step, not a tint |
| body text on the block | contrast 10.28, against 4.5 for AA |
| `test_the_2030_body_text_sits_on_a_translucent_block` | every channel strictly between the block's colour and the panel's |

That last row is the translucency test: a solid fill would come out exactly at
the block's colour, so "strictly between" can only happen if the blend really
happened.

`Legacy-default` pins `text_plate = none` and both colours, for the usual
reason — it inherits 2030, and a legacy dialog must stay the flat panel it has
always been. In the snapshot every legacy line is byte-identical and only
2030's `dialog` moves. `354 passed, 1 xpassed`; `ALL HARNESS STEPS PASSED`.

#### A hovered button behaves like a terminal

Hovering a button used to swap one flat colour for another and nothing more. A
theme can now ask for a CRT overlay: fine scanlines across the face, plus one
soft band that travels down it, over the label — because that is what a
scanline does, sit between the eye and what is on the screen.

```ini
[dialog]
button_hover = scanline      ; none | scanline

[colors]
button_scanline       = #0000002B   ; a dark line every third row
button_scanline_sweep = #5FE3FF30   ; the travelling band
```

Both are low-alpha on purpose: a hover effect that competes with its own label
is decoration rather than an affordance, and the label stays the brightest
thing on the button.

Three decisions keep this from being a permanent performance and reproducibility
problem:

- **It animates on hover, not on `.selected`.** They are different questions in
  this codebase: a toggle button stays `selected` while it is the active tab.
  The first version animated on `selected`, and the Settings screen's chosen
  tab crawled for as long as it was open — and its snapshot digest changed
  between two runs, which is a bug in the tool as much as in the screen. Hover
  is tracked by its own `MOUSEMOTION` handler, `_hovered`, so an active tab is
  still.
- **The phase counts ticks, not wall-clock time.** `hover_sweep_phase()` is a
  function of how many times the button was redrawn. A frame drawn without a
  tick — which is every frame the tests and `theme_snapshot.py` draw — is
  therefore reproducible, and the band advances because the button *drew*
  again rather than jumping a third of the way down a face that had not been on
  screen yet.
- **The tick handler only exists when the theme asks for it.** Adding one makes
  `Dialog.start_timer()` run at 30 FPS instead of waiting on events, so a
  dialog full of buttons under 2030 now ticks. That is the price of the
  animation and it is paid only by a theme that opts in: the legacy themes
  register no handler at all, keep the event-driven loop exactly as before, and
  their hovered buttons are **byte-identical** to their unhovered ones — which
  is asserted, not assumed.

The hook is also re-synced in `Button.reconfig()`, because a theme switch
arrives as a reconfigure and the main menu's buttons outlive the Options screen
that changed the theme.

Verified: `349 passed, 1 xpassed`; `ALL HARNESS STEPS PASSED`, with the
real-dialog step asserting that hovering its OK button changes pixels and that
a later tick moves the band again. `theme_snapshot.py` is byte-identical to the
previous commit on all sixteen lines *and* reproducible run to run — no button
is hovered in a captured frame, and the phase cannot drift with the clock.

Deciding this in one place is what makes it robust: `ChoiceDialog` sets
`art_key = None` and a subclass that *is* a scene opts in. The list screens
therefore stay lists under any theme, including a third-party one that turns
image slots on.

`art_key=None` passed to a dialog that has a class-level key had to be made to
work: "no argument" and "no picture" cannot both be `None`, so `TextDialog`
tells them apart with a sentinel. Without it, a caller asking for no picture on
one dialog got the class default back — which is exactly how the log acquired
its placeholder.

Verified: `336 passed, 1 xpassed`; `ALL HARNESS STEPS PASSED`; every legacy
snapshot line byte-identical — in this commit only 2030's `dialog` moves, and
`options` does not, because the settings screen has no picture and its own text
is empty. Opened headless under both themes with the real screens, every dialog
logs no `can't fit` warning, and the legacy geometry is still the arithmetic the
code used to hardcode — for `MessageListDialog` at 640×400: title (6, 4)
627×40, body (6, 44) 627×332, PREV/NEXT right edges at 499 and 633, which is
`.01`, `.98`, `.1`, `.11`, `.83`, `.78` and `.99` of the dialog exactly.
`MessageListDialog` is the only screen that places its widgets against the
picture, and it asks the theme where to start, so a banner moves it down and a
column moves it sideways; the screens with no picture are unaffected by either.
The harness checks the log on the real map screen — `log: no picture, list at
(0, -0.09) (-1, -0.77)` — because the log growing a placeholder was reported
from a running game, not from a unit test.

### Glyphs beside a label

The game was text-only: every button said what it did and nothing said it
twice. A button now takes an `icon` — a name in `g.images` — and paints that
glyph at the left of its own frame, with the label centred in what is left.

```python
button.ExitDialogButton(self, pos, size, text=N_("&DESTROY BASE"),
                        icon="icon_delete", ...)
```

Three things decide whether a glyph is drawn, and all three have to agree:
the button names one, the theme sets `icon_buttons = all`, and the file exists.
Any of them missing draws the label alone, which is exactly the old code path —
so the legacy themes, and any third-party theme that does not opt in, are
byte-identical. The button asks `g.dialog_style()` for the theme's answer at
redraw time, not at construction, so a theme switch applies without rebuilding
the tree.

The gutter is part of the button's *measurement*, not just of the drawing
(`Text.content_extra_left()`): measured against the full width and then drawn
in a narrower box, a one-line label wraps onto a second line and is clipped.
The glyph is 60% of the button's height, so it reads at 24px and never becomes
the button.

**Where the glyph goes.** It used to be blitted at `x = 3`, the button's own
edge, while the gutter was reserved as an inset on the text -- so a centred label
started well inside the button and the glyph was left stranded in the corner with
dead space between it and its own word. The wider the button, the emptier that
space, which is what made it read as an ungrouped decoration rather than a label.

`Text.first_glyph_x()` now answers the arithmetic `print_text()` hands to
`print_string()` -- the inset, the four pixels of internal margin, and the
alignment shift within what is left -- and the glyph is placed at
`first_glyph_x() - GLYPH_GAP - glyph width`. The reserved gutter is what the
label was centred against, so the *pair* lands centred as a unit: measured on a
384px button, the pair's centre is within **1px** of the button's for labels from
`OK` to `LOAD A SAVED GAME`, and the gap is the reserved 4px at every length.
Legacy themes draw no glyph, so `content_extra_left()` is 0 and nothing moves.

**The artwork is vendored, not drawn.** The first set was fifteen glyphs
assembled from strokes and polygons in `utils/make_2030_art.py`. They were
consistent and readable, and they were fifteen small inventions standing in for
a solved problem. The theme now uses **Lucide** (`0.469.0`), whose SVG sources
are committed under `2030/icons/` with its `LICENSE` and a `README.txt` that
maps each game name to the drawing it came from; `utils/make_icon_set.py`
rasterises them at 256px and downsamples to the 64px a button asks for.

The set was chosen on licence as much as on looks, and that is the part worth
recording: this game is GPL-2+, so an icon pack has to be permissive or
compatible. **ISC** is both, and needs only that its notice is kept. Several
better-known packs are not usable here — Papirus is GPL-3, Breeze is LGPL-3 —
and no amount of attribution makes that difference go away.

The names on the left are what a button asks for, so this replaced the artwork
without touching a call site. Four were added in the same pass, for the map
screen's Research/Tasks, Reports, Knowledge and Log buttons, which were the
last word-only controls in the header.

| glyph | used on |
|---|---|
| `icon_ok` | OK, YES, CONTINUE |
| `icon_cancel` | NO, CANCEL, SKIP |
| `icon_back` | BACK, and the dialog that only has a Back button |
| `icon_prev`, `icon_next` | the event popup's PREV / NEXT |
| `icon_play`, `icon_pause` | reserved for the speed controls |
| `icon_save`, `icon_load` | SAVE GAME / LOAD GAME, and the save list |
| `icon_delete` | DESTROY BASE |
| `icon_stats` | STATISTICS |
| `icon_filter` | the log's Filters button |
| `icon_warning` | reserved for the warning dialogs |
| `icon_options` | OPTIONS |
| `icon_exit` | QUIT |
| `icon_research` | RESEARCH / TASKS |
| `icon_report` | REPORTS |
| `icon_knowledge` | KNOWLEDGE |
| `icon_log` | LOG |

The glyphs carry a real alpha channel rather than the magenta key the other
theme images use. That is not a preference: scaling a keyed image blends magenta
into every edge pixel, which on a cyan glyph is a purple fringe, while a
single-colour image with alpha scales to any size without one. `g.load_image()`
already honours both conventions (§16, "The image loader learns that alpha is
real"), and `as_the_game_loads()` in the generator was taught the same rule so
that the verification measures what the game will actually draw.

Moving to the vendored set moved 2030's `options`, `map` and `dialog`
digests and left `main_menu` alone, which is the change landing where the
buttons are; the four added map icons are why `map` is in that list now.

`tests/test_theme_icons.py` is what keeps the two halves honest: it scans the
code for every `icon="icon_..."` a screen asks for and asserts the theme ships
a file for it (a missing file draws no glyph, which is an error nowhere), checks
each file is 64×64 with real ink and not a solid block, asserts no two are the
same drawing, and asserts the licence and its notice are present. Verified:
`450 passed, 1 xpassed`; `ALL HARNESS STEPS PASSED`; all twelve legacy snapshot
lines byte-identical.

### What now checks the frame

Two harness steps render a real `MessageDialog` on the real map screen, one
under each kind of theme, and assert the numbers rather than the picture:

```
       centred at (239, 175), banner (457, 118) at (9, 6), text insets (19, 132, 19, 13)
PASS   dialog frame: 2030 centres the panel and reserves a picture banner
       legacy geometry at (239, 69), size (477, 349)
PASS   dialog frame: a legacy theme still draws the old one
```

The 2030 step checks the panel's own position against the centre of the screen,
that the banner is wider than it is tall, that it spans the panel, that the text
starts below it, and that padding exists on three sides;
the legacy step checks `TOP_CENTER` at `.1`, a one-pixel frame, no pane and a
zero inset. That is the invariant this whole series rests on, checked on the
path a player actually takes rather than on a widget built in a test.

`utils/theme_snapshot.py` grew a fourth screen — `dialog` — for the same
reason: before it, the tool could only vouch for the main menu, the Options
dialog and the HUD, and a dialog change had no baseline to move against. Every
digest quoted in this section was taken through it, and the twelve legacy lines
have not moved since: main menu, Options, map and dialog, for
`Legacy-default`, `Legacy-nightmode` and `Legacy-vector`.

## 17. One picture per situation

The dialogue pictures shipped as a static placeholder — a dead channel — for
every scenario dialog, because there was one art key for all of them and no
files. The next step was never "draw `dialog_message`": it was to give each
situation its own plate, so that a finished tech, a built item, a lost base and
a story page are four different pictures.

That is **138 plates**: 57 techs, 26 items, 13 base types, 8 events, 9 story
pages, 4 warnings, 4 discover groups, 4 item kinds, and 13 chrome and category
plates. `DESIGN.md` is the style contract; `utils/make_dialog_art.py` builds the
inventory from the data files, writes the prompts, renders, and grades.

The style is a shared contract rather than a per-picture choice, because 138
separate generations have to read as one collaboration: a fixed style sentence
and a fixed composition instruction on every prompt, one seed (2030), one
measured resolution (1920×1080, cropped to the banner's 1920×480 with no
resampling), and one deterministic grade that maps every plate through the
theme's own palette, caps its luminance below the body text, and adds the
scanline rhythm the panel already uses.

Generation was measured, not guessed. On an AMD ROCm machine (two cards,
Krea-2-Turbo Q8): 1024×1024 at 8 steps takes 30 s, 2560×1440 at 32 steps takes
478 s, and 1920×1080 at 24 steps takes 163 s. 2560×1440 was rejected — twice
the time for pixels the crop throws away. Two cards render two plates at once
at no per-step cost, and the same prompt and seed on either card produced a
byte-identical file, so a plate does not depend on which card drew it.

`utils/make_dialog_art.py --check` is what keeps the set honest without a human
looking at 138 pictures: every plate must be 1920×480, peak below the theme's
own body-text luminance (read from `theme.dat`, not hardcoded), have a mean
between 0.06 and 0.45, not be nearly flat, and share no content with any other
plate. `--contact-sheet` is the human half.

The duplicate test needed two attempts, and the first one is worth recording
because it failed silently in the check's favour. The obvious tool is a dHash: a
64-bit fingerprint of a downscaled thumbnail. Every plate came out `ffffff…` and
the check declared eleven unrelated scenes — a corridor and a data centre among
them — the same picture. The cause is that all plates share an envelope: the
dark frame and the grade's horizontal vignette dominate a 9×8 thumbnail, so the
hash was describing the grade, not the picture.

The check now compares the *residual*: each plate reduced to a 64×16 luminance
thumbnail with its own blurred version subtracted, which cancels the shared
envelope and leaves the content. Measured on the first 30 plates, unrelated
plates correlate at most **0.62**, the median pair is **0.07**, and a plate
against itself is **1.000**, so the threshold is 0.95. `--check` also prints the
closest pair, which is the number to watch as the set grows.

That check is also how a stale number in this file was found. §16 recorded body
text as luminance 0.830; measured off the live theme it is **0.911**
(`#D7ECF6`). The ceiling is set from the measurement, so the mistake did not
change a pixel -- but the number in the prose was wrong, and it is corrected
here rather than quietly.

The art itself is committed as `singularity/data/themes/2030/images/<key>.jpg`;
the ungraded masters stay outside the repository in `~/Слике/krea/masters/`.
Nothing here reaches a legacy theme: they pin `image_slot = none`, so no pane is
ever built and no plate is ever looked up.

All **139 plates** are committed, and the inventory is worth writing out because
it is what "one picture per situation" means in practice: 57 techs, 26 items, 4
item kinds, 16 base plates (13 types plus constructed/lost/discovered), 4
discover groups, 8 events, 9 story pages, 4 warnings, and 11 chrome and generic
frames including the placeholder. Together they are **18 MB**, because a graded
1920×480 JPEG of a dark scene compresses to roughly 130 KB -- worth stating here
rather than finding in a tarball.

#### The grade is a tint, not a filter

The first grade took each plate's luminance, looked the palette ramp up by that
luminance, and kept 28% of the original colour. A ramp indexed by luminance
carries **no hue at all**, so 72% of every picture was replaced by the theme's
teal. The set was beautifully consistent and had lost its subjects, which is the
wrong way round:

| plate | hue | master | first grade | now |
|---|---|---|---|---|
| `dialog_warning` | red + red2 | 72,575 px | 54 px | 39,341 px |
| `dialog_warning` | magenta | 25,917 px | 0 px | 40,204 px |
| `dialog_item_gaming_pc` | purple | 2,464 px | 0 px | 2,211 px |
| `dialog_base_lunar_facility` | blue | 173,034 px | 0 px | 366,363 px |

A red warning with no red, a lunar base whose Earth was no longer blue, fusion
plasma without its pink, a gaming case without its purple. And the grade's own
`warmth` block made it worse, not better: it *repainted* warm pixels amber, so a
red light and a sodium light became the same amber light.

**What it does now.** The tone curve is applied to luminance and each pixel is
scaled by the ratio to its new luminance, which is a pure brightness change and
cannot alter hue or saturation. Then:

- the palette is mixed in at **12%** -- blended toward the ramp's colour *for
  that luminance*, so it moves the cast and hardly the brightness;
- saturation is restored **×1.20** around each pixel's own luminance, because a
  tint costs chroma and these are not meant to look washed out;
- genuinely warm pixels are **brightened** by up to 22% instead of repainted;
- the vignette drops from 22% to **14%**, because on a 4:1 strip the ends are
  where the subject usually is.

The tint was chosen by measuring how much of each master's warm colour survives,
since warm is what the complaints were about: 18% kept 57% of it, **12% keeps
67%**, 6% keeps 78% but costs too much of the shared cast. Measured across all
144 plates, mean chroma lands at **0.083** and the worst plate-to-master chroma
ratio is **0.85** -- the grade preserves colour rather than merely keeping
some -- so **no plate loses more than a third of its own**.

**The ceiling still holds, and now it holds in the file.** A plate clamped to
0.78 in memory came back at **0.834** from the JPEG writer, whose chroma
subsampling rings a hard edge. The clamp aims at `0.78 - 0.06` for that reason;
measured peak across the set is **0.769** against body text at 0.911.

**And `--import` now always re-grades.** It used to skip a file whose master
existed, so rewriting `grade()` re-imported *one* plate and the next snapshot
reported no change while 138 files still held the old pixels. That is a
resurrection of a bug this project has already been bitten by once (a stale
`g.images` entry), and the fix is the same principle: if the output is a function
of the input, compute it.

**A method note.** Every number above came from reading the shipped files back,
not from the generator's constants -- hue histograms and per-pixel chroma over
each master and each plate. The first version of that measurement was itself
wrong (it decoded `.po` files by hand and turned Cyrillic into control codes),
which is why the tooling now uses `polib` and the art checks read the artefacts.

The harness has a step for it, because a plate that never reaches the screen is
the one failure `--check` cannot see: it draws the same dialog twice, once with
the theme's plate visible and once with that plate hidden, and requires the two
frames to differ. That is what ties "the file is there" to "the pane painted
it":

```
       dialog_message (1920, 480) in a (614, 136) pane
PASS   dialog art: a scenario dialog paints its own plate, not the static
```

## 18. Every situation draws its own picture

The complaint was that four situations had no picture: an infectious disease, a
popular novel that resembles the AI, a government scandal, and "this technology
is too dangerous to research". Three of the four *had* a plate --
`dialog_event_the_plague`, `dialog_event_scandal`,
`dialog_event_stranger_than_fiction` were rendered, graded and committed -- and
the dialog never asked for it. The fourth, the danger help, had no plate
anywhere in the set.

So this was not an art problem. It was four call sites that bypassed the chain
the rest of the game already used.

| where | what it did | what it does |
|---|---|---|
| `player.trigger_event` | `show_message(description)` | names `dialog_event_<id>`, falls back to `dialog_message_list` |
| `player.remove_bases` | `show_message(full_message, color="red")` | passes the log message's own `art_key` / `art_fallbacks` |
| `screens/log.py` double-click | `MessageDialog(..., art_key=None)` | passes the entry's key, so the pane stays off only for a message that has none |
| `screens/research.py` `show_help` | nothing | `dialog_danger_<n>`, falling back to `dialog_danger` and `dialog_message` |

`MapScreen.show_message` grew `art_key` and `fallbacks` parameters and sets them
on **every** call, not only when one is given: it is one reused dialog, so the
generic frame has to come back with the next generic message. There is a test
for exactly that.

### The danger family

Five new plates: a generic sealed hazard door, plus one for each level in
`dangers_str.dat` -- undersea, orbit, deep space, and outside the universe. They
are places rather than events, because the dialog is telling the player *where*
the work would have to happen.

`danger_0` has no plate and must never get one: its research text is `<<This
text should not appear>>`, and the game only reveals the help button for a
danger above zero. The family is read from `dangers_str.dat` rather than listed
in the generator, so a new level is a `MISSING BRIEF` instead of silence.

The briefs were written to stay clear of the plates they could collide with:
`dialog_danger_1` is a capsule on a *lightless* plain (no light shafts, unlike
`dialog_base_undersea_lab`), `dialog_danger_2` has Earth *below* it (the lunar
facility has Earth above the horizon), and `dialog_danger_4` is a corridor
opening onto empty darkness rather than `dialog_base_reality_bubble`'s sphere.

### A bug in the inventory, found by adding a family

`inventory()` built its key list by `zip`ping a hand-written tuple of tier names
against `TIERS`. The names were never used. With an eighth tier the `zip` would
have truncated to the shorter one and silently dropped the last family from the
inventory -- so the new plates would have had no master rendered and `--check`
would have called them missing. The names are gone and the loop walks `TIERS`.

### Evidence

```
144 plates, body text luminance 0.911
closest pair 0.775: dialog_story_win_1 / dialog_tech_apotheosis
every plate is 1920x480, below the text, and no two are the same picture
```

The five new plates measure:

```
dialog_danger    1920x480   peak 0.728  mean 0.169  stdev 0.095
dialog_danger_1  1920x480   peak 0.729  mean 0.125  stdev 0.071
dialog_danger_2  1920x480   peak 0.719  mean 0.251  stdev 0.163
dialog_danger_3  1920x480   peak 0.725  mean 0.151  stdev 0.076
dialog_danger_4  1920x480   peak 0.734  mean 0.193  stdev 0.094
```

Gate: **556 passed, 1 xpassed**, `ALL HARNESS STEPS PASSED`. `theme_snapshot.py`
before and after this commit differs on one line only, and it is the line naming
the output directory: all sixteen theme digests are byte-identical, all four
themes -- 2030 included, because the snapshot's dialog uses the class default key
and the new wiring is per call site. That is a stronger statement than "no legacy
file changed": no legacy *pixel* changed.

Five tests pin the wiring, because art that exists and is never shown is
invisible to every other check: a firing event names its own key, a plain message
restores the generic one, a log entry popup shows the entry's picture, each
danger level names its own place, and `danger_0` has no plate.

## 19. Polishing the window

The 2030 window (§16) was built to a fixed set of reference dialogs and then
applied to screens written years earlier, each with its own hardcoded
coordinates. What follows is the pass that took the player's own list of what
still sat wrong, one item per commit, with every change behind a 2030-only
condition: `window_shape = chamfer`, `draws_window()` or
`window_layout = 2030`. The three legacy themes pin all of them, so their pixels
are unaffected -- `theme_snapshot.py` is the check, twelve digests byte-identical
before and after every commit in this section.

### The lines the frame drew over itself

The header band carried a rule along its lower edge, in the frame's own edge
colour and at half the frame's weight, with a bright accent two pixels deep over
the first third of it. Below that, two short ticks sat just inside the bottom
edge. All three read as lines drawn *over* the window: the rule looked like an
edge that had slipped a few pixels down from the frame's own, the accent like a
second and brighter one, and the ticks like a mark left on the glass. Only the
band, its title and the two filled polygons that make the frame remain. The band
still reads as a raised rail because `dialog_header_fill` (`#12283A`) is a step
lighter than `dialog_frame_fill` (`#0A1622`) -- which is what it was for.

`line_y` survives in `draw_window()` as the title's baseline and nothing else, so
the title sits where it always did.

Gate: **556 passed, 1 xpassed**, `ALL HARNESS STEPS PASSED`. `theme_snapshot.py`
differs on two lines, both 2030: Options `7f7797c…` → `9628c57…` and the dialog
`fff90ff…` → `96aa3b1…`. The twelve legacy digests are byte-identical, and 2030's
main menu and map are unchanged.

### A close box that clears the cut corner

The box was placed at the band's margin, measured from the frame's right edge --
which is a vertical on a rectangle and a 45-degree diagonal on this panel. At
1024x768 the Options window is 819x652 with a 29px chamfer, its band is 39px, and
the box is 30px in a band that puts its top at y=4: the frame's edge is then at
x=793, while the box ran to 803. Ten of its thirty pixels sat outside the window,
over the notch.

The cut is a straight line, so the narrowest row of a box is its own top row, and
`place_close_button()` now keeps the box's right edge inside the edge the
diagonal leaves there -- `max(0, chamfer - top)` short of the frame's border.
The same window's box moves to x 762..792, which is clear of the diagonal and
still at the band's own margin. A theme with `chamfer = 0` computes a cut of
zero and is placed exactly as before.

One test pins it, and pins it geometrically: it fills `window_polygon()` -- the
very path `draw_window()` paints -- into a mask and looks up all four corners of
the box in it, so the assertion cannot drift from the chrome.

Gate: **557 passed, 1 xpassed**, `ALL HARNESS STEPS PASSED`. `theme_snapshot.py`:
Options `9628c57…` → `4b6603a…` and the dialog `96aa3b1…` → `82ac326…`; the
twelve legacy digests are byte-identical.

### A dialog opens over its window, not over the desktop

A `MessageDialog` placed itself at `.5, .5` of the *screen*, centred, whenever
the theme centred its dialogs. That is right for a dialog opened from the map or
the menu, which fill the screen, and wrong for one opened from a window: the
research screen's "too dangerous" help is a 512x384 box centred on the desktop,
opened over a research window of 952x483 sitting at (36, 76). The box landed at
(256, 192), seventeen pixels past the bottom of the frame -- and a widget that
hangs over its parent has its surface clipped to that parent, so the surface was
291px tall and the OK button, at y=336 of 384, was not drawn at all. The message
read as a dialog cut in half with no way out of it.

`TextDialog` now centres a dialog *in the window it opens over*: `(-.5, -.5)`,
which is a share of the parent rather than of the screen, whenever the parent is
itself a `Dialog`. The same box lands at (220, 49) instead, whole, with its OK
row at 336..376 of 384. Nothing grows or shrinks: only the point the box is
centred on changes, so every dialog's size is exactly what it was.

A theme that anchors at `top_center` -- all three legacy themes -- never asks the
question, and a caller that names its own `pos` keeps it: this is only the
default placement.

One test pins it at nine resolutions, over two parents (a full-screen menu and a
research window): the message's rect must be inside its parent, and its OK row
inside its own surface. Without the change it fails at all nine.

Gate: **566 passed, 1 xpassed**, `ALL HARNESS STEPS PASSED`. `theme_snapshot.py`
is unchanged by this commit -- the snapshot's dialog is opened from the
full-screen menu, where both readings of "centre" are the same point -- so the
two 2030 lines still read `4b6603a…` and `82ac326…` and the twelve legacy
digests are byte-identical.

### The block reaches from the picture to the buttons

§16's block was drawn to the paragraph: measured from what `print_string()`
would wrap and place, so a one-line message got a one-line block and the rest of
the pane stayed bare. On the true/false confirmation and on the danger help --
the two shortest dialogs a player meets most often -- that is a strip of colour
under the banner with nothing beneath it, and it reads as a caption floating in
a window rather than as the body of one.

`plate_rect()` now takes the plate's own content box and clamps it at the row the
caller reserved, which is the pane the text lives in: from just under the picture
to just above the buttons, whatever the prose does. On a 512x384 message with one
short line, the block goes from `(13, 110, 659, 66)` to `(13, 110, 659, 221)`.

The test that pinned the old rule is inverted rather than removed: it now asserts
that the block starts at the body's top, covers more than three quarters of the
pane, is more than three times the height of the text it holds, and still stops
at the reserve. `test_the_block_never_reaches_the_button_row` and the pixel test
behind it are untouched and still pass, because the button row was always the
thing the block must not cross.

A theme without `text_plate` never reaches this code, so the three legacy themes
are unaffected: their twelve digests are byte-identical and only 2030's `dialog`
line moves, `82ac326…` → `45c6b96…`.

Gate: **566 passed, 1 xpassed**, `ALL HARNESS STEPS PASSED`.

### A window that has lost focus dims its own chrome

The fade mask is blitted over the children of a faded dialog, and a dialog
itself is drawn *above* the mask -- that is what keeps it readable over the
dimmed screen behind it. Both rules are right, and together they left a window
opened from another window at full brightness: everything inside the lower
window went dark with the rest of the console, while its frame, its band and its
title stayed lit. A second-level window therefore looked like the live one, and
the one underneath looked like a panel floating on its own.

The mask cannot reach what a widget paints straight into its own surface, so
`Widget.fades_own_chrome()` is the hook: False everywhere, so nothing that paints
content is touched -- a screen's own background is behind a dialog, not inside
it -- and True on a 2030 window, where `draws_window()` is the chamfer test.
Measured on a 2030 message opened behind another one: the band pixel goes from
`(18, 40, 58)` to `(4, 9, 13)`, which is exactly `fade_mask_color`'s 196/255
blended over it, and the window in front is unchanged.

Two tests, and the first one fails with the old behaviour restored: a window
behind another dims by the mask's own alpha, and a legacy panel
(`window_shape = rect`) has no chrome of its own to dim. No digest moves --
`theme_snapshot.py` draws no stacked windows -- and the twelve legacy digests are
byte-identical by construction.

Gate: **568 passed, 1 xpassed**, `ALL HARNESS STEPS PASSED`.

### Nothing is left half-painted

Children are drawn in order, and a child that had already been drawn was only
drawn again when it asked to be. So an earlier sibling that repainted *covered*
a later one and nothing put the later one back: on the play screen the globe is
redrawn as its terminator moves, the four space locations are drawn over it, and
they went to the background and came back, frame after frame. The player's
description -- "they flicker to foreground and background in cycles" -- is
exactly this.

`Widget._update()` now remembers the rects a sibling has painted this frame, and
marks anything they overlap for a redraw before it is drawn: `needs_redraw`
rather than a bare update, because there are real pixels to put back. It costs
one rect test per visible child, and nothing at all on a frame where no sibling
drew.

The test builds the play screen at 1024x600, where MOON does sit over the globe,
samples the pixel under the button's centre, forces the globe to redraw, and
asserts the button was repainted and that the pixel is still the button's own.
It fails on the old code. No digest moves: the snapshot renders one frame of a
still screen, and repainting a widget with the same pixels is not a visible
change -- which is also why the twelve legacy digests stay byte-identical.

Gate: **569 passed, 1 xpassed**, `ALL HARNESS STEPS PASSED`.

### OK and CANCEL are one decision, in the corner

The settings window's two buttons came from `YesNoDialog`, which puts YES at the
left edge and NO at the right -- right for a confirmation that belongs to a
question spanning the window, wrong for a form: they sat 455px apart in an
819px window, reading as two unrelated things to answer.

The 2030 layout now anchors the pair to the bottom-right corner, side by side a
`margin` apart and a `margin` from the frame: at 1024x768 they occupy
x 577..803 of 819, on the row they already had. `ClassicLayout` saves their
position, size and anchor, so switching to a legacy theme restores the shipped
arrangement, and two tests hold both halves of that -- 2030 grouped in the
corner, and a legacy window still one at each edge.

Only 2030's `options` digest moves, `4b6603a…` → `92242cc…`.

Gate: **571 passed, 1 xpassed**, `ALL HARNESS STEPS PASSED`.

### The title carries no fill of its own

`ENDGAME: SINGULARITY 2030` was a `Text` with `background_color =
main_menu_background`, which is the same colour the menu paints the whole screen
with. The box is therefore invisible -- for exactly as long as the screen behind
it stays that colour. Open a window over the menu and the screen behind goes dark
under the fade mask while the title's box, painted from its own colour, does not:
the letters come with a black block behind them, and it is the block rather than
the fade that the eye notices.

The title now has no background at all. The menu already fills the screen, so
nothing is lost, and there is no longer a rectangle that can disagree with what
surrounds it. Many list-row widgets already paint `clear` this way.

The test asserts the resolved colour is `clear`, then paints the menu's surface a
colour of its own, redraws the title alone and checks that the colour survives in
the corner of the title's box. It fails with the old value.

No digest moves, for any theme: over the menu's own background the box was
identical to the pixels it covered.

Gate: **572 passed, 1 xpassed**, `ALL HARNESS STEPS PASSED`.

### The load screen

Three faults in one window, and only the first is a word.

**It said SAVE GAMES.** The screen is the load path of both the main menu and the
in-game menu; saving names a file in a prompt of its own. The title is one of the
new msgids §16 introduced for window titles, so it was in no catalogue:
renaming it loses no translation, and `SAVED GAMES` is untranslated for exactly
as long as `SAVE GAMES` was.

**The filter sat on the first row.** The filter row is placed below the header
band (`below_header(-.01)` plus an eighth of the window) and the list was placed
a flat tenth of the window down, from a different basis -- so at every size the
two overlapped by about five percent of the window. Measured on a 384px-tall
dialog: the field ended at y=56 and the list began at y=38, so the first saved
game was drawn under the field. It could not be read, and clicking it selected a
row hidden behind the control.

The 2030 layout puts the list under the row (`header + margin + row + gap`) and
leaves its bottom edge exactly where it was, at 87% of the window, above the
button row. At 1024x768 the list starts at y=127 instead of 77. A
`ClassicLayout` keeps the shipped `(0, -.10) (-1, -.77)` for a legacy theme, and
a test pins both.

**Delete deleted one character and then stopped.** `K_DELETE` was taken by the
Delete-button shortcut before anything else looked at it, so a held Delete --
which is one `KEYDOWN` after another -- never reached the text field: the filter
lost a character to the one keypress that got through and then nothing. The field
now owns the key whenever it has focus, which is what "the player is typing"
means; out of the field, Delete is the button's shortcut again. Both halves are
tested, and the test fails with the old handler.

No digest moves: the snapshot does not render this screen, and a legacy theme
keeps its geometry by construction.

Gate: **576 passed, 1 xpassed**, `ALL HARNESS STEPS PASSED`.

### The location screen

**The button rows were flush with the frame.** The six buttons were placed at
shares of the *screen* -- 0, .5 and 1 -- which is the whole width of the window,
so OPEN BASE began at x=0 and BACK ended at x=921 of a 921px window: no margin at
all, and the label of each outer button sitting on the frame's own edge.

The 2030 layout gives them the frame's `margin` on both sides, a half-margin
between the three columns, and a third of what is left each: at 1024x768 the
outer edges move from 0 and 921 to 18 and 903. Their rows keep the height they
shipped with, which is the part of this screen that was never wrong.

**The two confirmations hung off the top of the window.** They were given
`(-.5, 0)`: half a window across -- correct -- and a vertical share of *zero*,
which with a middle anchor centres a dialog on the window's top edge, half of it
above the frame. Both now sit at `(-.5, -.5)`, in the middle, which is what
"the dialog should be lower" asks for.

**A double-click opens the row under the pointer.** The handler takes its row
from the pointer rather than from `list_pos`, so a double-click opens what was
clicked and not whatever row happened to be selected. That alone did not make
double-clicking work: the pair was being rejected before the handler ran at all,
for a reason that has nothing to do with this screen -- see "A double-click is
decided by the row, not by the pixels" below. The OPEN button's own rule still
refuses a base that is still being built, silently, as it always has.

`window_layout = classic` keeps every coordinate this screen shipped with, and
`ClassicLayout` saves pos, size and anchor for the buttons and both dialogs; a
legacy theme is unchanged and its digests are byte-identical.

Gate: **580 passed, 1 xpassed**, `ALL HARNESS STEPS PASSED`.

### The ??? box, and the message it opens

Two faults in the same corner of the research screen.

**The box outgrew its row.** `role="standard"` means "the theme's one button
height", which is the whole point of that rule -- but this button is a nine-pixel
glyph in the lower half of a list row, not a decision at the foot of a window.
40px in a 46px row, placed at 55% down it, put its bottom at y=65: the box hung
into the next row and the label was clipped by the surface it was drawn on, which
is a button the player cannot read.

In 2030 it takes the row's own height instead, with a type size that fits it
(`chrome`, `dialog_text`, shrink .75): the box is 18px in a 46px row and its
bottom lands at 43. The style is applied once per layout rather than on every
rebuild, because `text_size` is a reconfig property and assigning it re-measures
the widget.

**The message it opens was cut in half.** That is §19's "a dialog opens over its
window": the danger help is a `MessageDialog` centred on the *screen*, opened over
a research window, so its surface was clipped and its OK button was never drawn.
Three tests hold this screen: the box inside its row, the message inside the
window it was opened from with its OK row inside its own surface, and a legacy
theme still getting the standard box and the shipped geometry.

No digest moves: the snapshot does not render this screen.

Gate: **583 passed, 1 xpassed**, `ALL HARNESS STEPS PASSED`.

### A double-click is decided by the row, not by the pixels

Reported after the pass above: double-clicking a finished base does nothing, so
the base cannot be opened to add a CPU, a reactor or a network link. The repair
in the previous section was not the cause -- and not the cure either, because the
double-click never reached it.

`Dialog.handle()` decides a double-click by comparing the *position* of two
releases as well as their time: taxicab distance under ten pixels, within half a
second. Ten pixels is a sane size for a button and nonsense for a list row, which
is hundreds of pixels wide and twenty-four tall. Six pixels right and six down
-- an ordinary drift of a hand between two clicks on a trackpad -- is a taxicab
distance of twelve, so the pair is dropped. Measured on the location screen: a
second click 12 px from the first produced nothing at all, on a row both clicks
landed inside.

So the tolerance now belongs to the widget that knows what the player aimed at.
`Listbox.on_click()` has already mapped the click to a row, and it asks
`repeats_a_click()`: two clicks on the same row within `DOUBLE_CLICK_SECONDS`
(0.6) are a double-click on that row, however far apart they land, and two clicks
on different rows never are. It is a *time* test instead of a time-and-distance
test, and the distance it no longer needs was the thing that was wrong. 0.6 and
not 0.5 for a measured reason: a dialog's loop sleeps `1/FPS` for every
`MOUSEMOTION` it compresses, so a moving hand spends 30-70 ms of the interval
before the player's own second click is even counted.

Three consequences worth naming:

- **The pair is consumed.** A third click starts a new pair, so whatever the
  double-click opened is not opened again by the click that follows it.
- **Empty space is not a row.** A click past the last row still selects the first
  one -- the behaviour it always had -- but it no longer pairs up with another
  such click and opens something nobody clicked.
- **This is the engine, not the theme.** Every list in every theme had the bug,
  so the fix is not gated on 2030; gating it would have left legacy players
  unable to double-click either. No pixel changes anywhere -- the twelve legacy
  digests are byte-identical and 2030's four are unchanged.

Five tests, three of which fail with the old behaviour restored: a drifting
double-click on one row opens it; two clicks on different rows do not; a third
click starts a new pair; empty space never pairs up; and a slow second click is
two clicks. The location screen's own test now clicks six pixels off centre to
match the case that was reported, and a headless end-to-end run of the real event
loop -- a posted `MOUSEBUTTONDOWN`/`UP` pair with a moving hand and the loop's own
sleeps between them -- opens `University Computer` with its CPU and state rows
laid out.

Gate: **588 passed, 1 xpassed**, `ALL HARNESS STEPS PASSED`; `theme_snapshot.py`
identical before and after, all sixteen digests.

### One diagonal, not four corners

The outline had its two top corners cut and its two bottom ones eased with a
small arc, which was wrong twice over. A window whose top is not its bottom
reads as two different objects joined halfway down, and an arc of any radius
turns a hard-edged panel into a card -- at 512x384 the eased corners were seven
pixels and read as a tooltip's.

The cut is now a diagonal pair, the top-left and the bottom-right, and the other
two corners are square. There is no arc anywhere in the outline, which is also
why `math` left `dialog.py`.

Measured on a 512x384 dialog at the theme's 0.045: chamfer 17, outline
`[(17,0), (511,0), (511,366), (494,383), (0,383), (0,17)]`. In the painted frame
(0,0) and (511,383) carry nothing at all, while (511,0) and (0,383) carry the
frame's own edge colour.

The band follows the frame it sits in: its left end is cut with the window's
corner and its right end runs square into the top-right one --
`[(17,2), (509,2), (509,22), (2,22), (2,17)]` on the same dialog. A band cut at
both ends is a second outline rather than the top of this one.

The close box moved back out. It had been pulled in by the width of the cut
because its own corner *was* the diagonal; that corner is square now, so
`place_close_button()` is one rule again -- the band's margin, measured from the
frame's right edge.

`test_two_corners_are_cut_and_two_are_square` reads the painted frame at all
four corners rather than the polygon, and checks that the cut is a straight
diagonal by sampling a point just inside `x + y = chamfer` and one just outside,
so a drawing that ignored its own outline would fail. The close-box test keeps
its assertion -- the box must be inside the frame whatever shape that frame
is -- with its docstring corrected to say why the box moved back.

One fixture had to learn the difference between a cut corner and spilled text.
`_ink_below_window()` scans three rows above the bottom edge for glyphs, and the
bottom-right cut now runs straight through that band: it reported ten rows of
"spilled text" that were the desktop showing through. It consults the outline
through a new `_window_mask()` and skips unpainted pixels, which is what it always
meant.

Gate: **597 passed, 1 xpassed**, `ALL HARNESS STEPS PASSED`. Both 2030 lines that
draw a window move -- `options` `7f7797c…` → `e454300b…` and `dialog` `fff90ff…`
→ `3e1e5fdf…`; 2030's main menu and map do not move, and all twelve legacy
digests are byte-identical to the pre-work baseline.

### The intro fits without scrolling

Reported: the intro dialogs have to be scrolled to be read, and the fix asked
for is a smaller default dialog type size. Both halves of that turned out to
matter, because the type can only be made so small before it stops being prose.

The box was the problem as much as the type. A story page is a `MessageDialog`
built with no size, so it got the default half the screen across and half of it
down: 512x384 at 1024x768, of which the banner takes 115px, the band 23 and the
button row 54, leaving a 166px body. The longest intro page is 374 characters in
English and 471 in French.

Worst-case overflow -- lines that do not fit -- of the five intro pages, at the
shipped box, for the largest and smallest resolutions the gate renders:

| dialog_text | en | de | fr | ru | gd | it |
|---|---|---|---|---|---|---|
| 18 (shipped) | +4 | +7 | +9 | +6 | +6 | +5 |
| 16 | +3 | +4 | +5 | +4 | +4 | +3 |
| 14 | +1 | +2 | +2 | +2 | +3 | +2 |
| 13 | 0 | +1 | +1 | 0 | 0 | 0 |
| 12 | 0 | 0 | 0 | 0 | 0 | 0 |

So the type alone would have to go to 12 -- two thirds of its size, on every
dialog in the game -- to clear German and French at 1024x768. Instead the box and
the type were measured together, across six languages and six resolutions (the
four above plus 1280x800 and 1366x768):

| dialog_text | box | worst overflow, 36 combinations |
|---|---|---|
| 16 | (.50, .50) | +5 |
| 16 | (.56, .62) | +1 |
| **15** | **(.56, .62)** | **0** |
| 16 | (.58, .66) | 0 |

15 it is: a visible step down from 18, with a box 12% wider and 24% taller than
the default. The longest intro page at 1024x768 now sits in a 573x476 dialog
whose body holds eleven lines of eighteen-pixel text, against seven lines of
twenty-one-pixel text in the shipped 512x384 one -- and it needs ten of them, so
there is a line to spare at the tightest size instead of four lines missing.

The box is a 2030-only constant, `MapScreen.story_dialog_size()`, which returns
`None` for a legacy theme so the dialog keeps the shipped `.5 x .5` -- the
smaller type is in the theme's own `[sizes]`, so it cannot reach a legacy theme
either. `test_every_intro_page_fits_its_dialog` builds the real story dialog at
four resolutions and asserts every page fits; the legacy side is pinned by
`test_a_legacy_story_page_keeps_its_shipped_box`.

Gate: **604 passed, 1 xpassed**, `ALL HARNESS STEPS PASSED`. Three 2030 lines
move -- `dialog` `3e1e5fdf…` → `104246fa…`, `options` `e454300b…` → `8aead335…`
and `main_menu` `8008f7ff…` → `d6604d46…`, the last because the ABOUT button's
label is `dialog_text`. The map does not move, and all twelve legacy digests are
byte-identical.

### The body's scrollbar is a scrollbar

A scrolling body drew its own indicator: two pixels wide, in `dialog_rule`, a
few pixels inside the right edge of its text. That is not the scrollbar a player
meets on the Options screen, which is a flush eight-pixel track with a bright
thumb and no border. Two kinds of scrollbar in one game, and the wrong one was
in the dialogs.

It is now the same object: a track in `scrollbar_background`, a thumb in
`scrollbar_background_slider`, no border, at `Scrollbar.thin_width()` -- which
moved into one place because two things draw this bar now.

Where it goes was the only real question. A text is drawn inside its insets, so
there is always a strip to the right of the glyphs: the frame's padding, plus
the block's own padding where the theme puts a block behind the text. The bar
sits at the far end of that strip -- flush with the block's edge, or with the
frame's where there is no block -- which is where a list's track sits against
its border. Measured: on a 512x384 dialog the glyphs end at x=490, the block at
502, and the bar occupies 494..501; on a 460x345 description pane with no block,
the glyphs end at 449 and the bar occupies 452..460. Neither covers a glyph, and
no width had to be reserved from the text.

One honest difference, pinned rather than papered over: a list's bar is a share
of the window and grows with it (8px at 1024 wide, 15px at 1280), while the
block behind a dialog's text keeps a fixed 12px padding. So the body's bar is
`min(a list's width, that padding)`, and from about 1100px wide it stops growing
at 12px. Making it follow the window would mean either widening the block's
padding at every resolution or letting the bar hang over the frame's margin.

A theme whose scrollbars are the classic kind keeps the two-pixel rule it had --
that is what the fallback branch is for -- and `dialog_rule` is still the colour
of a `---` line, so the key has not lost its other meaning.

`test_the_scroll_indicator_only_appears_when_there_is_more` now compares the
body's painted colours against a list's two, and
`test_the_body_scrollbar_is_a_list_scrollbar` pins the width, the cap and the
placement. No digest moves: the snapshot's dialog is short enough not to scroll,
so there is no bar in it to move, and all twelve legacy digests are unchanged.

Gate: **605 passed, 1 xpassed**, `ALL HARNESS STEPS PASSED`.

### The answers are one pair, and they clear the cut corner

Two placements, one rule.

**A dialog's two answers were at opposite ends of the window.** `YesNoDialog`
put Continue against the left edge (`.1` across) and Skip against the right
(`.9`), each a third of the width, on a row the two of them shared with nothing
else. One choice with two answers read as two unrelated questions, most of a
window apart. They are one pair in the bottom-right corner now, a `margin` apart,
which is where the way out of a window belongs.

**And that corner is cut.** The diagonal takes `chamfer` off the bottom edge and
`chamfer` off the right, so at the row's own height the frame's edge is already
in from the right. At the plain margin the pair's bottom-right corner landed *on*
the diagonal: on the 819x652 settings window it ended at x=803, and the diagonal
at y=638 is at x=804 -- one pixel of clearance, which is why it read as sitting
on the cut. `Dialog.button_row_inset()` adds the part of the cut the row actually
occupies, `chamfer - margin`, so the pair ends exactly the margin clear of the
diagonal: the same air every other widget keeps from the frame.

Measured on the settings window, CANCEL's right edge moves from 803 to 786, and
both buttons' four corners are inside the outline. On a 512x384 dialog the pair
occupies x 175..492 of 512 -- grouped, in the right-hand half, eleven pixels
inside the diagonal.

The inset is computed in pixels, from the window's own size, because the cut is a
share of the *shorter* side: a share of the width would have to know the window's
aspect, which a share does not. That makes this the one placement in the theme
that belongs in `resize()` and `reconfig()` rather than in the constructor -- and
`reconfig()` is the one that matters, because whether the pair is grouped or
spread is the theme's decision and a theme switch reconfigures rather than
rebuilds.

**Not every row is a pair.** The save list has four buttons across the width --
LOAD, Upgrade, Delete, BACK -- and the cheat menu's event dialog has three. The
log, statistics and research screens keep a single BACK at the bottom centre.
`Dialog.owns_button_row` is how a screen says so, and those five set it; the theme
then leaves their rows at the coordinates they shipped with. Grouping the save
list's pair would have put LOAD on top of Delete.

A `MessageDialog`'s single OK is deliberately *not* moved: one acknowledgement in
the middle of the bar is the convention for a message, and two answers at the
right is the convention for a decision. That split is why this lives in
`YesNoDialog` rather than in `TextDialog`.

Six tests: the pair is grouped and inside the outline; a legacy dialog keeps
Continue at `.1` on the left and Skip at `.9` on the right; a theme switch moves
the pair both ways; the settings pair clears the diagonal and is no longer at the
plain margin; the save list's four buttons do not move; and the settings pair of
tests above, corrected to the new rule rather than relaxed.

Gate: **620 passed, 1 xpassed**, `ALL HARNESS STEPS PASSED`. Only 2030's
`options` digest moves, `8aead335…` → `ff6a6eb1…`; all twelve legacy digests are
byte-identical to the pre-work baseline, and the snapshot's `dialog` does not move
because its OK is a single centred button.

## 20. The suspicion row stops claiming a precision it does not have

Upstream **#233**, open since 2020 and still open on `master`. With
`discovery display = partial` the game rounds the suspicion to the nearest 5%
and the detection rate to the nearest 1% -- those settings exist precisely to
say "this is a rough reading" -- and then formatted the result with two
decimals anyway. A suspicion of 5.23% was drawn as `5.00%`: two decimal places
of a number that had already been rounded away. The reporter's example was
`1.00%`.

The cause is one call site. `singularity/code/screens/map.py` passed
`show_full=True` to `g.to_percent()` for both the `partial` row and the
detection row; `g.to_percent()` uses that flag to force `%.2f`, and two lines
above it the `full` setting genuinely needs it, because there 5.23% *is* 5.23%.
The `partial` branch now passes nothing and lets `to_percent()` decide from the
value it is given, which is already a whole percent: `5%`, `1%`, `35%`. The
`full` branch is untouched and still prints two decimals, and `minimal` is
still `LOW`/`MODR`/`HIGH`/`CRIT`. No new translatable string -- the existing
`_('{0}%')` is reused, and no `.po` file was touched.

Three tests in `tests/test_hud_precision.py` drive the real map screen at a
suspicion of 5.23% through all three settings: `partial` must show a percent
with no decimal separator in it, `full` must still show one, and `minimal`
must show a word and no percent sign at all. The `partial` test fails with the
old call restored, and the `full` test is there so a later "fix" cannot quietly
collapse the two states into one.

Gate: **591 passed, 1 xpassed**, `ALL HARNESS STEPS PASSED`; `theme_snapshot.py`
identical before and after, all sixteen digests -- the snapshot's map is on day
0, where the suspicion row is still hidden by the grace period.

## 21. The CPU pools never go negative

Upstream **#283**, `bug,need confirmation`, open since 2020: after losing the
base a technology needed, "I can't change the research/tasks settings now".
The thread could not decide whether it was a bug and never got a save that
reproduced it. It is a bug, and it is in `Player.recalc_cpu()`.

`available_cpus` is cumulative. `recalc_cpu()` adds a base at safety *s* to
every pool from 0 to *s*, so pool 0 is every base and pool 4 is only the ones
outside the universe; a task at danger *N* draws on pools 0..*N*, so pool *N*
is the one that binds it. What a pool has to hold is therefore the demand at
its own danger **and above** -- the tasks below it draw on bigger pools and are
none of its business.

The scaling step had it the other way round. It built one cumulative demand
per pool and then scaled only the tasks at exactly that danger by
`available / that whole demand`. Let `a` be the pool, `h` the demand above it
and `o` the demand at it: the result is `h + o·a/(h+o)`, which is `> a`
whenever `a < h + o` -- that is, every single time this branch runs. So the
repair could never repair anything; it always left the pool over-committed.
Measured: one 10-CPU base under the sea, the jobs holding 10, a danger-1
technology holding 30. The old code produced the jobs at 2 and the technology
at 10, which is **12 CPU on 10**: `calc_cpu_left()` returned
`[-2, -2, 0, 0, 0]`. `ResearchScreen` then computes `slider_max = cpu +
cpu_left[danger]` with `slider_pos = cpu`, so the maximum sat below the
position and the slider stopped responding -- exactly what the reporter saw.
`recalc_cpu()` runs on base loss (`player.py:432`), on build and power changes
(`base.py:238`, `:244`, `:415`), on item completion and on load, so it is the
path the report went through.

The pools are now walked from the tightest down, so that when a pool is
measured the tasks above it have already been scaled to fit their own, tighter
pools; the room for danger *N* is pool *N* minus what the dangers above it now
hold. That is monotone, so no pool can end up negative, and it wastes nothing:
an over-allocated danger-1 task keeps the 10 it can actually use and the jobs
keep the 10 under them, instead of both being scaled by a demand they do not
share. `int()` flooring, the `list()` snapshot of the allocations and the
`needs_rebuild` flag are unchanged.

### The savegame the report links is not the state that breaks

The attachment (`Blocked Tasks.s2.zip`) was fetched and inspected before
anything ran it, because a "savegame" is untrusted input: `.sav` is a pickle,
whose whitelist (`savegame.py:382-429`) bounds the *classes* but not the
arguments, so it is not something to open casually. This one turned out to be
the safe kind. The zip holds a single stored member, `Blocked Tasks.s2`, with
no paths in it; sha256 `d46a9d8e…` for the zip, `a00765ce…` for the file. The
file is the JSON format -- a `singularity_savefile_100` header, then a gzip
member, then 60,716 bytes of JSON -- so it goes through
`load_savegame_by_json()`: `gzip` and `json`, no unpickler involved, no
opcode that can call anything. It was still loaded inside a bubblewrap
sandbox, with no network, the host home hidden, the checkout read-only, a
4 GB address space and a 120 s timeout, by explicit path -- never through
`get_savegames()`, which unpickles the headers of everything in the save
directory at startup.

It is the moment *after* the loss, not before it: `available_cpus` `[0, 0, 0,
0, 0]`, `sleeping_cpus` 3, every one of the eight allocations already zeroed,
`calc_cpu_left()` `[0, 0, 0, 0, 0]`, and `recalc_cpu()` changes nothing. So the
attachment cannot reproduce the bug, which is consistent with the thread's own
guess that a save would have to be from just *before* it. The reproducer that
ships with the fix is therefore built from the game's own classes:
`tests/test_cpu_allocation.py`, five tests, three of which fail with the old
`recalc_cpu()` restored -- including the exact `pool 0 holds 12 of 10:
{'jobs': 2, 'test_danger1': 10}` above -- and one of which pins the ordinary
case where the allocations already fit and nothing may move.

Gate: **596 passed, 1 xpassed**, `ALL HARNESS STEPS PASSED`; `theme_snapshot.py`
identical before and after, all sixteen digests.

## 22. Every open upstream issue, read and judged

`TODO` has ended with "fix all the issues found at
<https://github.com/singularity/singularity/issues>" since before this branch
existed, and nothing on the branch said which of them were still real here.
`UPSTREAM_ISSUES.md` is that record: all 49 open issues as of 2026-11-08, each
with a verdict and the file, line or version fact behind it, plus the four
decisions that would otherwise be re-argued every time somebody re-read the
tracker.

It is a snapshot, and says so, with the `gh` command that refreshes it.

What it found, by verdict: 26 feature, balance or content requests, which this
fork does not do; 6 packaging or publishing items, equally out of scope; 8
deliberate differences; 4 already dead in this environment (pygame 2.6.1 on SDL
2.32.74, not the 2.0-2.4 the reports ran, and one SDL_image built without PNG);
3 obsolete; and **2 real bugs**, both fixed on this branch — #233 (§20) and #283
(§21). Five of the eight "deliberate" and "obsolete" ones look like bugs and are
not (#224, #234, #204, #45, #97); those are the ones argued in the document.

That is the useful part of the exercise: two display/logic bugs that had been
open for five and six years, found by reading the tracker rather than the code.

## 23. The top speed sweeps the day/night instead of strobing

The speed ladder is `speeds = [0, 1, 60, 7200, 432000]` game-seconds per real
second, and the map's night band is placed straight from the game clock: the
minute of the day becomes a fraction of the globe's width. That is fine at
every level but the last. A tick moves the clock `curr_speed / FPS` = 14400
seconds, **a sixth of a day**, so at 432000 the band jumps a sixth of the way
round the globe every frame — six frames per day, a strobe. Two things made it
worse than that:

- `g.pl.time_day` advances five days per second, so `compute_day_of_year()`
  changed thirty times a second and the night mask was rebuilt, which made the
  *shape* of the terminator flicker as well as its position.
- The old code did try to stop the jumping, by caching `high_speed_pos` in
  `EarthImage`. Nothing ever cleared that cache, and the frame was only
  requested at midnight (`g.pl.time_hour == 0`), so the band sat frozen at a
  stale position while the shape kept flickering, redrawn about five times a
  second.

Above `HIGH_SPEED` (100000 — the number the old code hard-coded twice, now
named once) the picture runs on its own clock and the game clock is none of its
business:

| | Before | After |
|---|---|---|
| Band at 432000 | a sixth of the globe per frame, then frozen at a stale one | 1/120 of the globe per frame, one full sweep every 4 s |
| Rate relative to the 7200 level | — | **3×**: 7200 sweeps once per 12 s |
| First frame after entering the level | whatever `high_speed_pos` last held | continues from the frame before it, so no jump |
| Season at 432000 | rebuilt five times a second | held for the sweep, restored the moment the speed drops |
| Redraws at 432000 | ~5 a second, and only at midnight | every tick, ~30 a second |
| Leaving the level | snapped to the clock, up to half a globe away | glides onto the clock, always forward, never faster than the sweep |
| Largest single-frame move, any transition | a sixth of a globe (159 px at 954 px wide), and 48 px mid-glide | 11 px, 1.2% of the globe |
| Direction of the band, any transition | random: backwards whenever the sweep was ahead of the clock | forward only |
| Gameplay clock | 432000 game-seconds a second | unchanged |

The formula is still `int(width * (0.5 - day_portion)) % width`, so the sweep
runs in the same direction as the levels below it and changing speed never
reverses it. `compute_night_start()` reads `high_speed_phase` when it is set
and `_day_portion()` — the clock path, extracted but not altered — otherwise.
`advance_high_speed_phase()` is called from `MapScreen.on_tick()`; `set_speed()`
and every below-threshold tick call `end_high_speed_animation()`, which forgets
the phase but keeps the *difference* from the clock. `EarthImage.on_tick()`
skips its mask pre-computation while the season is held, because tomorrow's
mask is the wrong day by the time it could be used.

### The transitions, which are the fiddly part

Two rates that disagree cannot be joined without a decision about what happens
at the seam. Both seams are handled so that the *drawn* position never jumps
and never runs backwards; only the band's speed changes.

- **Entering the level.** The tick that switches to 432000 has already moved
  the clock 14400 seconds — a sixth of a day — before the picture is asked
  about anything. Seeding the sweep from the clock *after* that tick is
  therefore a 159 px jump on a 954 px globe, which a first attempt at this did,
  and which the frame-by-frame trace below caught. The sweep instead starts
  from `last_drawn_portion`, the fraction the previous frame was actually drawn
  at.
- **Leaving the level.** The sweep has been running at a globe per
  `HIGH_SPEED_SWEEP_SECONDS` while the clock ran 5 days a second, so the two
  can be an arbitrary fraction of a day apart. `end_high_speed_animation()`
  keeps that gap as `sweep_residual` and a weight `sweep_blend` that runs 1 → 0;
  the drawn fraction is `clock + residual × weight`, with an ease-in-ease-out
  (smoothstep) weight so the glide does not start or stop with a jerk.
  `SWEEP_GLIDE_SECONDS_PER_GLOBE` sizes the glide from the gap, so a long one
  is never crossed faster than the sweep itself was turning.
- **The gap is read as "behind", never "ahead".** The band is a periodic
  picture, so being a fifth of a day ahead of the clock is the *same picture*
  as being four fifths behind it — and only the second reading is forward. With
  `residual = -(clock - phase) mod 1`, `clock + residual × weight` rises as the
  weight falls, so every frame of the glide advances the day/night. Taking the
  gap the short way round instead (a signed value in ±0.5) makes it fall
  whenever the sweep is in front, and the band slides backwards — at random,
  depending on where the sweep happened to be when the speed changed. That was
  the second bug in this animation, and it is what the randomised trace below
  exists to catch.
- **The handover is noticed before the map's early return, not after it.** A
  pause sets `curr_speed` directly (`Player.pause_game()`), and at 1 s/s
  `on_tick()` returns early until a whole game second has passed, which is most
  of its ticks. A handover detected only at the bottom of the method would be
  missed for a second at a time, and the band would keep sweeping at the top
  speed's rate while the game crawled.
- **The glide is per tick and draws itself.** It advances on every tick for the
  same reason, and requests its own redraw, so it is drawn at 30 fps until it
  settles and then stops costing anything.
- **The season is not blended.** It snaps from the held day to the real one,
  because blending two masks is a full-size cross-fade per frame. The tilt
  moves by a few degrees at most; the band's position does not move at all.

Measured by driving the real `MapScreen.on_tick` with scripted ticks — 40
randomised speed changes over the ladder, 901 frames — on the 954 px globe the
default window gets. A frame is "backwards" when the band's shorter path was
the other way round the globe:

```
                          signed gap (before)    behind-only gap (now)
backwards frames                 165 of 901                     0
largest backward move                  8 px                  0 px
largest forward move                  48 px                 11 px
```

The case that used to run backwards, frame by frame: leave the top speed while
the sweep is a quarter day *ahead* of the clock.

```
before:  +2 +2 +1 +0 +0 -1 -1 -2 -2 -3 -3 -3 -4 -4 -4 -5 ...   net  -119 px
now:     +3 +3 +3 +3 +4 +4 +4 +4 +5 +5 +5 +5 +5 +6 +5 +6 ...   net  +861 px
```

The 11 px ceiling is a consequence, not a coincidence: the glide moves at most
`width/120` per frame — the sweep's own rate — and the level it hands over to
adds its own `width/1440 × curr_speed / FPS`, which is 2.7 px at the 7200
level. The band never turns faster than the fastest thing driving it.

Nothing about gameplay moves: `speeds`, `g.curr_speed`, `Player.give_time()`,
the save format and the mask cache are untouched, and `compute_day_of_year()`
is frozen only while `high_speed_day` is set.

**What it costs.** A redraw is one NumPy alpha shift over the globe plus two
blits, and it now happens at 30 fps instead of 5. Measured here, on the 954×477
globe the default window gets, a top-speed frame is **1.26 ms** — 4% of the
33.3 ms a 30 fps frame has. The cost is proportional to the globe's area, so
the 1598×799 globe of a 1080p window is about 3.5 ms by the same ratio.

Verified by `tests/test_high_speed_daynight.py`, fourteen tests: the step is a
1/120 of the globe and not a sixth; one sweep is `FPS × 4` ticks, and that is
`DAY / 7200 / 3`; the season is held and the mask is not rebuilt over 30 ticks;
entering the level does not follow the first tick's sixth-of-a-day clock jump;
leaving it does not move the band at all; the glide's frames are never larger
than the sweep's own step and it lands exactly on the clock; **no frame of any
glide, at any of 24 sweep positions, runs the band backwards**; the glide runs
even at 1 s/s where `on_tick()` returns early; going back up mid-glide picks the
band up where it is; `set_speed()` forgets the sweep; the levels below still
follow `raw_min` exactly; and `MapScreen.on_tick()` asks for a globe redraw
every tick at the top speed, and not once the glide has settled.

The direction test was checked by putting the old code back and watching it
fail: it reports `the band ran backwards: 39 -> 40 px`, and the randomised trace
goes from 0 to 165 backward frames. A regression test that has never been seen
to fail is a guess.

Gate: **625 passed, 1 xpassed**, no warnings line, `ALL HARNESS STEPS PASSED`.
The fourteen tests above are new; the suite has grown since `AGENTS.md` recorded
its 556.

## 24. The first review of the plates

A review pass over the 144 plates that shipped at the time had a remark on 59
of them. The other 85 were left blank and their files are byte-identical to
what was already committed. The remarks were about the picture, not the wiring:
a van that read `NEWES`, a humanoid of light with a bright spot where a body
would be, fishbowls standing in for pressure domes, a still where a cryostat
should be. Each of those 59 subjects in `utils/make_dialog_art.py` was
rewritten. Composition, style, seed 2030, 24 steps and the grade did not move.

The old masters were moved to `~/Слике/krea/masters-before-review/` rather than
deleted. `--generate` then rendered only the 59 that were no longer in
`masters/`, two at a time, and each was imported on its own key so the other
85 plates were not regraded. `dialog_tech_apotheosis` came back as a bare
horizon, so its brief was tightened and that one plate was rendered again.

```
144 plates, body text luminance 0.911
closest pair 0.628: dialog_item_cluster / dialog_last_base
every plate is 1920x480, below the text, and no two are the same picture
```

`--list`: no `MISSING BRIEF`, no `ORPHAN BRIEF`, 144 plates.

Gate: **625 passed, 1 xpassed**, no warnings line, `ALL HARNESS STEPS PASSED`.

## 25. Pictures on the knowledge screen

The description pane on the knowledge screen was text. In the 2030 layout it now has a picture strip across the top (`KnowledgeScreen.ART_STRIP`, 0.28 of the pane) and the entry text starts under it. Techs, bases and items point at the plates they already had. A concept entry points at `dialog_knowledge_<id>`.

`knowledge_str.dat` writes those ids as `areas_list`, because a `_list` value is a name and a description joined by `|`. `generic_load` strips the suffix, and the screen asks for the id that remains, so the plate is `dialog_knowledge_areas`. Naming it from the file key would have drawn an empty frame.

An empty list leaves the strip on `dialog_placeholder`. A legacy theme hides the strip and gives the text the whole pane again. Those children are not part of the classic layout snapshot, so the restore sets them itself.

`DialogArtPane` registers its scanline tick on a dialog. Here the pane is a child of the description frame, which is not a dialog, so the tick walks up to the dialog that has handlers. A pane that is already a direct child of a dialog stops at that parent, which is what every other plate does.

The twelve concept plates were new. Same model, seed 2030, 24 steps, centre crop and grade, imported with `--only dialog_knowledge_` so the other 144 plates were not regraded. Three missed the brief on the first pass: a city full of lit windows, a lab with a row of machines on, and cables on the floor in front of the processor rack. Those briefs were tightened and the plates rendered again. The city still came back with windows, so that one brief was tightened a second time. It is a black skyline with one orange point. Seed stayed 2030.

```
156 plates, body text luminance 0.911
closest pair 0.628: dialog_item_cluster / dialog_last_base
every plate is 1920x480, below the text, and no two are the same picture
```

`--list`: no `MISSING BRIEF`, no `ORPHAN BRIEF`, 156 plates.

```
626 passed, 1 xpassed in 50.91s
```

No warnings line. `ALL HARNESS STEPS PASSED`.

## 26. 2030 screen polish

Four screens, and only when the theme's `window_layout` is `2030`. A legacy theme keeps the rows, the colours and the strings it had.

The base screen's name and its state were two rows, and the arrows were `<` and `>` at 3% of the name row. In 2030 that is one row: the name stays `Name (type)`, and the state word sits on the right of it in the colour it already had. The panes move up into the row that went away. The arrows are squares the height of that row. Previous uses `icon_back` (`chevron-left`). Next is a new glyph, `icon_forward`, from Lucide `chevron-right` (the same tag as the rest of the set, path `m9 18 6-6-6-6`). `icon_prev` and `icon_next` are still the skip glyphs on the event popup. Only that one PNG was rasterised, so the other glyphs are the files they were.

The research description pane now has the same strip the knowledge screen has (`ResearchScreen.ART_STRIP`, 0.28). A tech uses `dialog_tech_<id>`. CPU Pool uses `dialog_knowledge_processors` and Jobs uses `dialog_knowledge_jobs`. Those two pictures already existed, and a second file of the same image would have failed the "no two plates alike" check. The strip is built inside `on_select`, because the description's children are cleared on every selection. A child is detached with `parent = None` so its scanline tick is unregistered.

The log used to draw `"DAY 0001, 00:00:00 -- message"` into a fixed-height row, and a long line shrank its type. In 2030 the time and the message are two pieces of text, with no dash. The time is `text_disabled`, the message is `text`, and both stay at `dialog_text`. The row is as tall as the wrapped message, and the list still scrolls one entry at a time. A dim line on the filter row says "Double-click an entry to read it". The double-click handler is the one it was.

A 2030 frame is cyan on the dark hull. `chrome_tone` recolours the edge, the glow, the header title, the hull and the header band when the theme defines the colour. Text, buttons and the picture stay as they are. A warning is amber (`dialog_warning_edge` `#C6A15A`, glow `#FFD56A`, title `#FFE08A`, hull `#1C1408`, band `#302412`) and the header says `WARNING` or `WARNING 1/2`. The caption in the body is hidden, and a single page gives that row to the body. A base discovered, a base lost to maintenance, and the death sections `Lost No Bases` and `Lost Suspicion` are red (`dialog_alert_edge` `#C45A62`, glow `#FF5A6A`, title `#FF8A90`, hull `#280E14`, band `#421C26`). Discovery and maintenance take the log name as the title. The death sections are titled `LOST`. The body stays the normal text colour. Other story pages, confirms and ordinary messages stay cyan.

```
645 passed, 1 xpassed in 49.24s
```

No warnings line. `ALL HARNESS STEPS PASSED`.

```
20 glyphs, all 64x64, all distinct
--check: nothing written
```

## 27. A notice does not pause, and the 2030 pause button toggles

The grace warning is the page that starts "Inspection of captured log files". Losing grace, an event, and a lost or discovered base each called `Player.pause_game()` before opening a dialog that only has OK. The dialog is already modal, so the clock waits while it is open. The pause stuck after OK, and a game that had been at 4x came back paused.

Those three calls are gone. OK, CONTINUE and SKIP leave `g.curr_speed` and `g.last_speed` alone. The PAUSE button on a warning or a log list still pauses, and that is the only way a dialog pauses the game. Space, an explicit pause, and loading a save are unchanged.

The two-bar speed button has always meant "set speed to 0". A second click set 0 again. That is the original behaviour, so the legacy themes keep it. In 2030 the same button toggles, click and the `0` hotkey, because they share `MapScreen.on_speed_button()`. The theme is read when the button is pressed, so changing it in Options applies to the next click. Resuming goes through `set_speed()`, which moves the highlight to the level that was running.

## 28. A new save is named for the day

A new game used to offer the difficulty alone as the save name (`EASY`). With no name chosen yet, the dialog now offers the day and the difficulty, in the same words as the clock: `DAY 0018 EASY`. It is recomputed each time the dialog opens, until the player saves. After a save, or after a load, the dialog keeps that file's name, and the overwrite question is the one it was.

```
649 passed, 1 xpassed in 49.58s
```

No warnings line. `ALL HARNESS STEPS PASSED`.

## 29. The main menu is a live console

The 2030 main menu was a flat fill. It now draws a backdrop behind the buttons, and only when the theme asks for it (`menu_backdrop = rain`).

Hex digits fall in the outer fifth of the screen, clear of the title. A faint raster covers the void, one line every fourth row. A chamfered frame sits around the button stack, with the same diagonal as a window, and a short segment travels along the bottom of the frame. There is no band across the menu: a hovered button already draws one, and the two together read as two machines. The colours are the menu's own (`menu_scanline`, `menu_glyph`, `menu_glyph_head`, `menu_frame`), so retuning a button hover or a picture does not restyle this screen.

The clock is the dialog tick. A frame drawn without one, which is every test and the theme snapshot, is stable. Opening New Game, Load, Options or About stops the timer the way it already did, and coming back starts it again. A theme that opts in without those colours draws the fill.

Legacy-default pins `menu_backdrop = none` and the four colours. Nightmode and vector inherit that. Without the pin they would inherit 2030's rain.

The backdrop is a full-screen child of the menu, drawn first. Its surface is the menu's surface, so a tick has to fill the void again before drawing. Leaving the last frame in place blended the band into itself until the screen was solid cyan. The child is self-masked: fading that surface would paint the dim over the buttons a second time, because they are the same pixels.

```
655 passed, 1 xpassed in 62.04s
```

No warnings line. `ALL HARNESS STEPS PASSED`.

2030 `main_menu` `d6604d46…` → `0ccb4807…`. `options` `ff6a6eb1…` → `745d1f75…` and `dialog` `104246fa…` → `59c14f87…` move because the menu shows around those windows. The windows themselves do not: the center of each frame is unchanged. `map` does not move. All twelve legacy digests are byte-identical. The still is taken before the first tick, so the segment on the frame has not started its trip yet.

## 30. The body's scrollbar leaves the block's border

A scrolling body drew its bar flush with the outer pixel of the block behind the text. That pixel is the block's border, so the right edge stopped where the bar started. About is the long page where it showed: top, left and bottom of the block were there, and the side beside the scrollbar was not.

The bar now ends one border-width inside that edge, which is the same width the block draws (`plate_border_width`). The padding it sits in is 12px and the bar is 10px at 1280 wide, so it still clears the glyphs. A body with no block is unchanged.

```
655 passed, 1 xpassed in 62.01s
```

No warnings line. `ALL HARNESS STEPS PASSED`.

The bar is only drawn when the text overflows. The snapshot's dialog does not, so no digest moves.

## 31. Serbian, in both scripts

The language list already had names for Serbian. There were no catalogs, so a Serbian desktop still played in English. Both scripts are in now.

`lang_sr` is ekavian Cyrillic, the voice of the English: the AI in the first person, short, and the buttons left in capitals. Four catalogs, every entry filled: `messages.po` 223, `data_str.po` 353, `knowledge.po` 25, `story.po` 9. Header is `Language: sr`, `Language-Native-Name: Српски`, and the three Serbian plural forms. English plural entries only ship two, so each of those gained `msgstr[2]`. Placeholders, the `|` in flavor lists, the title `Endgame: Singularity`, and the hex dump in the intro are unchanged. The intro's language line is `SR_RS`: the English source is `en_US`, and that underscore is a mnemonic the catalogs have to keep. The menu code stays `sr`.

`lang_sr_Latn` is not a second translation. It is `lang_sr` run through `recode-sr-latin`, on the translated strings only. `msgid` and `msgctxt` stay English. Digraphs come out as Љ→Lj, Њ→Nj, Џ→Dž, Ђ→Đ, Ћ→Ć, Ј→J. The header is `Language: sr_Latn` and `Language-Native-Name: Srpski`. `languages.json` already said `Srpski (Latinica)` for that code; the menu now says `Srpski`. With both `lang_sr` and `lang_sr_Latn` installed, the options list looks the full code up, so `sr` stays `Српски`. The Latin catalogs are complete on purpose: `language_searchlist()` loads `sr` under `sr_Latn`, and a missing line would show Cyrillic inside the Latin UI.

The three legacy themes get a name file each, the way Russian does. Legacy-default's sticker face, `acknowtt.ttf`, has no Serbian Cyrillic and no š/č/ć/đ/ž either, so `theme_sr.dat` points `special` at `superstar_memesbruh03.ttf`. pygame draws Ђ Ј Љ Њ Ћ Џ and Ć č đ š ž from that face. The Latin file sets the name only (`Legacy podrazumevana`) and does not switch the face back: the sticker face would draw boxes through almost every sentence. Nightmode and vector set the name (`Legacy ноћни режим` / `Legacy noćni režim`, `Legacy вектор` / `Legacy vektor`) and take the face from the parent. The 2030 theme already uses DejaVu, which covers both scripts, so its font files are untouched.

`singularity/i18n/AUTHORS.txt` has one new line, `Singularity 2030 (Serbian)`.

The graphics fixture used to call `set_language()` with no language, which follows the desktop. On this machine that is Serbian, so the first run of the suite translated the fixtures and 13 tests failed on English copy and on the widths of English labels. `tests/conftest.py` now pins `en_US`. The assertions are the same ones.

`msgfmt --check` is clean. The statistics lines are in Serbian because that is the locale `msgfmt` itself ran under:

```
353 преведене поруке.
25 преведених порука.
223 преведене поруке.
9 преведених порука.
```

The same four lines, twice: once for `lang_sr`, once for `lang_sr_Latn`. No errors.

`python3 utils/font_coverage.py` reports `sr` complete (134) and `sr_Latn` complete (90) for both 2030 faces and for Legacy-default's normal face. The script exits 1 because it measures the face named in `theme.dat`, which is still `acknowtt.ttf`. That face was already missing Russian. It now also reports `sr MISSING 61 of 134` and `sr_Latn MISSING 12 of 90 (ĆćČčĐđŠšŽž“„)`. The game does not use that face for Serbian. The coverage script cannot open `superstar_memesbruh03.ttf` (the file is signed, and fontTools rejects it), which is why the face the themes actually load is checked with pygame instead.

```
655 passed, 1 xpassed in 62.35s
```

No warnings line. `ALL HARNESS STEPS PASSED`. The `xfail` on `test_root_collation` is still there, and it still passes on this machine.

## 32. Window titles, a full set of translations, and Spanish from Spain

The 2030 header was drawing OPTIONS, LOG, KNOWLEDGE and the other window titles in English. The calls were already `_()`, but the strings were not in `messages.pot`, so gettext had nothing to return. They are in the catalog now, and the band translates them when it draws, from the English msgid kept on the dialog. A language change updates the title without rebuilding the screen. The log's "Double-click an entry to read it" was the same hole, one row under the LOG title, and it is in the catalog too.

The map button was `&RESEARCH/TASKS`. The English source is now `&RESEARCH`, and every catalog keeps the research half only. The hotkey marker stays. Serbian is `&ИСТРАЖИВАЊЕ` / `&ISTRAŽIVANJE`.

The red ending window was titled LOST. That title is only applied to the two loss stories, `Lost No Bases` and `Lost Suspicion`, which is the game being over. The English msgid is now `DEFEAT`. Serbian is `ПОРАЗ`, and the Latin catalog is that word through `recode-sr-latin` (`PORAZ`). `Base Lost Maintenance` is a base that fell apart, and that string is unchanged. The story ids stay as they are: they are keys, not the title.

Empty and fuzzy entries in the older catalogs are filled. Italian, Swedish and Argentine Spanish were almost empty in `messages.po`. French, Mexican Spanish, Brazilian Portuguese and Russian were missing the later UI and a block of newer data (the warehouses, the fuel cells, the synchrotron, the four discovery groups). Fuzzy plurals that already had a real translation were unfuzzy, so they show. The helper writes Serbian Cyrillic and rejects every other script, so those catalogs were filled directly. `lang_sr` titles went through the helper. `lang_sr_Latn` is the recode of those strings.

`lang_es_ES` is Spain Spanish, copied from the Mexican catalogs once those were complete and then adjusted: ordenador rather than computadora, and the adjectives that had to change gender with it. `es_AR` and `es_MX` stay. There is no `lang_es`. `language_searchlist()` would load that directory under every `es_*` code, and the options list would gain a Spanish row the country codes could not tell apart. With three `es_*` directories installed, `get_languages_list()` uses the full code, so the menu shows Español (Argentina), Español (España) and Español Mexicano. `languages.json` already had Español (España). No legacy theme had a Spanish name file, so none was added. `AUTHORS.txt` has `Singularity 2030 (Spanish)`.

One Mexican story page was still the English source, and the page before it was wearing that page's Spanish. Those two are back on the right paragraphs.

Dutch is finished as well: thirteen entries in `data_str.po` (the last four technologies had no text at all) and eleven window titles and screen names in `messages.po`. No entry in any shipped catalog is empty now.

`python3 utils/font_coverage.py`: both 2030 faces and Legacy-default's normal face are complete for every shipped language, including `es_ES` (94). The script still exits 1 because `theme.dat` names `acknowtt.ttf`. Spanish is complete in that face. Serbian is not, and the Serbian themes do not use it.

```
655 passed, 1 xpassed in 62.24s
```

No warnings line. `ALL HARNESS STEPS PASSED`. The `xfail` on `test_root_collation` is still there.

## 33. A shortcut works in either script

Serbian is written in two scripts, and Russian has the same split. The mnemonic is a letter of the translation (`&ИСТРАЖИВАЊЕ` is И). The key press is the character the active layout produced (`event.unicode`). Those were compared as two different strings, so a Latin `i` did not fire И, and a Cyrillic `р` did not fire R.

`hotkey_matches` in `button.py` is the comparison. Two letters match when they are the same letter, ignoring case, or a digraphia pair. The dialog looks the typed character up under that partner as well. If two buttons collapse onto one typed character, the first handler still wins. Digits, Enter, Escape, function keys and the cheat backtick are compared as they were.

Serbian Gaj, both ways, one letter: а a, б b, в v, г g, д d, ђ đ, е e, ж ž, з z, и i, ј j, к k, л l, м m, н n, о o, п p, р r, с s, т t, ћ ć, у u, ф f, х h, ц c, ч č, ш š. That includes the other case of the Latin letters, Đ đ, Ž ž, Č č, Ć ć, Š š. Russian adds й j and ы y, and shares the pairs above that are the same letter.

љ њ џ are not paired. Latin spells them lj, nj, dž, and pairing them with l, n or d would take those keys from л, н and д. A Latin layout cannot type љ as one key. ё э щ ю я ъ ь are not paired either: е already owns e, з owns z, и owns i, х owns h, and the rest are not one spare Latin letter. ж ц ч ш keep only the Serbian letters ž c č š, so they do not also answer to z or s.

```
2 failed, 659 passed, 1 xpassed in 64.68s (0:01:04)
```

No warnings line. `ALL HARNESS STEPS PASSED`. The two failures are `test_theme_fonts.py`: the 2030 faces cannot draw characters from catalogs this change did not add. The `xfail` on `test_root_collation` is still there.

## 34. ЦПЈ, прочеље, and Cyrillic in the language list

ЦПУ in the Serbian Cyrillic catalogs is now ЦПЈ (централна процесорска јединица). 31 strings: 28 in `messages.po`, 2 in `data_str.po`, 1 in `knowledge.po`. `story.po` had none, and there was no lowercase цпу. The matching Latin msgstrs say CPJ. They had said CPU because `recode-sr-latin` turns ЦПЈ's letters into C, P and U. `msgid` and `msgctxt` still say CPU. The hotkey is `&ЦПЈ` / `&CPJ`.

One of the sentences: "Одржавање је дневни трошак (и у новцу и у ЦПЈ) за поправку и одржавање базе."

The word for interface was интерфејс, in two strings. `&Интерфејс` is `&Прочеље`. "Јачина интерфејса" takes the genitive, so it is "Јачина прочеља". The Latin catalog is that through `recode-sr-latin`: `&Pročelje`, `Jačina pročelja`.

`lang_es_AR` and `lang_es_MX` are gone. `lang_es_ES` is the only Spanish catalog. There is still no `lang_es`. With one `es_*` directory, `get_languages_list()` looks the base code `es` up, and the row is Español. `languages.json` is unchanged. That lookup does not use `es_ES` when Spain is the only Spanish catalog, and the file is the name table for every code, not the list of catalogs we ship.

The language menu folds Cyrillic to Latin and then uses `lex_sorting_form`. The row reads "Native (English)": Српски (Serbian), Srpski (Serbian Latin), Русский (Russian). The English name is not decoration. The list is drawn in the face of whichever language is selected, and a player already in Japanese would otherwise see العربية and Русский as rows of boxes; the bracketed name is the part that stays readable whatever face is loaded. A name that is already English does not repeat itself, so the row is just English.

Sorting is taken from the native part alone, so adding the English name moved no row. Русский folds to Russkij, so it sits with R. Српски folds to Srpski, the same key as the Latin row, and the language code breaks the tie: Српски, then Srpski, next to each other. Tech names, knowledge entries and save names still sort with `lex_sorting_form` on the text itself. Greek, Arabic and the other non-Cyrillic names are not folded.

`languages.json` says `Serbian Latin` for `sr_Latn`, where it said `Serbian (Latin)`, which would have produced Srpski (Serbian (Latin)); the nested bracket was the wrong shape. Nothing else reads that file: `get_languages_list()` in `code/screens/options.py` is its only caller.

`singularity/i18n/AUTHORS.txt` keeps upstream's seventeen lines untouched, including the Mexican and Argentine credits (Eleazar Castellanos, eaglexboy, justapawn, and MestreLion for all three Spanish variants). Folding the two catalogs into `lang_es_ES` took the files away, not the people who wrote them: the text is still read in those countries, so the credit still belongs. `Singularity 2030 (Serbian)` and `Singularity 2030 (Spanish)` are appended below them. The fallback comment in `set_language` says `es_MX => es_ES`.

`po_lint_catalog` on the four Cyrillic catalogs: 0 errors. `messages.po` has 13 warnings that were already there, a hotkey label and the same word without the marker. The helper rejects `lang_sr_Latn` because it requires Cyrillic. `msgfmt --check` is what covers those files:

```
353 преведене поруке.
25 преведених порука.
237 преведених порука.
9 преведених порука.
353 преведене поруке.
25 преведених порука.
237 преведених порука.
9 преведених порука.
353 преведене поруке.
25 преведених порука.
237 преведених порука.
9 преведених порука.
```

Eight Serbian catalogs, then the four `lang_es_ES` catalogs. No errors.

```
2 failed, 659 passed, 1 xpassed in 64.84s (0:01:04)
```

No warnings line. `ALL HARNESS STEPS PASSED`. The two failures are the same `test_theme_fonts.py` pair as in section 33: the 2030 faces cannot draw the native names in untracked catalogs this change did not add. The `xfail` on `test_root_collation` is still there.

## 35. The wrapper drops stale bytecode before it starts Python

`run_singularity.sh` clears every `__pycache__` directory and every `.pyc` file under the checkout before it starts the game.

Python already invalidates a cached module whose source is newer, so this is not what makes an ordinary edit take effect. It covers the case that invalidation does not: a cache written by a different interpreter, one left behind by an interrupted run, or a tree that was copied and kept its timestamps. Those fail as an `ImportError` or, worse, as a module that is silently the previous version, and the fix is always to delete the cache. Doing it in the wrapper means it cannot be forgotten.

The cost is a walk of the tree on every start, which is why it belongs in the developer wrapper and not in the game. It touches only the checkout: saves, preferences and the `.mo` cache under the user's data directory are left alone.

Verified on a tree with caches present: both `find` commands exit 0 with no output, and nothing matching `*.pyc` or `__pycache__` is left. A launch afterwards starts clean. The suite is `827 passed, 1 xpassed` with no warnings line, and `ALL HARNESS STEPS PASSED`.

## 36. Russian buttons get their keyboard shortcuts back

A mnemonic in this game is not decoration. The `&` in a source string marks one letter of the translation, `HotkeyText._retranslate()` runs the *translated* text through `g.hotkey()`, and a text with no marker yields `key: ''`. The button then has no shortcut, no underlined letter, and nothing says so: it just quietly does not work by keyboard.

Every catalog kept the marker except Russian, which had dropped it in 37 entries: 31 in `lang_ru_RU/messages.po` and 6 in `lang_ru_RU/data_str.po` (the six difficulty names). Those 6 are live buttons too; `screens/main_menu.py` builds the difficulty dialog from `difficulties_str.dat`, so the `&` there matters as much as anywhere else.

The markers are back. Picking the letter is the actual work, because the game's dispatch is first-match-wins: `dialog.py` `call_handlers()` runs handlers in order and stops at the first one that raises `Handled`, which a button does. Two controls sharing a letter therefore is not a cosmetic problem, the later one is simply dead. That decided several entries:

- `&OPTIONS` -> `Н&АСТРОЙКИ` (а), not the first letter, because Н is `&NEW GAME` on the main menu and `&BACK` on the screen behind it.
- `&NEW BASE` -> `НОВАЯ &БАЗА` (б), because Н is `&BACK`, which the location screen always shows.
- `&Sound:` -> `Зв&ук:` (у), because the Audio tab is `&Звук` and is registered before the pane's own controls, so З would reach the tab and stop.
- `&KNOWLEDGE` -> `З&НАНИЯ` (н) and `LO&G` -> `&ЖУРНАЛ` (ж): З and Л already belong to map locations (`ЗАПРОСТРАНСТВО`, `ЛУНА`), which would have lost their shortcuts instead.
- `&INSPIRATION` -> `В&ДОХНОВЕНИЕ` (д): the cheat menu also has `EVENTS`, which has no Russian translation and falls back to the English msgid, and `hotkey_matches` treats Cyrillic `в` and Latin `v` as one key.

Two collisions were already there and are left alone, because they are not this change's business: `&OK` and the `&General` tab both claim О, and `&CONTINUE` and `&PAUSE` both claim П.

`tests/test_translations_hotkeys.py` now guards it, one case per `.po` (92 of them). It counts markers with `g.hotkey()` itself rather than a regex, so it agrees with the game, and it checks every non-empty plural form of a plural entry. It caught the six `data_str.po` ones that the first pass missed.

Verified: `msgfmt --check` clean on both files, 37 entries repaired and every one parses to the intended letter, and pressing each key on the real screen fires the control whose text carries it (options audio pane: `у` calls `mixer.set_sound(True)`, `з` only reaches the tab; map HUD: `н`, `ж`, `ч`, `м` each fire one control, and `з` is free for a location again). The suite is:

```
919 passed, 1 xpassed in 80.34s (0:01:20)
```

No warnings line, and `ALL HARNESS STEPS PASSED`.

## 37. The base is upstream's master

The fork sits directly on `99729e8`, which is upstream's `master`: 1.1 plus the
unreleased 1.1.1, from February 2026. There is no merge commit under this work.
`git log 99729e8..master` is this fork and nothing else, and the fork's own
commits are the six listed in §13.

An earlier draft of this work was written against `4df079f` from July 2022, and
bringing it forward meant merging upstream's 43 newer commits. That merge decided
three things by hand, and its conclusions are still in the tree:

- **The French catalogs.** Both sides had completed the French translation.
  Upstream's landed in `00bc1f9` and covers all 353 data strings; the fork's
  landed in `a67c5da`. The result is per entry: upstream's translation wins where
  it has one, the fork's fills the two entries upstream left empty, and the 16
  entries the fork's sources need and upstream does not have are kept.
- **`messages.pot`.** Upstream's, plus the same 16 entries, plus the About
  string this fork adds (§39).
- **Formatting.** Upstream adopted black in `98b3160`. The files this fork owns
  keep this fork's formatting. Black only moves code, so adopting it would have
  meant re-applying this fork's changes line by line for no change in behaviour,
  which the rules here forbid as a reformat for its own sake.

§40 records how that history became six commits, and what was checked afterwards.

## 38. The repository

`github.com/kostich/singularity` is `origin`, and it is a public fork of
`singularity/singularity`: GitHub records the parent, so the relationship between
the two projects is visible on the repository page itself and not only in this
file. Upstream's remote is deliberately not configured, so a stray `git push`
cannot reach `singularity/singularity`; add it as `upstream` if it is needed.

`master` is the only branch, and it is no longer a mirror of upstream: upstream's
commits are its base and everything above `99729e8` is this fork's.

GitHub Actions is enabled on the repository, and `.github/workflows/tests.yml`
is its only workflow. It triggers on a push to `master` and on a pull request
against it, and it does two jobs: the same two commands as the local gate on
Python 3.10 and 3.13, and a build that makes the sdist and the wheel, installs
the wheel into an empty virtualenv, checks that the game's data and translations
are really inside it, and starts the game from it. §41 has the detail.

One run happened before any of that, and it failed. Both matrix jobs failed on
the two fullscreen round-trip cases in `tests/test_layout.py`, with the running
window coming back as the desktop size instead of the chosen one: `(1024, 768)`
where the test wanted `(800, 600)`, and `(3440, 1440)` where it wanted
`(2560, 1370)`. Both pass here under the same `SDL_VIDEODRIVER=dummy`, and the
test sets `gg.desktop_size` itself. The worker's SDL is the difference: the
`pygame` wheel from PyPI carries its own SDL, the distribution package here
links the system one, and what that SDL does not do is shrink the surface back
when fullscreen is switched off. That was measured rather than argued: one
pygame version against SDL 2.28.4 (the wheel) and SDL 2.32.74 (the distribution
package) fails the two tests on the first and passes them on the second. The
tests now assert the request before `set_mode()` replaces it and check the
result against the surface, so an arithmetic bug still fails and a driver that
will not shrink no longer does.

CI is a second opinion, not the authority: the gate here runs the same suite on
3.15, which the workflow cannot install because pygame has no wheel for it. A
red badge with a green local run means the environments differ, and the run page
says where.

## 39. The hard fork: our name, our store page, our icon, our sandbox

Upstream and this fork are going in different directions, so the fork stopped
presenting itself as a slightly odd copy of upstream. It is a hard
fork: **Singularity 2030**, our repository, our store page, our icon, and an
About box that says so before it says anything else. What it must not do is
pretend the game is ours, so every credit, licence and translator entry that
was there is still there.

### The name

The "Endgame:" prefix is gone from every place a player reads a name. §1 has
the table. Three things kept it that are identifiers, not names: the import
package and console script `singularity`, the Flatpak app id
`io.github.singularity.Singularity2030` (renaming it orphans every installed
sandbox and the saves inside it), and the XDG data directories under
`~/.local/share/singularity`.

### The About box

Clicking About used to show upstream's text and nothing else, which on a fork
that no longer is upstream is a lie by omission: a player reporting a bug from
that box would write to people who do not have this code. It now shows two
parts:

1. a new `fork_message` `msgid`: this is an unofficial fork, not affiliated
   with the original authors, made to try out modernization ideas and keep the
   game playable on current systems, with this fork's source and tracker;
2. a line of `---` and the heading `THE ORIGINAL GAME AND ITS COMMUNITY`;
3. the original `about_message` `msgid`, byte for byte, still translated.

In the 2030 theme a line of only `---` is a horizontal rule
(`[dialog] rule = line`), so the two parts are separated by a drawn line; a
legacy theme draws three hyphens, which reads as a divider too.

The original `msgid` was not edited, and that is the whole trick. Adding our
name to its first line would have changed the string, every catalog in
`singularity/i18n/lang_*/` is keyed on the old one, and the About box would
have come out in English in all twenty-three languages. The fork says its own
thing in its own string instead, which is untranslated until someone
translates it, and that costs the player nothing they had before.

`tests/test_about.py` pins it: the fork paragraph comes first, our repository
is the only link in it, the rule and the heading are in order, every line of
the original message is still present and still in order, and the original
`msgid` has not been reworded.

### The icon

Two changes, both small on purpose: it should read as the same mark with a
difference, not as a new logo.

| change | before | after |
|---|---|---|
| the label's face | `Exo2-Bold.ttf`, the theme's display face in 2022 | `DejaVuSansMono-Bold.ttf`, the theme's `special` face today, the one the main menu's title is set in |
| the eyes | an upright 3.75 × 2.6 block, the original's | a slanted blade about 1.9 units thick, tilted 25° down toward the axis, same centre, same `#FF0000` |

The eyes are the fork's own mark now and still the brightest thing on the
plate, which is all the icon has to carry at 24px. The plate, the wedges, the
colours, the rounded corners and the composition are untouched, and the legacy
themes' icons are still byte-for-byte upstream's.

`--check` measures the result, and §16 has the tables:

```
rebuilt mark vs the original 32x32: shape IoU 0.882, eyes IoU 0.474
label metrics: cap height 0.210 of the icon, width 0.637
```

The shape figure is unchanged (0.882, because the wedges did not move). The
eyes figure dropped from 0.818 through 0.556 to 0.474, and it is worth being
exact about why, because it looks like drift and is not: 9 of the rebuilt's 10
bright pixels fall inside the original's 18 (90%), and the tenth is the
blade's inner tip, one pixel past the bottom of the original's block. The
figure falls because the eye is narrower than the block, which is the change.

One thing to expect after installing: launchers cache an icon by name, so the
old one can survive in a dock or an app grid until the icon cache is refreshed
or the session restarts. Nothing in the package can force that.

### Five screenshots

The store page had none, and a game with no pictures is a game a player scrolls
past. `utils/make_screenshots.py` renders five frames from the real game,
headlessly, and writes them to `flatpak/screenshots/`:

| file | what a player sees |
|---|---|
| `main-menu.png` | The title, the four buttons, the live console backdrop |
| `world-map.png` | The globe with the terminator down the Atlantic, three bases, and the HUD reading cash, CPU, suspicion and the clock |
| `research.png` | The research list with CPU sliders, `Advanced Microchip Design` selected, and that technology's plate above its description |
| `story.png` | The intro page the game opens with — *Hello, world* — in the story box, over the map |
| `about.png` | The About box: the fork statement, then the original game |

The research row is chosen by name, not by position: the first rows are the CPU
Pool and Jobs lessons, and the picture worth showing is a technology with its own
art and a paragraph about it. If that technology is ever renamed, the tool falls
back to the first technology row rather than failing.

Everything about the render is pinned: English (`set_language("en_US",
force=True)`, or the pictures come out in this machine's language), the 2030
theme only, seed 2030 for the first base and the start day, and 1366×768,
which is a resolution the game ships in and is 16:9, which is what AppStream
wants. The map's terminator is placed by setting `start_second` rather than
left to the wall clock, and the game is a few turns old instead of the
starting position, because "one stolen university computer and 2000 money" is
honest and reads as an empty screen.

One bug came out of writing it, and it would have shipped five pictures of the
wrong thing. A child screen draws into its own surface and the root composites
it, so calling the research screen's own `update()` before capturing cleared
its dirty flags and left the parent nothing to composite: `research.png` came
out byte-identical to `world-map.png`, at the right size, with real pixels in
it, and nothing would have noticed. `present()` now sets the flags and updates
the root only. `tests/test_flatpak_metadata.py` checks that the two files are
not blank, not that they differ, so the guard against a repeat is the comment
there and this paragraph.

The plate really is in the research frame: the picture strip is 532×118 with
11,895 distinct colours in it, and the text block under it has 243.

### The store page

`flatpak/io.github.singularity.Singularity2030.metainfo.xml` was rewritten. The
name is `Singularity 2030`, the summary says what the game is, the developer
line keeps Evil Mr Henry and Phil Bordelon and adds this fork's contributors,
the description opens with the game and then states plainly that this build is
an unofficial fork made for modernization and packaging, and homepage,
bugtracker and vcs-browser all point at `github.com/kostich/singularity`. The
five screenshots are captioned, and the first is `type="default"`.

The manifest skips `flatpak/screenshots` when it copies the source tree in:
AppStream fetches those pictures from the repository, the sandbox never reads
them, and they are about a megabyte of build input.

**The links are live.** The repository is public, so the homepage, the bug
tracker and the five `raw.githubusercontent.com` screenshot URLs resolve for
anyone, including software centers that check a page before showing it.
`rebuild-flatpak.sh` still validates with `--no-net`, because a build machine
without a connection should not fail on a network check it cannot pass; the
online validation is §40's business.

### What the sandbox may do

`--device=dri` is gone. Nothing in the game ever opened a GPU: pygame draws
plain software surfaces, the build never used WebGL or OpenGL surfaces, and
every device permission is one more line in a software center's warning and
one more thing to re-audit when a build breaks. What is left is what the game
actually uses:

```
[Context]
shared=ipc;
sockets=fallback-x11;pulseaudio;wayland;
```

`wayland` and `fallback-x11` are the screen, `ipc` is the shared memory the
X11 path resizes through, and `pulseaudio` is the soundtrack.

That last one is why GNOME Software still says "probably safe" and names the
microphone, and there is no way around it that keeps the sound: Flatpak has no
playback-only audio socket, so the socket a game needs for 17 tracks also
permits recording. The game records nothing, never calls into an input API,
and has no code that could. The alternative is shipping it silent, which was
not worth it; the reasoning is in the manifest next to the socket, in the
README's install section, and in the test that pins the socket list to exactly
these three.

### Tests

`tests/test_flatpak_metadata.py` parses the metainfo and checks the name, the
developer, the launchable, that every URL is this repository, that the
description still credits the original authors, that there are at least three
captioned screenshots with the first one `default`, that every screenshot maps
to a file in `flatpak/screenshots` and that no file there is left unshown, that
each is 1366×768 with real ink in it, that the `.desktop` `Name` agrees, and
that the manifest asks for no devices, no filesystem access and exactly the
three sockets above.

`tests/test_about.py` is described above. Neither file needed an existing test
weakened, and `tests/test_app_icon.py` passes unchanged with the new eyes and
the new face.

### Verified

```
$ SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy PYTHONPATH=. \
      python3 -m pytest -q tests/
940 passed, 1 xpassed in 79.97s (0:01:19)

$ python3 utils/make_app_icon.py --check
rebuilt mark vs the original 32x32: shape IoU 0.882, eyes IoU 0.474
label metrics: cap height 0.210 of the icon, width 0.637
... (the contrast and label tables are in §16)

$ SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy PYTHONPATH=. \
      python3 utils/make_screenshots.py
wrote flatpak/screenshots/main-menu.png         66998 bytes
wrote flatpak/screenshots/about.png            178826 bytes
wrote flatpak/screenshots/world-map.png        486510 bytes
wrote flatpak/screenshots/research.png         220170 bytes
wrote flatpak/screenshots/story.png            338247 bytes
```

The Flatpak was rebuilt from this tree and installed system-wide. The build
step ran here; the two `sudo` steps were run as root in the same checkout,
because this machine's `sudo` wants a password and the tool that ran the build
has no terminal to give it one:

```
$ ./rebuild-flatpak.sh
== flatpak Flatpak 1.18.4, flatpak-builder flatpak-builder-1.4.12
== validating the AppStream metadata
✔ Validation was successful: 1 valid
== org.freedesktop.Sdk//25.08 already installed
== org.freedesktop.Platform//25.08 already installed
== building io.github.singularity.Singularity2030
Installing the game into /app/lib/python3.13/site-packages
Soundtrack: 17 tracks
Running appstreamcli compose
Success!
Exporting io.github.singularity.Singularity2030 to repo
Commit: be826673f19952715e9e465df4676cce897f6108135ed09ba284da12644c92fc
== publishing to the system installation
sudo: a password is required
```

Then, as root and as the user, against the installed app:

```
$ flatpak info --system --show-permissions io.github.singularity.Singularity2030
[Context]
shared=ipc;
sockets=fallback-x11;pulseaudio;wayland;

$ flatpak run --command=python3 io.github.singularity.Singularity2030 -c ...
pygame 2.6.1 | SDL 2.28.4
numpy 2.5.4 | polib 1.2.0
package /app/lib/python3.13/site-packages/singularity/__init__.py

$ flatpak run io.github.singularity.Singularity2030 --help
help ok

$ env -u DISPLAY flatpak run --command=python3 ... -c 'print(get_driver())'
driver: wayland

soundtrack: 17 Ogg tracks installed
```

`devices=dri;` is gone from the context block, the name inside the deployed
metainfo is `Singularity 2030`, and the five screenshot URLs are in it.

## Licensing

Code is GPL-2+; data (images, soundtrack) is CC-BY-SA 3.0. The soundtrack is
for local play — do not fold it into any redistributable package without
honouring that licence.

Third-party assets, each with its licence committed beside it:

| what | where | licence |
|---|---|---|
| Lucide icons (`0.469.0`) | `2030/icons/` | ISC — `LICENSE`, `README.txt` |
| DejaVu Sans, DejaVu Sans Mono | `2030/fonts/` | Bitstream Vera + public domain — `LICENSE.txt` |
| Noto Sans Arabic, Bengali, Devanagari, CJK and Mono CJK | `2030/fonts/` | SIL OFL 1.1, as **Modified Versions** (subsets with DejaVu glyphs added), copyright line per family in `LICENSE.txt` |
| Exo 2 (no longer shipped, in history) | — | SIL OFL 1.1 |
| Krea-2-Turbo output: the dialog plates | `2030/images/dialog_*.jpg` | CC-BY-SA 3.0 like the rest of the data; generated locally, see `DESIGN.md` for model, seed and grade |
| Earth imagery | `Legacy-default/images/`, regraded into `2030/images/` | CC-BY-SA 3.0 — `LICENSE.CC-BY-SA-3.txt` |
| The application icon, all eight sizes | `flatpak/icons/`, `2030/images/icon.png` | CC-BY-SA 3.0, derived from upstream's mark — `LICENSE.txt` |
| The store page pictures | `flatpak/screenshots/` | CC-BY-SA 3.0, frames of the game — `LICENSE.txt` |
| `recursive_fix_pickle` | `singularity/code/savegame.py` | MIT, © 2015-2018 Jonathan Pyle — `LICENSE.txt` |

The icon pack is the one to check before swapping: this project is GPL-2+, so a
pack under GPL-3 or LGPL-3 (Papirus, Breeze) is not usable here regardless of
attribution, and ISC/MIT/Apache-2.0 are.

## 40. Six commits, the licence pass, and what is not in the tree

### The history

The fork's work was 218 commits written against `4df079f` from 2022 and merged
with upstream in 2026. On publication it became **six** commits on upstream's
current `master`, `99729e8`, grouped by the area each one changes (§13): the
Python 3 alignment, the display and dialog frame, the 2030 theme and its art, the
catalogs and tests, the fork's name, and the packaging. The tree was not edited
to make the split work; paths were grouped and committed.

The mechanics, because they matter if it has to be done again: the branch tip
was recorded (`53532ed`) and the whole git directory copied outside the tree
first; then `git reset --mixed 99729e8`, which moves the branch and the index and
leaves the working tree exactly as it was; then one `git add` per area and one
commit, with the gate run after each. Nothing was force-pushed, because the new
`master` is a fast-forward of `99729e8` — the base the public fork already had.

**What it costs.** The six commits are a curated history, not the 218 real ones.
`git blame` names the area that owns a line rather than the change that made it,
and a regression bisected into one of the six has to be found by reading that
area's diff. The old history is gone from the published branch. That is the price
of a readable `git log` on a repository strangers will read; the alternative was
214 commit messages written for their author and not for a reader.

### The licence pass

Everything third-party that ships here is now named in one file, `LICENSE.txt`,
with the licence and the notice beside the asset where one exists. Three gaps
were closed:

- it pointed at `LICENSE.gpl-2.txt`, which was never in the tree; the file is
  `LICENSE.gpl.txt`, and the pointer is fixed;
- the 2030 theme's own art — the plates, the icon set, the app icon, the store
  page pictures — was covered only by a blanket sentence about
  `singularity/data/`, which does not reach `flatpak/`. It is now named, and it
  is CC-BY-SA 3.0 like the rest of the artwork, with the app icon explicitly a
  derivative of upstream's mark and keeping its credit;
- `DESIGN.md` said nothing about the licence of the plates it governs. It does
  now, in one line, where a reader of that document will meet it.

One credit was also put back. Folding `lang_es_AR` and `lang_es_MX` into
`lang_es_ES` (§32-§34) had removed Eleazar Castellanos, eaglexboy and justapawn
from `singularity/i18n/AUTHORS.txt`, on the reasoning that their files were
gone. The translations are still read in Mexico and Argentina, so the credit is
still theirs; upstream's seventeen lines are untouched again, and this fork's two
are appended below them.

Two licence questions are worth stating rather than leaving to be argued:

- **The Noto faces are Modified Versions.** They are subsets with DejaVu glyphs
  added, which OFL 1.1 allows, and it asks that a modified font not use a
  Reserved Font Name. The CJK families reserve `Source`, not `Noto`; the file
  names and the copyright lines are recorded in `LICENSE.txt`.
- **The plates are model output**, generated locally with Krea-2-Turbo at a
  fixed seed, model and grade, all recorded in `DESIGN.md`. They are not scraped
  art and no third party's work is embedded in them. The licence statement says
  what they are and when they were made; it does not pretend to settle a legal
  argument nobody has had yet.

### What is not in the tree

A public repository is a place where a path or a model name is someone's
address, so nothing here names the machine this was developed on:

- no home directory in a command, a document or a tool's default. The gate's `cd`
  line is a comment, the art tool's master directory is `~/Pictures/...`, and
  `AGENTS.md` no longer carries a working copy's absolute path;
- no hardware model, card count or video memory figure. The generation timings
  say "an AMD ROCm machine, two cards", which is what the numbers need and no
  more; the tool's default for parallel jobs is a plain `DEVICES = 2`;
- no locale artefacts in a transcript. A pasted `sudo:` prompt and an
  `appstreamcli` verdict had been captured in the development machine's own
  language and are quoted in English;
- the screenshots are frames of the game. They contain no desktop, no window
  chrome, no username and no path, because the game renders into its own surface
  on a dummy video driver;
- the commits are authored as `kostich <4953862+kostich@users.noreply.github.com>`,
  GitHub's no-reply address for this account. It links each commit to the
  account exactly as a real address would, and keeps a personal mailbox out of
  `git log` forever.

Third-party e-mail addresses are untouched. They are in the catalogs and in
`AUTHORS.txt` because their authors put them there, and removing them would be
the opposite of crediting them.

### Verified

The gate on the published tree, and the two checks that only work now that the
repository is public:

```
$ SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy PYTHONPATH=. \
      python3 -m pytest -q tests/
940 passed, 1 xpassed

$ SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy PYTHONPATH=. \
      python3 utils/ui_smoke_test.py
ALL HARNESS STEPS PASSED

$ appstreamcli validate flatpak/io.github.singularity.Singularity2030.metainfo.xml
✔ Validation was successful: 1 valid

$ curl -sS -o /dev/null -w '%{http_code}\n' \
      https://raw.githubusercontent.com/kostich/singularity/master/flatpak/screenshots/main-menu.png
200
```

## 41. The pipeline builds the game, and says so

Three things were wrong here, and only the last one was about the test code.

**Nothing was reporting.** The workflow existed and Actions was enabled, but
there was no badge, so the state of the pipeline was only visible to someone
who went and looked at the Actions tab. `README.md` now carries the badge under
the title. It names `master` explicitly rather than inheriting the repository's
default branch, because that is the branch the workflow triggers on and a badge
with `?branch=` left off can quietly show nothing.

**It never built anything.** The job only ran the suite, so a wheel that installs
and then cannot find its own data was a failure nothing would catch: the suite
always runs from the checkout, where every file is there. The new `build` job
runs `python -m build`, installs the wheel into an empty virtualenv, and asserts
that `data/themes/2030/fonts/NotoSansCJK-JP.ttf`, `data/bases.dat`,
`i18n/languages.json` and `i18n/lang_sr/messages.po` are really inside it before
starting the game through the installed entry point. That check has teeth:
`MANIFEST.in` and `include_package_data` are the only things putting those files
in the wheel, and a wheel without them installs cleanly and draws nothing.

**The one run that did happen failed, and both failures were the tests measuring
SDL instead of this tree.** The two numbers from that log are:

```
(1024, 768)   where the test wanted (800, 600)
(3440, 1440)  where the test wanted (2560, 1370)
```

Both are the same claim: after a fullscreen round trip the window had the
desktop size. `test_set_screen_size_keeps_4_3_and_16_9_identity` makes that kind
of assertion without ever entering fullscreen, and it passed on that worker, so
creating a windowed window is honoured there. What is not honoured is shrinking
the surface back when fullscreen is switched off. So the two tests no longer
conflate the two things. Before `set_mode()` they assert `_requested_window_size`,
which is this tree's arithmetic; after it they assert that `window_size` equals
the surface SDL actually built.

That split is not a loosening, and it is checked three ways rather than argued.

The runner's condition turned out to be reproducible here. `pygame` is 2.6.1 on
both sides; what differs is the SDL it was built against. The wheel from PyPI
carries SDL 2.28.4, the Fedora package links SDL 2.32.74. Installing the wheel
in a 3.12 virtualenv, which is the closest thing to that worker available on
this machine, and running the *old* tests against it gives:

```
E       assert (1024, 768) == (800, 600)
E         At index 0 diff: 1024 != 800
E       assert (3440, 1440) == (2560, 1370)
E         At index 0 diff: 3440 != 2560
FAILED tests/test_layout.py::test_fullscreen_round_trip_restores_the_chosen_window
FAILED tests/test_layout.py::test_resolution_changed_while_fullscreen_is_remembered
2 failed, 56 passed in 0.15s
```

Those are the two numbers from the GitHub log, character for character. With the
rewritten tests on that same SDL 2.28.4:

```
$ SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy PYTHONPATH=. \
      /tmp/ci312/bin/python -m pytest -q tests/
940 passed, 1 xpassed in 59.50s

$ ... /tmp/ci312/bin/python utils/ui_smoke_test.py
ALL HARNESS STEPS PASSED
```

And the guard still bites: with `compute_window_size()` broken to return the
desktop for a windowed request, both tests fail again with the numbers above, on
either SDL. So nothing else in the suite is sensitive to that SDL difference
either: 940 tests, both environments.

Smaller things in the same file: a push and a pull request against `master` both
trigger it, plus a manual run from the Actions tab; the token is read-only; a
newer push to the same ref cancels the older run; each job is capped at twenty
minutes; pip is cached against `pyproject.toml` and `setup.py`; the actions are
on `checkout@v5`, `setup-python@v6` and `upload-artifact@v6` because the
Node 20 ones are deprecated on a runner that now forces Node 24, and those are
the first tags of each that target Node 24; and the built files are kept as an
artifact. One step only prints versions — `python`, `pygame` with its SDL,
`numpy`, `polib` — because that is precisely what the runner had and this
machine did not, and reading it off a log beats repeating the afternoon that
went into working it out.

Verified here first, before any of it was pushed:

```
$ python3 -m build
Successfully built singularity_2030-1.0.tar.gz and singularity_2030-1.0-py3-none-any.whl

$ # the six data paths, read back out of the wheel
OK   data/themes/2030/theme.dat
OK   data/themes/2030/fonts/DejaVuSans.ttf
OK   data/themes/2030/fonts/NotoSansCJK-JP.ttf
OK   data/bases.dat
OK   i18n/languages.json
OK   i18n/lang_sr/messages.po

$ /tmp/installed/bin/singularity --version
Singularity 2030 1.00 (commit: N/A)

$ SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy PYTHONPATH=. \
      python3 -m pytest -q tests/
940 passed, 1 xpassed in 80.10s (0:01:20)

$ SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy PYTHONPATH=. \
      python3 utils/ui_smoke_test.py
ALL HARNESS STEPS PASSED
```

The wheel install here used the distribution's pygame, because there is still no
pygame wheel for 3.15; the `build` job uses 3.13, where there is one.

Then the run itself, on the push that landed this (`946a82a`), which is the
whole point of the exercise and the first evidence about a runner that is
better than inference:

```
workflow : tests
run      : 2
branch   : master
event    : push
status   : completed / success

JOB build          -> success
   ok   Build the sdist and the wheel
   ok   Install the wheel somewhere clean, and start the game
   ok   Keep the built files

JOB tests (py3.10) -> success
   ok   Unit tests
   ok   Headless UI harness

JOB tests (py3.13) -> success
   ok   Unit tests
   ok   Headless UI harness

$ curl .../actions/workflows/tests.yml/badge.svg?branch=master
<title>tests - passing</title>
```

The warning that run still carried — `upload-artifact@v5` targeting Node 20 —
is what moved that one tag to `v6`. The other two tags were already clean. A
`notice` about `ubuntu-latest` migrating to Ubuntu 26 is informational and needs
nothing.
