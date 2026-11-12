# DESIGN.md — the rules for the dialog plates

This is the style contract for the pictures the game shows at the top of a
scenario dialog: a finished tech, a built item, a base type, an event, a story
page, a warning, a danger level. It exists so that a second person, or a
language model, can add a plate that belongs to the set without reading the
generator's source.

The generator is `utils/make_dialog_art.py` and it is the authority. Where this
document and the script disagree, the script is right and this document is a
bug.

The plates are part of the game's data and are CC-BY-SA 3.0 with the rest of
it; `LICENSE.txt` says so in the artwork section.

## The one rule

**No two situations share a picture.**

A plate is the reward for reaching a situation. The player who has just spent
forty minutes on `Quantum Computing` should get a different picture from the one
who finished `Arbitrage`, and both should be different from the picture that
appears when a base is lost. Reusing one picture across a family is the failure
mode this whole document exists to prevent: it turns a gift into chrome.

The corollary is the naming rule. A plate's filename is the art key the game
asks for, and the key is built from the **data id** in `techs.dat`,
`items.dat`, `bases.dat`, `groups.dat`, `events.dat` or `story.dat` — never from
the displayed name, because a name is translated and a picture is not.

```
dialog_tech_quantum_computing      [Quantum Computing] in techs.dat
dialog_item_quantum_computer_mk2   [Quantum Computer MK2] in items.dat
dialog_base_undersea_lab           [Undersea Lab] in bases.dat
dialog_event_the_plague            [the-plague] in events.dat
dialog_story_intro_3               the third page of [Intro] in story.dat
dialog_warning_cpu_maintenance     "cpu_maintenance" in warning.py
dialog_danger_2                    [danger_2] in dangers_str.dat
```

The slug rule is: lowercase; every run of non-alphanumeric characters becomes
one `_`; no leading or trailing `_`. So `Project: Impossibility Theorem` is
`project_impossibility_theorem`, with **one** underscore, and
`Exploit Discovery/Repair` is `exploit_discovery_repair`.

The danger family has one exception, and it is deliberate. `danger_0` is the
"study anywhere" level and its research text is `<<This text should not
appear>>`; the game only reveals the help button for a danger above zero, so
level 0 is the one danger with **no plate**. A `dialog_danger_0` in the
inventory would mean the art had drifted from the data file.

## Which dialog draws which plate

Having a plate and showing it are two different jobs, and the second one is
where this set was actually broken: 139 plates existed and a player still saw
the generic server rack, because three dialogs asked for `dialog_message`
whatever had happened. This table is the wiring, and any new scenario dialog
belongs in it:

| dialog | plate | fallbacks |
|---|---|---|
| an event fires (`player.trigger_event`) | `dialog_event_<event id>` | `dialog_message_list` |
| a base is lost or found (`player.remove_bases`) | the log message's own key | the message's own chain |
| a log entry, double-clicked | `log_message.art_key` | `log_message.art_fallbacks` |
| a warning (`Warning` list) | `dialog_warning_<id>` | `dialog_warning`, `dialog_message_list` |
| a danger level's `?` (research screen) | `dialog_danger_<n>` | `dialog_danger`, `dialog_message` |
| a story page | `dialog_story_<section>_<page>` | `dialog_story_<section>`, `dialog_story` |
| a knowledge entry | `dialog_tech_`, `dialog_base_` or `dialog_item_` for those sections; `dialog_knowledge_<id>` for a concept | `dialog_placeholder` when the list is empty |
| anything else | `dialog_message` | — |

A message object carries `art_key` and `art_fallbacks` (`logmessage.py`), so a
dialog that shows a message should ask the message rather than name a plate
itself. The art key is never derived from translated text.

The knowledge screen is not a message dialog. Its description pane shows the
plate for the entry being read, at the top of that pane, and only in the 2030
layout. A concept entry is written in `knowledge_str.dat` as `areas_list`
because a `_list` value is a name and a description; the loader strips the
suffix, and the plate is `dialog_knowledge_areas`.

The research screen's description pane does the same in the 2030 layout, with the same strip. A tech uses `dialog_tech_<id>`. CPU Pool uses `dialog_knowledge_processors` and Jobs uses `dialog_knowledge_jobs`, the plates the knowledge screen already has.

A 2030 window frame is cyan. A warning uses the amber `dialog_warning_edge`, `dialog_warning_glow` and `dialog_warning_text`, and its hull and header band are the dark amber `dialog_warning_fill` and `dialog_warning_header`. A base discovered, a base lost to maintenance, and the two death story sections (`Lost No Bases`, `Lost Suspicion`) use the red `dialog_alert_edge`, `dialog_alert_glow` and `dialog_alert_text`, with `dialog_alert_fill` and `dialog_alert_header` for the hull and the band. Text, buttons and the picture stay as they are. Legacy frames are unchanged.

