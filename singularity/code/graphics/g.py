#file: g.py
#Copyright (C) 2005,2006,2007,2008 Evil Mr Henry, Phil Bordelon, Brian Reid,
#                        and FunnyMan3595
#This file is part of Endgame: Singularity.

#Endgame: Singularity is free software; you can redistribute it and/or modify
#it under the terms of the GNU General Public License as published by
#the Free Software Foundation; either version 2 of the License, or
#(at your option) any later version.

#Endgame: Singularity is distributed in the hope that it will be useful,
#but WITHOUT ANY WARRANTY; without even the implied warranty of
#MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#GNU General Public License for more details.

#You should have received a copy of the GNU General Public License
#along with Endgame: Singularity; if not, write to the Free Software
#Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

#This file contains all global objects.

import collections
import time

import pygame

# User desktop size. Set at probe_desktop_size()
desktop_size = ()

# Margin used in windowed mode to compensate for panels and title bar
# Should be sensibly large enough to account for all common OS layouts, like
# Ubuntu/Unity side launcher (65px), Gnome panels (24+24px), Windows bottom
# panel (48px), Mac OSX, KDE, etc.
# It will not affect windows smaller than desktop size
desktop_margin = (70, 70)

#initial screen size. Can be set via command-line option or preferences file
default_screen_size = (1024, 768)

#Current screen size. This size is an abstraction, tightly tied to resolutions.
#Real window size in windowed mode may be smaller due to desktop_margin
screen_size = default_screen_size

#Size handed to pygame.display.set_mode(). In windowed mode it is screen_size
#minus desktop_margin when it would reach the desktop; in fullscreen it is the
#desktop itself. It is refreshed from the size SDL actually granted.
window_size = screen_size

#The windowed size last chosen or dragged to. Fullscreen must never overwrite
#it: losing it is what made "leave fullscreen" restore a desktop-sized window
#that looked exactly like fullscreen.
windowed_size = screen_size

#The area the UI is laid out in, and where that area starts inside the window.
#A window wider than LAYOUT_MAX_ASPECT is pillarboxed and centred, so a 21:9
#screen shows the same layout a 16:9 screen of the same height shows. For 4:3,
#5:4, 3:2 and 16:9 windows the layout is the whole window, exactly as before.
layout_size = screen_size
layout_origin = (0, 0)

#Current real window size. This is the size the widget layer lays out in, so it
#tracks layout_size rather than the window.
real_screen_size = layout_size

min_resolution = (100, 100)

# Aspect ratio above which the layout is pillarboxed instead of stretched wide.
# A 21:9 screen uses the whole window, and so must its *windowed* size: on a
# 3440x1440 desktop the window is 3370x1370, which is 2.46:1, so a threshold at
# 2.33 or 2.4 pillarboxes a window and not the fullscreen of the same screen.
# Only 32:9 (3.56) and wider would push the HUD clusters so far apart that the
# layout reads as broken, so those get the centred column.
LAYOUT_MAX_ASPECT = 2.5

# How many pixels wider than 16:9 a window may be before it counts as wider.
# 1366x768 is 1.779:1 and rounds a pixel under 16:9; it is not an ultrawide and
# must keep using its whole width.
LAYOUT_ASPECT_SLACK = 4

# Aspect ratios up to this are "sane" when picking a first-run window size.
# 16:9 is 1.78, 16:10 is 1.6, 21:9 is 2.33.
MAX_DEFAULT_ASPECT = 1.92

# Available resolutions
resolutions = [
    ( 800, 600),
    (1024, 600),
    (1024, 768),
    (1280,1024),

    (1280, 800),
    (1366, 768),
    (1440, 900),
    (1920,1080),
    (2560,1080),
    (2560,1440),
    (3440,1440),
    (3840,2160),
    (5120,2880),
    (7680,4320),
]


# The text sizes the code ships with, per name. Never mutated: a theme's
# [sizes] section and the player's saved preferences are layers on top of this,
# and rebuild_text_sizes() is what combines the three.
default_text_sizes = {
    'default': 20,
    # The body of a dialog, and of a description pane. Kept apart from
    # 'default' because a dialog is *read* rather than scanned and lives in a
    # fixed box: a point or two smaller is more prose in the same frame, which
    # is the difference between a message that fits and one that scrolls.
    'dialog_text': 20,
    'button': 36,
    'suspicion_bar': 32,
    'time_display': 24,
    'resource_display': 24,
    'report_content': 20,
}

# Filled from the current theme's [sizes] section. See theme.Theme.init_cache().
theme_text_sizes = {}

# Filled from the player's saved preferences. Only sizes the player actually
# chose live here: Options writes every size out, so "equal to the default" is
# not a choice and must not pin one theme's scale over the next one's.
user_text_sizes = {}

# What widgets read, always. Built from the three layers above.
configured_text_sizes = dict(default_text_sizes)


