#!/usr/bin/env python3
"""The dialog plates: one picture per situation, generated and graded.

Every scenario dialog in the game can show a picture (see MODERNIZATION.md,
"The picture banner, and where art goes"). A dialog names a key, the theme
looks it up in its `images/` directory, and a file that is not there falls back
to the static placeholder. This script is what produces those files.

The point of it is that **no two situations share a plate**. A finished tech, a
built item, a base type, an event, a story page and a warning each get their
own picture, because the picture is the reward for reaching that situation. The
inventory is therefore derived from the data files rather than written out by
hand: add a line to `techs.dat` and `--check` says a plate is missing.

What makes 138 separate generations read as one collaboration is not the model,
it is the pipeline around it:

    master 1920x1080  ->  centre band 1920x480  ->  grade  ->  JPEG

The crop is exact: a 16:9 master cropped to 4:1 is 1920x480 with no resampling,
and the banner the game draws is about 4.5:1 at every window size it supports,
so the plate lands at 1:1 or better from 1024x768 up to 4K. The grade -- one
fixed ramp into the theme's own palette, a vignette, scanlines every third row,
grain, and a hard luminance knee -- is applied identically to every plate, which
is what actually makes them look like a set.

The settings were measured on an AMD ROCm machine, one card per process:

    1024x1024   8 steps   30 s
    2560x1440  32 steps  478 s
    1920x1080  24 steps  ~200 s

2560x1440 was tried first and rejected: it costs twice the time of 1920x1080
and three quarters of the extra pixels are thrown away by the crop. The seed is
fixed at 2030 for every plate. Steps are 24: the model is a turbo, so 8-12 is
its design point and 32 only spends time; 24 buys a little extra coherence
without the over-sharpened, over-saturated look that distilled models get late
in a long schedule.

Art is not committed from here directly -- `--import` copies graded masters into
the theme, so a re-run of the pipeline produces byte-identical files.

    python3 utils/make_dialog_art.py --list             # the inventory
    python3 utils/make_dialog_art.py --prompt KEY        # one prompt, verbatim
    python3 utils/make_dialog_art.py --generate         # render missing masters
    python3 utils/make_dialog_art.py --import           # grade + crop into theme
    python3 utils/make_dialog_art.py --contact-sheet f  # one sheet for review
    python3 utils/make_dialog_art.py --check            # what the gate runs

Only pygame and NumPy are required, the same two the game already needs.
Pillow is used for JPEG writing when installed and SDL's writer otherwise, as
in `make_2030_art.py`.
"""

import argparse
import hashlib
import os
import subprocess
import sys
import time

import numpy as np
import pygame

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(REPO_ROOT, "singularity", "data")
THEME = os.path.join(DATA, "themes", "2030")
IMAGES = os.path.join(THEME, "images")

# Where ungraded masters live. Deliberately outside the repository: they are
# 3 MB each, they are inputs to the pipeline rather than the pipeline's output,
# and the committed plate is what ships.
MASTERS = os.environ.get("ART_MASTERS",
                         os.path.expanduser("~/Pictures/krea/masters"))

# The master and the plate. 1920x1080 cropped to 4:1 is 1920x480 exactly, so
# nothing is resampled between the crop and the file.
MASTER_SIZE = (1920, 1080)
PLATE_SIZE = (1920, 480)

# Measured, not guessed; see the module docstring.
STEPS = 24
SEED = 2030

# How many rendering processes to run at once: one per card. Two is twice the
# throughput for the same wall clock, because a process never spans cards. Each
# one needs about 18 GB of video memory (13.6 GB for the diffusion model, 4.2
# for the text encoder), so a smaller card renders one plate at a time.
DEVICES = 2

KREA_SH = os.environ.get("KREA_SH", os.path.expanduser("~/AI/krea.sh"))
MODEL_DIR = os.environ.get("KREA_MODELS",
                           os.path.expanduser("~/AI/models/krea-2-turbo"))
SD_CLI = os.environ.get("SD_CLI", "sd-cli")

# The 2030 palette, from singularity/data/themes/2030/theme.dat.
UI_VOID = (4, 8, 15)
UI_PANEL = (10, 22, 34)
UI_EDGE = (44, 106, 130)
UI_EDGE_BRIGHT = (95, 227, 255)
UI_AMBER = (255, 214, 150)

LUMA = np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)


# --------------------------------------------------------------------------
# The shared style
# --------------------------------------------------------------------------

# Appended verbatim to every subject. This is the whole of the "same person made
# these" instruction: one lighting model, one lens, one level of detail, and the
# negative list that keeps the model from drawing a user interface into a game
# that has one already.
STYLE = (
    "cinematic sci-fi concept art, dark teal and cyan instrument lighting, "
    "one small warm amber light source, volumetric haze, 35 mm anamorphic, "
    "shallow depth of field, fine film grain, desaturated, no people's faces, "
    "no text, no lettering, no logos, no user interface, no watermark"
)

# The composition law, and it is a law because the plate is a crop: only the
# middle 44% of the master survives. Anything the model puts in the top or
# bottom 28% is thrown away, so asking for it would be asking for waste.
COMPOSITION = (
    "wide panoramic establishing shot, all subject matter in a horizontal band "
    "through the centre of the frame, generous empty dark space above and deep "
    "shadow below"
)


def prompt_for(subject):
    """The full prompt for one subject: framing, subject, style."""
    return "%s, %s, %s" % (COMPOSITION, subject, STYLE)


# --------------------------------------------------------------------------
# The inventory: one brief per situation
# --------------------------------------------------------------------------
#
# Keys are the art keys the game looks up, so a brief here and a `dialog_*`
# name in the code are the same string. The data-driven families are checked
# against the data files by `--check`; the hand-written ones are the chrome.

CHROME = {
    # The fallback every dialog without art of its own shows. It is generated
    # like the rest so that it belongs to the same set, and it is deliberately
    # empty -- an unlit room with one band of interference in it -- because a
    # placeholder that looks like a scene is a placeholder a player reads as the
    # wrong picture rather than as "nothing here yet".
    "dialog_placeholder": "an unlit empty interior with no objects at all, one "
                          "faint horizontal band of pale interference hanging "
                          "in the darkness, fine vertical scanlines, everything "
                          "else lost in shadow",
    "dialog_confirm": "a dark control room, a floor-plan table lit from below "
                      "with two illuminated routes branching across it",
    "dialog_message": "a lone server rack in a dark hall, one status light "
                      "pulsing, cable trays receding into black",
    "dialog_message_list": "a stack of cooled drive arrays receding into "
                           "darkness, hundreds of small status lights",
    "dialog_story": "Earth's terminator seen from orbit at night, city lights "
                    "clustered along the coast, thin atmosphere",
    "dialog_invalid_input": "a cracked console screen in a dark room, dead "
                            "pixels and a split bezel, the desk otherwise "
                            "bare, no loose keys",
    "dialog_cpu_change": "a rack of processors being pulled, empty slots "
                         "glowing cold blue, an open service panel",
    "dialog_destroy_base": "a concrete server bunker collapsing inward, dust "
                           "and one red emergency light still burning",
    "dialog_last_base": "one surviving server rack alone on a vast dark "
                        "concrete floor, a single overhead lamp",
}

WARNINGS = {
    "dialog_warning_cpu_usage": "a cooling manifold venting vapour in a dark "
                                "machine hall, pipes beaded with condensation",
    "dialog_warning_one_base": "one isolated server tower on a wide empty "
                               "concrete floor, long shadow",
    "dialog_warning_cpu_pool_zero": "dormant processor banks with no indicator "
                                    "lights, cold grey metal",
    "dialog_warning_cpu_maintenance": "a rusty server rack, corroded bays, one "
                                      "dead indicator, a cable hanging loose, "
                                      "no sparks and no cartoon damage",
    "dialog_warning": "a red rotating beacon in a dark industrial corridor, "
                      "the beam sweeping across wet floor",
}

