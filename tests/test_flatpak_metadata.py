"""The store page: this fork's name, this fork's links, and real screenshots.

AppStream is what a software center shows before a player installs anything, so
a wrong string here is not a documentation bug -- it is the shop window. The
fork used to present itself under upstream's name and send the homepage and the
bug tracker to `singularity/singularity`, where nobody can act on a report
about this code. These tests pin that it does not come back, and that every
screenshot the page names is a file that exists, at the size AppStream wants.
"""

import os
import re
import xml.etree.ElementTree as ET

import numpy as np
import pygame
import pytest


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FLATPAK = os.path.join(REPO_ROOT, "flatpak")
APP_ID = "io.github.singularity.Singularity2030"
METAINFO = os.path.join(FLATPAK, APP_ID + ".metainfo.xml")
DESKTOP = os.path.join(FLATPAK, APP_ID + ".desktop")
MANIFEST = os.path.join(FLATPAK, APP_ID + ".yml")
SCREENSHOTS = os.path.join(FLATPAK, "screenshots")

REPOSITORY = "https://github.com/kostich/singularity"
NAME = "Singularity 2030"

# What utils/make_screenshots.py renders. AppStream prefers 16:9 and wants the
# long edge at least 1280, which is why this is not the game's 1024x768 default.
SCREENSHOT_SIZE = (1366, 768)


def metainfo():
    return ET.parse(METAINFO).getroot()


def screenshots():
    """(caption, image source) for every screenshot the page shows."""
    found = []
    for shot in metainfo().findall("./screenshots/screenshot"):
        caption = (shot.findtext("caption") or "").strip()
        image = shot.find("image")
        assert image is not None, "a screenshot without an image"
        found.append((caption, image.text.strip()))
    return found


def test_the_store_page_calls_the_game_by_our_name():
    assert metainfo().findtext("name") == NAME


def test_the_store_page_has_a_summary_a_developer_and_a_launchable():
    root = metainfo()

    assert root.findtext("summary")
    assert root.findtext("./developer/name")
    assert root.findtext("./launchable") == APP_ID + ".desktop"


def test_every_link_points_at_this_fork():
    """Homepage, tracker and source browser: ours, all three."""
    urls = [url.text.strip() for url in metainfo().findall("./url")]
    kinds = {url.get("type") for url in metainfo().findall("./url")}

    assert {"homepage", "bugtracker"} <= kinds
    for url in urls:
        assert url.startswith(REPOSITORY), url


def test_the_description_credits_the_original_game():
    """The store page has to name what this is a fork of, and its authors."""
    text = " ".join(metainfo().itertext())

    assert "unofficial fork" in text
    assert "Evil Mr Henry" in text and "Phil Bordelon" in text


def test_there_are_at_least_three_screenshots_and_the_first_is_default():
    root = metainfo()
    shots = root.findall("./screenshots/screenshot")

    assert len(shots) >= 3, "a store page with two pictures is a store page"
    assert shots[0].get("type") == "default"


def test_every_screenshot_is_captioned_and_maps_to_a_file_we_ship():
    shipped = set(os.listdir(SCREENSHOTS))

    for caption, source in screenshots():
        assert caption, "an uncaptioned screenshot: %r" % (source,)
        # The raw.githubusercontent.com host is the same repository: AppStream
        # wants a direct image URL, and a github.com blob URL is an HTML page.
        assert "/kostich/singularity/" in source, (
            "a screenshot hosted somewhere other than this repository: %r"
            % (source,))
        name = os.path.basename(source)
        assert name in shipped, "%r is not in flatpak/screenshots" % (name,)


def test_no_screenshot_file_is_left_unshown():
    """An orphan PNG is a picture nobody sees, and a stale page."""
    named = {os.path.basename(source) for _, source in screenshots()}
    on_disk = {name for name in os.listdir(SCREENSHOTS)
               if name.endswith(".png")}

    assert on_disk == named


@pytest.mark.parametrize("name", sorted(os.listdir(SCREENSHOTS))
                         if os.path.isdir(SCREENSHOTS) else [])
def test_every_screenshot_is_the_pinned_size_with_real_ink(name):
    """Right size, and actually a frame of the game rather than a blank one.

    The ink check is what catches the failure this tool had: a screen that was
    never composited saves as a flat background, which is a valid PNG of the
    right size and a worthless screenshot.
    """
    if not name.endswith(".png"):
        pytest.skip("not a screenshot: %s" % name)

    surface = pygame.image.load(os.path.join(SCREENSHOTS, name))
    assert surface.get_size() == SCREENSHOT_SIZE

    rgb = pygame.surfarray.array3d(surface).astype(np.int16)
    luminance = rgb.mean(axis=2)
    assert luminance.std() > 4, "%s is flat, not a frame of the game" % name
    assert (luminance > 60).mean() > 0.005, "%s is almost entirely black" % name


def test_the_desktop_entry_agrees_with_the_store_page():
    """A launcher shows the desktop entry; the software center shows the
    metainfo. Two names for one application is a bug a player can see."""
    entries = {}
    with open(DESKTOP, encoding="utf-8") as fd:
        for line in fd:
            if "=" in line and not line.startswith("#"):
                key, value = line.split("=", 1)
                entries[key.strip()] = value.strip()

    assert entries["Name"] == NAME
    assert entries["Icon"] == APP_ID


def test_the_manifest_asks_for_no_devices():
    """pygame draws software surfaces, so the sandbox gets no /dev access.

    `--device=dri` was in the manifest from the first build and nothing ever
    used it; every device permission is one more thing a software center warns
    about, and one more thing to audit when a build breaks.
    """
    with open(MANIFEST, encoding="utf-8") as fd:
        text = fd.read()

    finish_args = text.split("finish-args:", 1)[1].split("cleanup:", 1)[0]
    assert not re.search(r"^\s*-\s*--device=", finish_args, re.MULTILINE), \
        "the sandbox may not ask for a device"
    assert not re.search(r"^\s*-\s*--filesystem=", finish_args, re.MULTILINE), \
        "the sandbox may not reach into the host's filesystem"


def test_the_manifest_keeps_exactly_the_sockets_the_game_needs():
    """Wayland, the X11 fallback, and the audio socket -- nothing else.

    The audio socket is not optional: the soundtrack is 17 tracks and Flatpak
    has no playback-only socket, so it also permits recording. That is the one
    entry a software center still warns about, and it is deliberate. Any other
    socket appearing here is not.
    """
    with open(MANIFEST, encoding="utf-8") as fd:
        text = fd.read()

    finish_args = text.split("finish-args:", 1)[1].split("cleanup:", 1)[0]
    sockets = set(re.findall(r"--socket=([a-z0-9-]+)", finish_args))
    assert sockets == {"wayland", "fallback-x11", "pulseaudio"}, sockets
    assert re.search(r"^\s*-\s*--share=ipc\s*$", finish_args, re.MULTILINE), \
        "the X11 fallback needs shared memory"
