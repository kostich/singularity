# Upstream's open issues, read against this fork

Snapshot of **Sunday, 2026-11-08**. Every one of the 49 open issues on
[`singularity/singularity`](https://github.com/singularity/singularity/issues)
was read, not summarised, and judged against *this* tree. Re-check with:

```sh
gh issue list --repo singularity/singularity --state open --limit 400
```

This is a snapshot, not a promise. Upstream may close or re-scope any of these
tomorrow; what follows is only the answer to "is there anything in there we
should act on?", asked on that date.

## The answer in one line

Two. **#233** (a rounded percentage drawn with two decimals) and **#283**
(`recalc_cpu()` could leave a CPU pool over-committed, which froze the research
screen's sliders). Both are fixed on `modernization` — §20 and §21 of
`MODERNIZATION.md`. Everything else is either already dead in this environment,
a deliberate difference, or a request this fork's rules rule out.

The three crash reports are worth a word, since they are the ones that look
urgent. **#343** (a `pygame_parachute` segfault) and **#326** (Sway/Xwayland)
are pygame 2.0–2.4 bugs: #326's own thread ends with "upgrading to pygame 2.5.2
appears to stop the crashing for sway", and #343's with the same advice. This
branch runs pygame 2.6.1 on SDL 2.32.74. **#316** is macOS only and **#307** is
an SDL_image built without PNG support — the reporter's own
`pygame.image.get_extended()` returned `True` while the loader still failed,
which is a distro build problem, not ours.

## Verdicts

| # | opened | labels | what it asks | verdict | evidence |
|---|---|---|---|---|---|
| 367 | 2026-07-19 | – | small icons beside UI labels | feature | the icon set is already this fork's own (§16) |
| 349 | 2025-01-26 | – | more story snippets in research results | feature | story text is frozen by rule |
| 343 | 2024-06-24 | bug, crash | segfault / freeze during play | environment | pygame 2.6.1, SDL 2.32.74; thread: pre-2.5 pygame crashes |
| 340 | 2024-06-16 | – | Linux AppImage | packaging | out of scope |
| 337 | 2024-02-01 | enhancement | update credits and attribution | by decision | `AUTHORS.txt` is untouched by rule |
| 331 | 2023-07-30 | enhancement | auto-save: feedback, frequency, slots | feature | upstream v1.1 `915a7ea2`; `grep autosave` → no match here |
| 329 | 2023-07-04 | – | publish on Steam and elsewhere | packaging | out of scope |
| 326 | 2022-08-30 | bug, crash | crash under Sway/Wayland | environment | thread: "pygame 2.5.2 appears to stop the crashing" |
| 322 | 2022-04-11 | bug | music needs proprietary tools to rebuild | by decision | `singularity/music/` is a submodule, untouched by rule |
| 320 | 2022-01-18 | – | upload to PyPI | packaging | out of scope |
| 319 | 2022-01-07 | enhancement | five more music tracks | feature | data, and the soundtrack is not ours to extend |
| 316 | 2021-10-03 | bug, crash | crash on macOS at max speed | environment | not this platform |
| 307 | 2021-08-30 | bug, crash | `Unsupported image format` on the default theme | environment | SDL_image without PNG; loads fine here |
| 303 | 2021-08-14 | – | script that installs the Python packages | packaging | out of scope |
| 300 | 2021-05-12 | enhancement | graphs of money and CPU over time | feature | the 24 h projection already answers the question |
| 299 | 2021-05-12 | enhancement | show a tech's results before committing | feature | changes what the game tells you |
| 294 | 2020-08-05 | enhancement | spend cash on what is closest to done | feature | gameplay |
| 285 | 2020-06-21 | enhancement | Ctrl-S quicksave, and feedback that it saved | feature | upstream F5 quicksave `ec0ce8b2`, v1.1; `grep quicksave` → no match here |
| **283** | 2020-06-11 | bug | research/tasks settings become unsettable | **fixed here** | `player.py:499-522`, `tests/test_cpu_allocation.py` — §21 |
| 278 | 2020-06-06 | enhancement | mention the AUR package in the README | packaging | out of scope |
| 277 | 2020-06-06 | bug | submodule `git@` URL breaks packagers | by decision | `.gitmodules` is off-limits by rule |
| 276 | 2020-06-06 | enhancement | ship the music via `setup.py` | packaging | licensing, and a submodule |
| 234 | 2020-03-16 | bug | hotkeys vs. a focused text field | by decision | accelerators are already hidden; Enter/Esc confirm — see below |
| **233** | 2020-03-16 | bug | two decimals on a rounded percentage | **fixed here** | `screens/map.py:1156-1161`, `tests/test_hud_precision.py` — §20 |
| 224 | 2020-03-08 | bug | hotkeys are eaten by the load-screen filter | by decision | upstream hid the markers (`f72e83bf0`); ours carry none — see below |
| 204 | 2019-12-15 | – | the HUD's "flow rates" are not rates | by decision | it is a 24 h projection under optimal conditions — see below |
| 185 | 2019-08-20 | enhancement | rename and expand techs and items | feature | content is frozen |
| 146 | 2019-02-10 | enhancement | autobuild items in a base | feature | merged upstream after 1.00 (PR 214) |
| 124 | 2019-01-06 | enhancement | difficulty that scales with time | feature | balance |
| 121 | 2018-12-29 | enhancement | a solar map instead of edge-of-earth | feature | gameplay |
| 109 | 2018-08-21 | bug | ampersand hotkeys missing from Russian | by decision | catalogs are frozen by rule |
| 106 | 2018-08-20 | enhancement | split the ocean into named regions | feature | data |
| 99 | 2018-07-20 | help wanted | a font covering every translated glyph | by decision | `utils/font_coverage.py` measures what ships |
| 97 | 2018-07-19 | balance | `roll_chance` uses the wrong model | obsolete | `roll_chance` is gone; `code/chance.py` already rolls Poisson |
| 91 | 2018-07-11 | – | stolen computer time and the early story | feature | content |
| 86 | 2018-06-29 | enhancement | arcade *and* realistic detection models | feature | balance |
| 84 | 2018-06-26 | enhancement | hacked bases | feature | gameplay |
| 79 | 2018-06-19 | enhancement | interactive, timed events | feature | gameplay |
| 77 | 2018-06-19 | enhancement | parallel, riskier job types | feature | gameplay |
| 76 | 2018-06-19 | enhancement | more scenarios and endings | feature | content |
| 75 | 2018-06-18 | balance | rebalance items, bases and CPU costs | feature | balance |
| 69 | 2018-06-01 | enhancement | jobs should lose efficacy as they grow | feature | balance |
| 68 | 2018-05-31 | enhancement | a "far reaches" ending | feature | content |
| 66 | 2018-05-31 | enhancement | a robot workforce instead of money | feature | a different game |
| 55 | 2018-04-22 | – | Milestone 2.0 (Python 3, SDL2) | obsolete | this branch is long past it |
| 54 | 2018-04-21 | enhancement | remove the CPU pool | feature | a different game |
| 45 | 2018-03-31 | bug | completion time ignores holds and cash | obsolete | there is no completion-time indicator here (`grep` → only `CPU per day`) |
| 35 | 2017-12-27 | enhancement | multiple item types, a power grid | feature | gameplay |
| 20 | 2017-05-08 | enhancement | self-destruct and other base defences | feature | balance; the thread itself concludes the game is winnable |

## The decisions, so they are not re-litigated

Four of these look like bugs and are not going to be treated as ones.

**#224 / #234, hotkeys versus a text field.** The conflict is real and
structural: with a filter field on the Load screen, a letter is either a
hotkey or a character. Upstream's remedy was to stop *showing* the
accelerators, and our buttons are plain `N_("Upgrade")` / `N_("Delete")` with no
`&`, so nothing on screen promises a key that will not work; `screens/savegame.py:100`
hands every key to the field and `graphics/text.py:1150-1152` swallows printable
characters whether the field has focus or not. Enter and Escape still confirm
and cancel. Changing that would be a new focus model for every screen with a
field — an interface redesign, not a repair, and this fork's rule is
behaviour-preserving.

**#204, the HUD's cash and CPU "flow rates".** `compute_future_resource_flow()`
projects the next 24 in-game hours under optimal conditions and the HUD prints
the difference (`player.py:725-735`, `screens/map.py:1074-1079`). The report
wants the momentary drain instead. Both are defensible; the shipped one is what
every player of 1.00 has read for years, and redefining it changes the reading,
so it stays, with this note.

**#285 / #331, quicksave and autosave.** Neither exists in this tree at all
(`grep -E 'autosave|auto_save|quicksave'` finds nothing); upstream added them in
v1.1, after the commit this branch starts from. Adding autosave would change
what the game writes and when — a save-behaviour change, which is exactly what
this fork does not do.

**#97, the detection model.** The helper the report names no longer exists;
`singularity/code/chance.py` rolls occurrences with the Poisson distribution
and explains why in a comment, which is what the report was asking for.

## What the two fixes were

**#233** — `screens/map.py` rounded the suspicion to the nearest 5 % and then
passed `show_full=True` to `g.to_percent()`, forcing `%.2f`: 5.23 % was drawn
as `5.00 %`. The rounded branch now lets `to_percent()` decide from the value
it is given; the `full` branch keeps its two decimals, because there they are
real. §20.

**#283** — `Player.recalc_cpu()` scaled the tasks at each danger by
`available / the pool's whole demand`, which leaves `h + o·a/(h+o)` against a
pool of `a` — over-committed whenever the branch runs, so `calc_cpu_left()` went
negative and the research screen's sliders were built with their maximum below
their position. The pools are now walked from the tightest down and each danger
gets the pool minus what the dangers above it hold. §21.

The savegame attached to #283 was audited before it was loaded — the zip holds
one stored member with no paths in it, and the member is the JSON format
(`singularity_savefile_100` header, gzip, 60,716 bytes of JSON), not a pickle,
so it is parsed by `gzip` and `json` and no unpickler is involved. It was still
loaded in a `bubblewrap` sandbox, by explicit path, with no network and the host
home hidden. It turned out to be the state *after* the loss — `available_cpus`
all zero, every allocation zeroed — so it cannot reproduce; the reproducer that
ships is built from the game's own classes instead. The whole measurement is in
§21.