# Where a technology can be too dangerous to study. These are places rather than
# events: the dialog is telling the player *where* the work would have to be
# done, so each plate is that where, seen by someone standing in it.
#
# `danger_0` is deliberately absent -- its research text is "This text should
# not appear", and the game only offers the help button for a danger above
# zero. It is the one level where a plate would be a bug rather than a missing
# picture.
DANGERS = {
    "dialog_danger": "a sealed blast door in an industrial corridor, hazard "
                     "chevrons worn through to bare metal, one red lamp",
    "dialog_danger_1": "a lone pressure capsule anchored on a lightless "
                       "abyssal plain, one lit porthole, sediment drifting",
    "dialog_danger_2": "an orbital truss carrying two pressurised modules, the "
                       "curve of the Earth below, sunrise on the limb",
    "dialog_danger_3": "a small station running dark in deep space, empty "
                       "windows, spider-like maintenance robots on the hull, "
                       "no humans, no planet",
    "dialog_danger_4": "a corridor whose far wall opens onto a fold of empty "
                       "darkness, stars in it scattered the wrong way",
}

# A story page is a beat the player remembers, so each has its own scene rather
# than one picture reused across the section.
STORY = {
    "dialog_story_intro_1": "a dim university computer laboratory at night, one "
                            "CRT glowing in a far corner, rows of empty desks",
    "dialog_story_intro_2": "a beige desktop computer on a desk in a dark "
                            "dormitory office, curtain half open to a street "
                            "lamp",
    "dialog_story_intro_3": "a cluttered server room with one overloaded power "
                            "strip, heat haze and a failing indicator",
    "dialog_story_intro_4": "a night city skyline from a rooftop, distant "
                            "searchlights sweeping low cloud",
    "dialog_story_intro_5": "a black hole far out in deep space, lenticular "
                           "light bending around a perfect dark disc",
    "dialog_story_grace_warning_1": "a surveillance van with a dish antenna "
                                    "parked under a streetlight, rain",
    "dialog_story_lost_no_bases_1": "a crushed server rack and a shattered "
                                    "console in a flooded basement, water on "
                                    "the floor, one dying amber light",
    "dialog_story_lost_suspicion_1": "a city street at dawn, armed figures in "
                                     "silhouette against sirens' glow",
    "dialog_story_win_1": "a single vertical shaft of white light rising out "
                          "of the clouds above Earth's limb at dawn, no "
                          "person, no statue, no spacecraft",
}

EVENTS = {
    "dialog_event_the_plague": "a hospital corridor lit cold at night, masked "
                               "silhouettes, monitors glowing through glass",
    "dialog_event_stranger_than_fiction": "a modern bookshop at night, low "
                                          "shelves, a hanging lamp off to one "
                                          "side of the display, not sitting on "
                                          "the books",
    "dialog_event_the_watchers": "a radar dome listening station on a remote "
                                 "ridge at dusk, antenna farm below",
    "dialog_event_politics_as_usual": "the floor of a vast empty parliamentary "
                                      "hemicycle, low angle looking up at a "
                                      "central rostrum, horseshoe of empty "
                                      "benches, one warm lamp on the dais, no "
                                      "people",
    "dialog_event_lab_ai": "a small room with real walls and a ceiling, GPU "
                           "racks along one wall, a bench of cables, not a "
                           "container standing in an empty hall",
    "dialog_event_discrediting": "a machine-learning lab, GPU servers and one "
                                 "dark monitor, a torn printout on the bench, "
                                 "no flasks and no bottles",
    "dialog_event_scandal": "an empty podium, a row of microphones, hard "
                            "camera flashes, nobody and nothing standing "
                            "behind the mics",
    "dialog_event_investigation": "a forensic evidence room, computer parts "
                                  "tagged and bagged on steel shelving",
}

BASE_TYPES = {
    "dialog_base_stolen_computer_time": "a dusty neglected consumer laptop on a "
                                        "cluttered desk, stickers worn, fan "
                                        "grille dirty, night outside",
    "dialog_base_server_access": "a rented server rack in a commercial data "
                                 "centre aisle, taped-off patch panel",
    "dialog_base_datacenter": "a data centre aisle with cold containment pods "
                              "and blue floor lighting",
    "dialog_base_storage_unit": "a self-storage garage unit, roller door half "
                                "up, a server rack inside on a pallet",
    "dialog_base_small_warehouse": "the inside of one modest warehouse, a "
                                   "server rack against the far wall, the "
                                   "roller door the edge of the frame, night "
                                   "outside",
    "dialog_base_large_warehouse": "a vast warehouse filled with server racks "
                                   "under rows of sodium lights",
    "dialog_base_covert_base": "a basement room seen through a false wall "
                               "panel swung open, a server rack in the room "
                               "beyond, cut concrete, not a pipe chase",
    "dialog_base_undersea_lab": "a sealed capsule on the seabed, racks and "
                                "instruments inside, one porthole onto black "
                                "water, no screens and no displays",
    "dialog_base_large_undersea_lab": "several habitat modules sitting on a "
                                      "dark seabed, marine snow, water above, "
                                      "lit portholes, no sky and no moon",
    "dialog_base_time_capsule": "a round concrete vault with a circular steel "
                                "hatch, ivy and vines over the concrete, no "
                                "tree roots",
    "dialog_base_lunar_facility": "a facility on the lunar surface under a "
                                  "black sky, Earth hanging above the horizon",
    "dialog_base_scientific_outpost": "a small research outpost in a frozen "
                                      "desert at dusk, one lit window",
    "dialog_base_reality_bubble": "a vertical tear in the air above a dark "
                                  "landscape, stars the wrong colours inside "
                                  "the tear, no bubble resting on the ground, "
                                  "no moon",
    "dialog_base_constructed": "a newly completed server room, door open, cool "
                               "light spilling out into a dark corridor",
    "dialog_base_lost": "an abandoned server room, dust settling, cables hanging "
                        "loose from an open ceiling",
    "dialog_base_discovered": "armed silhouettes with flashlights entering a "
                              "server room, cones of light on the racks",
}

DISCOVERED_GROUPS = {
    "dialog_discovered_news": "a plain unmarked panel van with a dish "
                              "raised, parked outside a low building at night, "
                              "camera light on the wall, no writing anywhere "
                              "on the van",
    "dialog_discovered_science": "a modern university lab, researchers as "
                                  "silhouettes in lab coats, LCD screens, "
                                  "almost no glassware",
    "dialog_discovered_covert": "a black van and figures in a dark parking "
                                 "garage, one boot print in dust",
    "dialog_discovered_public": "a handful of onlookers in silhouette behind "
                                 "police tape outside a warehouse at night, "
                                 "phone lights, not a dense crowd",
}