## Point of view

The player **is** the AI. It has no body, no hands, and no camera; every plate
is what it sees through hardware it has taken over, or what it is imagining
while it thinks about a problem.

That gives one rule for people: **humans appear only as silhouettes, backs,
hands, or reflections in glass — never a face, never a portrait, never a hero
shot.** The AI does not know what a person looks like from the front, and a
plate with a character in it turns the player into an observer of somebody
else's story.

Prefer the *place* over the event: a data centre aisle, a rooftop array, an
undersea capsule, a campus laboratory at 3 a.m., a downlink dish on a ridge.
The subject is hardware, weather, light and emptiness.

## The shared style block

Every prompt is built as:

```
<COMPOSITION>, <the situation's own sentence>, <STYLE>
```

with these two literals, verbatim, from the script:

```
COMPOSITION
wide panoramic establishing shot, all subject matter in a horizontal band
through the centre of the frame, generous empty dark space above and deep
shadow below

STYLE
cinematic sci-fi concept art, dark teal and cyan instrument lighting, one small
warm amber light source, volumetric haze, 35 mm anamorphic, shallow depth of
field, fine film grain, desaturated, no people's faces, no text, no lettering,
no logos, no user interface, no watermark
```

Do not paraphrase either. They are the reason 156 separate generations read as
one collaboration: the same lens, the same light, the same degree of detail, and
the same list of things that must not appear. The negative list matters more
than it looks — a diffusion model asked for "a server room" will happily letter
`SERVER ROOM` on the wall, and text inside this game's own art reads as a
rendering bug.

## Composition: only the middle band survives

The master is **1920×1080**. The plate is **1920×480**, which is the centre band
of the master — a 4:1 crop, chosen because the banner the game draws is about
4.5:1 at every supported window size. Cropping 1080 to 480 throws away 300
rows above and 300 below: **the top and bottom 28% of every master is deleted.**

- Put the subject in the middle 44%.
- Let the top be empty dark space and the bottom be shadow. Asking for
  something there is asking for waste.
- Everything that carries meaning — the one lit window, the pointed dish, the
  amber lamp — must be inside that band or it will not exist.

The crop is exact, so nothing is resampled between the master and the file, and
a 1920-wide plate covers a 4K display at 1:1.

## Palette

The grade **tints** every plate toward one palette, the theme's own, from
`singularity/data/themes/2030/theme.dat`:

| role | value | where it comes from |
|---|---|---|
| void | `#04080F` | `ui_void` |
| panel | `#0A1622` | `ui_panel` |
| edge | `#2C6A82` | `ui_edge` |
| highlight | `#5FE3FF` | `ui_edge_bright` |
| the one warm light | `#FFD696` | `dialog_plate_text` family, amber stop |

The tint is **12%**. It is not a desaturation and it does not replace hue: the
tone curve is applied to luminance and each pixel is scaled by the ratio, which
leaves every colour where the model put it. What the set shares is a cast, a
vignette, a raster and a grain -- not a palette manufactured out of the pictures.

That distinction is the important one, and it was learned by getting it wrong.
The first version put every plate *through* the ramp, which replaced 72% of each
picture with theme teal; the set was beautifully consistent and had lost its
subjects. A red warning with no red, a lunar base whose Earth was no longer blue,
fusion plasma without its pink, a gaming case without its purple. If you are
tempted to raise `TINT` because a plate looks off-style, look at the picture
first: what reads as off-style is usually a scene that needs a better brief, not
a picture that needs more filtering.

Warm light is the one thing the grade pushes: a genuinely warm pixel is
**brightened** by up to 22% rather than repainted, so a furnace stays orange and
a sodium lamp stays yellow, and the picture keeps the one accent that stops it
being all-blue. If a prompt has no warm light at all the plate reads flatter than
its neighbours -- add a lamp, a monitor, a fire, a street light. Do not paint the
palette into the prompt: ask for the *scene*, because the grade is the palette.

## Legibility: never outshine the text

Body text in this theme is `#D7ECF6`, luminance **0.911**. No plate may reach
it: a brighter picture turns the paragraph under it into an afterthought, and the
text is the game. The grade rolls highlights off with a soft knee from **0.62**
and then clamps final luminance at `0.78 - 0.06`. The subtraction is measured,
not defensive: a plate clamped to 0.78 in memory came back at **0.834** from the
JPEG writer, because chroma subsampling rings a hard edge. A ceiling that holds
only before compression is not a ceiling.

