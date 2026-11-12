#file: menu_backdrop.py
#Copyright (C) 2026
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

#The main menu's live background. Only a theme that asks for it draws one.

import random

import pygame

from singularity.code.graphics import constants, g as gg, widget


class MenuBackdrop(widget.Widget):
    """Hex in the side gutters, a faint raster, and a frame.

    The raster stays. The slow band that used to cross the whole menu does not:
    a hover already draws one of those down a button, and the two together read
    as two machines. A short segment still travels the bottom of the frame.

    The buttons and the title are siblings drawn after this, so they cover it.
    The columns stay in the outer fifth of the screen: the title is wider than
    the buttons and is centred, and a column under those letters would read as
    noise on the name of the game.

    The clock is the dialog tick, not the wall clock. A frame drawn without a
    tick -- every test, and the theme snapshot -- is therefore the same picture
    every time, and two runs agree on where the columns are.
    """

    ALPHABET = "0123456789ABCDEF"

    # Outer bands. The title occupies about 0.225..0.775, so 0.20 leaves a gap
    # between the last column and the first letter.
    GUTTER = 0.20

    # The frame around the button stack, as fractions of the menu. The buttons
    # themselves run from x 0.375..0.625 and y 0.20..0.76.
    FRAME = (0.34, 0.16, 0.66, 0.80)

    # Same diagonal as a 2030 window: top-left and bottom-right cut, the other
    # two corners square. A share of the frame's short side, as `chamfer` is a
    # share of a dialog's.
    CHAMFER = 0.045

    TRAIL = 16
    # Every fourth row. The picture's raster is every second row, over a
    # photograph; across the whole menu that spacing reads as stripes.
    RASTER_STEP = 4
    SEED = 0x2030

    # One trip of the segment along the bottom of the frame.
    TRACE_PERIOD_MS = 7000

    # Both halves, as with the picture overlay: the theme asking, and the
    # colours. A theme that opts in and defines none of these draws the fill.
    COLOURS = ("menu_scanline", "menu_glyph", "menu_glyph_head", "menu_frame")

    def __init__(self, parent):
        # Before super: Widget.__init__ calls add_hooks, which syncs the tick.
        self._ticks = 0
        self._hooked = False
        self._static = None
        self._trace = None
        self._masks = None
        self._tinted = {}
        self._columns = None

        super(MenuBackdrop, self).__init__(parent, (0, 0), (1, 1),
                                           constants.TOP_LEFT)

        # This widget's surface is the menu's own surface. The fade pass blits
        # the dim onto every child that is not self-masked, and a full-screen
        # blit here would dim the buttons a second time -- they are drawn into
        # the same pixels and then faded on their own. The void behind a dialog
        # was never dimmed either; the rain is part of that void.
        self.self_mask = True

    @classmethod
    def enabled(cls):
        return (gg.dialog_style("menu_backdrop", "none") == "rain"
                and all(name in gg.colors for name in cls.COLOURS))

    @staticmethod
    def _colour(name):
        try:
            return tuple(gg.resolve_color_alias(name))
        except KeyError:
            return None

    def _period_ticks(self, milliseconds):
        step = 1000.0 / max(1, gg.FPS)
        return max(1, int(round(milliseconds / step)))

    def handle_tick(self, event):
        """Advance the columns and the trace, and ask for a redraw.

        Nothing is flagged when the theme does not want the effect, so a legacy
        menu that somehow still has the handler costs one check per tick.
        """
        if not self.visible or not self.enabled():
            return
        self._ticks += 1
        self.needs_redraw = True

    def _sync_handler(self):
        """Add or drop the tick handler to match the current theme.

        `start_timer` caches whether the dialog had any tick handlers the first
        time it was called. A theme switch onto 2030 happens after that, so the
        cache has to be forgotten or the menu stays still until the next
        launch. The timer itself is only touched while this dialog is the one
        on screen: constructing the menu, and a switch made from a dialog on
        top of it, must not start or stop a clock that is not running the loop.
        """
        host = self.parent
        if host is None or not hasattr(host, "handlers"):
            return
        wanted = self.enabled()
        if wanted and not self._hooked:
            host.add_handler(constants.TICK, self.handle_tick)
            self._hooked = True
        elif not wanted and self._hooked:
            host.remove_handler(constants.TICK, self.handle_tick)
            self._hooked = False
        else:
            return

        host.needs_timer = None
        if host.visible and not getattr(host, "faded", False):
            host.start_timer()
            if not host.needs_timer:
                host.stop_timer()

    def add_hooks(self):
        super(MenuBackdrop, self).add_hooks()
        self._sync_handler()

    def remove_hooks(self):
        super(MenuBackdrop, self).remove_hooks()
        host = self.parent
        if host is not None and self._hooked:
            host.remove_handler(constants.TICK, self.handle_tick)
        self._hooked = False

    def reconfig(self):
        super(MenuBackdrop, self).reconfig()
        self._sync_handler()
        # The tick redraws this widget and not the menu under it. A theme
        # switch has to repaint that menu, or the old columns stay on a theme
        # that no longer draws them.
        if self.parent is not None:
            self.parent.needs_redraw = True

    def _clear(self):
        """The menu's own fill, painted again because the menu did not redraw.

        This surface is the menu's surface. A tick sets needs_redraw here and
        that flag does not climb to the parent, so the parent does not fill.
        Drawing over the previous frame would blend the moving parts into
        themselves until the void is solid cyan. The buttons are siblings drawn
        after this, and
        _repaint_if_covered sends any sibling this rect covers back over the fill.
        """
        parent = self.parent
        colour = getattr(parent, "resolved_background_color", None)
        if colour is None or colour == gg.colors.get("clear"):
            return
        self.surface.fill(colour)

    def _metrics(self, height):
        """The face and the cell the columns are drawn on, or None.

        `special` is the theme's monospace. Every hex glyph is the same width,
        which is what keeps a column from wandering sideways as the digits change.
        """
        try:
            face = gg.fonts["special"]
        except KeyError:
            return None
        size = max(12, int(height * 0.022))
        try:
            font = face[size]
        except (IndexError, KeyError):
            return None
        sample = font.render("0", True, (255, 255, 255))
        if sample.get_width() < 1 or sample.get_height() < 1:
            return None
        return font, size, sample.get_width(), sample.get_height() + 1

    def _mask(self, font, size, char):
        key = (size, char)
        if self._masks is None or self._masks[0] != size:
            self._masks = (size, {})
            self._tinted = {}
        cache = self._masks[1]
        mask = cache.get(char)
        if mask is None:
            rendered = font.render(char, True, (255, 255, 255))
            mask = pygame.Surface(rendered.get_size(), pygame.SRCALPHA)
            mask.blit(rendered, (0, 0))
            cache[char] = mask
        return mask

    def _tinted_glyph(self, font, size, char, colour, fade):
        """One glyph in one colour at one strength.

        The fade is quantized: a trail of sixteen steps would otherwise build
        sixteen copies of every character, and the eye cannot tell the eighth
        from the one beside it.
        """
        red, green, blue, alpha = colour
        strength = max(0, min(255, int(alpha * fade)))
        if strength <= 0:
            return None
        # Eight steps from nothing to the colour's own alpha.
        strength = max(1, int(round(strength / 32.0))) * 32
        strength = min(255, strength)
        key = (size, char, (red, green, blue, strength))
        glyph = self._tinted.get(key)
        if glyph is None:
            glyph = self._mask(font, size, char).copy()
            glyph.fill((red, green, blue, strength),
                       special_flags=pygame.BLEND_RGBA_MULT)
            self._tinted[key] = glyph
        return glyph

    def _build_columns(self, width, height, cell_w, cell_h):
        """Where the columns fall, from a fixed seed.

        Phase is spread through the height and then jittered, so the first
        frame already has glyphs on screen instead of a row of them waiting
        above it. The seed is a constant: `hash()` is salted per process, and
        the snapshot would never settle.
        """
        key = (width, height, cell_w, cell_h)
        if self._columns is not None and self._columns[0] == key:
            return self._columns[1]

        rng = random.Random(self.SEED)
        gutter = int(width * self.GUTTER)
        span = max(1, height // cell_h + self.TRAIL)
        step = max(cell_w + 4, int(cell_w * 1.85))
        columns = []

        def place(x0, x1):
            xs = list(range(x0, max(x0, x1 - cell_w + 1), step))
            jitter = max(1, span // max(1, len(xs)))
            for index, x in enumerate(xs):
                phase = (index * span) // max(1, len(xs))
                phase = (phase + rng.randrange(0, jitter)) % span
                speed = rng.randint(2, 5)
                stream = tuple(rng.randrange(len(self.ALPHABET))
                               for _ in range(48))
                columns.append((x, speed, phase, stream))

        place(2, gutter)
        place(width - gutter, width - 2)
        self._columns = (key, columns)
        return columns

    def _frame_box(self, width, height):
        left = int(width * self.FRAME[0])
        top = int(height * self.FRAME[1])
        right = int(width * self.FRAME[2])
        bottom = int(height * self.FRAME[3])
        return left, top, right, bottom

    def _polygon(self, box, chamfer):
        left, top, right, bottom = box
        # The last pixel of the box, matching Dialog.window_polygon: a vertex
        # one past the edge is clipped, and the stroke disappears on that side.
        far_x = max(left + 1, right - 1)
        far_y = max(top + 1, bottom - 1)
        return [(left + chamfer, top), (far_x, top),
                (far_x, far_y - chamfer), (far_x - chamfer, far_y),
                (left, far_y), (left, top + chamfer)]

    def _stroke(self, layer, colour, points, width):
        """Lines whose alpha is the colour's alpha.

        `pygame.draw.line` writes an opaque pixel on some surfaces. The frame
        is opaque and would not care; the corner ticks are not, and a tick
        that ignores its alpha is a white-hot mark. Draw the shape in white
        and multiply, which is what a tint is.
        """
        mask = pygame.Surface(layer.get_size(), pygame.SRCALPHA)
        pygame.draw.lines(mask, (255, 255, 255, 255), True, points, width)
        mask.fill(colour, special_flags=pygame.BLEND_RGBA_MULT)
        layer.blit(mask, (0, 0))

    def _static_layer(self, size, raster, frame_colour, head):
        key = (size, raster, frame_colour, head)
        if self._static is not None and self._static[0] == key:
            return self._static[1]

        width, height = size
        layer = pygame.Surface(size, pygame.SRCALPHA)
        if raster is not None:
            for y in range(0, height, self.RASTER_STEP):
                layer.fill(raster, (0, y, width, 1))

        box = self._frame_box(width, height)
        left, top, right, bottom = box
        side = min(right - left, bottom - top)
        chamfer = int(side * self.CHAMFER)
        chamfer = max(0, min(chamfer, side // 2 - 2))
        stroke = max(1, int(round(height * 2 / 768.0)))
        points = self._polygon(box, chamfer)

        if frame_colour is not None and side > 16:
            self._stroke(layer, frame_colour, points, stroke)
        if head is not None and side > 16 and chamfer > 0:
            # Brighter ticks at the four corners, on top of the frame. The two
            # cut corners get the diagonal; the square ones get the two edges.
            tick = max(chamfer, stroke * 4)
            marks = pygame.Surface(size, pygame.SRCALPHA)
            far_x = points[1][0]
            far_y = points[3][1]
            pygame.draw.line(marks, (255, 255, 255, 255),
                             points[5], points[0], stroke)
            pygame.draw.line(marks, (255, 255, 255, 255),
                             (left, top + chamfer),
                             (left, min(far_y, top + chamfer + tick)), stroke)
            pygame.draw.line(marks, (255, 255, 255, 255),
                             (left + chamfer, top),
                             (min(far_x, left + chamfer + tick), top), stroke)
            pygame.draw.line(marks, (255, 255, 255, 255),
                             (far_x, top), (far_x, min(far_y, top + tick)),
                             stroke)
            pygame.draw.line(marks, (255, 255, 255, 255),
                             (far_x, top), (max(left, far_x - tick), top),
                             stroke)
            pygame.draw.line(marks, (255, 255, 255, 255),
                             (left, far_y), (left, max(top, far_y - tick)),
                             stroke)
            pygame.draw.line(marks, (255, 255, 255, 255),
                             (left, far_y), (min(far_x, left + tick), far_y),
                             stroke)
            pygame.draw.line(marks, (255, 255, 255, 255),
                             points[2], points[3], stroke)
            pygame.draw.line(marks, (255, 255, 255, 255),
                             (far_x, far_y - chamfer),
                             (far_x, max(top, far_y - chamfer - tick)), stroke)
            pygame.draw.line(marks, (255, 255, 255, 255),
                             (far_x - chamfer, far_y),
                             (max(left, far_x - chamfer - tick), far_y), stroke)
            marks.fill(head, special_flags=pygame.BLEND_RGBA_MULT)
            layer.blit(marks, (0, 0))

        self._static = (key, layer, chamfer, stroke)
        return layer

    def _trace_layer(self, length, thickness, colour):
        key = (length, thickness, colour)
        if self._trace is not None and self._trace[0] == key:
            return self._trace[1]
        segment = pygame.Surface((length, thickness), pygame.SRCALPHA)
        segment.fill(colour)
        self._trace = (key, segment)
        return segment

    def _draw_columns(self, width, height):
        metrics = self._metrics(height)
        body = self._colour("menu_glyph")
        head = self._colour("menu_glyph_head")
        if metrics is None or body is None or head is None:
            return
        font, size, cell_w, cell_h = metrics
        columns = self._build_columns(width, height, cell_w, cell_h)
        span = height + self.TRAIL * cell_h
        for x, speed, phase, stream in columns:
            travelled = (self._ticks // speed) * cell_h + phase * cell_h
            y_head = travelled % span - self.TRAIL * cell_h
            head_cell = travelled // cell_h
            for index in range(self.TRAIL):
                y = y_head - index * cell_h
                if y <= -cell_h or y >= height:
                    continue
                char = self.ALPHABET[stream[(head_cell - index) % len(stream)]]
                if index == 0:
                    colour, fade = head, 1.0
                else:
                    fade = 1.0 - index / float(self.TRAIL - 1)
                    colour, fade = body, fade * fade
                glyph = self._tinted_glyph(font, size, char, colour, fade)
                if glyph is not None:
                    self.surface.blit(glyph, (x, y))

    def _draw_trace(self, width, height, chamfer, stroke, colour):
        if colour is None:
            return
        left, top, right, bottom = self._frame_box(width, height)
        edge_left = left
        edge_right = max(edge_left + 1, right - 1 - chamfer)
        length = edge_right - edge_left
        if length < 8:
            return
        segment = max(stroke * 4, int(length * 0.16))
        period = self._period_ticks(self.TRACE_PERIOD_MS)
        phase = (self._ticks % period) / float(period)
        travel = length + segment
        x = edge_left + int(phase * travel) - segment
        x0 = max(edge_left, x)
        x1 = min(edge_right, x + segment)
        if x1 <= x0:
            return
        thickness = max(stroke, 2)
        piece = self._trace_layer(segment, thickness, colour)
        src = x0 - x
        y = bottom - thickness // 2
        self.surface.blit(piece, (x0, y),
                          pygame.Rect(src, 0, x1 - x0, thickness))

    def redraw(self):
        super(MenuBackdrop, self).redraw()
        if not self.enabled():
            return
        size = self.real_size
        width, height = size
        if width < 32 or height < 32 or self.surface is None:
            return

        self._clear()
        raster = self._colour("menu_scanline")
        frame = self._colour("menu_frame")
        head = self._colour("menu_glyph_head")
        layer = self._static_layer(size, raster, frame, head)
        self.surface.blit(layer, (0, 0))

        chamfer, stroke = self._static[2], self._static[3]
        self._draw_columns(width, height)
        self._draw_trace(width, height, chamfer, stroke, head)