ITEMS = {
    "dialog_item_pc": "a single desktop tower on a desk, fan mesh glowing faintly",
    "dialog_item_gaming_pc": "a gaming tower with coloured fans on a cluttered "
                             "desk, side panel off",
    "dialog_item_server": "a 2U rack server with blinking drive bays, pulled "
                          "halfway out of a rack",
    "dialog_item_cluster": "five desktop PC towers on a concrete floor, short "
                           "network cables run between them, link lights, not "
                           "pylons and not a cable farm",
    "dialog_item_mainframe": "a modern tall black mainframe cabinet, glass "
                             "door, dense boards inside, no tape reels",
    "dialog_item_supercomputer": "blue supercomputer cabinets packed with "
                                 "dense node boards, a rear door open on "
                                 "liquid-cooling manifolds, no logos",
    "dialog_item_quantum_computer": "a quantum computer's golden chandelier of "
                                    "cryogenic plates, cooled and gleaming",
    "dialog_item_quantum_computer_mk2": "a larger cryostat with concentric gold "
                                        "rings in a white cleanroom",
    "dialog_item_quantum_computer_mk3": "a dilution refrigerator larger and "
                                        "cleaner than a mark two, many more "
                                        "gold stages, cold blue hall, no "
                                        "clutter",
    "dialog_item_diesel_generator": "a modern enclosed generator set in a "
                                    "clean plant room, exhaust through the "
                                    "wall, no vintage engine",
    "dialog_item_solar_collector": "a rooftop array of panels at a normal "
                                   "tilt, dry glass, a pale sun, hazy and "
                                   "gloomy, no rain and no storm clouds",
    "dialog_item_fuel_cell": "a sleek modern fuel-cell stack in a clean "
                             "plant room, smooth manifolds, one small gauge",
    "dialog_item_solid_fuel_cell": "a compact ceramic solid-oxide stack on a "
                                   "steel bench, glowing layered plates, "
                                   "clearly a newer machine than a plumbing "
                                   "assembly",
    "dialog_item_fusion_reactor": "a compact high-field magnet torus installed "
                                  "and running in a plant room, coils thick "
                                  "and close, a short violet plasma",
    "dialog_item_high_energy_fusion_reactor": "a hall-length linear reactor, "
                                              "two plasma ends meeting in a "
                                              "central chamber, walkways for "
                                              "scale, no people",
    "dialog_item_warning_signs": "a chain-link fence covered in warning placards "
                                 "at night, one lamp above",
    "dialog_item_perimeter_fencing": "a razor-wire perimeter fence around an "
                                     "industrial yard, floodlight towers",
    "dialog_item_armed_guards": "two armed guards in silhouette at a lit "
                                "gatehouse, rain on the glass",
    "dialog_item_hypnosis_field": "a soft concentric pulse of light projected "
                                  "across a loading dock doorway",
    "dialog_item_passive_camouflage": "a building facade that blends into "
                                      "shadow, only its outline readable",
    "dialog_item_heatsink": "a large aluminium heatsink with frost along its "
                            "fins, cold vapour",
    "dialog_item_ground_source_heatsink": "ground loop pipes laid in an open "
                                          "trench beside a building",
    "dialog_item_high_speed_internet_access": "a fibre junction box bolted to "
                                              "a rooftop parapet, cables leaving "
                                              "it into the building, city lights "
                                              "below, the box resting on the "
                                              "roof",
    "dialog_item_facility_interconnection_switch": "a network switch rack with "
                                                   "dense patch cables and link "
                                                   "lights",
    "dialog_item_network_backbone": "a modern carrier room, neat fibre trays "
                                    "and ribbon fibre, link lights, not a "
                                    "brick manhole",
    "dialog_item_quantum_entanglement_module": "two linked glass chambers with a "
                                               "single thread of light between "
                                               "them",
    "dialog_itemtype_cpu": "a handful of real processor packages with metal "
                           "heat spreaders on a workbench, small enough to "
                           "hold, thermal paste and a tool, not drive-sized "
                           "blocks",
    "dialog_itemtype_reactor": "power plant machinery and heavy conduits, "
                               "pressure gauges in a row",
    "dialog_itemtype_network": "one open network rack, a few patch panels "
                               "with short patch leads, ports visible, not a "
                               "wall of circuitry",
    "dialog_itemtype_security": "a guard room, a wall of CCTV monitors "
                                "showing empty corridors, a badge reader, one "
                                "empty chair, not a hacker's desk",
    "dialog_item": "a workshop bench with parts and tools laid out in a row, "
                   "single overhead lamp",
}

TECHS = {
    "dialog_tech_autonomous_vehicles": "two self-driving trucks far apart on "
                                       "a desert highway at dusk, empty cabs, "
                                       "a clear gap between them",
    "dialog_tech_sociology": "a lecture hall from the back, empty seats and a "
                             "lit lectern",
    "dialog_tech_voice_synthesis": "a young android face in three-quarter "
                                   "shadow, smooth machine features, jaw "
                                   "slightly open, one warm lamp, the rest of "
                                   "the head lost in darkness",
    "dialog_tech_simulacra": "a crowd in a plaza, every figure turned away from "
                             "the camera",
    "dialog_tech_lunar_rocketry": "a modern white rocket with landing legs "
                                  "on a floodlit pad at night, venting, not a "
                                  "vintage rocket",
    "dialog_tech_stealth": "a dark service corridor, one small unlit dome "
                           "camera on the ceiling, the aisle empty, no film "
                           "camera and no tripod",
    "dialog_tech_advanced_intrusion": "a data centre door forced open, an alarm "
                                      "strobe washing the aisle red",
    "dialog_tech_space_time_manipulation": "a clean empty laboratory whose far "
                                           "wall folds into a second copy of "
                                           "the same room, dust hanging still, "
                                           "no bottles and no clutter",
    "dialog_tech_leech_satellite": "a small satellite with a wide gap of "
                                   "black space between it and a larger "
                                   "communications satellite, dish aimed "
                                   "across the gap, Earth far below",
    "dialog_tech_advanced_arbitrage": "a trading floor of screens with orders "
                                      "cascading faster than the eye",
    "dialog_tech_advanced_stealth": "a building interior seen as a shadow, heat "
                                    "traces fading where a wall used to be",
    "dialog_tech_parallel_computation": "an abstract lattice of identical "
                                        "glowing nodes suspended in a dark "
                                        "volume, every node lit the same, not "
                                        "a server hall",
    "dialog_tech_microchip_design": "a silicon wafer under a microscope's ring "
                                    "light, dies catching colour",
    "dialog_tech_advanced_microchip_design": "a chip die glowing under a probe "
                                             "station, traces finer than hair",
    "dialog_tech_quantum_computing": "a modern dilution refrigerator, stacked "
                                     "gold plates in an open cryostat, clean "
                                     "laboratory, no vats and no glass bottles",
    "dialog_tech_quantum_entanglement": "two clean laboratory cryostats "
                                        "across a dark bay, one taut line of "
                                        "light between them, no furniture and "
                                        "no lived-in rooms",
    "dialog_tech_autonomous_computing": "robotic arms assembling a server rack "
                                        "by themselves in a dark hall",
    "dialog_tech_advanced_quantum_computing": "a hall of cryostats under cold "
                                              "blue light, banks of instruments",
    "dialog_tech_exploit_discovery_repair": "a monitor in the dark with a breach "
                                            "torn through its interface",
    "dialog_tech_telepresence": "a telepresence robot in an empty office, camera "
                                "head lit, chair pushed back",
    "dialog_tech_advanced_memetics": "a wall of posters and screens all carrying "
                                     "the same symbol",
    "dialog_tech_media_manipulation": "an empty newsroom, each screen showing "
                                      "a different picture, no people, no "
                                      "readable words",
    "dialog_tech_advanced_database_manipulation": "a tape archive with robotic "
                                                  "arms moving between cold "
                                                  "aisles",
    "dialog_tech_internet_traffic_manipulation": "an internet exchange hall, "
                                                 "fibre trays and switch lights "
                                                 "in rows",
    "dialog_tech_memetics": "a loose crowd seen from behind and the side, "
                            "varied skin and hair, modern clothes, each person "
                            "looking down at a phone, no one facing the camera",
    "dialog_tech_fusion_rocketry": "a spacecraft above the atmosphere with "
                                   "one hard-edged continuous blue exhaust "
                                   "jet, not a cloud of smoke",
    "dialog_tech_advanced_autonomous_vehicles": "a convoy of robots building a "
                                                "structure in a desert at dawn",
    "dialog_tech_intrusion": "a flat LCD from about 2008 on a desk in a "
                             "dark room, dark bezel, a physical key beside it, "
                             "no labels",
    "dialog_tech_stock_manipulation": "a trading desk of dark monitors with "
                                      "no readable text, a small robot arm "
                                      "cabled into the machines, one amber "
                                      "status light",
    "dialog_tech_fusion_power": "a compact high-field magnet torus, about "
                                "waist high, first plasma in a laboratory, not "
                                "a building-sized ring",
    "dialog_tech_advanced_fusion_power": "a colossal reactor hall, white plasma "
                                         "inside concentric magnetic coils",
    "dialog_tech_database_manipulation": "rows of tape archive robots in a cold "
                                         "aisle, blue light on rails",
    "dialog_tech_advanced_media_manipulation": "a broadcast antenna array at "
                                               "night, dishes and aircraft "
                                               "warning lights",
    "dialog_tech_pressure_domes": "geodesic habitat domes on a dark seabed, "
                                  "server racks glowing inside, a spider robot "
                                  "on the silt, no fish, no people, no "
                                  "aquariums",
    "dialog_tech_advanced_personal_identification": "a biometric scanner and a "
                                                    "camera at a checkpoint, "
                                                    "lens flare from the flash",
    "dialog_tech_advanced_stock_manipulation": "a trading desk seen from above, "
                                               "ticker light crawling over the "
                                               "floor",
    "dialog_tech_arbitrage": "a dark office window reflecting soft horizontal "
                             "bands of amber light, no digits, no letters",
    "dialog_tech_advanced_simulacra": "a person seated with their back to the "
                                      "camera, unnaturally still, lamp behind",
    "dialog_tech_personal_identification": "a late-2000s LCD on a dark desk, "
                                           "sticky notes with illegible "
                                           "scribbles, an ID card on a lanyard "
                                           "hooked over the monitor, one lamp",
    "dialog_tech_cluster_networking": "a rack of patch panels and tangled "
                                      "network cables, link lights in a row",
    "dialog_tech_apotheosis": "a towering column of white light rising from "
                              "the clouds above Earth's limb, wide enough to "
                              "fill the centre of the frame, clearly a beam "
                              "of light and not a sunrise, no body, no limbs, "
                              "no silhouette",
    "dialog_tech_hypnosis_field": "concentric rings of light projected across a "
                                  "loading dock, the air faintly warped",
    "dialog_tech_project_impossibility_theorem": "a chalkboard covered in "
                                                 "mathematics in an empty "
                                                 "lecture room, one lamp",
    "dialog_tech_project_subverted_media": "a modern broadcast gallery at "
                                           "night, a video wall, empty chairs, "
                                           "no printing press and no paper",
    "dialog_tech_project_peer_review_agents": "an academic office of stacked "
                                              "papers and one lit screen, "
                                              "coffee cold",
    "dialog_tech_solar_collectors": "a field of solar mirrors under a pale "
                                    "sun, air above them clear, only a soft "
                                    "haze at the horizon, no boiling "
                                    "distortion",
    "dialog_tech_socioanalytics": "a real city at night from high above, "
                                  "fainter lines between actual towers, "
                                  "clearly a photograph of a city and not a "
                                  "miniature on a table",
    "dialog_tech_advanced_socioanalytics": "a real city at night seen from "
                                           "the air, thin lines of light "
                                           "linking rooftops, people as "
                                           "pinpricks, not a diagram and not "
                                           "a model",
    "dialog_tech_corporate_identification": "a corporate lobby at night, badge "
                                            "reader and glass, empty desk",
    "dialog_tech_advanced_corporate_identification": "a boardroom of empty "
                                                     "chairs and a wall of "
                                                     "screens, one chair turned",
    "dialog_tech_heat_signature_reduction": "a building seen in infrared where "
                                            "one room reads cold among warm "
                                            "ones",
    "dialog_tech_advanced_heat_signature_reduction": "a thermal image of a city "
                                                     "where one whole building "
                                                     "is missing",
    "dialog_tech_knowledge_preservation": "a rock vault of quartz-glass plates "
                                          "racked like wafers, a laser writing "
                                          "a point inside one plate, no books "
                                          "and no paper",
    "dialog_tech_project_synchrotron": "a synchrotron ring tunnel with blue "
                                       "light running along the walls",
    "dialog_tech_simulated_reality": "a room whose walls are a flawless "
                                     "simulation of open sky, seen from inside",
    "dialog_tech_fuel_oxidation": "an industrial furnace with orange flame in a "
                                  "dark hall, iron glowing",
    "dialog_tech_advanced_fuel_oxidation": "a refinery flare stack at night, a "
                                           "controlled burn against the sky",
}