Measured on the shipped set of **156**: peak **0.769**
(`dialog_base_storage_unit`), mean **0.117-0.333**. The dark end is the black
skyline (`dialog_knowledge_death`, mean 0.117). The placeholder sits just above
it (mean 0.131), still empty on purpose, so it is not mistaken for a scene.

## Generation settings

Measured on an AMD ROCm machine, two cards, Krea-2-Turbo Q8:

```sh
krea.sh "<prompt>" 1920 1080 24 2030      # ~163 s per plate
```

| setting | value | why |
|---|---|---|
| size | **1920×1080** | the crop to 1920×480 is then exact |
| steps | **24** | the model is a turbo: 8–12 is its design point, 32 spends time without adding coherence, 24 buys a little without the over-sharpened late-schedule look |
| seed | **2030, every plate** | one latent family, and any plate can be regenerated byte-for-byte |
| cfg | 1.0 | the model ignores negatives, so the prompt does all the work |
| width note | 2560×1440 was tried and rejected | twice the time, and three quarters of the extra pixels are cropped away |

Two cards render two plates at once at no per-step cost, and the same prompt and
seed produce **byte-identical files** on either card, so which card drew a plate
does not matter.

## The pipeline, and why the grade is not optional

```
master 1920x1080  ->  centre band 1920x480  ->  grade  ->  JPEG q88
```

The grade, in order, every plate, deterministically:

1. exposure `0.80` (a fixed lift; generated night scenes are darker than they
   look on a monitor);
2. the tone curve, applied to **luminance only** -- each pixel is scaled by
   `target_luminance / current_luminance`, a pure brightness change that cannot
   alter hue or saturation;
3. the palette mixed in at **12%**, toward the ramp's colour for that luminance;
4. saturation **x1.20** around each pixel's own luminance, because a tint costs
   chroma and these are not meant to look washed out;
5. genuinely warm pixels brightened by up to 22% -- never repainted;
6. a horizontal-only vignette at 14% (a radial one on a 4:1 strip eats the ends);
7. scanlines at 94% on every third row -- the same rhythm as the placeholder and
   the button hover, so the picture belongs to the same machine as the panel;
8. seeded grain, ±0.015, which also hides the upscale on a 4K display;
9. a luminance clamp at `0.78 - 0.06`, below the text and with the writer's own
   overshoot accounted for.

Measured across the 144 plates that were in the set when the grade settled:
mean chroma **0.083**, and the worst
plate-to-master chroma ratio is **0.85** -- so the grade preserves colour rather
than merely keeping some, and **no** plate loses more than a third of its own.

Skipping the grade is what makes a set look like unrelated renders. It is a
few hundred milliseconds per plate and it is applied by
`utils/make_dialog_art.py --import`, never by hand.

## Adding a situation

1. Add the brief to the right table in `utils/make_dialog_art.py` — a comma
   clause describing the *scene*, not the mechanic. `dialog_tech_atmospheric_processing`
   is "cooling towers exhaling into a cold dawn", not "atmospheric processing".
   The data-driven families (tech, item, base, group, item type, event, story,
   danger) otherwise need nothing: a new `[section]` in the data file is a
   `MISSING BRIEF` until it has one, and `danger_0` is the only level excluded
   by name.
2. `python3 utils/make_dialog_art.py --list | grep dialog_` — it must appear with
   no `MISSING BRIEF` and no `ORPHAN BRIEF`.
3. `python3 utils/make_dialog_art.py --prompt dialog_your_key` and read the
   prompt. If it does not describe something a camera could stand in front of,
   rewrite the brief.
4. `python3 utils/make_dialog_art.py --generate --only dialog_your` (resumable;
   existing masters are skipped).
5. `python3 utils/make_dialog_art.py --import --only dialog_your`.
6. `python3 utils/make_dialog_art.py --contact-sheet /tmp/plates.png` and look
   at the new plate **next to its neighbours**. That is the only check that
   matters and the only one no script can do.
7. `python3 utils/make_dialog_art.py --check` — size, luminance, and a
   similarity score proving no two plates are the same picture. It compares
   *content*, not brightness: each plate is reduced to a 64×16 high-passed
   luminance thumbnail, so the dark frame and the vignette that every plate
   shares cancel out. Unrelated plates score at most about 0.62, the median
   pair is 0.07, and the same picture twice scores 1.0 — so anything at 0.95 or
   above is a failure. It also prints the closest pair, which is the number
   worth watching as the set grows.

## Provenance

Every plate is generated locally by `sd-cli` (stable-diffusion.cpp) with
Krea-2-Turbo Q8 at seed 2030, 24 steps, 1920×1080, and graded by the script
above. The master is kept outside the repository at
`~/Слике/krea/masters/<art-key>.png`; the committed file is the graded
1920×480 JPEG. Reproducing the set is `--generate` followed by `--import`, and
it needs no network.