def rebuild_text_sizes():
    """Combine the size layers into configured_text_sizes, in place.

    In place, because widgets and the diagnostics report hold this dict as
    module state rather than a copy. Unknown names are dropped: a typo in a
    theme file must not invent a size that save_options() then persists for
    ever, and changing one is a theme switch away from being invisible.
    """
    sizes = dict(default_text_sizes)
    for layer in (theme_text_sizes, user_text_sizes):
        for name, value in layer.items():
            if name in default_text_sizes:
                sizes[name] = value

    configured_text_sizes.clear()
    configured_text_sizes.update(sizes)


# Filled from the current theme's [dialog] section. See theme.Theme.init_cache().
# A missing key is not an error: dialog_style() answers the caller's default,
# which is the geometry the game shipped with before the 2030 theme existed.
theme_dialog = {}


def dialog_style(key, default=None):
    """One value from the current theme's [dialog] section, or `default`.

    Nothing is read here but the merged theme layer. The legacy themes pin
    every key to its old value in their own theme.dat (they inherit from the
    default theme otherwise), so a theme that never mentions dialogs and one
    that says "the old way" both come out of this function the same.
    """
    return theme_dialog.get(key, default)


def content_border_width():
    """The width of the edges *inside* a dialog: the picture's and the block's.

    One question with two askers. The frame around a dialog's picture
    (`dialog.DialogArtPane`) and the translucent block behind its body text
    (`text.Text.draw_plate`) are two parts of one frame, so they are one width
    -- and a theme can make them thinner than the dialog's own outer border
    without the two halves of that frame disagreeing, which is what happened
    when the block read `border_width` and the picture read it too but the
    theme wanted its contents lighter than its shell.

    A theme that names no `content_border_width` gets `border_width`, which is
    what both used before the key existed, so this is a no-op for every theme
    that does not ask for it.
    """
    return dialog_style("content_border_width", dialog_style("border_width", 1))


# Filled from the current theme's [hud] section. Like [dialog], a missing key is
# not an error: hud_style() answers the caller's default, which is the layout
# the game shipped with before the 2030 theme had opinions about it.
theme_hud = {}


def hud_style(key, default=None):
    """One value from the current theme's [hud] section, or `default`."""
    return theme_hud.get(key, default)

fullscreen = False

# When True, a widget that does not fit inside its parent raises instead of
# printing a warning and drawing a clipped copy of itself. The game leaves this
# off so a player never gets a crash; the tests and the UI harness turn it on,
# because a silent clip is how a whole half-screen of HUD went missing.
strict_layout = False

# When True, every layout change prints the numbers it computed. This is how a
# "no text" report gets diagnosed instead of guessed at: every font size is
# derived from the layout height, so the height is the number that matters.
debug_layout = False

_last_layout_report = None

# Set when the UI area itself changed: a resize, a fullscreen switch, an adopted
# window. The root then presents the whole window once. A resize hands the
# window a freshly allocated buffer, and nothing in the widget tree draws
# outside the layout area, so every pixel out there is whatever the compositor
# left in the new allocation -- a band of green/black stripes down the side of
# the window.
geometry_dirty = False

#What the next set_mode() should give us, and what the current window actually
#is. restart_needed() compares the two. Kept apart from window_size because what
#a display grants can differ from what was asked (HiDPI scaling, a compositor
#refusing a size).
_requested_window_size = screen_size
_applied_window_size = screen_size
_applied_fullscreen = fullscreen

#colors:
colors = {}

# Cache font dictionary.
fonts = {}

# Cache image dictionary.
images = {}

# The dialog plates, decoded on demand.
#
# `images` above is filled eagerly by Theme.init_cache(): every entry is a live
# surface for the whole session. That is right for an icon or the planet, and it
# is wrong for the one image family a theme may ship a hundred of -- the plates
# behind the scenario dialogs. A theme with 138 of them at 1920x480 would cost
# roughly half a gigabyte of resident memory for pictures a player sees a few
# times in a session, and every theme switch would pay the decode again.
#
# So a theme registers a plate by *filename* here, and dialog_art() decodes one
# when a dialog actually shows it. The table is a name -> path mapping; the
# cache below is the handful of plates decoded and not yet evicted.
dialog_art_files = {}

# How many decoded plates to keep. A dialog shows one, two dialogs are never on
# screen at once, and the only plate ever revisited is the previous page of the
# story -- so a handful is generous. It is bounded on purpose: the point of the
# filename table is that decoding is not free.
DIALOG_ART_CACHE_SIZE = 4

_dialog_art_cache = collections.OrderedDict()


def has_dialog_art(name):
    """Whether the current theme ships a plate under this name.

    A pure table lookup, deliberately: the callers ask this to choose between
    art keys, and answering must not decode anything.
    """
    return name in dialog_art_files


def dialog_art(name):
    """One decoded dialog plate, or None if the theme ships no such file.

    Loaded through the ordinary image loader, so a plate is a theme image like
    any other and either transparency convention works.
    """
    surface = peek_dialog_art(name)
    if surface is not None:
        return surface

    filename = dialog_art_files.get(name)
    if filename is None:
        return None

    surface = load_image(filename)
    _dialog_art_cache[name] = surface
    while len(_dialog_art_cache) > DIALOG_ART_CACHE_SIZE:
        _dialog_art_cache.popitem(last=False)
    return surface