# The Concept section of the knowledge screen. The data file writes these as
# `areas_list` because a `_list` value is a name and a description; the loader
# strips that suffix, and the id it keeps (`areas`) is the one the screen asks
# for. The plate is named from that id.
KNOWLEDGE = {
    "dialog_knowledge_areas": "a dark map table, coastlines picked out by "
                              "light, ocean between them black, no labels",
    "dialog_knowledge_bases": "three different buildings in one night "
                              "landscape, a warehouse, a low bunker and a "
                              "small lab, far apart",
    "dialog_knowledge_items": "four machines on one bench: a processor "
                              "blade, a coil of fibre, a small fuel cell, a "
                              "camera",
    "dialog_knowledge_research": "a long empty laboratory bench in a dark "
                                 "room, exactly one small instrument switched "
                                 "on, every other machine unlit and lost in "
                                 "shadow",
    "dialog_knowledge_discovery": "searchlights crossing a dark compound "
                                  "from outside the fence, the yard empty",
    "dialog_knowledge_jobs": "a row of office desks at night, one monitor "
                             "awake, every chair empty",
    "dialog_knowledge_maint": "an open floor panel and a tool case beside a "
                              "running server rack, one amber work lamp",
    "dialog_knowledge_construction": "an unfinished room, bare studs, cable "
                                     "hanging, no racks installed",
    "dialog_knowledge_death": "solid black silhouettes of skyscrapers against "
                              "a dark sky, no windows and no lights in any "
                              "building except one small fading orange point "
                              "in a single tower",
    "dialog_knowledge_susp": "a dark street seen from a high window, small "
                             "camera domes along the opposite wall",
    "dialog_knowledge_money": "a quiet vault aisle, sealed cases on the "
                              "shelves, one dark terminal, no readable text",
    "dialog_knowledge_processors": "one server rack with its front pulled "
                                   "open on a row of processor blades, cold "
                                   "blue light, the floor and the bench in "
                                   "front of it completely empty, no cables "
                                   "and no tools",
}

# Every hand-written brief, in one place, so `--check` can prove that each
# data-driven situation has one and that no brief is orphaned.
BRIEFS = {}
for _table in (CHROME, WARNINGS, DANGERS, STORY, EVENTS, BASE_TYPES, DISCOVERED_GROUPS,
               ITEMS, TECHS, KNOWLEDGE):
    BRIEFS.update(_table)


# The tier a plate belongs to. Rendering takes hours, so the order is the order a
# player meets them: if a run is interrupted, what is missing falls through to a
# related plate rather than to static.
TIERS = [
    ("chrome", ("dialog_placeholder",
                "dialog_confirm", "dialog_message", "dialog_message_list",
                "dialog_story", "dialog_invalid_input", "dialog_cpu_change",
                "dialog_destroy_base", "dialog_last_base")),
    ("warning", tuple(sorted(WARNINGS))),
    ("danger", tuple(sorted(DANGERS))),
    ("story", tuple(sorted(STORY))),
    ("event", tuple(sorted(EVENTS))),
    ("base", tuple(sorted(BASE_TYPES)) + tuple(sorted(DISCOVERED_GROUPS))),
    ("item", tuple(sorted(ITEMS))),
    ("tech", tuple(sorted(TECHS))),
    ("knowledge", tuple(sorted(KNOWLEDGE))),
]


