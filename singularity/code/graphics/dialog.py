#file: dialog.py
#Copyright (C) 2008 FunnyMan3595
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

#This file contains the dialog class.

import hashlib
import random
import time
import pygame
import operator

from singularity.code.graphics import g, constants, widget, text, button, listbox
from singularity.code.graphics import image as image_module
from singularity.code.global_hotkeys import detect_global_hotkey


KEYPAD = {pygame.K_KP1: 1, pygame.K_KP2: 2, pygame.K_KP3: 3, pygame.K_KP4: 4,
          pygame.K_KP5: 5, pygame.K_KP6: 6, pygame.K_KP7: 7, pygame.K_KP8: 8,
          pygame.K_KP9: 9}

# X11 reports the mouse wheel as buttons rather than as a wheel: 4/5 are the
# vertical axis and 6/7 the horizontal one. None of them is a click, whichever
# of them a driver chooses to deliver.
SCROLL_BUTTONS = (4, 5, 6, 7)

# The wheel reaches a scrolling body after the listboxes have had their turn
# (they register at 200): a list under the pointer owns its own wheel, and a
# body may only claim what is left over.
BODY_SCROLL_PRIORITY = 300


def wheel_event(direction, position=None):
    """One MOUSEWHEEL event, in the shape SDL2 delivers.

    X11 reports the wheel as buttons 4 and 5 instead, so both spellings are
    turned into this single event and the handlers only ever see one.

    `flipped` and `precise_y` are part of the real event and are read by
    Listbox.on_mousewheel(); a hand-built event without them raises
    AttributeError the first time a real wheel is turned, which is exactly what
    a test that invented its own wheel had been hiding.
    """
    fields = {"x": 0, "y": direction, "flipped": False, "precise_y": 0.0}
    if position is not None:
        fields["pos"] = position
    return pygame.event.Event(pygame.MOUSEWHEEL, fields)

# A theme's dialog frame -- see MODERNIZATION.md, "Dialog geometry belongs to
# the theme too". The names a theme file uses, mapped to layout constants.
DIALOG_ANCHORS = {
    "top_center": constants.TOP_CENTER,
    "mid_center": constants.MID_CENTER,
}

# The gap between the picture and the text beside or below it, as a fraction of
# the dialog.
#
# A banner is a fixed share of the dialog's height rather than the picture's own
# aspect ratio, so that adding or deleting an art file never reflows the dialog:
# the picture is scaled to cover the strip and centre-cropped instead.
ART_GAP = .02

# The picture a slot falls back to when the dialog's own art is not there yet.
# One file for every art key: a dead channel says "nothing here" without looking
# like a rendering fault, which is what an empty panel looks like.
PLACEHOLDER_ART = "dialog_placeholder"

# "The caller said nothing" and "the caller said no picture" are different
# questions: a subclass sets art_key on the class, and a caller that passes
# art_key=None wants the picture turned off for one dialog, not the class's
# key back. A sentinel is the only way to tell the two apart, since None is
# the value that means "no picture".
_UNSPECIFIED = object()


class ClassicLayout(object):
    """The geometry a screen was built with, and how to put it back.

    A theme switch runs through `rebuild()`, so a screen's 2030 arrangement has
    to be undone as well as applied: the theme picker is on the settings screen
    itself, and choosing a legacy theme with it open otherwise left the 2030
    tabs and panes behind on a theme that never asked for them.
    """

    def __init__(self, widgets):
        self.saved = [(widget_, widget_.pos, widget_.size, widget_.anchor)
                      for widget_ in widgets]

    def restore(self):
        for widget_, pos, size, anchor in self.saved:
            widget_.anchor = anchor
            widget_.pos = pos
            widget_.size = size


def button_row_reserve():
    """The fraction of a dialog's height its button row owns.

    Buttons sit with their bottom edge at `1 - margin` and are a tenth of the
    dialog tall, so the row starts that far up; the gap on top keeps a block of
    text from touching them.
    """
    return g.dialog_style("margin", .01) + .10 + .02


def apply_text_plate(widget, reserve_bottom=None, is_frame=False):
    """Put a translucent block behind a text widget, if the theme asks for one.

    A theme that does not set `text_plate` leaves every text widget exactly as
    it was: the colours stay None, so nothing is drawn and nothing is measured
    differently.
    """
    if g.dialog_style("text_plate", "none") != "block":
        return
    widget.plate_color = "dialog_plate_background"
    widget.plate_border_color = "dialog_plate_border"
    if reserve_bottom is None:
        reserve_bottom = button_row_reserve()
    widget.plate_reserve_bottom = reserve_bottom
    widget.plate_reserve_is_own = is_frame


SDL_V2 = True if pygame.get_sdl_version()[0] == 2 else False


def _debug_resize(message):
    """Resize handling is invisible except when it is wrong, and when it is
    wrong it looks like the window flipping between two states. Under
    singularity --debug, say what was ignored and why."""
    from singularity.code import g as game_g

    if game_g.debug:
        print("resize: " + message)


def insort_right_w_key(a, x, lo=0, hi=None, key=lambda v: v):
    """Insert item x in list a, and keep it sorted assuming a is sorted.

    If x is already in a, insert it to the right of the rightmost x.

    Optional args lo (default 0) and hi (default len(a)) bound the
    slice of a to be searched.

    (Basically bisect.insort_right but with support for a key function)
    """

    if lo < 0:
        raise ValueError('lo must be non-negative')
    if hi is None:
        hi = len(a)
    x_key = key(x)
    while lo < hi:
        mid = (lo+hi)//2
        mid_key = key(a[mid])
        if x_key < mid_key:
            hi = mid
        else:
            lo = mid+1
    a.insert(lo, x)


def move_mouse(dxy):
    (dx, dy) = dxy
    old_x, old_y = pygame.mouse.get_pos()
    x = old_x+dx
    y = old_y+dy
    pygame.mouse.set_pos((x, y))

def fake_click(down):
    if down:
        type = pygame.MOUSEBUTTONDOWN
    else:
        type = pygame.MOUSEBUTTONUP
    click_event = pygame.event.Event(type, {'button': 1, 'pos': pygame.mouse.get_pos()})
    pygame.event.post(click_event)

def fake_key(key):
    down_event = pygame.event.Event(pygame.KEYDOWN,
                                    {'key': key, 'unicode': None})
    up_event = pygame.event.Event(pygame.KEYUP, {'key': key, 'unicode': None})
    pygame.event.post(down_event)
    pygame.event.post(up_event)

def handle_ebook(event):
    key = KEYPAD[event.key]
    new_key = None

    if event.type == pygame.KEYDOWN:
        if key == 2:
            move_mouse((0,10))
        elif key == 4:
            move_mouse((-10,0))
        elif key == 6:
            move_mouse((10,0))
        elif key == 8:
            move_mouse((0,-10))

    if key == 1:
        fake_click(event.type == pygame.KEYDOWN)
    elif key == 3:
        new_key = constants.XO1_X
    elif key == 9:
        new_key = constants.XO1_O
    elif key == 7:
        new_key = constants.XO1_SQUARE

    if new_key is not None:
        new_event = pygame.event.Event(event.type, {'key': new_key, 'unicode': None})
        pygame.event.post(new_event)

def call_dialog(dialog, parent=None):
    parent_dialog = None
    target = parent
    while target:
        if isinstance(target, Dialog):
            parent_dialog = target
            break
        target = target.parent

    if parent_dialog:
        parent_dialog.lost_focus()

    retval = dialog.show()

    if parent_dialog:
        parent_dialog.regained_focus()

    Dialog.top.needs_redraw = True

    return retval


def insort_all(sorted_list, items):
    for item in items:
        insort_right_w_key(sorted_list, item, key=operator.itemgetter(0))