def peek_dialog_art(name):
    """A plate that is already decoded, or None -- and never a decode.

    A widget that has scaled a picture wants to know whether the picture under
    that name is still the one it scaled, on every redraw. Answering that has to
    be a dictionary lookup or the bounded cache buys nothing: a redraw that
    decodes to decide whether it needs to decode is the same cost as one that
    decodes.
    """
    surface = _dialog_art_cache.get(name)
    if surface is not None:
        _dialog_art_cache.move_to_end(name)
    return surface


def clear_dialog_art():
    """Forget the plates: they belong to the theme that was current."""
    dialog_art_files.clear()
    _dialog_art_cache.clear()

# Template for surfaces that should have transparency: its pixel format is the
# one with an alpha channel.  Note that a surface passed as the `depth`
# argument of pygame.Surface() copies only the format, not the SRCALPHA flag,
# so a surface that must blend has to be created with pygame.SRCALPHA.
ALPHA = None

# Related to ALPHA, used by widget.Widget class
fade_mask = None

# Global FPS, used where continuous behavior is undesirable or a CPU hog.
FPS = 30

# OLPC ebook mode.
ebook_mode = False

screen_surface = None


def probe_desktop_size():
    """Refreshes the cached desktop size and returns it, or None if unknown.

    Under Wayland either SDL2 call can report the surface instead of the
    monitor, so a 0x0 answer counts as "unknown" and the previous value is
    kept rather than being overwritten.
    """
    global desktop_size

    size = (0, 0)

    try:
        sizes = pygame.display.get_desktop_sizes()
    except (pygame.error, AttributeError):
        sizes = []

    if sizes:
        size = tuple(sizes[0])

    if not (size[0] > 0 and size[1] > 0):
        try:
            info = pygame.display.Info()
            size = (info.current_w, info.current_h)
        except pygame.error:
            size = (0, 0)

    if size[0] > 0 and size[1] > 0:
        desktop_size = size

    return desktop_size or None