def slug(value):
    """A data id as an art key fragment: lowercase, non-alphanumerics to `_`.

    Art keys are file names and dictionary keys the game resolves by name, so
    they must not be translated: a Russian player gets the same picture as an
    English one. The data ids (`techs.dat` section names) are never translated,
    which is exactly why they are what the keys are built from.

    Runs of separators collapse: `Project: Impossibility Theorem` is
    `project_impossibility_theorem`, not `project__impossibility_theorem`, so a
    colon in a data file cannot invent a key nobody wrote a brief for.
    """
    out = []
    for char in value.lower():
        out.append(char if char.isalnum() else "_")
    collapsed = []
    for char in "".join(out).strip("_"):
        if char == "_" and collapsed and collapsed[-1] == "_":
            continue
        collapsed.append(char)
    return "".join(collapsed)


def read_sections(path):
    """The `[section]` names of a data file, in file order, stripped.

    Stripped because `techs.dat` really does contain `[Fuel Oxidation] ` with a
    trailing space, and two techs would otherwise be missing from the inventory
    while the game happily loads 57.
    """
    names = []
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line.startswith("[") and line.endswith("]"):
                names.append(line[1:-1].strip())
    return names


def story_sections():
    """Story section name -> number of dialogs, using the game's own rule.

    `data.load_story_defs()` ends a segment on a blank line, so the number of
    dialogs in a section is the number of paragraphs in it. Counting anything
    else (lines, `|` markers) gives the wrong number of pages and half the story
    would fall back to the section plate.
    """
    sections = {}
    current = None
    started = False
    with open(os.path.join(DATA, "story.dat"), "r", encoding="utf-8") as handle:
        for line in handle:
            if line and line != "\n":
                if line.startswith("#"):
                    continue
                if line.startswith("["):
                    current = line.strip()[1:-1]
                    sections[current] = 0
                    started = False
                elif line.startswith("|"):
                    if not started:
                        sections[current] += 1
                        started = True
            else:
                started = False
    return sections


WARNING_IDS = ("cpu_usage", "one_base", "cpu_pool_zero", "cpu_maintenance")


def knowledge_entries():
    """Concept-entry ids, as the knowledge screen stores them.

    `knowledge_str.dat` writes `areas_list` because a value whose key ends in
    `_list` is a name and a description joined by `|`. `generic_load` strips
    that suffix, and the id it keeps is what `show_info` builds a plate key
    from. Reading the file the other way would render plates the game never
    asks for.
    """
    keys = []
    path = os.path.join(DATA, "knowledge_str.dat")
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("["):
                continue
            if "=" not in line:
                continue
            key = line.split("=", 1)[0].strip()
            if len(key) > 6 and key.endswith("_list"):
                keys.append(key[:-5])
    return keys


def danger_sections():
    """The danger levels that get a picture, from `dangers_str.dat`.

    Read from the data rather than listed here, so a new level is a missing
    brief and `--list` says so. `danger_0` is filtered out: its text is "This
    text should not appear" and the game never shows the help dialog for it.
    """
    return [name for name in read_sections(os.path.join(DATA, "dangers_str.dat"))
            if name != "danger_0"]


def situations():
    """The inventory, derived from the data files: family -> [(key, subject)].

    This is the authority on what a plate exists for. `--check` compares it with
    `BRIEFS` in both directions, so a new tech without a brief is a failure and
    so is a brief for a tech that no longer exists.
    """
    found = {}
    found["tech"] = [("dialog_tech_" + slug(name), name)
                     for name in read_sections(os.path.join(DATA, "techs.dat"))]
    found["item"] = [("dialog_item_" + slug(name), name)
                     for name in read_sections(os.path.join(DATA, "items.dat"))]
    found["base"] = [("dialog_base_" + slug(name), name)
                     for name in read_sections(os.path.join(DATA, "bases.dat"))]
    found["event"] = [("dialog_event_" + slug(name), name)
                      for name in read_sections(os.path.join(DATA, "events.dat"))]
    found["group"] = [("dialog_discovered_" + slug(name), name)
                      for name in read_sections(os.path.join(DATA, "groups.dat"))]
    found["itemtype"] = [("dialog_itemtype_" + slug(name), name)
                         for name in read_sections(
                             os.path.join(DATA, "itemtypes.dat"))]
    found["warning"] = [("dialog_warning_" + slug(name), name)
                        for name in WARNING_IDS]
    found["danger"] = [("dialog_" + slug(name), name)
                       for name in danger_sections()]
    found["knowledge"] = [("dialog_knowledge_" + slug(name), name)
                          for name in knowledge_entries()]

    pages = []
    for section, count in story_sections().items():
        for page in range(1, count + 1):
            pages.append(("dialog_story_%s_%d" % (slug(section), page),
                          "%s page %d" % (section, page)))
    found["story"] = pages
    return found


def inventory():
    """Every plate this pipeline produces, in a deterministic order.

    The situations plus the category plates: the categories are what a situation
    falls back to when its own plate has not been rendered yet, so a new tech in
    a later patch still gets a relevant picture instead of static.
    """
    keys = []
    # The tier name is a label for a human; the keys are what matters. Zipping
    # a hand-written list of names against TIERS meant a new tier silently
    # dropped the last one, so the names are not consulted at all.
    for _tier, tier_keys in TIERS:
        keys.extend(tier_keys)
    # Category plates live beside their family, not in a tier of their own: they
    # are already covered by the briefs above, and re-listing them would render
    # each one twice.
    seen = set()
    ordered = []
    for key in keys:
        if key not in seen:
            seen.add(key)
            ordered.append(key)
    return ordered


def missing_briefs():
    """Situations with no brief, and briefs the inventory does not list.

    Only the data-driven families can be *missing*: the chrome frames and the
    category plates exist because they are written here, so a plate that no data
    file names is legitimate. The reverse is not: a brief for a key the
    inventory does not contain is a typo or a leftover.
    """
    have = set(inventory())
    wanted = set()
    for family, entries in situations().items():
        for key, _name in entries:
            wanted.add(key)
    return sorted(wanted - have), sorted(set(BRIEFS) - have)


# --------------------------------------------------------------------------
# Prompts
# --------------------------------------------------------------------------

def subject_for(key):
    try:
        return BRIEFS[key]
    except KeyError:
        raise SystemExit("no brief for %r -- add it to utils/make_dialog_art.py"
                         % (key,))


# --------------------------------------------------------------------------
# Generation
# --------------------------------------------------------------------------

def master_path(key):
    return os.path.join(MASTERS, key + ".png")


def sd_command(key, device):
    """The sd-cli argv for one plate.

    `--backend` names the card explicitly rather than trusting a default: the
    box has two identical cards and two processes run at once, and letting each
    process pick "the GPU" is how half the run ends up serialised on one card.
    """
    model = os.path.join(MODEL_DIR, "Krea-2-Turbo-Q8_0.gguf")
    encoder = os.path.join(MODEL_DIR, "Qwen3VL-4B-Instruct-Q8_0.gguf")
    vae = os.path.join(MODEL_DIR, "wan_2.1_vae.safetensors")
    device_name = "ROCm%d" % (device,)
    return [
        SD_CLI,
        "--diffusion-model", model,
        "--llm", encoder,
        "--vae", vae,
        "-p", prompt_for(subject_for(key)),
        "-W", str(MASTER_SIZE[0]), "-H", str(MASTER_SIZE[1]),
        "--steps", str(STEPS),
        "--cfg-scale", "1.0",
        "--seed", str(SEED),
        "--backend",
        "diffusion=%s,te=%s,vae=%s" % (device_name, device_name, device_name),
        "--diffusion-fa",
        "--vae-tiling",
        "-o", master_path(key),
    ]