class Dialog(text.Text):
    """A Dialog is a Widget that has its own event loop and can be faded out."""

    top = None # The top-level dialog.
    current_dialog = None # The dialog whose run loop is on top right now.

    # Whether this dialog is a window with a frame of its own. The play screen
    # fills the whole area and is not one, and neither is the root.
    #
    # A theme decides what the frame looks like: `[dialog] window_shape = rect`
    # is the plain panel every dialog drew before the key existed, and the
    # shapes below are for a theme that wants hardware.
    window_frame = True

    # What the header band says. None draws the band and no title -- right for a
    # dialog whose own title row is already its heading.
    window_title = None
    # None, "warning" or "alert". Only the 2030 theme has colours for the last
    # two, and only that layout reads them, so a legacy frame is unchanged.
    chrome_tone = None

    faded = widget.causes_redraw("_faded")

    # Used for detecting double-clicks.
    #            (time, (x, y), button)
    last_click = (0,    (0, 0), -1    )

    def __init__(self, parent=None, pos=(.5, .1), size=(1, .9),
                 anchor=constants.TOP_CENTER, **kwargs):
        kwargs.setdefault("background_color", (0, 0, 0, 0))
        kwargs.setdefault("borders", ())
        super(Dialog, self).__init__(parent, pos, size, anchor, **kwargs)
        self.visible = False
        self.faded = False
        self.is_above_mask = True
        self.self_mask = True
        self.needs_remask = True

        self.needs_timer = None

        self.handlers = {}
        self.key_handlers = {}

        self.add_handler(constants.CLICK, self.fake_escape, 200)

        # The corner close box, if the theme asks for one. Built here rather
        # than in each screen so that every window has it, and re-synced from
        # rebuild() so that a theme switch adds or drops it.
        self.close_button = None
        self.sync_close_button()

    def lost_focus(self):
        self.faded = True
        self.stop_timer()

    def fake_escape(self, event):
        if event.button == 3:
            fake_key(pygame.K_ESCAPE)
            raise constants.Handled

    def regained_focus(self):
        self.faded = False
        self.start_timer()
        self.fake_mouse()

    def make_top(self):
        """Makes this dialog be the top-level dialog."""
        if self.parent != None:
            raise ValueError("Dialogs with parents cannot be the top-level dialog.")
        else:
            Dialog.top = self

    def remake_surfaces(self):
        """Recreates the surfaces that this widget will draw on."""
        super(Dialog, self).remake_surfaces()

    # -- The window: shape, header and the space it reserves -------------------

    @staticmethod
    def themed_shape():
        """`rect` or `chamfer`, from the theme."""
        return g.dialog_style("window_shape", "rect")

    @staticmethod
    def cut_pixels(size):
        """The chamfer of a window this size, in pixels.

        One place, because three things need the same number: the outline that
        is drawn, the close box's inset, and the one a button row keeps.
        """
        return int(min(size) * g.dialog_style("chamfer", 0.0))

    @staticmethod
    def header_fraction():
        """How much of a window's height its header band owns, 0 for none."""
        if g.dialog_style("header", "none") != "bar":
            return 0.0
        return g.dialog_style("header_height", 0.0)

    def header_pixels(self, rect=None):
        """The band's height in pixels, for a chrome rect or the whole dialog."""
        if rect is None:
            rect = self.window_rect()
        return int(round(self.header_fraction() * rect.height))

    def window_rect(self):
        """The rectangle the chrome is drawn in, in this dialog's own pixels.

        The whole dialog, for every dialog that is a window and nothing else.
        `SimpleMenuDialog` overrides it: its widget fills the screen so that the
        dialogs it opens are not clipped into a corner, while the frame it draws
        is only as big as its own panel.
        """
        return pygame.Rect(0, 0, self.real_size[0], self.real_size[1])

    def below_header(self, y):
        """A top-anchored position moved out from under the header band.

        Positions are fractions: negative ones are shares of the parent, and
        `0` is the parent's top edge. A positive one is a share of the screen
        and is already somewhere else, so it is left alone.
        """
        header = self.header_fraction()
        if y > 0 or not header:
            return y
        return y - header

    def less_header(self, size):
        """A negative height shortened by the header's share of the window."""
        header = self.header_fraction()
        if size >= 0 or not header:
            return size
        return size + header

    def content_bottom_reserve(self):
        """The share of a window's height its own bottom row of buttons owns.

        The shipped `.15` is exactly the `.85` every description pane and list
        was given before the 2030 layout existed, so a legacy theme is unmoved.
        The 2030 layout reserves the row itself, and gives it back when the row
        is gone -- which is what a close box in the corner does.
        """
        if g.dialog_style("window_layout", "classic") != "2030":
            return .15
        if self.close_only_buttons and self.has_close_box():
            # No row down there any more; only the frame's own margin.
            return .03
        return .14

    def screen_y_share(self, y):
        """A share of the screen expressed as a share of this window.

        A `pos` above zero is measured against the whole screen -- that is how a
        dialog places itself on the desktop -- while a negative one is a share
        of the parent. A window that has to move its own content out from under
        its header therefore needs the conversion, and gets `y` back unchanged
        when it is already in the parent's terms.
        """
        if y <= 0:
            return y
        share = self.size[1] if self.size and self.size[1] > 0 else 0
        if not share:
            return y
        return y / share

    def draws_window(self):
        """Whether this dialog paints the shaped panel instead of a rectangle."""
        if not self.window_frame or self.themed_shape() != "chamfer":
            return False
        # `rebuild()` runs before the first `resize()`, so a dialog may not have
        # a size yet; a dialog with no size has nothing to frame.
        size = getattr(self, "_real_size", None)
        return size is not None and min(size) > 40

    @staticmethod
    def _chrome_colour(name, fallback):
        """A chrome colour, or the one the widget would have used anyway."""
        try:
            return g.resolve_color_alias(name)
        except KeyError:
            if fallback is None:
                return None
            return g.resolve_color_alias(fallback)

    def chrome_colours(self):
        """Edge, glow, title, fill, and the header band.

        The frame is cyan on the dark hull unless this dialog is carrying a tone
        and the theme has named a colour for it. A theme that has not -- every
        legacy theme -- keeps the edge, the glow, the fill and the band it
        already used, and the title stays the glow.
        """
        edge = self._chrome_colour("dialog_frame_edge", "text_dialog_border")
        glow = self._chrome_colour("dialog_frame_glow", "pane_border")
        title = glow
        fill = self._chrome_colour("dialog_frame_fill", "text_dialog_background")
        band = self._chrome_colour("dialog_header_fill", "pane_background")
        tone = getattr(self, "chrome_tone", None)
        if not tone or g.dialog_style("window_layout", "classic") != "2030":
            return edge, glow, title, fill, band
        named = {"edge": edge, "glow": glow, "text": title,
                 "fill": fill, "header": band}
        for part in ("edge", "glow", "text", "fill", "header"):
            found = self._chrome_colour("dialog_%s_%s" % (tone, part), None)
            if found is not None:
                named[part] = found
        return (named["edge"], named["glow"], named["text"],
                named["fill"], named["header"])

    def window_polygon(self, chamfer, size):
        """The outline of a panel `size` pixels across, in local coordinates.

        An instrument panel, not a rectangle, and not a symmetrical one either:
        an opposing pair of corners is cut at 45 degrees -- the top-left and the
        bottom-right -- and the other two are square. One corner cut reads as
        damage; all four cut reads as a rectangle with its corners shaved off.
        Two, on the diagonal, read as a shape.

        The one thing a corner may not be is rounded: a disc of any radius turns
        a hard-edged panel into a card or a tooltip, which is the opposite of
        what this frame is for. There is no arc anywhere in the outline.

        The points reach the far edge of the box, one pixel past the last pixel
        it covers. That is deliberate, and it is why the frame is two *filled*
        polygons rather than one stroked one: a fill that stopped short of the
        edge would leave a one-pixel gap, while a stroke along this path falls
        outside the surface on the right and the bottom -- which is exactly the
        border that went missing.
        """
        width, height = size
        # The last pixel of the box, not the edge past it. A polygon's boundary
        # is filled, so a vertex at `width` fills pixel `width` -- which only
        # looks right for the outer shape because that pixel is off the surface.
        # Used for the interior as well, it ate one pixel off the right and the
        # bottom of the rim, which is why those two edges came out half as thick
        # as the other two.
        right = max(1, width - 1)
        bottom = max(1, height - 1)
        chamfer = max(0, min(int(chamfer), right // 2 - 2, bottom // 2 - 2))

        # Clockwise from the top-left cut: along the top edge to the square
        # top-right corner, down the right edge to the bottom-right cut, along
        # the bottom to the square bottom-left corner, and up the left edge.
        return [(chamfer, 0), (right, 0),
                (right, bottom - chamfer), (right - chamfer, bottom),
                (0, bottom), (0, chamfer)]

    def header_polygon(self, height, chamfer, inset, size):
        """The band, cut to the same outline as the panel it sits in.

        One end of the band is cut and it is the window's own corner, the
        top-left; the other runs to the square corner above it. A band with both
        ends cut would be a second outline rather than the top of this one.
        """
        width, _ = size
        left = top = inset
        # Inclusive far edges, for the same reason `window_polygon()` uses them.
        right = max(left + 1, left + width - 1)
        chamfer = max(0, min(int(chamfer), (width - 1) // 2 - 2))
        bottom = max(top + max(0, int(height)) - 1, top + chamfer + 1)
        return [(left + chamfer, top), (right, top), (right, bottom),
                (left, bottom), (left, top + chamfer)]

    def draw_window(self):
        """Paint the shaped panel the children then draw on top of."""
        rect = self.window_rect()
        width, height = rect.width, rect.height
        if width < 8 or height < 8:
            return

        edge, _glow, title_colour, fill, band = self.chrome_colours()
        chamfer = int(min(width, height) * g.dialog_style("chamfer", 0.0))
        border = max(1, min(int(self.border_width), width // 4, height // 4))

        # Composed on its own alpha surface and blitted at the frame's corner: a
        # widget's surface is a subsurface of the screen, which has no alpha
        # channel, so filling in place would paint the cut corners back in as
        # solid colour.
        panel = pygame.Surface((width, height), pygame.SRCALPHA)

        # The frame, in two fills: the whole outline in the edge colour, then
        # the same shape inset by the border in the fill. What survives of the
        # first is the border, and it is the same width on all four sides --
        # which a stroked outline was not.
        pygame.draw.polygon(panel, edge,
                            self.window_polygon(chamfer, (width, height)))
        inner_size = (max(1, width - 2 * border), max(1, height - 2 * border))
        inner_chamfer = max(0, chamfer - border)
        inner = [(x + border, y + border) for x, y in
                 self.window_polygon(inner_chamfer, inner_size)]
        pygame.draw.polygon(panel, fill, inner)

        header = self.header_pixels(rect)
        if header > border:
            # Inset with the interior, or the band paints over the rim for its
            # own height and the frame loses its left, right and top edges.
            pygame.draw.polygon(
                panel, band,
                self.header_polygon(header - border, inner_chamfer, border,
                                    inner_size))
            line_y = max(header, border + 2)
            # The band's lower edge used to carry a rule in the frame's own edge
            # colour and a brighter accent over it, and `line_y` survives only
            # as the title's baseline. Both are gone: the rule was the same
            # weight as the frame and read as a stroke that had slipped, and the
            # accent made it a second, brighter edge under a band that already
            # separates itself from the panel by being a step lighter.
            self.draw_window_title(panel, line_y, chamfer, title_colour)

        # The two short bright ticks just inside the bottom edge are gone as
        # well. They sat a few pixels above the lower corners, a little apart
        # from each other, and read as lines drawn *over* the window rather
        # than as part of it.
        self.surface.blit(panel, rect.topleft)

    def draw_window_title(self, panel, baseline_y, chamfer, colour):
        if not self.window_title:
            return
        fonts = g.fonts.get("special") or g.fonts.get("normal")
        if not fonts:
            return
        size = max(1, int(baseline_y * .55))
        font = fonts[min(size, len(fonts) - 1)]
        # The stored title is the English msgid (or a name that is already
        # translated). Translate here, on the draw, so a language change
        # updates the band without rebuilding the screen.
        rendered = font.render(_(self.window_title).upper(), True, colour)
        panel.blit(rendered,
                   (chamfer + 12,
                    max(0, (baseline_y - rendered.get_height()) // 2)))

    def redraw(self):
        if not self.draws_window():
            super(Dialog, self).redraw()
            return

        # The shaped panel, then exactly the parts of Text.redraw() that belong
        # on top of it. BorderedWidget's rectangular fill is deliberately
        # skipped -- it would paint the cut corners back in.
        widget.Widget.redraw(self)
        self.draw_window()
        if self.text is not None:
            self.draw_plate()
            self.print_text()
            self.draw_scroll_indicator()

    def fades_own_chrome(self):
        """A window that has lost focus dims its frame, band and title too.

        Only a window: a screen is content, and the mask belongs to whatever is
        behind it. A theme with `window_shape = rect` draws no chrome of its
        own, so nothing changes for a legacy theme.
        """
        return self.draws_window() and getattr(g, "fade_mask", None) is not None

    # -- The close box ---------------------------------------------------------

    # Buttons whose only job is to close this window. A window that carries a
    # close box in its corner does not need them as well, so they are hidden
    # while the box is there -- and kept, invisibly, as the screen's own cancel
    # path: a hidden button still answers a key handler, which is what makes
    # hiding one safe and why Escape keeps working after BACK is gone.
    close_only_buttons = ()

    # A menu is a column of buttons, not a window with contents in it: its
    # buttons already say how to leave.
    draws_close_box = True

    def wants_close_button(self):
        """Whether this dialog carries a close box in its header band."""
        return (self.window_frame and self.draws_close_box
                and g.dialog_style("close_button", "none") == "corner")

    def has_close_box(self):
        """The same question as a fact about the theme, for geometry.

        Deliberately the prediction rather than `self.close_button is not None`:
        a screen lays itself out at the start of `rebuild()`, before the button
        has been created or dropped, and a layout that had to wait a frame would
        jump once on every theme switch.
        """
        return self.wants_close_button()

    def make_close_button(self):
        """A close box in the header band's right-hand corner."""
        self.close_button = button.FunctionButton(
            self, (-1, 0), (-.02, -.02),
            role="chrome", icon="icon_cancel", text="",
            anchor=constants.TOP_LEFT,
            function=self.close_window,
            # A selectable text sets its own background on every redraw, so the
            # face is given as its two states rather than as `background_color`.
            # The box sits quietly in the band until it is hovered.
            unselected_color="dialog_header_fill",
            selected_color="ui_select",
            border_color="dialog_frame_edge")
        return self.close_button

    def sync_close_button(self):
        """Add the box, drop it, or hide the buttons it replaces."""
        wanted = self.wants_close_button()
        if wanted and self.close_button is None:
            self.make_close_button()
        elif not wanted and self.close_button is not None:
            self.close_button.parent = None
            self.close_button = None

        if self.close_button is not None:
            # A theme that asks for the corner box but draws no glyphs would get
            # an empty button; a letter is a worse close box than an icon and a
            # better one than nothing.
            icons = g.dialog_style("icon_buttons", "none") != "none"
            self.close_button.text = "" if icons else "X"

        for name in self.close_only_buttons:
            other = getattr(self, name, None)
            if other is not None and other is not self.close_button:
                other.visible = not wanted

    def place_close_button(self):
        """Put the box in the band's corner, in shares of this dialog.

        Shares rather than pixels because that is how every widget in this tree
        is placed, and a resize has to move the box with the corner it belongs
        to rather than leave it at a stale offset.
        """
        close = getattr(self, "close_button", None)
        if close is None:
            return

        width, height = self.real_size
        band = self.header_pixels()
        if band <= 0 or width <= 0 or height <= 0:
            close.visible = False
            return

        rect = self.window_rect()
        border = max(1, int(self.border_width))
        margin = max(3, int(round(g.dialog_style("margin", 0.01) * width)))
        # Nearly the band's own height: a close box is the smallest thing a
        # player aims at, and a 9px glyph in a 16px square is a puzzle, not a
        # target.
        side = max(10, int(round(band * .78)))
        side = min(side, max(10, height // 3), max(10, width // 3))
        top = rect.top + max(border, (band - side) // 2)
        left = rect.right - margin - side

        # A margin from the frame's right edge is the whole rule, because the
        # top-right corner is square. While that corner was cut, the edge there
        # was a diagonal and the box hung over it -- it had to be pulled in by
        # the width of the cut, which is what this used to do. The cut moved to
        # the two opposing corners, so the box is back at the margin.
        close.visible = True
        close.pos = (-max(1, left) / float(width),
                     -max(1, top) / float(height))
        close.size = (-side / float(width), -side / float(height))

    def close_window(self, event=None):
        """Close this dialog the way its own cancel path would.

        The box is the mouse's Escape, so it has to produce the same exit value
        the keyboard's cancel produces: a caller that branches on that value
        must not be able to tell which one the player used.
        """
        on_escape = getattr(self, "on_escape", None)
        if callable(on_escape):
            on_escape(event)
            return

        for name in ("cancel_button", "back_button", "no_button", "ok_button"):
            candidate = getattr(self, name, None)
            if isinstance(candidate, button.Button):
                candidate.activate_with_sound(event)
                return

        raise constants.ExitDialog(False)

    # -- The bottom row of buttons --------------------------------------------

    # Whether this dialog lays out a row of its own at the bottom. A window with
    # two answers -- Continue/Skip, Yes/No, OK/BACK -- groups that pair in the
    # bottom-right corner under the 2030 layout. A screen whose row is something
    # else (four buttons across the width, a hidden BACK at the bottom centre)
    # says so here, and the theme leaves it at the coordinates it shipped with.
    owns_button_row = False

    def button_row_inset(self):
        """The right inset of a bottom button row, as a share of the width.

        The theme's `margin`, plus what the cut corner takes out of the row. The
        cut is a diagonal, so at the row's own bottom edge it is still
        `chamfer - margin` in from the frame: a pair placed at the plain margin
        ends with its bottom-right corner on the diagonal rather than inside it.
        Adding that term leaves the row exactly the margin clear of the
        diagonal, which is the same air every other widget keeps from the frame.

        A window that is not chamfered has no cut, so this is the margin and
        nothing else -- which is why a legacy theme is placed where it always
        was.
        """
        margin = g.dialog_style("margin", .01)
        size = getattr(self, "_real_size", None)
        if not size or not size[0] or not size[1]:
            # No size yet: the first layout happens before the first resize.
            return margin
        if self.themed_shape() != "chamfer":
            return margin
        width, height = size
        into_cut = max(0, self.cut_pixels(size) - int(round(margin * height)))
        return margin + into_cut / float(width)

    def place_bottom_button_pair(self, left, right, width, height=-.10,
                                 gap=None):
        """Put two buttons side by side in the bottom-right corner.

        Both are anchored to that corner and positioned by their *right* edge,
        so the gap between them and the space to the frame's edge are one number
        each -- rather than a left edge and a right edge that have to agree.
        `width` and `height` are negative shares, as every `size` in this tree
        is.
        """
        if gap is None:
            gap = g.dialog_style("margin", .01)
        right_edge = 1 - self.button_row_inset()
        span = abs(width)
        bottom = -(1 - g.dialog_style("margin", .01))
        for index, widget_ in enumerate((right, left)):
            widget_.anchor = constants.BOTTOM_RIGHT
            widget_.pos = (-(right_edge - index * (span + gap)), bottom)
            widget_.size = (width, height)

    def place_button_row(self):
        """Where this dialog's own bottom row goes. Nothing, unless it has one."""
        return

    def rebuild(self):
        super(Dialog, self).rebuild()
        self.sync_close_button()
        self.place_button_row()

    def reconfig(self):
        """Re-place the button row on a theme switch.

        A switch reconfigures the tree rather than rebuilding it, and whether
        the row sits grouped in the corner or at the two edges is the theme's
        decision -- so it has to be re-asked here, not only at build time.
        """
        super(Dialog, self).reconfig()
        self.place_button_row()

    def resize(self):
        super(Dialog, self).resize()
        self.place_close_button()
        self.place_button_row()

    def start_timer(self, force = False):
        if self.needs_timer == None:
            self.needs_timer = bool(self.handlers.get(constants.TICK, False))
        if self.needs_timer or force:
            pygame.time.set_timer(pygame.USEREVENT, 1000 // g.FPS)

    def stop_timer(self):
        pygame.time.set_timer(pygame.USEREVENT, 0)

    def reset_timer(self):
        self.stop_timer()
        self.start_timer()

    def show(self):
        """Shows the dialog and enters an event-handling loop."""
        from singularity.code.mixer import play_music

        self.visible = True
        self.needs_rebuild = True
        self.start_timer()

        # Pretend to jiggle the mouse pointer, to force buttons to update their
        # selected state.
        Dialog.top.maybe_update()
        self.fake_mouse()

        # Force a timer tick at the start to make sure everything's initialized.
        if self.needs_timer:
            self.handle(pygame.event.Event(pygame.USEREVENT))
            Dialog.top.maybe_update()
            pygame.display.flip()

        # Remember which dialog was running, so a global hotkey (quickload,
        # the cheat toggle) can tell whether the map screen is what the player
        # is looking at.  Upstream c2401ab.
        previous_dialog = Dialog.current_dialog
        Dialog.current_dialog = self

        while True:
            # Update handles updates of all kinds to all widgets, as needed.
            Dialog.top.maybe_update()
            play_music()
            event = pygame.event.wait()
            result = self.handle(event)
            if result != constants.NO_RESULT:
                break
        self.stop_timer()
        self.visible = False
        Dialog.current_dialog = previous_dialog
        return result

    def add_handler(self, type, handler, priority = 100):
        """Adds a handler of the given type, with the given priority."""
        insort_right_w_key(self.handlers.setdefault(type, []),
                           (priority, handler), key=operator.itemgetter(0))

    def remove_handler(self, type, handler):
        """Removes all instances of the given handler from the given type."""
        self.handlers[type] = [h for h in self.handlers.get(type, [])
                                 if h[1] != handler]

    def add_key_handler(self, key, handler, priority=100):
        """Adds a key handler to the given key, with the given priority."""
        insort_right_w_key(self.key_handlers.setdefault(key, []),
                           (priority, handler), key=operator.itemgetter(0))

    def remove_key_handler(self, key, handler):
        """Removes all instances of the given handler from the given key."""
        self.key_handlers[key] = [h for h in self.key_handlers.get(key, [])
                                    if h[1] != handler]

    def handle(self, event):
        """Sends an event through all the applicable handlers, returning
           constants.NO_RESULT if the event goes unhandled or is handled without
           requesting the dialog to exit.  Otherwise, returns the value provided
           by the handler."""
        # Get the applicable handlers.  The handlers lists are all sorted.
        # If more than one handler type is applicable, we use [:] to make a
        # copy of the first type's list, then insort_all to insert the elements
        # of the other lists in proper sorted order.
        handlers = []
        if event.type == pygame.MOUSEMOTION:
            # Compress multiple MOUSEMOTION events into one.
            # Note that the pos will be wrong, so pygame.mouse.get_pos() must
            # be used instead.
            time.sleep(1. / g.FPS)
            pygame.event.clear(pygame.MOUSEMOTION)

            # Generic mouse motion handlers.
            handlers = self.handlers.get(constants.MOUSEMOTION, [])[:]

            # Drag handlers.
            if event.buttons[0]:
                insort_all(handlers, self.handlers.get(constants.DRAG, []))
        elif SDL_V2 and event.type == pygame.MOUSEWHEEL:
            # Generic mouse wheel handlers.
            handlers = self.handlers.get(constants.MOUSEWHEEL, [])[:]
        elif event.type == pygame.USEREVENT:
            # Clear excess timer ticks.
            pygame.event.clear(pygame.USEREVENT)

            # Timer tick handlers.
            handlers = self.handlers.get(constants.TICK, [])

        elif event.type in (pygame.KEYDOWN, pygame.KEYUP):

            # The global hotkeys (ALT+Enter fullscreen, F5 quicksave, F6
            # reload theme, F9 quickload, F11 cheat menu) are registered in
            # singularity/code/global_hotkeys.py; upstream 176581f moved them
            # out of this method, so this is only the dispatch.
            hotkey_action = detect_global_hotkey(event)
            if hotkey_action is not None:
                hotkey_action()
            elif event.type == pygame.KEYDOWN:
                # Generic keydown handlers.
                insort_all(handlers, self.handlers.get(constants.KEYDOWN, []))

                # Generic key event handlers.
                insort_all(handlers, self.handlers.get(constants.KEY, []))

                if event.unicode:
                    # Unicode-based keydown handlers for this particular key.
                    insort_all(handlers, self.key_handlers.get(event.unicode, []))
                    # Same letter, other case or other script. И and i are one
                    # shortcut; the layout decides which character arrives.
                    # Equal priority keeps the exact letter first.
                    for registered, registered_handlers in self.key_handlers.items():
                        if (isinstance(registered, str)
                                and registered != event.unicode
                                and button.hotkey_matches(registered, event.unicode)):
                            insort_all(handlers, registered_handlers)
                # Keycode-based handlers for this particular key.
                insort_all(handlers, self.key_handlers.get(event.key, []))

            else:  # event.type == pygame.KEYUP:

                # Generic keyup handlers.
                insort_all(handlers, self.handlers.get(constants.KEYUP, []))

            # OLPC XO-1 ebook mode.
            if g.ebook_mode and event.key in KEYPAD:
                handlers = [(0, handle_ebook)]
        elif event.type == pygame.MOUSEBUTTONUP:
            # A wheel axis is not a click. SDL2 turns 4/5 into a MOUSEWHEEL
            # event, so what arrives here is either that same notch reported
            # twice or the horizontal axis (6/7), which pygame never converts.
            # Letting it through dispatched it to the CLICK handlers, and
            # Listbox.on_click() selects the row under the pointer -- on the
            # Options screen that row is the resolution, so flicking the wheel
            # changed the resolution instead of scrolling the list.
            #
            # The 4/5 part used to be turned into PAGEUP/PAGEDOWN on a build
            # without MOUSEWHEEL. That reached Listbox.got_key(), which moves
            # list_pos, and through UpdateListbox list_pos *is* the setting. A
            # wheel may only ever scroll the view; see Listbox.on_mousewheel().
            if event.button in SCROLL_BUTTONS:
                # ...but it is still a wheel. A driver that reports the
                # vertical wheel this way has to scroll what a MOUSEWHEEL
                # scrolls, so the notch is dispatched as one instead of being
                # dropped on the floor. Dropping it is why a dialog body could
                # not be scrolled with an X11 wheel at all.
                #
                # The horizontal axis (6/7) stays inert: nothing in this game
                # scrolls sideways, and turning it into a vertical notch would
                # be a guess about which way the player meant.
                if event.button in (4, 5):
                    return self.call_handlers(
                        self.handlers.get(constants.MOUSEWHEEL, []),
                        wheel_event(1 if event.button == 4 else -1,
                                    getattr(event, "pos", None)))
                return constants.NO_RESULT

            # Mouse click handlers.
            handlers = [] + self.handlers.get(constants.CLICK, [])

            when = time.time()
            where = event.pos
            what = event.button

            old_when, old_where, old_what = self.last_click
            self.last_click = when, where, what

            if what == old_what and when - old_when < .5:
                # Taxicab distance.
                dist = (abs(where[0] - old_where[0]) +
                        abs(where[1] - old_where[1]))

                if dist < 10:
                    # Add double-click handlers, but keep the click handlers.
                    insort_all(handlers,
                               self.handlers.get(constants.DOUBLECLICK, []))
        elif event.type == pygame.VIDEORESIZE:
            # Compress multiple requests and take the last one
            events = pygame.event.get(pygame.VIDEORESIZE)
            if events:
                event = events[-1]
            new_size = tuple(event.size)

            # While fullscreen the window is the desktop and there is nothing to
            # resize. Feeding the compositor's idea of the fullscreen size back
            # into screen_size is what made the fullscreen toggle bounce and
            # made it impossible to leave fullscreen: every mode change caused a
            # resize event, which changed the mode again.
            if g.fullscreen:
                _debug_resize("ignored %r: the window is fullscreen"
                              % (new_size,))
                return constants.NO_RESULT

            # A programmatic mode change makes the window manager answer with a
            # resize event carrying the size we just left. Leaving fullscreen
            # therefore arrives looking like a request to become the desktop
            # size, which is a window that looks exactly like fullscreen -- and
            # granting it produced yet another resize event. That is the
            # oscillation.
            #
            # On Wayland the answer arrives after set_mode() has already
            # returned, so a window of time is the only way to tell it apart
            # from a player dragging the corner.
            if g.mode_change_settling():
                _debug_resize("ignored %r: still settling after a mode change"
                              % (new_size,))
                return constants.NO_RESULT

            # Ignore a no-op resize.
            if new_size == tuple(g.window_size):
                _debug_resize("ignored %r: already that size" % (new_size,))
                return constants.NO_RESULT

            # Adopt the size instead of demanding it. The window is already
            # this size, so there is nothing to enforce, and calling set_mode()
            # here is what let this handler feed itself: the mode change
            # produced another resize event, which produced another mode
            # change. Without that call the loop is structurally impossible.
            if g.adopt_window_size(new_size):
                _debug_resize("adopted %r" % (new_size,))
                Dialog.top.needs_resize = True
        elif event.type == pygame.QUIT:
            raise SystemExit
        elif event.type == pygame.VIDEOEXPOSE:
            # If a window is dragged over the singularity window, we will get a VIDEOEXPOSE event
            # to notify us to redraw the window.  The issue is easier to trigger with pygame 2
            # than with pygame 1.
            self.needs_redraw = True
            return constants.NO_RESULT

        return self.call_handlers(handlers, event)

    def fake_mouse(self):
        """Fakes a MOUSEMOTION event.  MOUSEMOTION handlers must be able to
           handle a None event, in order to support this method."""
        handlers = self.handlers.get(constants.MOUSEMOTION, [])[:]
        self.call_handlers(handlers, event=None)

    def on_close_dialog(self):
        pass

    def call_handlers(self, handlers, event):
        # Feed the event to all the handlers, in priority order.
        for __, handler in handlers:
            try:
                handler(event)
            except constants.Handled:
                break # If it's been handled, we leave the rest alone.
            except constants.ExitDialog as e:
                # Exiting the dialog.
                self.on_close_dialog()
                if e.args:
                    # If we're given a return value, we pass it on.
                    return e.args[0]
                else:
                    # Otherwise, exit with a return value of None.
                    return

        # None of the handlers instructed the dialog to close, so we pass that
        # information back up to the event loop.
        return constants.NO_RESULT


class FocusDialog(Dialog):
    def __init__(self, *args, **kwargs):
        self.focus_list = []
        self.current_focus = None

        super(FocusDialog, self).__init__(*args, **kwargs)

        self.add_key_handler(pygame.K_TAB, self.change_focus, 0)

    def add_focus_widget(self, widget):
        self.focus_list.append(widget)

    def remove_focus_widget(self, widget):
        try:
            self.focus_list.remove(widget)
        except ValueError:
            pass

    def took_focus(self, widget):
        if self.current_focus is not None and self.current_focus is not widget:
            self.current_focus.has_focus = False
        self.current_focus = widget
        widget.has_focus = True

    def clear_focus(self, widget):
        if self.current_focus is not None and self.current_focus is widget:
            self.current_focus.has_focus = False
            self.current_focus = None

    def change_focus(self, event):

        if len(self.focus_list) == 0:
            raise constants.Handled
        elif len(self.focus_list) == 1:

            has_focus = not self.focus_list[0].has_focus
            self.focus_list[0].has_focus = has_focus

            if has_focus:
                self.current_focus = self.focus_list[0]
            else:
                self.current_focus = None

            raise constants.Handled

        backwards = bool(pygame.key.get_mods() & pygame.KMOD_SHIFT)

        if self.current_focus is not None:
            self.current_focus.has_focus = False

        if self.current_focus not in self.focus_list:
            if backwards:
                index = len(self.focus_list) - 1
            else:
                index = 0
        else:
            old_index = self.focus_list.index(self.current_focus)
            if backwards:
                index = old_index - 1 # Correctly wraps to -1
            else:
                index = old_index + 1
                if index > len(self.focus_list):
                    index = 0

        if index == -1 or index == len(self.focus_list):
            self.current_focus = None
        else:
            self.current_focus = self.focus_list[index]
            self.current_focus.has_focus = True

        raise constants.Handled


class NullDialog(Dialog):
    """NullDialog, for when you absolutely, positively need to do nothing at
       all."""

    # A placeholder, not a window.
    window_frame = False

    def show(self):
        pass


class TopDialog(Dialog):
    """A Dialog that sets itself as the top-level dialog.
       It must not have a parent, or exception will occur"""

    # The root of the tree covers the whole screen: it is the desktop, not a
    # window on it.
    window_frame = False

    def __init__(self, *args, **kwargs):
        super(TopDialog, self).__init__(*args, **kwargs)
        self.size = (1, 1)
        self.pos = (0, 0)
        self.anchor = constants.TOP_LEFT
        self.make_top()


class DialogArtPane(widget.BorderedWidget):
    """The picture a scenario dialog shows beside its text.

    The art is optional in every sense. `g.images` is cleared on every theme
    switch and a theme only fills it from the files it ships, so "no picture
    for this dialog yet" is the normal case; the pane then draws its own frame.
    Nothing here may raise on a missing image: a dialog that will not open is
    worse than a dialog with an empty panel in it.
    """

    # Keys to try after `art_key`, nearest first. `is_known()` decides.
    fallback_keys = ()

    def __init__(self, parent, pos, size, anchor=constants.TOP_LEFT,
                 art_key=None, crop=False, fallback_keys=()):
        # Before the super call, not after: Widget.__init__ runs add_hooks(),
        # which syncs the overlay's tick handler, and a handler cannot ask
        # whether it is already hooked before the field exists.
        self._alive_ticks = 0
        self._alive_hooked = False
        self._raster = None
        self._band = None
        self._scaled = None
        # The glitch schedule. `_glitch_start` is None while the picture is
        # still, and the first glitch is scheduled once the tick handler has a
        # key to seed from.
        self._scramble = None
        self._glitch_start = None
        self._next_glitch = None
        # The dialog the tick was registered on. Set by _sync_alive_handler,
        # which runs from add_hooks during the super call below.
        self._tick_host = None

        super(DialogArtPane, self).__init__(
            parent, pos, size, anchor,
            background_color="pane_background_empty",
            border_color="pane_border",
            borders=constants.ALL,
            border_width=g.content_border_width())
        # The frame around a picture has its own colour, because it sits
        # against the picture rather than against the panel: the ordinary pane
        # edge is a few percent of luminance away from the static and vanishes
        # into it. A theme that does not define the name keeps the pane edge,
        # which is what every theme did before the name existed.
        self.border_color = self.pick_border_color()
        self.art_key = art_key
        # A banner wants the whole strip filled, so a picture that does not
        # match its shape is scaled up and cropped rather than letterboxed; a
        # column shows the picture whole and leaves the pane's fill around it.
        self.crop = crop
        self.fallback_keys = tuple(fallback_keys)

        # The live-feed overlay is counted in ticks, never read from the clock,
        # for the same reason the button's hover band is (button.py): a frame
        # drawn without a tick -- which is every frame the snapshot tool and the
        # tests draw -- has to be reproducible.

    @staticmethod
    def pick_border_color():
        """The picture frame's colour name, falling back to the pane's.

        Kept as a name rather than resolved to an RGBA tuple so that a theme
        switch still recolours it, and falling back rather than assuming, so a
        third-party theme that turns the image slot on without defining this
        one draws a frame instead of raising KeyError.
        """
        if "dialog_art_border" in g.colors:
            return "dialog_art_border"
        return "pane_border"

    def reconfig(self):
        self.border_color = self.pick_border_color()
        # The overlay's colours belong to the theme that was current, so both
        # layers are rebuilt on a switch rather than blitted in the old colour.
        self._raster = None
        self._band = None
        super(DialogArtPane, self).reconfig()
        self._sync_alive_handler()

    # A glitch, not a shimmer. The raster and the band are not drawn
    # continuously: they appear, cross the picture once, and then it is still
    # again for a long irregular pause. A permanently crawling overlay competes
    # with the text under it and reads as a broken renderer.
    #
    # The crossing is not a flicker, though. 2600 ms is the period the first
    # continuous version used, so the band moves at the speed that looked right;
    # what was wrong was that it never stopped. With the pause drawn from 9-15 s
    # a glitch occupies about a sixth of the time and starts every eleven to
    # eighteen seconds.
    #
    # The direction is the button's (`draw_hover_effect` in button.py uses the
    # same expression), top to bottom: a scan line runs down a frame, and having
    # the picture's sweep disagree with every hovered button's was the one part
    # of this that read as two effects rather than one machine.
    GLITCH_MIN_MS = 9000
    GLITCH_MAX_MS = 15000
    GLITCH_DURATION_MS = 2600

    # Every second row rather than every third: a finer raster reads as
    # dithering on the picture, which is what the theme asks for here, and it is
    # the one cadence that would collide with the button's if it were shared.
    RASTER_STEP = 2

    @staticmethod
    def overlay_enabled():
        """Both halves have to be there: the theme asking, and the colour.

        A theme that opts in without defining `image_scanline` gets a still
        picture rather than a KeyError while drawing.
        """
        return (g.dialog_style("image_overlay", "none") == "scanline"
                and "image_scanline" in g.colors)

    @staticmethod
    def _overlay_colour(name):
        try:
            return g.resolve_color_alias(name)
        except KeyError:
            return None

    @classmethod
    def _glitch_rng(cls, key):
        """A generator seeded from the art key, so the schedule is repeatable.

        `hash()` cannot be used for this: it is salted per process for strings,
        so the same picture would glitch at different times in two runs of the
        same build, and the theme snapshot could never be reproducible. A digest
        of the name is stable everywhere.
        """
        digest = hashlib.sha256(("glitch:" + str(key)).encode("utf-8")).digest()
        return random.Random(int.from_bytes(digest[:8], "big"))

    def _schedule_glitch(self):
        """Pick when the next glitch starts, in ticks from now."""
        step = 1000.0 / max(1, g.FPS)
        if self._scramble is None:
            self._scramble = self._glitch_rng(self.art_name() or "dialog")
        gap = self._scramble.randint(self.GLITCH_MIN_MS, self.GLITCH_MAX_MS)
        self._next_glitch = self._alive_ticks + max(1, int(gap / step))

    def glitch_progress(self):
        """How far through the current glitch, 0..1, or None when still."""
        if self._glitch_start is None:
            return None
        step = 1000.0 / max(1, g.FPS)
        elapsed = (self._alive_ticks - self._glitch_start) * step
        if elapsed >= self.GLITCH_DURATION_MS:
            return None
        return elapsed / float(self.GLITCH_DURATION_MS)

    def alive_phase(self):
        """Where the band is within the glitch: 0 entering, 1 leaving."""
        progress = self.glitch_progress()
        return 0.0 if progress is None else progress

    def _start_glitch(self):
        self._glitch_start = self._alive_ticks

    def reset_glitch(self):
        """Forget the schedule: a different picture keeps its own clock."""
        self._scramble = None
        self._glitch_start = None
        self._next_glitch = None

    def handle_alive_tick(self, event):
        """Count towards the next glitch, and redraw only while one runs.

        The handler runs every tick because the tick is the only clock the
        widget tree has, but it asks for a redraw only during the glitch itself:
        redrawing a still picture thirty times a second to leave it unchanged is
        exactly the waste this replaced.
        """
        if not self.visible or not self.overlay_enabled():
            return
        self._alive_ticks += 1

        if self.glitch_progress() is not None:
            self.needs_redraw = True
            return

        # The glitch that just finished ended between this tick and the last.
        if self._glitch_start is not None:
            self._glitch_start = None
            self.needs_redraw = True
            self._schedule_glitch()
            return

        if self._next_glitch is None:
            # Scheduled on the first tick rather than in __init__: the seed is
            # the art key, and a pane is constructed before its key is set.
            self._schedule_glitch()
            return

        if self._alive_ticks >= self._next_glitch:
            self._start_glitch()
            self.needs_redraw = True

    def _dialog_host(self):
        """The dialog whose timer this pane's glitch runs on.

        A picture parented to the dialog finds it immediately. One parented to
        a pane walks up: only a dialog has a handler registry, and only the
        dialog that is showing receives ticks.
        """
        host = self.parent
        while host is not None and not hasattr(host, "handlers"):
            host = getattr(host, "parent", None)
        return host

    def _sync_alive_handler(self):
        """Add or drop the tick handler to match the current theme."""
        host = self._dialog_host()
        if host is None:
            return
        wanted = self.overlay_enabled()
        if wanted and not self._alive_hooked:
            host.add_handler(constants.TICK, self.handle_alive_tick)
            self._alive_hooked = True
            self._tick_host = host
        elif not wanted and self._alive_hooked:
            (self._tick_host or host).remove_handler(
                constants.TICK, self.handle_alive_tick)
            self._alive_hooked = False
            self._tick_host = None

    def add_hooks(self):
        super(DialogArtPane, self).add_hooks()
        self._sync_alive_handler()

    def remove_hooks(self):
        super(DialogArtPane, self).remove_hooks()
        host = getattr(self, "_tick_host", None)
        if host is not None:
            host.remove_handler(constants.TICK, self.handle_alive_tick)
        self._alive_hooked = False
        self._tick_host = None

    def _raster_layer(self, size):
        colour = self._overlay_colour("image_scanline")
        if colour is None:
            return None
        key = (size, tuple(colour))
        if self._raster is None or self._raster[0] != key:
            layer = pygame.Surface(size, pygame.SRCALPHA)
            for y in range(0, size[1], self.RASTER_STEP):
                layer.fill(colour, (0, y, size[0], 1))
            self._raster = (key, layer)
        return self._raster[1]

    def _band_layer(self, size):
        colour = self._overlay_colour("image_scanline_sweep")
        if colour is None:
            return None
        key = (size, tuple(colour))
        if self._band is not None and self._band[0] == key:
            return self._band[1]

        width, height = size
        # Taller than the button's half-height band: it is a glow crossing a
        # picture, not a sheen on a control.
        band_height = max(8, int(height * 1.4))
        red, green, blue, alpha = colour
        band = pygame.Surface((width, band_height), pygame.SRCALPHA)
        for row in range(band_height):
            across = row / float(max(1, band_height - 1))
            fade = 1.0 - abs(across * 2.0 - 1.0)
            # Squared, so the band has no readable edge anywhere on the picture.
            band.fill((red, green, blue, int(alpha * fade * fade)),
                      (0, row, width, 1))
        self._band = (key, band)
        return band

    def draw_overlay(self, inset, box):
        """The live-feed treatment, over the picture and inside its frame.

        Two parts with two different jobs, and they are on different clocks:

        * the **raster** is always on. A fine, 5%-alpha line every second row is
          what makes a photograph read as a screen rather than as a painting,
          and it is invisible while it is there;
        * the **band** comes and goes. It is the thing that says "this signal is
          live", and it is the thing worth being rare.

        Drawing the raster only during a glitch was wrong in a way that showed:
          the picture visibly lost its texture the instant the band finished, so
          the eye read the end of every glitch as a change to the *picture*
          rather than as the band leaving. The raster is cheap and static, so it
          costs no redraws to keep it.
        """
        if not self.overlay_enabled() or box[0] < 4 or box[1] < 4:
            return

        self.surface.set_clip(pygame.Rect(inset, inset, box[0], box[1]))
        try:
            raster = self._raster_layer(box)
            if raster is not None:
                self.surface.blit(raster, (inset, inset))

            # The band is the part that is only sometimes there.
            band = (self._band_layer(box)
                    if self.glitch_progress() is not None else None)
            if band is not None:
                # From entirely above the box to entirely below it -- the
                # button's own expression, and the same direction, so the band
                # enters and leaves the frame instead of appearing in the
                # middle of the picture.
                span = box[1] + band.get_height()
                offset = int(self.alive_phase() * span) - band.get_height()
                self.surface.blit(band, (inset, inset + offset))
        finally:
            self.surface.set_clip(None)

    def art_names(self):
        """The keys this pane will try, in order, ending at the placeholder."""
        names = []
        if self.art_key:
            names.append(self.art_key)
        for key in self.fallback_keys:
            if key and key not in names:
                names.append(key)
        if PLACEHOLDER_ART not in names:
            names.append(PLACEHOLDER_ART)
        return names

    @staticmethod
    def is_known(name):
        """Whether this name can be drawn, without decoding it.

        `g.images` holds what the theme loaded eagerly; `has_dialog_art` answers
        for the plates that are decoded on demand. Asking here rather than in
        `fetch()` is what keeps a redraw from decoding a plate it is not going
        to show.
        """
        return name in g.images or g.has_dialog_art(name)

    def art_name(self):
        """The key that will actually be drawn, or None if nothing can be."""
        for name in self.art_names():
            if self.is_known(name):
                return name
        return None

    @staticmethod
    def peek(name):
        """The picture under a name if it is already in memory, else None.

        Never decodes, so a redraw can ask "is this still the picture I scaled"
        for free.
        """
        surface = g.images.get(name)
        if surface is not None:
            return surface
        return g.peek_dialog_art(name)

    @staticmethod
    def fetch(name):
        surface = g.images.get(name)
        if surface is not None:
            return surface
        return g.dialog_art(name)

    def inner_box(self):
        """(inset, (width, height)): the drawable area inside the frame."""
        inset = max(1, self.border_width)
        box = (self.real_size[0] - 2 * inset, self.real_size[1] - 2 * inset)
        if box[0] < 1 or box[1] < 1:
            return None
        return inset, box

    def redraw(self):
        super(DialogArtPane, self).redraw()

        area = self.inner_box()
        if area is None:
            return
        inset, box = area

        # Which key wins is decided without decoding, and the scale is kept
        # against the name *and* the surface it came from: once a plate is
        # scaled for this pane, a redraw neither decodes nor re-scales it. The
        # identity check matters -- two different surfaces under one name (a
        # theme that swaps its art, a test that injects one) must not share a
        # cached copy.
        name = self.art_name()
        if name is None:
            return
        cache_key = (name, box, self.crop)
        source = self.peek(name)
        if (self._scaled is None or self._scaled[0] != cache_key
                or self._scaled[1] is not source):
            art = source if source is not None else self.fetch(name)
            if art is None:
                return
            art_width, art_height = art.get_size()
            if self.crop:
                scale = max(box[0] / float(art_width),
                            box[1] / float(art_height))
            else:
                scale = min(box[0] / float(art_width),
                            box[1] / float(art_height))
            target = (max(1, int(art_width * scale)),
                      max(1, int(art_height * scale)))
            self._scaled = (cache_key, art,
                            image_module.scale(art, target))

        scaled = self._scaled[2]

        # A covering picture is *larger* than the box in one axis, so its blit
        # offset is negative there and it paints over the frame on that axis --
        # which is why the banner had a frame on the left and right and none on
        # the top and bottom. The clip is what makes the frame survive a crop at
        # any aspect ratio, and it is reset in a finally because a clip left
        # behind would confine every later widget drawn onto this surface.
        self.surface.set_clip(pygame.Rect(inset, inset, box[0], box[1]))
        try:
            self.surface.blit(
                scaled, (inset + (box[0] - scaled.get_width()) // 2,
                         inset + (box[1] - scaled.get_height()) // 2))
        finally:
            self.surface.set_clip(None)

        # Over the picture, never over the frame: the overlay is part of the
        # image, so it is drawn last and clipped the way the image is.
        self.draw_overlay(inset, box)


class TextDialog(Dialog):
    # The picture this dialog shows beside its text. A theme that turns the
    # image slot on looks this name up in g.images, which is filled from
    # <theme>/images/<name>.png: dropping the file in is the whole wiring.
    art_key = None

    # Keys tried after `art_key`, nearest first. A theme that ships a plate for
    # a base type but not yet for the group that discovered it should show the
    # base type's plate, not static -- so the chain is what makes a partial set
    # of art degrade into "a related picture" instead of "no picture".
    art_fallbacks = ()

    def __init__(self, parent, pos=None, size=(.50, .5),
                 anchor=None, **kwargs):
        art_key = kwargs.pop("art_key", _UNSPECIFIED)
        if art_key is not _UNSPECIFIED:
            self.art_key = art_key

        kwargs.setdefault("valign", constants.TOP)
        kwargs.setdefault("align", constants.LEFT)
        kwargs.setdefault("shrink_factor", .88)
        kwargs.setdefault("text_size", "dialog_text")
        kwargs.setdefault("background_color", "text_dialog_background")
        kwargs.setdefault("border_color", "text_dialog_border")
        kwargs.setdefault("borders", constants.ALL)

        # Geometry. A theme may centre its dialogs; a dialog that was handed a
        # position of its own keeps it, because that caller has placed itself
        # deliberately (a confirmation under its own button, a filter list
        # beside the log it filters).
        if pos is None:
            if self.is_centred():
                pos = (.5, .5)
                if anchor is None:
                    anchor = constants.MID_CENTER
                if isinstance(parent, Dialog):
                    # A dialog opened *from* a window is a window in it, not a
                    # window on the desktop. Measured against the screen it can
                    # be centred on a point outside the frame it hangs in -- and
                    # a widget that hangs over its parent has its surface
                    # clipped to it, which is a message whose lower half, and
                    # whose OK button, are simply not drawn. Centred in the
                    # parent instead, the same box lands inside it.
                    pos = (-.5, -.5)
            else:
                pos = (.5, .1)
        if anchor is None:
            anchor = constants.TOP_CENTER

        border_width = g.dialog_style("border_width", 1)
        if border_width != 1:
            kwargs.setdefault("border_width", border_width)

        super(TextDialog, self).__init__(parent, pos, size, anchor, **kwargs)

        self.image_pane = None
        # The art key is the opt-in. A dialog that names no picture is a dialog
        # no picture belongs in, whatever the theme says about image slots.
        if self.art_key and g.dialog_style("image_slot", "none") != "none":
            self.add_art_pane()

        self.text_padding = self.content_insets()
        apply_text_plate(self, is_frame=True)
        self.build_scroll_handlers()

    # A body longer than its block scrolls instead of shrinking its type and
    # drawing past the block. `none` is the behaviour every theme had before the
    # key existed, so a legacy dialog draws exactly what it always did.
    #
    # A property rather than a value set in __init__: a theme switch has to
    # change it, and the switch reconfigures widgets rather than rebuilding
    # them.
    scrollable = property(lambda self: g.dialog_style("scroll_body", "none")
                          == "block")

    def scrollable_body(self):
        """Whether this dialog's body scrolls, from the theme's [dialog]."""
        return self.scrollable

    def build_scroll_handlers(self):
        """Register the wheel on *this* dialog, which is the one running.

        It used to go on `self.parent`, the way every other widget registers its
        handlers -- and that is why a long message did not scroll. A modal
        dialog runs its own `handle()` loop, so the map screen or menu it hangs
        from is not in that loop at all and the handler never fired. A dialog is
        itself a Dialog with its own registry, and `show()` dispatches through
        it.

        Both spellings of the wheel arrive here as one event: SDL2 sends
        MOUSEWHEEL, and a driver that reports buttons 4 and 5 has them turned
        into the same event by `Dialog.handle()`. A dialog answering only one
        of them is scrollable on some machines and not others.

        Registered at BODY_SCROLL_PRIORITY so a listbox under the pointer keeps
        its own wheel.
        """
        self.remove_handler(constants.MOUSEWHEEL, self.handle_body_scroll)
        self.add_handler(constants.MOUSEWHEEL, self.handle_body_scroll,
                         BODY_SCROLL_PRIORITY)

    def clear_scroll_handlers(self):
        if getattr(self, "handlers", None) is None:
            return
        self.remove_handler(constants.MOUSEWHEEL, self.handle_body_scroll)

    def add_hooks(self):
        super(TextDialog, self).add_hooks()
        # Widget.__init__ runs add_hooks() before Dialog has created its handler
        # registry, so the first call is skipped; __init__ registers the handler
        # once the registry exists, and a re-parent comes through here.
        if getattr(self, "handlers", None) is not None:
            self.build_scroll_handlers()

    def remove_hooks(self):
        super(TextDialog, self).remove_hooks()
        self.clear_scroll_handlers()

    def handle_body_scroll(self, event):
        """The wheel -- either spelling -- over a body that can scroll."""
        if not self.visible or not self.scrollable_body():
            return
        # A MOUSEWHEEL event carries no position in pygame 2 -- it has x, y and
        # precise_y, all about the wheel itself -- so the pointer is asked for
        # directly. Reading event.pos here raised AttributeError the first time
        # a real wheel was turned inside a dialog, which no test caught because
        # the tests delivered a hand-made event that had one.
        position = getattr(event, "pos", None) or pygame.mouse.get_pos()
        if not self.is_over(position):
            return
        rows = -int(getattr(event, "y", 0) or 0) * 2
        if self.scroll_body_by(rows):
            raise constants.Handled

    def rebuild(self):
        # A new message starts at its beginning. A scroll offset carried over
        # from the previous page would open the next one in the middle.
        self.scroll_lines = 0
        super(TextDialog, self).rebuild()

    def set_art_key(self, key, fallbacks=None):
        """Point this dialog at another picture.

        The message list uses it to swap the plate with the text when the player
        pages through events. A dialog whose theme gives it no slot has no pane,
        and asking is not an error: the key is merely recorded.
        """
        self.art_key = key
        if fallbacks is not None:
            self.art_fallbacks = tuple(fallbacks)
        if self.image_pane is None:
            if key and g.dialog_style("image_slot", "none") != "none":
                self.add_art_pane()
            return
        self.image_pane.art_key = key
        self.image_pane.fallback_keys = tuple(self.art_fallbacks)
        self.image_pane.reset_glitch()
        self.image_pane._scaled = None
        self.image_pane.needs_redraw = True

    @staticmethod
    def is_centred():
        return g.dialog_style("anchor", "top_center") == "mid_center"

    def art_pane_right(self):
        """Where a left-hand picture ends, as a fraction of the width.

        Zero unless the theme asks for a column: a banner across the top moves
        nothing sideways.
        """
        if self.image_pane is None or g.dialog_style("image_slot", "none") != "left":
            return 0.0
        margin = g.dialog_style("margin", 0.0)
        width = g.dialog_style("image_slot_width", .28)
        return min(.75, margin + width + ART_GAP)

    def art_pane_bottom(self):
        """Where the content starts below the picture, as a fraction of the height.

        Zero unless the theme asks for a banner: a column starts at the top.
        """
        if self.image_pane is None or g.dialog_style("image_slot", "none") != "top":
            return 0.0
        margin = g.dialog_style("margin", 0.0)
        return margin + g.dialog_style("image_slot_height", .34) + ART_GAP

    def content_margins(self):
        """(margin, left, top): where this dialog's own widgets may start."""
        margin = g.dialog_style("margin", .01)
        top = margin + self.header_fraction()
        if self.image_pane is None:
            return margin, margin, top
        if g.dialog_style("image_slot", "none") == "left":
            return margin, self.art_pane_right(), top
        return margin, margin, self.header_fraction() + self.art_pane_bottom()

    def content_insets(self, padding=None):
        """How far this dialog's own text sits from its frame, per side."""
        if padding is None:
            padding = g.dialog_style("padding", 0.0)
        left, right = self.body_insets(padding)
        return (left,
                self.header_fraction() + max(padding, self.art_pane_bottom()),
                right, padding)

    def body_insets(self, padding):
        """The left and right inset for the body text.

        A theme may ask for the paragraph to be as wide as the picture above it
        (`text_width = pane`). The banner is inset by `margin` and the text by
        `padding`, and those are different numbers -- 0.02 and 0.04 in the 2030
        theme -- so a dialog with a banner used to have text stopping short of
        both of its picture's edges. With `pane` the text takes the picture's
        insets, and the block behind it follows, because the block is measured
        from the text rather than from the frame.
        """
        if (g.dialog_style("text_width", "padding") != "pane"
                or self.image_pane is None):
            return padding, padding
        margin = g.dialog_style("margin", 0.0)
        # A column down the side still owns its width, so `max` and not `margin`
        # alone: the text starts where the column ends, not underneath it.
        return max(margin, self.art_pane_right()), margin

    def add_art_pane(self):
        margin = g.dialog_style("margin", 0.0)
        # Below the header band: the banner belongs under the bar, not behind it.
        top = margin + self.header_fraction()
        if g.dialog_style("image_slot", "none") == "top":
            height = g.dialog_style("image_slot_height", .34)
            self.image_pane = DialogArtPane(
                self, (-margin, -top), (-(1 - 2 * margin), -height),
                anchor=constants.TOP_LEFT, art_key=self.art_key, crop=True,
                fallback_keys=self.art_fallbacks)
        else:
            width = g.dialog_style("image_slot_width", .28)
            self.image_pane = DialogArtPane(
                self, (-margin, -top),
                (-width, -(1 - 2 * margin - top) * .70),
                anchor=constants.TOP_LEFT, art_key=self.art_key,
                fallback_keys=self.art_fallbacks)


class YesNoDialog(TextDialog):
    """A Dialog with YES and NO buttons which exits the dialog with True and
    False return values, respectively.
    """
    art_key = "dialog_confirm"

    def __init__(self, parent, *args, **kwargs):
        self.parent = parent
        self.window_title = N_("CONFIRM")

        yes_type = kwargs.pop("yes_type", N_("&YES"))
        no_type = kwargs.pop("no_type", N_("&NO"))
        self.invert_enter = kwargs.pop("invert_enter", False)
        self.invert_escape = kwargs.pop("invert_escape", False)

        super(YesNoDialog, self).__init__(parent, *args, **kwargs)

        margin = g.dialog_style("margin", .01)
        bottom = -(1 - margin)

        yes_x, yes_anchor = self.SHIPPED_ANSWERS[0]
        no_x, no_anchor = self.SHIPPED_ANSWERS[1]

        self.yes_button = button.ExitDialogButton(self, (yes_x, bottom),
                                                  self.ANSWER_SIZE,
                                                  text=yes_type,
                                                  autotranslate=True,
                                                  icon="icon_ok",
                                                  anchor=yes_anchor,
                                                  exit_code=True, default=False)

        self.no_button = button.ExitDialogButton(self, (no_x, bottom),
                                                 self.ANSWER_SIZE,
                                                 text=no_type,
                                                 autotranslate=True,
                                                 icon="icon_cancel",
                                                 anchor=no_anchor,
                                                 exit_code=False, default=False)

        self.add_key_handler(pygame.K_RETURN, self.on_return)
        self.add_key_handler(pygame.K_KP_ENTER, self.on_return)
        self.add_key_handler(pygame.K_ESCAPE, self.on_escape)

    # Where the two answers sit, and how big they are, when a theme does not
    # group them: Continue against the left bottom corner and Skip against the
    # right, sharing the row. One source for both the dialog's own construction
    # and for `ship_button_row()`, so the two cannot drift.
    SHIPPED_ANSWERS = ((-.1, constants.BOTTOM_LEFT),
                       (-.9, constants.BOTTOM_RIGHT))
    ANSWER_SIZE = (-.3, -.1)

    def ship_button_row(self):
        """Put the answers back where the shipped layout has them.

        Recomputed from the current theme rather than restored from a snapshot:
        the row's height is a share of the window and the margin is part of it,
        so a snapshot taken under one theme would be a percent out under another
        -- and this path runs precisely when the theme changes.
        """
        bottom = -(1 - g.dialog_style("margin", .01))
        for widget_, (x, anchor) in zip((self.yes_button, self.no_button),
                                        self.SHIPPED_ANSWERS):
            widget_.anchor = anchor
            widget_.pos = (x, bottom)

    def place_button_row(self):
        """The two answers as one pair in the corner, clear of the cut corner.

        They were at the two bottom edges -- Continue at the far left, Skip at
        the far right -- which reads as two unrelated questions rather than one
        choice with two answers. Grouped at the right is where a window's way
        out belongs, and the inset keeps the pair off the cut corner so its
        bottom-right button is not sitting on the diagonal.
        """
        if self.owns_button_row:
            return
        if getattr(self, "yes_button", None) is None:
            return
        if g.dialog_style("window_layout", "classic") != "2030":
            self.ship_button_row()
            return
        self.place_bottom_button_pair(self.yes_button, self.no_button,
                                      width=self.ANSWER_SIZE[0],
                                      height=self.ANSWER_SIZE[1])

    def on_return(self, event):
        if event and event.type == pygame.KEYUP:
            return
        if self.invert_enter:
            self.no_button.activate_with_sound(event)
        else:
            self.yes_button.activate_with_sound(event)

    def on_escape(self, event):
        if event and event.type == pygame.KEYUP:
            return
        if self.invert_escape:
            self.yes_button.activate_with_sound(event)
        else:
            self.no_button.activate_with_sound(event)


class MessageDialog(TextDialog):
    """A Dialog with an OK button that exits the dialog, return value of None"""
    art_key = "dialog_message"

    def __init__(self, parent, **kwargs):
        ok_type = kwargs.pop("ok_type", N_("&OK"))
        self.window_title = N_("MESSAGE")

        super(MessageDialog, self).__init__(parent, **kwargs)

        self.ok_button = button.ExitDialogButton(
                                                 self,
                                                 (-.5, -(1 - g.dialog_style("margin", .01))),
                                                 (-.3, -.1),
                                                 autotranslate=True,
                                                 icon="icon_ok",
                                                 text=ok_type,
                                                 anchor=constants.BOTTOM_CENTER)

        self.add_key_handler(pygame.K_RETURN, self.on_return)
        self.add_key_handler(pygame.K_KP_ENTER, self.on_return)

    def on_return(self, event):
        if event.type == pygame.KEYUP: return
        self.ok_button.activate_with_sound(event)


class TextEntryDialog(TextDialog, FocusDialog):

    def __init__(self, parent, pos=(-.50, -.50), size=(.55, .25),
                 anchor=constants.MID_CENTER, **kwargs):
        self.window_title = N_("INPUT")
        kwargs.setdefault('wrap', False)
        kwargs.setdefault("shrink_factor", 1)
        kwargs.setdefault("text_size", "dialog_text")
        self.default_text = kwargs.pop("default_text", "")
        ok_type = kwargs.pop("ok_type", N_("&OK"))
        cancel_type = kwargs.pop("cancel_type", N_("&CANCEL"))
        super(TextEntryDialog, self).__init__(parent, pos, size, anchor, **kwargs)

        self.text_field = text.EditableText(self, (-.05, -.30), (-.90, -.25),
                                            borders=constants.ALL,
                                            background_color="text_entry_background",
                                            base_font="normal")

        self.ok_button = button.FunctionButton(self, (-.14, -.65), (-.30, -.25),
                                               autotranslate=True,
                                               text=ok_type,
                                               function=self.return_text)
        self.cancel_button = button.FunctionButton(self, (-.56, -.65), (-.30, -.25),
                                                   autotranslate=True,
                                                   text=cancel_type,
                                                   function=self.return_nothing)

        self.add_key_handler(pygame.K_RETURN, self.return_text)
        self.add_key_handler(pygame.K_KP_ENTER, self.return_text)
        self.add_key_handler(pygame.K_ESCAPE, self.return_nothing)

    def show(self):
        self.text_field.text = self.default_text
        self.text_field.cursor_pos = len(self.default_text)
        return super(TextEntryDialog, self).show()

    def return_nothing(self, event=None):
        if event and event.type == pygame.KEYUP:
            return
        raise constants.ExitDialog("")

    def return_text(self, event=None):
        if event and event.type == pygame.KEYUP:
            return
        raise constants.ExitDialog(self.text_field.text)

class ChoiceDialog(YesNoDialog):
    # A list is not a scene: a subclass that wants a picture names its own key.
    art_key = None

    list = widget.causes_rebuild("_list")
    def __init__(self, parent, *args, **kwargs):
        self.parent = parent
        self.list = kwargs.pop("list", [])
        self.default = kwargs.pop("default", None)
        kwargs.setdefault("yes_type", N_("&OK"))
        kwargs.setdefault("no_type", N_("&BACK"))
        kwargs.setdefault("background_color", "clear")

        super(ChoiceDialog, self).__init__(parent, *args, **kwargs)

        self.yes_button.exit_code_func = self.return_list_pos
        self.no_button.exit_code = None
        self.listbox = self.make_listbox()

    def make_listbox(self):
        return listbox.Listbox(self, (0, self.below_header(0)),
                               (-1, self.less_header(-.85)),
                               anchor=constants.TOP_LEFT,
                               on_double_click_on_item=self.yes_button.activated,
                               )

    def return_list_pos(self):
        return self.listbox.list_pos

    def show(self):
        if type(self.default) == int:
            self.listbox.list_pos = self.default
        elif type(self.default) == str and self.default in self.list:
            self.listbox.list_pos = self.list.index(self.default)
        else:
            self.listbox.list_pos = 0
        self.listbox.auto_scroll = True

        return super(ChoiceDialog, self).show()

    def rebuild(self):
        self.listbox.list = self.list
        super(ChoiceDialog, self).rebuild()


class ChoiceDescriptionDialog(ChoiceDialog):
    key_list = widget.causes_rebuild("_key_list")

    def __init__(self, parent, *args, **kwargs):
        self.parent = parent
        self.key_list = kwargs.pop("key_list", None)
        self.desc_func = kwargs.pop("desc_func", lambda pane, key: NullDialog)

        super(ChoiceDescriptionDialog, self).__init__(parent, *args, **kwargs)

        self.description_pane = \
            widget.BorderedWidget(self, (-1, self.content_box()[0]),
                                  (-.45, self.content_box()[1]),
                                  anchor = constants.TOP_RIGHT)

    def content_box(self):
        """(top, height) for a pane that must not reach the bottom row."""
        reserve = self.content_bottom_reserve()
        return self.below_header(0), self.less_header(-(1 - reserve))

    def make_listbox(self):
        return listbox.UpdateListbox(self, (0, self.content_box()[0]),
                                     (-.53, self.content_box()[1]),
                                     anchor=constants.TOP_LEFT,
                                     update_func=self.handle_update)

    def _update_desc_pane(self):
        list_pos = self.listbox.list_pos

        if 0 <= list_pos < len(self.list):
            if self.key_list:
                assert len(self.list) <= len(self.key_list), \
                    "Key list must be at least as long as display list."

                key = self.key_list[self.listbox.list_pos]
            else:
                key = self.list[self.listbox.list_pos]
        else:
            key = None

        # Safely clear all the description pane's children. Detach them,
        # rather than dropping the list: a picture pane registers its tick on
        # the dialog, and abandoning the child would leave that handler behind.
        self.description_pane.remove_hooks()
        for child in list(self.description_pane.children):
            child.parent = None
        self.description_pane.add_hooks()

        self.desc_func(self.description_pane, key)

    def rebuild(self):
        self.listbox.needs_rebuild = True
        self._update_desc_pane()
        super(ChoiceDescriptionDialog, self).rebuild()

    def handle_update(self, item):
        self.needs_rebuild = True
        # This is called before the class is fully initialized
        if hasattr(self, 'listbox'):
            self._update_desc_pane()



class SimpleMenuDialog(Dialog):
    # A column of buttons is not a window with contents in it: no close box.
    draws_close_box = False

    width = widget.causes_rebuild("_width")

    def __init__(self, *args, **kwargs):
        buttons = kwargs.pop("buttons", [])
        width = kwargs.pop("width", .20)
        super(SimpleMenuDialog, self).__init__(*args, **kwargs)

        self.size = (-1, -1)
        self.pos = (0, 0)
        self.anchor = constants.TOP_LEFT
        self.width = width

        # An optional line above the buttons, taking one row of the panel. The
        # in-game menu uses it for the difficulty, which stops being permanent
        # furniture on the map screen and becomes something you see when you
        # open the menu. `None` keeps the panel exactly as tall as its buttons.
        self.header_text = None

        self.button_panel = \
            widget.BorderedWidget(self, (-.5, -.5), (0.22, 0.43),
                                  anchor=constants.MID_CENTER,
                                  background_color="simple_menu_background",
                                  border_color="simple_menu_border",
                                  borders=constants.ALL)

        self.buttons = buttons

    @property
    def buttons(self):
        return self._buttons

    @buttons.setter
    def buttons(self, buttons):
        if (hasattr(self, '_buttons') and not self._buttons is None):
            for button in self._buttons:
                if button.parent is not None:
                    button.parent = None

        self._buttons = buttons
        self.needs_rebuild = True

    def rebuild(self):
        shows_header = self.header_is_shown()
        num_buttons = len(self.buttons)
        height = (.06 * (num_buttons + (1 if shows_header else 0))) + .01

        self.button_panel.size = (self.width + .02, height)
        # Under a shaped frame the panel is part of the window, so it draws no
        # border of its own -- a rectangle two pixels inside the frame reads as
        # a second, accidental one. A legacy theme keeps the panel it shipped.
        #
        # Asked of the theme rather than of `draws_window()`: this runs before
        # the first resize, when the dialog has no size to judge yet.
        shaped = self.window_frame and self.themed_shape() == "chamfer"
        self.button_panel.borders = () if shaped else constants.ALL

        y_pos = .01
        if shows_header:
            self.header_text.pos = (.01, y_pos)
            self.header_text.size = (self.width, .05)
            self.header_text.visible = True
            y_pos += .06
        elif self.header_text is not None:
            self.header_text.visible = False

        for button in self.buttons:
            button.parent = self.button_panel

            button.pos = (.01, y_pos)
            button.size = (self.width, .05)
            button.text_size = 24

            y_pos += .06

        super(SimpleMenuDialog, self).rebuild()

    def header_is_shown(self):
        """Whether the line above the buttons takes a row."""
        return self.header_text is not None

    def window_rect(self):
        """The chrome around the panel, not around the screen.

        The widget itself keeps covering the screen, on purpose: its child
        dialogs -- options, save/load, a name prompt -- are drawn into its
        surface, so a small widget would clip them into a corner of it. Only the
        frame that is drawn is as small as the menu, which is what stops the
        in-game menu reading as a window the size of the display with a column
        of buttons lost inside it.
        """
        if not self.draws_window():
            return super(SimpleMenuDialog, self).window_rect()

        panel = getattr(self, "button_panel", None)
        if panel is None or getattr(panel, "collision_rect", None) is None:
            # Not laid out yet: the panel's position does not exist until the
            # first resize, and a dialog that raises on its first frame is worse
            # than one whose frame is briefly the wrong size.
            return super(SimpleMenuDialog, self).window_rect()

        width, height = self.real_size
        margin = g.dialog_style("margin", 0.01)
        side = max(2, int(round(margin * width)))
        pad = max(2, int(round(margin * height)))

        # The band is a share of the *window*, and the window is the panel plus
        # the band plus the margins -- so the band is solved for rather than
        # guessed: b = f * (P + 2*pad + b).
        fraction = self.header_fraction()
        band = 0
        if 0 < fraction < 1:
            band = int(round(fraction * (panel.real_size[1] + 2 * pad)
                             / (1.0 - fraction)))

        rect = pygame.Rect(panel.real_pos[0] - side,
                           panel.real_pos[1] - band - pad,
                           panel.real_size[0] + 2 * side,
                           panel.real_size[1] + band + 2 * pad)
        return rect.clip(pygame.Rect(0, 0, width, height))