def compute_layout(size):
    """Splits a real window size into the UI area and the area's position.

    A window at or below 16:9 uses all of its space, so the answer is the
    window itself at (0, 0) -- the geometry every existing layout was written
    for. A wider window is pillarboxed, so a 21:9 window lays out exactly like
    a 16:9 window of the same height instead of stretching everything.
    """
    width, height = int(size[0]), int(size[1])

    if width <= 0 or height <= 0:
        return (width, height), (0, 0)

    layout_width = min(width, int(round(height * LAYOUT_MAX_ASPECT)))

    if width - layout_width <= LAYOUT_ASPECT_SLACK:
        return (width, height), (0, 0)

    return (layout_width, height), ((width - layout_width) // 2, 0)


def fit_aspect_size(area, aspect, height_fraction=1.0):
    """Largest `aspect`-shaped size that fits in `area`, using at most
    `height_fraction` of the area's height."""
    area_width, area_height = int(area[0]), int(area[1])

    height = int(area_height * height_fraction)
    width = int(round(height * aspect))

    if width > area_width:
        width = area_width
        height = int(round(width / aspect))

    return (width, height)


def update_layout():
    """Recomputes the layout area from window_size.

    A degenerate window size is refused outright. Every font size is derived
    from the layout height (text.convert_font_size), so laying out in 0x0 draws
    every glyph at 0px: the panes appear and the text does not, which reads as
    "the fonts are broken" rather than as a layout problem. A compositor can
    report exactly that for a window it has not mapped yet.
    """
    global layout_size, layout_origin, real_screen_size, geometry_dirty

    new_layout, new_origin = compute_layout(window_size)

    if not _usable_size(new_layout):
        return

    if (tuple(new_layout), tuple(new_origin)) != (tuple(layout_size),
                                                  tuple(layout_origin)):
        geometry_dirty = True

    layout_size, layout_origin = new_layout, new_origin
    real_screen_size = layout_size

    _report_layout()


def _report_layout():
    """Under --debug, says what the UI is actually laid out in.

    This is the number that explains a game with no readable text: 20pt text at
    a layout height of 1370 renders at 35px, and at a height of 0 renders at
    0px.
    """
    global _last_layout_report

    if not debug_layout:
        return

    from singularity.code.graphics import text as text_module

    base = configured_text_sizes["default"]
    font_px = text_module.convert_font_size(base)

    report = (tuple(window_size), tuple(layout_size), tuple(layout_origin),
              font_px)

    if report == _last_layout_report:
        return

    _last_layout_report = report

    print("layout: window %s -> area %s at %s; %dpt text renders at %dpx"
          % (report[0], report[1], report[2], base, font_px))


def layout_blit_pairs(rects, origin=None):
    """Maps window-space rects to (destination, source area) pairs.

    Widget rects are window space -- the root's collision rect starts at the
    layout origin, so hit-testing needs no translation. The root surface,
    however, covers only the layout area, so the destination is the rect
    itself and the source region is that rect shifted back by the origin.
    Shifting both would move the UI by the origin twice.
    """
    if origin is None:
        origin = layout_origin

    shift = (-origin[0], -origin[1])
    return [(rect, rect.move(*shift)) for rect in rects]


def outside_layout_rects():
    """The parts of the window that the layout area does not cover.

    Empty unless the window is wider than LAYOUT_MAX_ASPECT, in which case
    these are the pillarbox bands -- or unless the window and the layout
    disagree about their size, which is exactly when the uncovered strip holds
    garbage rather than a deliberate bar.

    Measured against the presentation surface when that is larger than
    window_size: the surface is what gets presented to, and a window that grew
    behind our back leaves its extra pixels there.
    """
    window_w, window_h = window_size

    if screen_surface is not None:
        surface_w, surface_h = screen_surface.get_size()
        window_w, window_h = max(window_w, surface_w), max(window_h, surface_h)

    layout_w, layout_h = layout_size
    origin_x, origin_y = layout_origin

    rects = []

    if origin_x > 0:
        rects.append(pygame.Rect(0, 0, origin_x, window_h))

    right = origin_x + layout_w

    if right < window_w:
        rects.append(pygame.Rect(right, 0, window_w - right, window_h))

    if origin_y > 0:
        rects.append(pygame.Rect(0, 0, window_w, origin_y))

    bottom = origin_y + layout_h

    if bottom < window_h:
        rects.append(pygame.Rect(0, bottom, window_w, window_h - bottom))

    return rects


def clear_outside_layout(color=(0, 0, 0)):
    """Paints the parts of the surface that the layout area does not cover.

    Nothing in the widget tree draws there, so those pixels keep whatever was
    in the window's buffer. When the window changes size that buffer is
    reallocated, and the leftovers are visible garbage. Returns the rects it
    filled, for the caller to present.
    """
    if screen_surface is None:
        return []

    rects = outside_layout_rects()

    for rect in rects:
        screen_surface.fill(color, rect)

    return rects


def init_graphics_system():
    # The desktop size has to be known before the window size is worked out.
    probe_desktop_size()

    # (Re-)calculate real screen size
    set_screen_size()

    # Initialize the screen
    set_mode()

    # Initialize the cache of the current theme.
    from singularity.code.graphics import theme
    theme.current.init_cache()

    init_alpha()

    # Set the application icon and caption
    pygame.display.set_icon(images["icon"])
    pygame.display.set_caption("Singularity 2030")

    request_window_focus()


def request_window_focus():
    """Asks the window manager to give our window keyboard focus.

    On Wayland a newly mapped window often does not get focus, so the game looks
    alive while ignoring every key and click until its title bar is clicked. It
    is only a hint to the compositor, so failure is normal and is ignored.
    """
    window = _sdl2_window()

    if window is None:
        return False

    try:
        window.focus()
    except (pygame.error, AttributeError, TypeError):
        return False

    return True


def _sdl2_window():
    """The SDL window behind the display surface, or None if unavailable.

    pygame._sdl2.video exposes the window itself, which is the only way to
    change a window's state without going through display.set_mode(). That call
    destroys and recreates the window, and the replacement window lost keyboard
    and mouse input entirely.
    """
    global _sdl2_window_cache

    if _sdl2_window_cache is not None:
        return _sdl2_window_cache

    try:
        from pygame._sdl2 import video as video2

        _sdl2_window_cache = video2.Window.from_display_module()
    except Exception:
        # Older pygame, or a build without the SDL2 window API. The caller falls
        # back to asking for a restart.
        return None

    return _sdl2_window_cache


def _forget_sdl2_window():
    """Drops the cached wrapper, for when the window itself went away."""
    global _sdl2_window_cache

    _sdl2_window_cache = None


def _usable_size(size):
    """True when `size` is a size a window can actually have."""
    if size is None or len(size) != 2:
        return False

    return (int(size[0]) >= min_resolution[0]
            and int(size[1]) >= min_resolution[1])


def window_size_actual():
    """The window size SDL reports right now, ignoring nonsense.

    A compositor can answer 0x0 -- for a window that is being mapped, or whose
    surface is not attached yet -- and that answer must not be believed. Every
    font size is derived from the layout height (text.convert_font_size), so a
    degenerate layout renders every glyph at 0px, and the game then draws its
    panes with no text at all. That reads as "the fonts are broken" rather than
    as a layout problem, which is exactly how it was reported.
    """
    try:
        reported = tuple(pygame.display.get_window_size())
    except (AttributeError, pygame.error):
        reported = None

    if _usable_size(reported):
        return reported

    if screen_surface is not None:
        surface_size = tuple(screen_surface.get_size())
        if _usable_size(surface_size):
            return surface_size

    # Nothing sane to go on: keep what we had rather than zeroing the layout.
    return tuple(window_size)


def _pump_until(predicate, attempts=50, delay_ms=10):
    """Pumps events until predicate() holds, or the attempts run out.

    SDL applies a window resize asynchronously: the new size only appears once
    the event queue has been drained.
    """
    for _ in range(attempts):
        try:
            pygame.event.pump()
        except pygame.error:
            return predicate()

        if predicate():
            return True

        pygame.time.wait(delay_ms)

    return predicate()


def refresh_screen_surface():
    """Re-grabs the display surface, which a resize replaces.

    SDL reallocates the window surface when the window changes size, and pygame
    only picks the replacement up when display.get_surface() is called again.
    Until then screen_surface still describes -- or points at -- the previous
    allocation, so everything drawn through it, and every rect measured against
    it, belongs to a size the window no longer has.
    """
    global screen_surface

    try:
        surface = pygame.display.get_surface()
    except pygame.error:
        return

    if surface is not None:
        screen_surface = surface


def _sync_window_state():
    """Reads the real window size back and makes it the truth."""
    global screen_surface, window_size
    global _requested_window_size, _applied_window_size, _applied_fullscreen

    refresh_screen_surface()

    actual = window_size_actual()
    if _usable_size(actual):
        window_size = actual

    _requested_window_size = window_size
    _applied_window_size = window_size
    _applied_fullscreen = fullscreen

    update_layout()
    note_mode_change()


def _window_is_fullscreen(window):
    """True while SDL still reports the window as fullscreen.

    Only a hint, and only where the property exists: a build that cannot say
    falls back to attempting the size outright, which is what actually matters.
    """
    try:
        return bool(window.fullscreen)
    except (AttributeError, pygame.error, TypeError):
        return False


def _leave_fullscreen(window, wanted_size):
    """Turns fullscreen off and puts the window back to the chosen size.

    Returns True when the window has really left fullscreen.

    SDL_SetWindowSize is ignored while the window is still flagged fullscreen,
    and SDL clears that flag asynchronously. Asking for the size before the flag
    is gone therefore does nothing -- and the old code then read the desktop
    size back and recorded it as both the window size and the applied state, so
    restart_needed() said there was nothing to do. The game believed it was
    windowed at desktop size: a fullscreen window that would not come out of
    fullscreen until the next start, which is exactly how it was reported.

    Measured on the dummy driver: after set_fullscreen(False) the window stayed
    1024x768 and a request for 800x600 was dropped for ever, while
    set_windowed() restored it immediately. So that is the call to make, with
    set_fullscreen(False) as the fallback for a build that lacks it.

    The chosen size is asked for, but it is not the test of success. A maximized
    or tiled window legitimately refuses to be resized and is still out of
    fullscreen; calling that a failure made a switch that had worked look
    pending, which is what armed the "you must restart" prompt on a session
    where fullscreen was in fact turning off. What is a failure is the window
    not moving at all: that is SDL ignoring the request because the flag never
    cleared.
    """
    wanted = (int(wanted_size[0]), int(wanted_size[1]))

    # The geometry it has while fullscreen. Anything else afterwards means the
    # exit took, whatever size the compositor chose to give back.
    fullscreen_size = tuple(window_size_actual())

    try:
        window.set_windowed()
    except (pygame.error, AttributeError, TypeError):
        try:
            window.set_fullscreen(False)
        except (pygame.error, AttributeError, TypeError):
            return False

    # Give SDL a moment to drop the flag. Best effort: where the flag cannot be
    # read, the size comparison below is what decides.
    _pump_until(lambda: not _window_is_fullscreen(window), attempts=8,
                delay_ms=10)

    # A maximized window ignores SDL_SetWindowSize entirely, so a resolution
    # asked for while it is maximized does nothing at all: that is the reported
    # "I pick a different resolution and the window never changes". The
    # compositor hands the window back maximized in this session, so this is
    # the common case and not an odd one, and picking a resolution is exactly
    # the request "stop being maximized, be this size". On a window that was
    # never maximized the call does nothing.
    try:
        window.restore()
    except (pygame.error, AttributeError, TypeError):
        pass

    # Then ask for the chosen window, retrying in case the compositor applies it
    # late. Bounded: ten tries of about 10 ms.
    if tuple(window_size_actual()) != wanted:
        for _ in range(10):
            try:
                window.size = wanted
            except (pygame.error, AttributeError, TypeError):
                break

            try:
                pygame.event.pump()
            except pygame.error:
                pass

            if tuple(window_size_actual()) == wanted:
                break

            pygame.time.wait(10)

    actual = tuple(window_size_actual())

    if not _usable_size(actual):
        return False

    # The size asked for, or at any rate no longer the fullscreen geometry.
    if actual == wanted or actual != fullscreen_size:
        if debug_layout and actual != wanted:
            print("fullscreen: left, window is %s (asked for %s)"
                  % (actual, wanted))
        return True

    return False


def apply_display_request():
    """Applies the recorded display request to the running window, in place.

    Returns True when the window now matches the request. False means this
    display cannot do it and the change has to wait for a restart, which
    restart_needed() reports.

    Nothing here calls display.set_mode(): that is the call that destroys the
    window and loses its input.
    """
    global fullscreen, window_size, windowed_size
    global _requested_window_size, _applied_fullscreen

    if screen_surface is None:
        return False

    window = _sdl2_window()
    if window is None:
        return False

    wanted_fullscreen = bool(fullscreen)
    wanted_size = compute_window_size(screen_size, wanted_fullscreen)

    try:
        if wanted_fullscreen:
            window.set_fullscreen(True)
        elif not _leave_fullscreen(window, wanted_size):
            # The display would not give the window back. Keep the geometry we
            # really have -- drawing into a strip of a desktop-sized window is
            # worse -- but do not record it as the windowed state: the chosen
            # size stays the request and the window stays reported as
            # fullscreen, so restart_needed() keeps telling the truth and the
            # choice applies at the next start.
            refresh_screen_surface()
            actual = window_size_actual()
            if _usable_size(actual):
                window_size = actual
            update_layout()
            windowed_size = tuple(wanted_size)
            _requested_window_size = tuple(wanted_size)
            _applied_fullscreen = True
            note_mode_change()
            if debug_layout:
                print("fullscreen: exit not honoured (window is %s), a restart "
                      "will apply it" % (tuple(window_size),))
            return False
    except (pygame.error, AttributeError, TypeError):
        return False

    _sync_window_state()

    return not restart_needed()


def set_fullscreen(value):
    """Switches fullscreen now where possible, else records it for a restart.

    Returns True when the switch happened immediately. False means the request
    was recorded and restart_needed() reports it.
    """
    value = bool(value)

    if value == bool(fullscreen):
        return True

    set_screen_size(fs=value)

    return apply_display_request()


def get_screen_size_list():
    res_list = set(resolutions)

    try:
        modes = pygame.display.list_modes()
    except pygame.error:
        modes = []

    # list_modes() answers -1 when it cannot tell.
    if modes and modes != -1:
        res_list.update(tuple(mode) for mode in modes)

    # The desktop size is always a sensible choice, even when SDL does not list
    # it, which is the common case under Wayland.
    if desktop_size:
        res_list.add(tuple(desktop_size))

    # Remove resolution inferior to minimal size since we will not allows them.
    if min_resolution:
        res_list = [res for res in res_list
                    if res[0] >= min_resolution[0] and res[1] >= min_resolution[1]]

    # Remove resolution superior to desktop size since we will not allows them.
    if desktop_size:
        res_list = [res for res in res_list
                    if res[0] <= desktop_size[0] and res[1] <= desktop_size[1]]

    return sorted(res_list)


def choose_default_screen_size(desktop=None):
    """Picks a starting window for a first run, i.e. when neither the command
    line nor the preferences file asked for a resolution.

    The old default, 1024x768, is a postage stamp on a 4K or ultrawide desktop.
    Pick the largest known resolution that fits, preferring one at or below
    16:9 so the HUD keeps its proportions.
    """
    if desktop is None:
        desktop = probe_desktop_size()

    if not desktop:
        return screen_size

    max_width = desktop[0] - desktop_margin[0]
    max_height = desktop[1] - desktop_margin[1]

    fits = [res for res in resolutions
            if res[0] <= max_width and res[1] <= max_height]

    if not fits:
        return screen_size

    sane = [res for res in fits if res[0] / float(res[1]) <= MAX_DEFAULT_ASPECT]

    return max(sane or fits, key=lambda res: (res[1], res[0]))


def compute_window_size(size, is_fullscreen=False, desktop=None):
    """Window size for a requested resolution.

    Fullscreen uses the desktop. A window has the desktop margin subtracted on
    any axis that would reach the desktop edge, so that the title bar and the
    desktop panels do not cover part of the game.
    """
    if desktop is None:
        desktop = desktop_size

    if is_fullscreen:
        return tuple(desktop) if desktop else tuple(size)

    width, height = int(size[0]), int(size[1])

    if desktop:
        if width >= desktop[0]:
            width = max(min_resolution[0], width - desktop_margin[0])
        if height >= desktop[1]:
            height = max(min_resolution[1], height - desktop_margin[1])

    return (width, height)


# TODO: Allows Fullscreen resolution could be higher than desktop_size when possible.
def set_screen_size(size=None, fs=None):
    """Records the resolution and fullscreen state to use from now on.

    This does not touch the running window. Applying a new mode means destroying
    and recreating the window, and on Wayland the new window then receives no
    events at all: the game stops responding while the music, on its own thread,
    keeps playing. That is measured, not guessed -- a stack dump taken while the
    game was hung showed the main thread blocked in pygame.event.wait(), i.e.
    nothing arriving.

    So the request is recorded, set_mode() builds the window from it at startup,
    and changing either while the game runs needs a restart. restart_needed()
    says whether one is pending.
    """
    global screen_size, windowed_size, fullscreen, _requested_window_size

    # default values for size and fullscreen are current values
    if size is None: size = screen_size
    if fs   is None: fs   = fullscreen

    # sets the new values
    screen_size = size
    fullscreen = fs

    # Limit screen to minimal value
    if min_resolution:
        screen_size = (min_resolution[0] if screen_size[0] < min_resolution[0] else screen_size[0],
                       min_resolution[1] if screen_size[1] < min_resolution[1] else screen_size[1]) 

    # Limit the screen size to desktop size
    if desktop_size and (screen_size[0] > desktop_size[0] or
                         screen_size[1] > desktop_size[1]):
        screen_size = tuple(desktop_size)

    # A window size that was saved as a resolution repairs itself here. A size
    # within the window margin of the desktop is the whole screen, not a
    # resolution, and storing it is how one drag wrote "3440x1371" into
    # prefs.dat: the next start then opens a nearly-fullscreen window that is
    # not fullscreen, which looks like windowed mode being broken.
    if desktop_size and tuple(screen_size) != tuple(desktop_size):
        if (abs(desktop_size[0] - screen_size[0]) <= desktop_margin[0]
                and abs(desktop_size[1] - screen_size[1]) <= desktop_margin[1]):
            screen_size = tuple(desktop_size)

    # Remembered even while fullscreen, so leaving it returns to the resolution
    # the player picked rather than to the desktop.
    windowed_size = compute_window_size(screen_size, False)

    _requested_window_size = compute_window_size(screen_size, fullscreen)


def restart_needed():
    """True when the requested display state differs from the running window.

    True means "this takes effect when the game restarts". There is no supported
    way to apply it in place; see set_screen_size().
    """
    if screen_surface is None:
        # No window yet: init_graphics_system() builds it from the request.
        return False

    return (fullscreen != _applied_fullscreen
            or tuple(_requested_window_size) != tuple(_applied_window_size))


#How long after a programmatic mode change a VIDEORESIZE is treated as the
#window manager's answer to that change rather than a deliberate resize.
#
#Both X11 and Wayland deliver the resize asynchronously, after set_mode() has
#already returned, so clearing the event queue inside set_mode() is not enough.
#Acting on that answer is acting on our own request, and on Wayland that is
#exactly what made the fullscreen toggle flip back and forth.
MODE_SETTLE_SECONDS = 0.4

_mode_changed_at = 0.0


def note_mode_change():
    """Records that we just asked for a new display mode."""
    global _mode_changed_at

    _mode_changed_at = time.monotonic()


def mode_change_settling():
    """True while a resize event may still be an echo of our own set_mode()."""
    return (time.monotonic() - _mode_changed_at) < MODE_SETTLE_SECONDS


def adopt_window_size(size, clamp=True):
    """Adopt a window size the window manager has already applied.

    Called from the VIDEORESIZE handler, and deliberately does not call
    set_mode(). The window is already this size; asking for it again produces
    another resize event, which asks again, which is the loop that made
    fullscreen impossible to turn off.

    Unlike set_screen_size() this applies no desktop margin: the window already
    has the size it has, and shaving 70px off a window the player dragged is
    not a correction, it is a jump.

    The *resolution* is left alone. It is what the player chose from the list,
    and it is what save_options() writes to prefs.dat; letting a drag overwrite
    it stored a window size like 3440x1371 as if it were a resolution, which
    then reopened as a near-fullscreen window on every start.

    `clamp` limits the size to the cached desktop size, which is right for a
    resize event, where a bogus size can arrive. reconcile_window_size() passes
    False: it is measuring the window SDL just made, and that measurement must
    not be overruled by a desktop size we only think we know -- a stale probe
    would then pin the layout below the window for good.

    Returns True if anything changed.
    """
    global window_size, windowed_size
    global _requested_window_size, _applied_window_size

    width, height = int(size[0]), int(size[1])

    if width <= 0 or height <= 0:
        return False

    if clamp and desktop_size:
        width = min(width, desktop_size[0])
        height = min(height, desktop_size[1])

    if min_resolution:
        width = max(width, min_resolution[0])
        height = max(height, min_resolution[1])

    size = (width, height)

    if size == tuple(window_size):
        return False

    # A resize defines the window, and drags have to be remembered so that the
    # next fullscreen round trip comes back to where the player left it.
    window_size = size
    windowed_size = size

    # The window is already this size, so nothing is waiting to be applied. The
    # raw size is recorded rather than compute_window_size(), which would
    # subtract the desktop margin from a window that happens to be exactly
    # desktop-sized, leaving restart_needed() reporting a change that could
    # never be applied.
    _requested_window_size = size
    _applied_window_size = size

    update_layout()

    return True


def reconcile_window_size():
    """Adopts the size the window actually has, if the layout disagrees.

    The layout is only as good as the last size we believed. A resize event can
    be lost, coalesced with another one, or refused while a mode change is
    still settling -- and then the game lays out in one size while the window is
    another. Everything outside the layout keeps whatever the compositor left in
    the reallocated buffer, which is the band of stripes down the side of a
    resized window.

    This is the safety net that makes all of those cases end in the same place:
    what the window is, is what the UI is laid out in. Cheap enough to run once
    a frame -- get_window_size() is one C call.

    Returns True when the geometry changed.
    """
    if screen_surface is None:
        return False

    # In fullscreen the window is the desktop and a resize means nothing, and
    # adopting it would overwrite the remembered windowed size with the
    # fullscreen one.
    if fullscreen:
        return False

    # A resize right after a mode change is that change's echo. Judging it now
    # is what made the fullscreen toggle flip back and forth.
    if mode_change_settling():
        return False

    # Before measuring: the surface is what gets drawn into and presented, and
    # after a resize pygame has not handed us the new one yet.
    refresh_screen_surface()

    previous = tuple(window_size)
    actual = window_size_actual()

    if tuple(actual) == previous:
        return False

    if not adopt_window_size(actual, clamp=False):
        return False

    if debug_layout:
        print("window: adopted %s from the compositor (was %s)"
              % (tuple(actual), previous))

    return True


def set_mode():
    """Wrapper for pygame.display.set_mode()"""
    global screen_surface, window_size
    global _requested_window_size, _applied_window_size, _applied_fullscreen

    # This destroys the window the cached wrapper belongs to, so the wrapper has
    # to go with it. See _sdl2_window().
    _forget_sdl2_window()

    if fullscreen:
        flags = pygame.FULLSCREEN
    else:
        flags = pygame.RESIZABLE

    # A fullscreen back buffer is the desktop, not the requested resolution:
    # asking for 1024x768 there is what made fullscreen look broken.
    screen_surface = pygame.display.set_mode(
        tuple(compute_window_size(screen_size, fullscreen)), flags)

    # SDL may hand back a different size than requested (fullscreen, HiDPI
    # scaling, compositor constraints). Lay out in what we actually got.
    granted = tuple(screen_surface.get_size())
    if _usable_size(granted):
        window_size = granted
    else:
        # Never adopt a degenerate size. The layout and every font size come
        # from it, so a 0x0 answer would leave the game with no readable text.
        window_size = tuple(compute_window_size(screen_size, fullscreen))

    # The window now matches what was asked for, whatever was granted, so there
    # is nothing pending. Comparing against the granted size rather than the
    # request keeps restart_needed() quiet when a compositor scales it.
    _requested_window_size = window_size
    _applied_window_size = window_size
    _applied_fullscreen = fullscreen

    update_layout()

    # Deliberately no note_mode_change() here. That call arms the settle window
    # that makes the resize handler ignore the next resize event, and the event
    # after a set_mode() is the compositor telling us the size it actually gave
    # the window -- the one answer that must not be thrown away. _sync_window_state()
    # arms it for a fullscreen toggle, where the event really is an echo.

    # Only the layout rectangle is redrawn later, so clear the pillarbox area
    # once, when the mode changes. This pushes just those rects: a full
    # flip() is a blocking presentation call, and making one immediately after
    # the window was recreated is the other way to stall the main thread.
    screen_surface.fill((0, 0, 0))
    outside = outside_layout_rects()
    if outside:
        pygame.display.update(outside)


def load_font(filename):
    from singularity.code.graphics.font import FontList
    return FontList(filename)


def load_image(filename):
    """Load a theme image, honouring whichever transparency it carries.

    Theme images come in two conventions and both have to work:

    * most draw on a magenta field, and the colour key is what makes that field
      transparent (every image upstream shipped, and the 2030 scrollbar arrow);
    * newer art carries a real alpha channel, for smooth edges -- an app icon
      with rounded corners cannot be expressed with a binary colour key.

    The old code did convert() -> set_colorkey() -> convert_alpha()
    unconditionally, and convert() throws the alpha channel away: every
    transparent pixel became opaque black, so an alpha image loaded as a black
    box. Nothing in the tree had alpha when that was written, so it was
    invisible; it is not invisible now.

    The key path is unchanged for images without alpha, so every existing image
    loads byte-identically.
    """
    image = pygame.image.load(filename)
    if image.get_flags() & pygame.SRCALPHA:
        return image.convert_alpha()

    # No alpha channel: the magenta field is the transparency.
    image = image.convert()
    image.set_colorkey((255, 0, 255, 255), pygame.RLEACCEL)
    # Do not convert_alpha() here.  The colour key survives that conversion as
    # a colour-key flag on a 32-bit surface, and any scaling of the image then
    # bleeds the key colour into neighbouring pixels -- visible as a magenta
    # fringe on the scrollbar arrows at some resolutions (upstream fa73a73).
    # Blitting onto an SRCALPHA surface turns the key into real alpha 0 instead.
    out = pygame.Surface(image.get_size(), pygame.SRCALPHA, 32)
    out.blit(image, (0, 0))  # colorkey -> alpha 0
    return out

def init_alpha():
    global ALPHA
    ALPHA = pygame.Surface((0,0)).convert_alpha()


def resolve_image_alias(image):
    if isinstance(image, str):
        return resolve_color_alias(images[image])
    else:
        return image


def resolve_color_alias(color):
    if isinstance(color, str):
        return resolve_color_alias(colors[color])
    else:
        return color


def resolve_font_alias(font):
    if isinstance(font, str):
        return resolve_color_alias(fonts[font])
    else:
        return font


def resolve_text_size(text_size):
    if isinstance(text_size, str):
        return resolve_text_size(configured_text_sizes[text_size])
    else:
        return text_size