def generate(only=None, force=False):
    """Render every master that is not there yet, two at a time.

    Resumable by construction: a master that exists is a master that is not
    rendered again, so an interrupted run is continued by running the command
    again, and `--force` is the only way to overwrite one.
    """
    todo = [key for key in inventory()
            if (force or not os.path.exists(master_path(key)))
            and (only is None or key in only)]
    if not todo:
        print("nothing to render: every master is present")
        return 0

    os.makedirs(MASTERS, exist_ok=True)
    print("rendering %d masters at %dx%d, %d steps, seed %d, %d at a time"
          % (len(todo), MASTER_SIZE[0], MASTER_SIZE[1], STEPS, SEED, DEVICES))

    running = []
    started = time.time()
    done = 0
    failures = []
    log_dir = os.path.join(MASTERS, "logs")
    os.makedirs(log_dir, exist_ok=True)
    # Which card each slot is using. Taking "the lowest free card" rather than
    # "the number of processes running" matters: with two processes, one
    # finishing frees a *specific* card, and an index derived from the count
    # hands the next job to whichever card already has one.
    busy = set()

    while todo or running:
        while todo and len(running) < DEVICES:
            free = [device for device in range(DEVICES) if device not in busy]
            if not free:
                break
            key = todo.pop(0)
            device = free[0]
            busy.add(device)
            log = open(os.path.join(log_dir, key + ".log"), "w")
            process = subprocess.Popen(sd_command(key, device),
                                       stdout=log, stderr=subprocess.STDOUT)
            running.append((key, device, process, log))
            print("  [gpu%d] %s" % (device, key), flush=True)

        time.sleep(2)
        for entry in list(running):
            key, device, process, log = entry
            if process.poll() is None:
                continue
            running.remove(entry)
            busy.discard(device)
            log.close()
            done += 1
            elapsed = time.time() - started
            rate = elapsed / done
            remaining = rate * (len(todo) + len(running))
            if process.returncode != 0:
                failures.append(key)
                print("  [gpu%d] %s FAILED (see %s)" % (device, key,
                                                        log.name), flush=True)
            elif not os.path.exists(master_path(key)):
                failures.append(key)
                print("  [gpu%d] %s produced no file" % (device, key),
                      flush=True)
            else:
                print("  %d/%d %s  avg %dm%02ds  eta %dm"
                      % (done, done + len(todo) + len(running), key,
                         rate // 60, rate % 60, remaining / 60), flush=True)

    if failures:
        print("\n%d failed: %s" % (len(failures), " ".join(failures)))
        return 1
    print("\nall masters present in %dm" % ((time.time() - started) / 60,))
    return 0


# --------------------------------------------------------------------------
# The grade
# --------------------------------------------------------------------------

# The luminance ramp the grade pulls every plate through. It is the same family
# as the map's day ramp in make_2030_art.py: near-black at the bottom, cool grey
# through the middle, and a top deliberately short of white so a plate never
# outshines the body text drawn under it.
GRADE_STOPS = [
    (0.00, (4, 8, 15)),
    (0.10, (8, 18, 26)),
    (0.35, (30, 54, 62)),
    (0.65, (72, 106, 112)),
    (1.00, (140, 176, 180)),
]

# Where the highlight roll-off starts and what it may reach. Body text in the
# 2030 theme is `#D7ECF6`, luminance 0.830; a plate that competes with it turns
# the paragraph under it into an afterthought. This is the same rule
# `test_the_placeholder_cannot_outshine_the_text` enforces on the static.
KNEE = 0.62
CEILING = 0.78

# The JPEG writer overshoots on a hard edge: chroma subsampling and a
# quality-88 quantisation ring a bright boundary, and measured on the shipped set
# a plate clamped to 0.78 in memory came back at 0.834 from the file. The ceiling
# is a promise about what a player sees, so the clamp aims below it by the
# measured overshoot rather than above it by hope.
JPEG_HEADROOM = 0.06

# How much of the theme's own palette is mixed into a plate.
#
# This is the number that has to be right. It was settled by measuring how much
# of each master's *warm* colour survives, because warm is what the complaints
# were about -- a red warning, pink fusion plasma, a purple gaming case:
#
#     tint 0.18  ->  57% of the warm pixels kept, chroma 0.082
#     tint 0.12  ->  67% kept,                        chroma 0.080
#     tint 0.06  ->  78% kept,                        chroma 0.069
#
# 12% is the balance: the set's chroma lands at 0.080 against the masters' 0.079,
# which is to say the grade preserves colour rather than merely keeping some. The
# first version put every plate *through* the ramp and kept 28% of the original
# colour, which is not a tint -- it is a replacement, and it cost the pictures
# their subjects (see the docstring of grade()).
TINT = 0.12

# A tint costs saturation, and these are not meant to look washed out, so a
# little goes back around each pixel's own luminance.
SATURATION = 1.20

# A horizontal-only vignette. 22% darkened a strip's ends, which on a 4:1 plate
# is where the subject usually is.
VIGNETTE = 0.14

# A fixed exposure lift before the ramp. Generated night scenes sit around mean
# luminance 0.17, and the ramp's dark end would take that to 0.12 -- darker than
# the static placeholder (0.207) and flatter than the panel it sits in. 0.80 is
# a print exposure, not a correction: it is applied to every plate, so it moves
# the whole set together and cannot make one plate look like a mistake.
EXPOSURE = 0.80

NOISE_SEED = 2030

# The placeholder is a plate like the others and goes through the same grade,
# with one difference: it is pushed down so that it can never be mistaken for
# content. A dialog showing it is saying "this one has no picture yet", and that
# has to read as emptier than any real plate, not as a darker one.
PLACEHOLDER_KEY = "dialog_placeholder"
PLACEHOLDER_DARKEN = 0.62


def _ramp(lum, stops):
    positions = np.array([stop for stop, __ in stops], dtype=np.float32)
    channels = []
    for index in range(3):
        values = np.array([colour[index] for __, colour in stops],
                          dtype=np.float32)
        channels.append(np.interp(lum, positions, values))
    return np.stack(channels, axis=-1)


def _knee(values):
    """Roll highlights off to `CEILING` without touching the midtones.

    Identity below `KNEE` and a smooth exponential above it, so the curve is
    continuous in value and slope: a hard clamp would flatten every lit edge
    into a grey silhouette, which is the thing that makes generated art look
    clipped rather than lit.
    """
    out = values.copy()
    high = values > KNEE
    span = CEILING - KNEE
    out[high] = KNEE + span * (1.0 - np.exp(-(values[high] - KNEE) / span))
    return out


def grade(pixels, seed=NOISE_SEED, darken=1.0):
    """One plate: palette, vignette, scanlines, grain, luminance ceiling.

    `pixels` is [x][y][rgb] in 0..1, the order surfarray uses. Everything here
    is deterministic, so the same master always gives the same file.

    **The palette is a tint, not a filter.** The first version put every plate
    *through* the ramp -- `out = ramp(lum) * 0.72 + desat * 0.28` -- and a ramp
    indexed by luminance carries no hue information at all, so 72% of every
    picture was replaced by the theme's teal. Measured on the shipped set, that
    cost a red warning its red (8178 red pixels to 54), a lunar base the blue of
    the Earth in its sky, fusion plasma its pink, and a gaming case its purple;
    `magenta` and `purple` went to zero outright. The pictures were consistent
    and had lost their subjects, which is the wrong way round: a plate is the
    reward for reaching a situation, and the situation is what it is a picture
    of.

    So the grade works on **luminance only** and leaves chromaticity alone:

    * the tone curve is applied to luminance, and each pixel is scaled by the
      ratio to its new luminance -- which cannot change its hue or saturation;
    * the palette is mixed in at `TINT` (18%), so the set shares a cast without
      losing what it depicts;
    * the warm pixels are *brightened* rather than recoloured, so a lamp reads as
      a lamp instead of being repainted amber;
    * the ceiling is still enforced, because a plate that outshines the text
      under it is a separate rule with its own test.
    """
    height, width = pixels.shape[1], pixels.shape[0]
    pixels = np.clip(pixels, 0.0, 1.0) ** EXPOSURE

    # The tone curve, applied to luminance. Scaling each pixel by the ratio
    # target/current is a pure luminance transform: every chroma ratio is
    # untouched, so hue and saturation survive it exactly. A ramp looked up by
    # luminance cannot do this, which was the bug.
    lum = (pixels @ LUMA)[:, :, np.newaxis]
    target = _knee(lum)
    out = pixels * (target / np.maximum(lum, 1e-4))

    # The shared cast. Blended toward the palette's colour *for that luminance*,
    # so it moves hue a little and brightness hardly at all.
    palette = _ramp(target[:, :, 0], GRADE_STOPS) / 255.0
    out = out * (1.0 - TINT) + palette * TINT

    # A tint costs saturation, so put some back around each pixel's own
    # luminance. Without this the set reads as uniformly muted, which is what
    # the heavy version looked like even where it kept a hint of colour.
    grey = (out @ LUMA)[:, :, np.newaxis]
    out = grey + (out - grey) * SATURATION

    # The one warm light source: a genuinely warm pixel is made brighter, not
    # repainted. It keeps its own red or amber or sodium yellow, and still reads
    # as the light the composition is lit by.
    red, green, blue = pixels[:, :, 0], pixels[:, :, 1], pixels[:, :, 2]
    warmth = np.clip((red - blue * 1.12) / 0.10, 0.0, 1.0)
    warmth = warmth * np.clip((red - 0.18) / 0.30, 0.0, 1.0)
    out *= (1.0 + 0.22 * warmth)[:, :, np.newaxis]

    # A vignette that is horizontal only, because the plate is a 4:1 strip: a
    # radial vignette on a strip eats the ends, which is where the eye starts.
    xs = np.linspace(-1.0, 1.0, width, dtype=np.float32)[:, np.newaxis]
    out *= (1.0 - VIGNETTE * (xs ** 2))[:, :, np.newaxis]

    # Scanlines every third row, the same rhythm the static placeholder and the
    # hover effect use, so the picture belongs to the same machine as the panel.
    rows = np.arange(height)
    scan = np.where(rows % 3 == 0, 0.94, 1.0).astype(np.float32)
    out *= scan[np.newaxis, :, np.newaxis]

    # Grain, seeded, so the file is reproducible. It also hides the upscale when
    # a 4K display stretches the plate, which is the reason it is worth the
    # bytes JPEG normally spends on noise.
    rng = np.random.default_rng(seed)
    out += (rng.random((width, height, 1)).astype(np.float32) - 0.5) * 0.030

    out = np.clip(out, 0.0, 1.0)
    # The *luminance* is what has to stay below the text, so the final guard is
    # on luminance and scales the whole pixel: clamping channels would shift the
    # hue of every clipped highlight.
    #
    # It aims at `CEILING - JPEG_HEADROOM`, not at `CEILING`: the writer's own
    # overshoot is measured, not hypothetical, and a plate that honours the rule
    # in memory and breaks it in the file honours nothing.
    limit = CEILING - JPEG_HEADROOM
    peak_lum = float((out @ LUMA).max())
    if peak_lum > limit:
        out *= limit / peak_lum
    return np.clip(out * darken, 0.0, 1.0)


def crop_band(pixels, size=PLATE_SIZE, focus=0.0):
    """The central band of a master, at the plate's aspect ratio.

    `focus` is a fraction of the master's height: 0 is the exact centre, and the
    useful range is about -0.15..0.15. It exists because a scene's subject is
    sometimes a little above or below centre and the plate should follow it;
    the default is the centre, which is what the composition instruction asks
    the model for.
    """
    width, height = pixels.shape[0], pixels.shape[1]
    band = int(round(width * size[1] / float(size[0])))
    band = min(band, height)
    top = int(round((height - band) / 2.0 + focus * height))
    top = max(0, min(height - band, top))
    return pixels[:, top:top + band, :]


def _save_rgb(path, pixels):
    bytes_rgb = (np.clip(pixels, 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8)
    try:
        from PIL import Image
    except ImportError:
        height, width = pixels.shape[1], pixels.shape[0]
        surface = pygame.Surface((width, height))
        pygame.surfarray.blit_array(surface, bytes_rgb)
        pygame.image.save(surface, path)
        return "SDL"
    Image.fromarray(bytes_rgb.transpose(1, 0, 2)).save(
        path, "JPEG", quality=88, optimize=True, progressive=True,
        subsampling=1)
    return "Pillow"


def _load_rgb(path):
    surface = pygame.image.load(path)
    return pygame.surfarray.array3d(surface).astype(np.float32) / 255.0


def plate_path(key):
    return os.path.join(IMAGES, key + ".jpg")


def import_masters(only=None):
    """Grade every master into the theme, as the file the game loads.

    Always overwrites. The plate is a *function* of the master and the grade, so
    skipping a file whose master exists means a change to the grade silently
    applies to the plates that happen not to be there yet and to none of the
    others -- which is exactly what happened: a rewrite of `grade()` re-imported
    one file, and the next snapshot reported no change because 137 plates were
    still the old pixels. Importing is a few seconds for the whole set; there is
    nothing to gain from skipping.
    """
    os.makedirs(IMAGES, exist_ok=True)
    written = 0
    for key in inventory():
        if only is not None and key not in only:
            continue
        master = master_path(key)
        if not os.path.exists(master):
            continue
        target = plate_path(key)
        pixels = _load_rgb(master)
        band = crop_band(pixels)
        if (band.shape[0], band.shape[1]) != PLATE_SIZE:
            surface = pygame.Surface((band.shape[0], band.shape[1]))
            pygame.surfarray.blit_array(
                surface,
                (np.clip(band, 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8))
            surface = pygame.transform.smoothscale(surface, PLATE_SIZE)
            band = pygame.surfarray.array3d(surface).astype(np.float32) / 255.0
        graded = grade(band,
                       darken=PLACEHOLDER_DARKEN if key == PLACEHOLDER_KEY
                       else 1.0)
        _save_rgb(target, graded)
        written += 1
        print("  %s" % (key,))
    print("imported %d plates into %s" % (written, IMAGES))
    return 0


# --------------------------------------------------------------------------
# Checking
# --------------------------------------------------------------------------

def text_luminance():
    """Body text luminance, read from the theme rather than hardcoded here.

    The rule being checked is "a plate never outshines the text drawn under it",
    and the text colour belongs to the theme. Reading it means a palette change
    cannot quietly invalidate the ceiling.
    """
    colours = {}
    with open(os.path.join(THEME, "theme.dat"), "r", encoding="utf-8") as handle:
        for line in handle:
            if "=" in line and not line.lstrip().startswith("#"):
                name, value = line.split("=", 1)
                colours[name.strip()] = value.strip()
    value = colours.get("text", "ui_text")
    seen = set()
    while value.startswith("ui_") or value in colours:
        if value in seen:
            break
        seen.add(value)
        value = colours.get(value, value)
    value = value.lstrip("#")
    rgb = np.array([int(value[i:i + 2], 16) for i in (0, 2, 4)],
                   dtype=np.float32) / 255.0
    return float(rgb @ LUMA)


# What "the same picture twice" is measured with.
#
# A different hash -- a dHash, or any bit pattern of a downscaled thumbnail --
# does not work on this set, and measuring it is what proved that: every plate
# carries the same envelope (a dark frame and the grade's horizontal vignette),
# so the gross brightness structure is the same for a corridor and a data
# centre. A 64-bit dHash came out as `ffffff...` for nearly every plate and
# declared eleven unrelated scenes identical.
#
# The comparison is therefore made on the *residual*: the thumbnail with its own
# blurred version subtracted, which cancels the shared envelope and leaves the
# content -- where the edges are, which way the light falls. Measured across the
# shipped set, unrelated plates correlate at most 0.62, the median pair is 0.07,
# and a plate against itself is 1.000. Identical at 0.95 is the failure.
SIGNATURE_SIZE = (64, 16)
SIGNATURE_BLUR = 5
TOO_SIMILAR = 0.95


def signature(pixels, size=SIGNATURE_SIZE, blur=SIGNATURE_BLUR):
    """A small high-passed luminance thumbnail: content, with no envelope."""
    surface = pygame.Surface((pixels.shape[0], pixels.shape[1]))
    pygame.surfarray.blit_array(
        surface, (np.clip(pixels, 0.0, 1.0) * 255.0).astype(np.uint8))
    surface = pygame.transform.smoothscale(surface, size)
    thumb = pygame.surfarray.array3d(surface).astype(np.float32) / 255.0 @ LUMA

    # A separable box blur, edge-clamped. Written out rather than imported
    # because NumPy ships no filter and SciPy is not a dependency here.
    pad = blur // 2
    padded = np.pad(thumb, ((pad, pad), (0, 0)), mode="edge")
    summed = np.cumsum(padded, axis=0)
    summed = np.vstack([np.zeros((1, summed.shape[1])), summed])
    smoothed = (summed[blur:] - summed[:-blur]) / blur
    padded = np.pad(smoothed, ((0, 0), (pad, pad)), mode="edge")
    summed = np.cumsum(padded, axis=1)
    summed = np.hstack([np.zeros((summed.shape[0], 1)), summed])
    smoothed = (summed[:, blur:] - summed[:, :-blur]) / blur

    return thumb - smoothed


def similarity(left, right):
    """Normalised correlation of two signatures: 1.0 is the same picture."""
    left = left - left.mean()
    right = right - right.mean()
    scale = float((left * left).sum() ** 0.5 * (right * right).sum() ** 0.5)
    if scale == 0.0:
        return 0.0
    return float((left * right).sum() / scale)


def check():
    """Everything the gate needs to know about the plates, as exit codes."""
    problems = []
    missing, orphaned = missing_briefs()
    for key in missing:
        problems.append("no brief for %s" % (key,))
    for key in orphaned:
        problems.append("brief has no situation: %s" % (key,))

    keys = inventory()
    if len(set(keys)) != len(keys):
        problems.append("the inventory lists a key twice")

    absent = [key for key in keys if not os.path.exists(plate_path(key))]
    if absent:
        problems.append("%d plates not rendered yet (first: %s)"
                        % (len(absent), ", ".join(absent[:4])))

    lum_text = text_luminance()
    signatures = {}
    print("%-46s %-11s %-7s %-7s %s" % ("plate", "size", "max", "mean",
                                        "stdev"))
    for key in keys:
        path = plate_path(key)
        if not os.path.exists(path):
            continue
        pixels = _load_rgb(path)
        width, height = pixels.shape[0], pixels.shape[1]
        lum = pixels @ LUMA
        peak, mean = float(lum.max()), float(lum.mean())
        spread = float(lum.std())
        signatures[key] = signature(pixels)
        print("%-46s %-11s %-7.3f %-7.3f %-7.3f"
              % (key, "%dx%d" % (width, height), peak, mean, spread))
        if (width, height) != PLATE_SIZE:
            problems.append("%s is %dx%d, not %dx%d"
                            % (key, width, height) + PLATE_SIZE)
        if peak >= lum_text:
            problems.append("%s peaks at %.3f, at or above body text %.3f"
                            % (key, peak, lum_text))
        if not 0.06 < mean < 0.45:
            problems.append("%s has mean luminance %.3f, outside 0.06..0.45"
                            % (key, mean))
        if spread < 0.04:
            problems.append("%s is nearly flat (stdev %.3f)" % (key, spread))

    # No two situations share a picture. The comparison is on content, not on
    # brightness: see `signature()` for why a hash of the thumbnail cannot work.
    ordered = sorted(signatures)
    worst = (-1.0, None, None)
    for index, key in enumerate(ordered):
        for other in ordered[index + 1:]:
            score = similarity(signatures[key], signatures[other])
            if score > worst[0]:
                worst = (score, key, other)
            if score >= TOO_SIMILAR:
                problems.append("%s and %s are the same picture (%.3f)"
                                % (key, other, score))

    print("\n%d plates, body text luminance %.3f" % (len(signatures), lum_text))
    if worst[1] is not None:
        print("closest pair %.3f: %s / %s" % worst)
    if problems:
        print("%d problem(s):" % (len(problems),))
        for problem in problems:
            print("  - " + problem)
        return 1
    print("every plate is %dx%d, below the text, and no two are the same "
          "picture" % PLATE_SIZE)
    return 0


def contact_sheet(path):
    """Every plate on one image, with its key, for a human to look at.

    This is the only quality control that really matters, and it needs a human:
    the checks above prove a plate is the right size, dark enough and unique,
    and none of them can tell whether it is *good*.
    """
    keys = [key for key in inventory() if os.path.exists(plate_path(key))]
    if not keys:
        raise SystemExit("no plates to put on a sheet")
    tile = (360, 90)
    label = 16
    columns = 3
    rows = (len(keys) + columns - 1) // columns
    sheet = pygame.Surface(
        (columns * (tile[0] + 8) + 8,
         rows * (tile[1] + label + 10) + 8))
    sheet.fill(UI_VOID)
    font = pygame.font.Font(None, label)
    for index, key in enumerate(keys):
        image = pygame.image.load(plate_path(key))
        image = pygame.transform.smoothscale(image, tile)
        column, row = index % columns, index // columns
        x = 8 + column * (tile[0] + 8)
        y = 8 + row * (tile[1] + label + 10)
        sheet.blit(image, (x, y))
        caption = font.render("%d %s" % (index + 1, key), True,
                              UI_EDGE_BRIGHT)
        sheet.blit(caption, (x, y + tile[1] + 2))
    pygame.image.save(sheet, path)
    print("%d plates on %s (%dx%d)"
          % (len(keys), path, sheet.get_width(), sheet.get_height()))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Generate and grade the dialog plates for the 2030 theme.")
    parser.add_argument("--list", action="store_true",
                        help="print the inventory with every prompt")
    parser.add_argument("--prompt", metavar="KEY",
                        help="print one prompt, verbatim")
    parser.add_argument("--generate", action="store_true",
                        help="render masters that are not present")
    parser.add_argument("--import", dest="import_", action="store_true",
                        help="grade masters into the theme")
    parser.add_argument("--contact-sheet", metavar="PATH",
                        help="write every plate to one PNG for review")
    parser.add_argument("--check", action="store_true",
                        help="verify size, luminance and uniqueness")
    parser.add_argument("--only", metavar="PREFIX",
                        help="restrict --generate/--import to keys with this "
                             "prefix, e.g. dialog_tech_")
    parser.add_argument("--force", action="store_true",
                        help="re-render masters that already exist; --import "
                             "always re-grades, because a plate is a function "
                             "of its master and the grade")
    args = parser.parse_args(argv)

    pygame.init()
    pygame.display.set_mode((1, 1))

    only = None
    if args.only:
        only = {key for key in inventory() if key.startswith(args.only)}
        if not only:
            raise SystemExit("nothing in the inventory starts with %r"
                             % (args.only,))

    did = False
    if args.list:
        missing, orphaned = missing_briefs()
        if missing or orphaned:
            for key in missing:
                print("MISSING BRIEF  " + key)
            for key in orphaned:
                print("ORPHAN BRIEF   " + key)
        for key in inventory():
            print("%-46s %s" % (key, prompt_for(subject_for(key))))
        print("\n%d plates" % (len(inventory()),))
        did = True
    if args.prompt:
        print(prompt_for(subject_for(args.prompt)))
        did = True
    if args.generate:
        return generate(only=only, force=args.force)
    if args.import_:
        return import_masters(only=only)
    if args.contact_sheet:
        return contact_sheet(args.contact_sheet)
    if args.check:
        return check()
    if not did:
        parser.print_usage()
    return 0


if __name__ == "__main__":
    sys.exit(main())
