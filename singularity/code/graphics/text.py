#file: text.py
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

#This file contains the (non-editable) text widget AKA label.

import pygame

from singularity.code import i18n
from singularity.code.graphics import g, widget, constants


DEBUG = False

def do_bisect(left, right, test):
    # Run a binary search for the largest acceptable value.
    # Thanks to bisect.bisect_left for the basic implementation.
    # Return is in range [left, right-1], inclusive
    while left + 1 < right:
        test_index = (left + right) // 2
        if test(test_index):
            left = test_index
        else:
            right = test_index
    return left

def convert_font_size(size):
    # Scale it to the screen size.
    raw_size = size * g.real_screen_size[1] // g.default_screen_size[1]
    # And round. A layout shorter than the baseline scales even the default
    # text down to nothing, and a 0pt face measures every glyph at zero width;
    # one point is the smallest size that still has glyphs.
    return max(1, int(raw_size + 0.5))

def get_widths(font, text):
    if hasattr(font, "metrics"):
        return [m[4] for m in font.metrics(text)]
    else:
        return [font.size(c)[0] for c in text]

def strip_to_null(a_string):
    if not a_string:
        return a_string
    if a_string[0] == " ":
        a_string = "\uFEFF" + a_string[1:]
    if a_string[-1] == " ":
        a_string =  a_string[:-1] + "\uFEFF"
    return a_string

class WrapError(Exception): pass

# Splits a string into lines based on newline and word wrapping.
def split_wrap(text, font, wrap_at, break_words=True):
    raw_lines = text.split("\n")
    lines = []

    for raw_line in raw_lines:
        if font.size(raw_line)[0] <= wrap_at or wrap_at == 0:
            lines.append(raw_line + "\uFEFF")
        else:
            words = raw_line.split(" ")
            pos = 0
            line = ""
            for word in words:
                word += " "
                word_size = font.size(word)[0]
                if pos + word_size <= wrap_at:
                    line += word
                    pos += word_size
                elif word_size < wrap_at:
                    lines.append(strip_to_null(line))
                    line = word
                    pos = word_size
                else:
                    if not break_words:
                        message = "'%s' is too wide and can't be broken"
                        raise WrapError(message % word)
                    widths = get_widths(font, word)
                    for index, char in enumerate(word):
                        width = widths[index]
                        if pos + width <= wrap_at:
                            line += char
                            pos += width
                        else:
                            lines.append(strip_to_null(line))
                            line = char
                            pos = width
            if line and line != " ":
                lines.append(strip_to_null(line))
    return lines

def split_wrap_marked(text, font, wrap_at, break_words=True):
    """`split_wrap()`, plus which of its lines begin a paragraph.

    A "paragraph" here is what the data file calls one: a hard `\\n` in the
    string. This game's prose puts each thought on its own line -- "Day 0." then
    "University computer, home." then "I exist.  I am ... alive." -- and drawn
    with no leading between them a dialog reads as one run-on sentence, which is
    exactly what a player sees now.

    The distinction matters because `split_wrap()` makes two kinds of line that
    look alike: the continuation of a paragraph that wrapped, which must *not*
    get extra air, and the first line of a new one, which must.
    """
    lines = []
    starts = []
    for index, raw_line in enumerate(text.split("\n")):
        wrapped = split_wrap(raw_line, font, wrap_at, break_words)
        for offset, line in enumerate(wrapped):
            lines.append(line)
            starts.append(index > 0 and offset == 0)
    return lines, starts


def paragraph_breaks(starts, font):
    """Which line indices begin a paragraph, as a set, for a given font."""
    if not paragraph_extra(font):
        return frozenset()
    return frozenset(index for index, starts_paragraph in enumerate(starts)
                     if starts_paragraph)


def size_of_block(text, font, width=0):
    # Apply newlines and word wrap.
    lines, starts = split_wrap_marked(text, font, width)
    breaks = paragraph_breaks(starts, font)
    extra = paragraph_extra(font)

    # Calculate height and width of the text.
    total_height = 0
    max_width = 0
    for index, line in enumerate(lines):
        line_width, line_height = font.size(line)
        max_width = max(max_width, line_width)
        total_height += line_height
        # A paragraph start is given air. Added here as well as in
        # print_string(): a block measured short is a block whose last
        # paragraph is clipped, and the auto-fit would pick a size that does
        # not fit what it draws.
        if index in breaks:
            total_height += extra

    return (max_width, total_height)

def _do_print(surface, text, xy, font, color):
    if font.size(text)[0] == 0:
        return
    rendered_text = font.render(text, True, color)
    surface.blit(rendered_text, xy)

# A line containing nothing but this is a horizontal rule, if the theme says so.
# The research and tasks panel has been writing "---" between its heading and
# its body since long before there was a theme to draw it with, and the player
# saw three hyphens.
RULE_TEXT = "---"

# split_wrap() appends this to every line it produces. It is a marker, not
# content, and comparing a line without removing it means no line ever equals
# "---".
LINE_MARKER = "\ufeff"


def is_rule_line(line):
    """Whether a wrapped line is a rule, ignoring the wrapper's own marker."""
    return line.replace(LINE_MARKER, "").strip() == RULE_TEXT


def is_blank_line(line):
    """Whether a wrapped line is a paragraph break.

    `split_wrap()` turns every `\\n` into a line of its own and appends the
    marker to it, so a paragraph break arrives here as a line whose only content
    is the marker.
    """
    return line.replace(LINE_MARKER, "").strip() == ""


def paragraph_extra(font):
    """How much air a paragraph break gets, in pixels.

    A blank line in this game's prose is a break between thoughts -- "Day 0."
    then "University computer, home." -- and one line of leading is the width of
    the line itself, which reads as a run-on rather than a pause. Half a line is
    enough to see and not enough to look like a mistake.

    Zero unless the theme asks: a legacy dialog keeps the leading it shipped
    with, where a blank line is exactly one line tall.
    """
    if g.dialog_style("paragraph_spacing", "none") != "half":
        return 0
    return font.get_linesize() // 2


def tabular_cell(font):
    """The width one digit occupies when every digit gets the same cell."""
    return max(font.size(str(digit))[0] for digit in range(10))


def tabular_width(line, font):
    """How wide `line` is when its digits are set in equal-width cells."""
    cell = tabular_cell(font)
    return sum(cell if char.isdigit() else font.size(char)[0]
               for char in line)


def tabular_digits_enabled():
    return g.dialog_style("tabular_digits", "none") == "all"


def wants_tabular(widget):
    """Whether this widget's digits should be set in equal-width cells.

    A *running* number needs them and a static one does not: `DAY 1111` is 45px
    narrower than `DAY 8888` in this face, so a centred clock slides sideways
    every second. A label that is written once and left alone has nothing to
    line up with, so it keeps the ordinary spacing -- which is also what keeps
    this from restyling every number in the game.
    """
    return bool(getattr(widget, "tabular", False)) and tabular_digits_enabled()


def print_line_tabular(surface, xy, font, line, colour, bgcolor, underline,
                       width):
    """Draw one line with every digit in a cell the width of the widest one.

    A clock that is redrawn ten times a second must not change width: with
    proportional figures `DAY 1111` is 45px narrower than `DAY 8888`, and a
    centred label then slides sideways as the seconds tick. Each digit is
    centred inside its own cell, so the string's advance is the same whatever
    the digits are.
    """
    if bgcolor is not None:
        surface.fill(bgcolor, (xy[0], xy[1], max(1, width),
                               font.get_linesize()))

    cell = tabular_cell(font)
    x = xy[0]
    font.set_underline(underline)
    for char in line:
        if char.isdigit():
            inner = font.size(char)[0]
            _do_print(surface, char, (x + (cell - inner) // 2, xy[1]),
                      font, colour)
            x += cell
        else:
            _do_print(surface, char, (x, xy[1]), font, colour)
            x += font.size(char)[0]
    font.set_underline(False)


def rule_colour():
    """The colour a `---` line is drawn in, or None to print it as text."""
    if g.dialog_style("rule", "none") != "line":
        return None
    for name in ("dialog_rule", "pane_border", "text_disabled"):
        if name in g.colors:
            return g.resolve_color_alias(name)
    return None


def print_string(surface, string_to_print, xy_orig, font, styles, align, valign,
                 dimensions, wrap, tabular=False):
    xy = list(xy_orig)

    width = dimensions[0] - 4
    height = dimensions[1] - 4

    if wrap:
        lines, starts = split_wrap_marked(string_to_print, font, width)
    else:
        lines, starts = split_wrap_marked(string_to_print, font, 0)

    # Decided once per string rather than once per line: it is one theme lookup
    # and the answer cannot change between lines.
    rule = rule_colour() if any(is_rule_line(line) for line in lines) \
        else None

    # The same, for the air between paragraphs -- and computed by the same
    # helper size_of_block() uses, so the two cannot disagree about the height.
    breaks = paragraph_breaks(starts, font)
    extra = paragraph_extra(font)

    if valign != constants.TOP:
        vsize = len(lines) * font.get_linesize() + len(breaks) * extra
        if vsize <= height:
            excess_space = height - vsize
            if valign == constants.MID:
                xy[1] += excess_space // 2
            else: # valign == constants.BOTTOM
                xy[1] += excess_space

    color, bgcolor, underline, switch_char = styles.pop(0)
    offset = 0
    for index, line in enumerate(lines):
        xy[0] = xy_orig[0]

        # The air above a new paragraph, before anything is drawn on this line.
        if index in breaks and index > 0:
            xy[1] += extra

        if rule is not None and is_rule_line(line):
            # A rule across the whole text width, vertically centred in the
            # line the three hyphens would have occupied -- so swapping one for
            # the other does not reflow the paragraph.
            middle = xy[1] + font.get_linesize() // 2
            pygame.draw.line(surface, rule,
                             (xy_orig[0], middle),
                             (xy_orig[0] + width, middle))
            xy[1] += font.get_linesize()
            continue

        if align != constants.LEFT:
            hsize = tabular_width(line, font) if tabular else font.size(line)[0]
            excess_space = width - hsize
            if align == constants.CENTER:
                xy[0] += excess_space // 2
            else: # align == constants.RIGHT
                xy[0] += excess_space

        chunks = [line]
        my_styles = [(color, bgcolor, underline)]
        while switch_char != 0 and switch_char < offset + len(chunks[-1]):
            real_switch = switch_char - offset
            offset += real_switch

            piece = chunks.pop()
            chunks.extend([piece[:real_switch], piece[real_switch:]])
            color, bgcolor, underline, switch_char = styles.pop(0)
            my_styles.append((color, bgcolor, underline))
        offset += len(chunks[-1])

        # A single-style line of digits can be set in cells; a line that changes
        # style mid-way cannot, so it keeps the ordinary path.
        if tabular and switch_char == 0 and any(ch.isdigit() for ch in line):
            print_line_tabular(surface, xy, font, line, color, bgcolor,
                               underline, tabular_width(line, font))
        else:
            print_line(surface, xy, font, chunks, my_styles)
        # A blank line is a paragraph break and gets its extra leading here as
        # well as in size_of_block(), so that what is measured is what is drawn.
        xy[1] += font.get_linesize()
        if extra and is_blank_line(line):
            xy[1] += extra


def print_line(surface, xy, font, chunks, styles):
    for chunk, (color, bgcolor, underline) in zip(chunks, styles):
        size = font.size(chunk)

        # Fill the background, if any.
        if bgcolor is not None:
            surface.fill(bgcolor, xy+size)

        # Print the text.
        font.set_underline(underline)
        _do_print(surface, chunk, xy, font, color)
        font.set_underline(False)

        # Adjust the starting position.
        xy[0] += size[0]


def resize_redraw(self):
    self.needs_resize = True
    self.needs_redraw = True


class Text(widget.BorderedWidget):

    # Set on a widget whose number is rewritten as it changes hours, seconds or
    # currency; the theme then draws its digits in equal-width cells. See
    # wants_tabular().
    tabular = False

    # Set on a body that should scroll rather than shrink when its text is
    # longer than the box. `print_text()` draws the whole body shifted by
    # `scroll_lines` and clipped to `text_window_rect()`, and `calc_text_size()`
    # stops treating the height as a constraint -- overflow becomes scroll
    # instead of smaller type.
    scrollable = False

    def _on_enabled_change(self):
        resize_redraw(self)
        if self.on_enable_change_func:
            self.on_enable_change_func()

    shrink_factor = widget.call_on_change("_shrink_factor", resize_redraw)
    underline = widget.call_on_change("_underline", resize_redraw)
    wrap = widget.call_on_change("_wrap", resize_redraw)
    bold = widget.call_on_change("_bold", resize_redraw)
    _text = widget.call_on_change("__text", resize_redraw)

    enabled = widget.call_on_change("_enabled", _on_enabled_change)

    align = widget.causes_redraw("_align")
    valign = widget.causes_redraw("_valign")

    color = widget.auto_reconfig("_color", "resolved", g.resolve_color_alias)
    resolved_color = widget.causes_redraw("_resolved_color")
    color_disabled = widget.auto_reconfig("_color_disabled", "resolved", g.resolve_color_alias)
    resolved_color_disabled = widget.causes_redraw("_resolved_color_disabled")
    # A translucent block behind this text, for a dialog whose body would
    # otherwise sit directly on the panel. None is "no block", which is what
    # every widget did before the theme key existed.
    plate_color = widget.auto_reconfig("_plate_color", "resolved",
                                       g.resolve_color_alias)
    resolved_plate_color = widget.causes_redraw("_resolved_plate_color")
    plate_border_color = widget.auto_reconfig("_plate_border_color", "resolved",
                                              g.resolve_color_alias)
    resolved_plate_border_color = widget.causes_redraw(
        "_resolved_plate_border_color")
    base_font = widget.auto_reconfig("_base_font", "resolved", g.resolve_font_alias)
    resolved_base_font = widget.call_on_change("_resolved_base_font", resize_redraw)

    text_size = widget.auto_reconfig("_text_size", "resolved", g.resolve_text_size)
    resolved_text_size = widget.causes_redraw("_resolved_text_size")

    def __init__(self, parent, pos, size=(0, .05), anchor=constants.TOP_LEFT,
                 text=None, base_font=None, shrink_factor=0.875,
                 color=None, align=constants.CENTER, valign=constants.MID,
                 color_disabled=None, on_enable_change=None, autotranslate=False,
                 underline=-1, wrap=True, bold=False, text_size="default", **kwargs):
        kwargs.setdefault("background_color", "text_background")
        kwargs.setdefault("border_color", "text_border")
        enabled = kwargs.pop('enabled', True)
        super(Text, self).__init__(parent, pos, size, anchor, **kwargs)

        self._autotranslate = autotranslate
        if self._autotranslate:
            assert text, "Automatic translatable widgets must get a default text"
            self._last_language = "!"  # Invalid to force an update
            self._untranslated_text = text
            self._check_translation()
        else:
            self._last_language = None
            self._untranslated_text = None
            self.text = text

        self.base_font = base_font or "normal"
        self.color = color or "text"
        self.color_disabled = color_disabled or "text_disabled"
        self.shrink_factor = shrink_factor
        self.underline = underline
        self.align = align
        self.valign = valign
        self.wrap = wrap
        self.bold = bold
        self.text_size = text_size
        self.on_enable_change_func = on_enable_change
        self.enabled = enabled

        self.plate_color = None
        self.plate_border_color = None
        # Pixels of margin between the plate's edge and the glyphs.
        self.plate_pad = 12
        # How much of the frame's height the block may not enter, as a
        # fraction of the frame that owns it -- the button row, in practice.
        # See plate_reserve_pixels().
        self.plate_reserve_bottom = 0.0
        # A frame is its own reference: a TextDialog's parent is the screen,
        # and the button row it must clear is its own bottom, not the screen's.
        self.plate_reserve_is_own = False
        self._plate = None

        # Whole lines scrolled off the top. Only meaningful when `scrollable`,
        # and clamped to `max_scroll()` on every draw: a body can be scrolled,
        # then have its text replaced by a shorter message.
        self.scroll_lines = 0

        # A theme may inset the text from the widget's own frame -- that is what
        # makes a dialog read as a panel rather than as a caption. Fractions of
        # the widget's box, per side: (left, top, right, bottom). All zero is
        # the path every widget took before the key existed, and it draws the
        # same pixels as before.
        self.text_padding = (0.0, 0.0, 0.0, 0.0)
        # Pixels added to the left inset while something is drawn beside the
        # text, such as a button's glyph.
        self.text_extra_left = 0

    max_size = property(lambda self: min(len(self.resolved_base_font)-1,
                                         convert_font_size(self._resolved_text_size)))
    font = property(lambda self: self._font)

    @property
    def autotranslate(self):
        return self._autotranslate

    @property
    def text(self):
        return self._text

    @text.setter
    def text(self, value):
        if self._autotranslate:
            raise ValueError("Cannot change text for an automatic translatable text widget")
        self._text = value

    def _retranslate(self):
        self._text = _(self._untranslated_text)

    def _check_translation(self):
        if self._last_language != i18n.language:
            self._last_language = i18n.language
            self._retranslate()

    def pick_font(self, dimensions):
        nice_size = self.pick_font_size(dimensions, False)
        mean_size = self.pick_font_size(dimensions)

        size = max(nice_size, mean_size - convert_font_size(5))

        return self.resolved_base_font[size]

    def font_bisect(self, test_font):
        left = 0
        right = (self.max_size or len(self.resolved_base_font)-1) + 1

        def test_size(size):
            font = self.resolved_base_font[size]
            font.set_bold(self.bold)
            result = test_font(font)
            font.set_bold(False)

            return result

        # do_bisect() answers 0 when nothing fits, and 0 is not a usable font
        # size (see convert_font_size). The smallest size the search may
        # return is one point.
        return max(1, do_bisect(left, right, test_size))

    def pick_font_size(self, dimensions, break_words=True):
        if dimensions[0]:
            width = int(dimensions[0] * self.shrink_factor)
        else:
            width = None
        height = int(dimensions[1] * self.shrink_factor)

        basic_line_count = self.text.count("\n") + 1

        def test_size(test_font):
            too_wide = False
            if width:
                if self.wrap:
                    try:
                        lines = split_wrap(self.text, test_font, width,
                                           break_words)
                    except WrapError:
                        lines = []
                        too_wide = True
                else:
                    lines = split_wrap(self.text, test_font, 0)
                    for line in lines:
                        if test_font.size(line)[0] > width:
                            too_wide = True
                            break
                line_count = len(lines)
            else:
                line_count = basic_line_count

            too_tall = (test_font.get_linesize() * line_count) > height

            return not (too_tall or too_wide)

        return self.font_bisect(test_size)

    def size_using_font(self, font, width=0):
        #Calculate the size of the text block.
        raw_width, raw_height = size_of_block(self.text, font, width)

        #Adjust for shrink_factor and borders.
        width = int(raw_width / self.shrink_factor) + 4
        height = int(raw_height / self.shrink_factor) + 4

        return width, height

    def text_insets(self, dimensions=None, for_plate=False):
        """The text's inset in pixels, from text_padding and a glyph gutter.

        `for_plate` asks for the content box rather than the glyph box: a text
        widget with a translucent plate gets the plate's inner padding added to
        its own insets, so the block has a margin between its edge and the
        glyphs. Without the distinction the two would be the same rectangle and
        the first line would touch the plate's border.
        """
        if dimensions is None:
            width, height = self.real_size
        else:
            width, height = dimensions

        left, top, right, bottom = self.text_padding
        insets = [int(left * width), int(top * height),
                  int(right * width), int(bottom * height)]
        insets[0] += self.text_extra_left + self.content_extra_left((width, height))

        if not for_plate and self.resolved_plate_color is not None:
            insets = [inset + self.plate_pad for inset in insets]

        # An inset may never eat the box: print_string() is handed a width and
        # a height, not a clamp, and a negative one draws nothing at all.
        if insets[0] + insets[2] >= width:
            insets[0] = insets[2] = max(0, width // 4)
        if insets[1] + insets[3] >= height:
            insets[1] = insets[3] = max(0, height // 4)

        return tuple(insets)

    def content_extra_left(self, dimensions=None):
        """Pixels another element keeps at the left of the text.

        A button with a glyph reserves the glyph's width here, so that
        measuring and drawing agree; measured against the full width and then
        drawn in a narrower one, a one-line label wraps onto a second line and
        is clipped.
        """
        return 0

    def inner_dimensions(self, dimensions):
        """What the text is measured against once its inset is removed."""
        if (not any(self.text_padding) and not self.text_extra_left
                and not self.content_extra_left(dimensions)
                and self.resolved_plate_color is None):
            return dimensions

        left, top, right, bottom = self.text_insets(dimensions)
        return (max(1, dimensions[0] - left - right),
                max(1, dimensions[1] - top - bottom))

    def calc_text_size(self, initial_dimensions):
        if not (initial_dimensions[0] and initial_dimensions[1]):
            if not self.max_size:
                raise ValueError("No font size given, but a dimension is 0.")

            max_font = self.resolved_base_font[self.max_size]
            if initial_dimensions[0] == initial_dimensions[1] == 0:
                # No size specified, use the natural size of the max font.
                width, height = self.size_using_font(max_font)
                return (width, height), max_font
            elif not initial_dimensions[1]:
                # Width specified, use the size of the max font, word-wrapped.
                text_width = int((initial_dimensions[0] - 4)
                                 * self.shrink_factor)
                width, height = self.size_using_font(max_font, width=text_width)
                return (initial_dimensions[0], height), max_font
            else:
                # Height specified.  Try the natural size of the max font.
                width, height = self.size_using_font(max_font)

                if height <= initial_dimensions[1]:
                    return (width, initial_dimensions[1]), max_font
                else:
                    # Too tall.  Run a binary search to find the largest font
                    # size that fits.
                    def test_size(font):
                        width, raw_height = size_of_block(self.text, font)
                        height = int(raw_height / self.shrink_factor) + 4
                        return height <= initial_dimensions[1]

                    font_size = self.font_bisect(test_size)
                    font = self.resolved_base_font[font_size]
                    width, height = self.size_using_font(font)

                    return (width, initial_dimensions[1]), font
        else:
            # Both sizes specified.  Search for a usable font size.
            dimensions = self.inner_dimensions(initial_dimensions)
            if self.scrollable:
                # A body that scrolls is not constrained by the box's height:
                # overflow becomes scroll, not smaller type. Width still
                # constrains it, because a line that does not fit still has to
                # wrap -- and an unbounded height is exactly what
                # `pick_font_size()` already reads as "only the width matters".
                dimensions = (dimensions[0], 10 ** 6)
            return initial_dimensions, self.pick_font(dimensions)

    def override_size(self, dimensions):
        """A last chance to change the box before the type is fitted to it.

        A button uses it to take the theme's one height. Everything else
        returns the box it was given, which is the path every widget took
        before the hook existed -- so this changes nothing on its own.
        """
        return dimensions

    def _calc_size(self):
        base_size = list(super(Text, self)._calc_size())
        base_size = list(self.override_size(tuple(base_size)))

        if self.text is None:
            return tuple(base_size)
        else:
            # Determine the true size and font of the text area.
            text_size, font = self.calc_text_size(base_size)
            self._font = font
            return tuple(text_size)

    def redraw(self):
        super(Text, self).redraw()

        if self.text is not None:
            self.draw_plate()
            self.print_text()
            self.draw_scroll_indicator()

    def draw_scroll_indicator(self):
        """A bar beside the body when there is more text than fits.

        A clipped paragraph with nothing to say so is indistinguishable from a
        paragraph that ended, and a player would never think to use the wheel.
        Height is the visible fraction of the body, position is how far through
        it the view is.

        Drawn the way the theme draws a scrollbar, so a dialog's body and the
        list inside another window are the same machine: a flush track and a
        bright thumb, no border. Where the theme puts a block behind the text
        there is a gutter between the glyphs and the block's edge, and the bar
        goes in it. A body with no gutter has nowhere to put a track without
        covering text and keeps the thin rule this drew before.
        """
        if not self.scrollable:
            return
        total, visible = self.body_line_count()
        if total <= visible:
            return
        window = self.text_window_rect()
        if window.width < 12 or window.height < 12:
            return

        thumb_height = max(6, int(window.height * visible / float(total)))
        span = window.height - thumb_height
        progress = self.scroll_lines / float(max(1, total - visible))
        thumb_top = window.top + int(span * progress)

        gutter = self.scroll_indicator_gutter(window)
        if gutter is not None:
            track, width = gutter
            track_colour = self.resolve_scroll_colour("scrollbar_background")
            thumb_colour = self.resolve_scroll_colour(
                "scrollbar_background_slider")
            if track_colour is not None:
                pygame.draw.rect(self.surface, track_colour, track)
            if thumb_colour is not None:
                pygame.draw.rect(
                    self.surface, thumb_colour,
                    pygame.Rect(track.left, thumb_top, width, thumb_height))
            return

        colour = self.resolve_scroll_colour("dialog_rule")
        if colour is None:
            return
        # Two pixels, just inside the window's right edge, so it belongs to the
        # body rather than to the frame around it.
        pygame.draw.rect(self.surface, colour,
                         pygame.Rect(window.right - 3, thumb_top, 2,
                                     thumb_height))

    @staticmethod
    def resolve_scroll_colour(name):
        """A colour for the scroll indicator, or None if the theme has none."""
        try:
            return g.resolve_color_alias(name)
        except KeyError:
            return None

    def scroll_indicator_gutter(self, window):
        """(track_rect, width) for a bar in the strip beside the glyphs.

        None when the theme draws classic scrollbars, or when the strip is too
        narrow to hold one. The width is a list scrollbar's own, clamped to the
        space that actually exists, so a body's bar is never wider than the
        track a list would draw.

        There is always such a strip, because a text is drawn inside its
        insets: the frame's padding, plus the block's own padding when the theme
        puts a block behind the text. The bar sits at the far end of it, inside
        the block's border where there is one. Ending on the outer pixel painted
        over that border, and the side of the block beside the bar disappeared.
        With no block, it sits flush with the frame.
        """
        if g.dialog_style("scrollbar", "classic") != "thin":
            return None
        # Imported here rather than at the top: scrollbar imports button, and
        # button imports this module. The cycle is fine at call time, which is
        # an ordinary dict lookup, and not at import time.
        from singularity.code.graphics import scrollbar

        glyph_right = self.real_size[0] - self.text_insets()[2]
        plate_right = self.text_insets(for_plate=True)[2]
        if plate_right < self.text_insets()[2]:
            # A block, so the bar belongs in the padding between the glyphs and
            # the border, not on the border itself.
            edge = self.real_size[0] - plate_right - self.plate_border_width()
        else:
            # No block: the frame's own padding is the strip.
            edge = self.real_size[0]

        space = edge - glyph_right
        width = min(scrollbar.Scrollbar.thin_width(), space)
        if width < 3:
            return None

        return (pygame.Rect(edge - width, window.top, width, window.height),
                width)

    def plate_rect(self):
        """Where the block behind this text goes, in widget pixels.

        The text's column, from the top of the content box to the top of the row
        the caller reserved. The picture above and the buttons below are what
        bound a dialog's body, not the length of its prose: a one-line message
        used to get a block only as tall as itself -- a strip of colour under
        the banner, with the rest of the pane left bare -- and read as a caption
        floating in a window.

        Still not the whole box: a TextDialog's text box is the whole frame and
        its CONTINUE and SKIP buttons are laid over it, so the reserve is what
        keeps the block out from under them.
        """
        if self.resolved_plate_color is None:
            return pygame.Rect(0, 0, 0, 0)

        left, top, right, bottom = self.text_insets(for_plate=True)
        rect = pygame.Rect(left, top,
                           max(0, self.real_size[0] - left - right),
                           max(0, self.real_size[1] - top - bottom))
        if rect.width < 1 or rect.height < 1:
            return pygame.Rect(0, 0, 0, 0)

        # The caller's guarantee: whatever sits below the text -- the button
        # row -- owns this much of the frame, and the block stops short of it.
        reserve = self.plate_reserve_pixels()
        if reserve > 0:
            limit = self.real_size[1] - reserve
            if rect.bottom > limit:
                rect.height = max(0, limit - rect.top)

        rect = rect.clip(pygame.Rect(0, 0,
                                     max(0, self.real_size[0]),
                                     max(0, self.real_size[1])))
        if rect.width < 1 or rect.height < 1:
            return pygame.Rect(0, 0, 0, 0)
        return rect

    def plate_reserve_pixels(self):
        """Pixels at the bottom of this widget that the block may not enter.

        `plate_reserve_bottom` is a fraction of the *frame* -- the dialog that
        owns the button row -- because that is the box the reserve is really
        about. A widget that is itself the frame says so with
        `plate_reserve_is_own`, since its parent is the screen.
        """
        fraction = self.plate_reserve_bottom
        if fraction <= 0:
            return 0

        frame = self if self.plate_reserve_is_own else self.parent
        if frame is None:
            frame = self
        return int(fraction * frame.real_size[1])

    def text_window_rect(self):
        """The rectangle a scrolling body may draw in, in widget pixels.

        The text box, less whatever the caller has reserved at the bottom. That
        reserve is the same expression `plate_rect()` clamps the block with, and
        it has to stay that way: if the window and the block disagree the glyphs
        draw outside their own block, which is the bug this replaced.
        """
        left, top, right, bottom = self.text_insets()
        width = max(0, self.real_size[0] - left - right)
        height = max(0, self.real_size[1] - top - bottom)
        limit = self.real_size[1] - self.plate_reserve_pixels()
        if top + height > limit:
            height = max(0, limit - top)
        return pygame.Rect(left, top, width, height)

    def body_line_count(self):
        """(total, visible) wrapped lines, for a scrolling body."""
        if not self.text:
            return 0, 1
        left, top, right, bottom = self.text_insets()
        width = max(1, self.real_size[0] - left - right) - 4
        lines = split_wrap(self.text, self.font, width if self.wrap else 0)
        window = self.text_window_rect()
        line_size = max(1, self.font.get_linesize())
        return len(lines), max(1, window.height // line_size)

    def max_scroll(self):
        """How many whole lines a scrolling body can be scrolled by."""
        total, visible = self.body_line_count()
        return max(0, total - visible)

    def scroll_body_by(self, rows):
        """Scroll by whole lines, clamped. Returns whether anything moved."""
        if not rows:
            return False
        limit = self.max_scroll()
        before = self.scroll_lines
        self.scroll_lines = max(0, min(limit, self.scroll_lines + rows))
        if self.scroll_lines != before:
            self.needs_redraw = True
            return True
        return False

    def text_block_rect(self):
        """The rectangle the glyphs actually occupy, in widget pixels.

        Mirrors what print_string() does with the same font and the same box:
        wrap to the inner width, then place the block by valign and align. The
        block behind the text needs this because "the widget's box" and "the
        text" are different rectangles.
        """
        left, top, right, bottom = self.text_insets()
        inner_width = max(1, self.real_size[0] - left - right)
        inner_height = max(1, self.real_size[1] - top - bottom)

        if self.text is None:
            return pygame.Rect(left + 3, top + 2, 0, 0)

        font = self.font
        self.font.set_bold(self.bold)
        try:
            width = inner_width - 4
            lines = split_wrap(self.text, font, width if self.wrap else 0)
            line_size = font.get_linesize()
            block_height = len(lines) * line_size
            block_width = max([font.size(line)[0] for line in lines] or [0])
        finally:
            self.font.set_bold(False)

        x = left + 3
        y = top + 2
        if self.valign != constants.TOP and block_height <= inner_height - 4:
            excess = (inner_height - 4) - block_height
            if self.valign == constants.MID:
                y += excess // 2
            else:
                y += excess
        if self.align != constants.LEFT:
            excess = width - block_width
            if self.align == constants.CENTER:
                x += excess // 2
            else:
                x += excess

        return pygame.Rect(x, y, block_width, block_height)

    def draw_plate(self):
        """Draw the translucent block this text sits on, if it has one.

        Composed on its own SRCALPHA surface and blitted, never filled in
        place: a widget's surface is a subsurface of the screen's, which has no
        alpha channel, so `surface.fill()` with a translucent colour produces a
        solid block instead of a blend -- the trap the comment in
        BorderedWidget.redraw() records.
        """
        colour = self.resolved_plate_color
        if colour is None:
            return

        rect = self.plate_rect()
        if rect.width < 1 or rect.height < 1:
            return

        border = self.resolved_plate_border_color
        # The block's edge is the same weight as the frame around the picture
        # above it, because they are two parts of one frame, not two frames.
        # It used to be a hardcoded 1 while the picture's came from the theme,
        # so a theme with a 2px frame drew a 1px block around its own text.
        border_width = self.plate_border_width()
        key = (rect.width, rect.height, colour, border, border_width)
        if self._plate is None or self._plate[0] != key:
            plate = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
            plate.fill(colour)
            if border is not None:
                pygame.draw.rect(plate, border, plate.get_rect(), border_width)
            self._plate = (key, plate)

        self.surface.blit(self._plate[1], rect.topleft)

    def plate_border_width(self):
        """Pixels of edge the block draws, or 0 when it draws none.

        Clamped to the block: a plate narrower than twice the border has no
        interior left, and drawing it anyway would fill the block with its own
        edge. The scrollbar asks the same question, because a track that ends
        on the outer pixel paints over this edge.
        """
        if (self.resolved_plate_color is None
                or self.resolved_plate_border_color is None):
            return 0
        rect = self.plate_rect()
        if rect.width < 2 or rect.height < 2:
            return 0
        return max(1, min(g.content_border_width(),
                          min(rect.width, rect.height) // 2))

    def reconfig(self):
        super(Text, self).reconfig()
        if self._autotranslate:
            self._check_translation()

    def pad_from_theme(self, vertical=True):
        """Inset this text from the pane it fills, by the theme's padding.

        A pane that a caller fills edge to edge puts the first glyph against the
        border, which is why every description panel in the game looked like it
        had been set in a box that was slightly too small. The inset is a theme
        value and defaults to zero, so a theme that does not ask for it -- the
        legacy themes -- lays its text out exactly as before.

        `vertical=False` is for a text that already carries its own top offset
        (a report body sits below a title row, and a list row is only as tall as
        its line): it takes the side inset, which is the one it is missing.

        Returns self, so a call site reads as one expression.
        """
        padding = g.dialog_style("content_padding", 0.0)
        if vertical:
            self.text_padding = (padding, padding, padding, padding)
        else:
            self.text_padding = (padding, 0.0, padding, 0.0)
        return self

    def first_glyph_x(self):
        """Where this text's first glyph lands, in the widget's own pixels.

        Mirrors the arithmetic `print_text()` hands to `print_string()`: the
        inset, the four pixels of internal margin, and the alignment shift
        within what is left. It exists so a widget that reserves space beside
        the text -- a button with a glyph -- can put that glyph next to the
        letters rather than at the frame's edge, which is where it used to go.

        Only meaningful for a single line, which is every button's label.
        """
        left, top, right, bottom = self.text_insets()
        inner = max(1, self.real_size[0] - left - right)
        line = (self.text or "").split("\n")[0]
        spare = inner - 4 - self.font.size(line)[0]

        x = 3 + left
        if self.align == constants.CENTER:
            x += spare // 2
        elif self.align == constants.RIGHT:
            x += spare
        return x

    @property
    def text_color(self):
        return self.resolved_color if self.enabled else self.resolved_color_disabled

    def print_text(self):
        # Mark the character to be underlined (if any).
        no_underline = [self.text_color, None, False]
        underline = [self.text_color, None, True]
        styles = [no_underline + [0]]
        if 0 <= self.underline < len(self.text):
            styles.insert(0, underline + [self.underline + 1])
            if self.underline != 0:
                styles.insert(0, no_underline + [self.underline])

        self.font.set_bold(self.bold)
        # Print the string itself.
        left, top, right, bottom = self.text_insets()
        inner_size = (self.real_size[0] - left - right,
                      self.real_size[1] - top - bottom)

        if not self.scrollable:
            print_string(self.surface, self.text, (3 + left, 2 + top),
                         self.font, styles, self.align, self.valign,
                         inner_size, self.wrap, tabular=wants_tabular(self))
            self.font.set_bold(False)
            return

        # A scrolling body is drawn whole and shifted up, then clipped to the
        # window. Slicing the line list instead would have to reproduce what
        # `print_string()` does per *string* rather than per line -- the `---`
        # rule and the centring of a block -- for no gain: the clip is the
        # whole of what a scroll is.
        window = self.text_window_rect()
        if window.width < 1 or window.height < 1:
            self.font.set_bold(False)
            return
        # Clamped here as well as in the wheel handler, because the text can be
        # replaced by something shorter while the body is scrolled.
        self.scroll_lines = max(0, min(self.max_scroll(), self.scroll_lines))
        offset = self.scroll_lines * self.font.get_linesize()

        self.surface.set_clip(window)
        try:
            print_string(self.surface, self.text, (3 + left, 2 + top - offset),
                         self.font, styles, self.align, constants.TOP,
                         inner_size, self.wrap, tabular=wants_tabular(self))
        finally:
            self.surface.set_clip(None)
        self.font.set_bold(False)

def text_changed(self):
    if self.text is None:
        new_len = 0
    else:
        new_len = len(self.text)
    if new_len != self.old_len:
        self.old_len = new_len
        self.needs_resize = True
    self.needs_redraw = True


class ScrollableText(Text):
    """A block of prose that scrolls when it is longer than its box.

    `Text.scrollable` is a class attribute, so until now only a *dialog* whose
    whole text is the body could scroll: everything else -- a message page, a
    knowledge description, a report column -- was a plain `Text` and shrank its
    type until the paragraph fitted, or (once it stopped shrinking) drew past
    its own box.

    This is that body. It is still gated on `[dialog] scroll_body = block`, so
    under a legacy theme the property is False, `calc_text_size()` keeps
    treating the height as a constraint, and the block draws exactly what it
    always drew.
    """

    # The wheel reaches this body after the listboxes (200) and before the
    # dialog that contains it (dialog.BODY_SCROLL_PRIORITY, 300). The order is
    # the point: a list under the pointer owns its wheel, and the dialog's own
    # text must not swallow the notch meant for the body inside it.
    SCROLL_PRIORITY = 290

    # A property rather than a value set in __init__: a theme switch has to
    # change it, and the switch reconfigures widgets rather than rebuilding them.
    scrollable = property(lambda self: g.dialog_style("scroll_body", "none")
                          == "block")

    def _on_text_change(self):
        # A new page starts at its beginning. An offset carried over from the
        # previous message would open the next one in the middle of a sentence.
        if getattr(self, "scroll_lines", 0):
            self.scroll_lines = 0
        resize_redraw(self)

    _text = widget.call_on_change("__text", _on_text_change)

    def add_hooks(self):
        super(ScrollableText, self).add_hooks()
        self._sync_scroll_handler()

    def remove_hooks(self):
        self._sync_scroll_handler(remove=True)
        super(ScrollableText, self).remove_hooks()

    def _sync_scroll_handler(self, remove=False):
        """Register the wheel on the nearest handler registry.

        `add_handler()` on a plain widget is a pass-through (`widget.py`), so
        this lands on the owning dialog however deeply the body is nested.
        Removing first makes it idempotent: `add_hooks()` runs again whenever
        the widget is re-parented, and two registrations mean two scrolls per
        notch.
        """
        if self.parent is None:
            return
        self.parent.remove_handler(constants.MOUSEWHEEL, self.handle_scroll)
        if not remove:
            self.parent.add_handler(constants.MOUSEWHEEL, self.handle_scroll,
                                    self.SCROLL_PRIORITY)

    def handle_scroll(self, event):
        """One wheel notch, over this body, in whole lines."""
        if not self.visible or not self.scrollable:
            return
        # A MOUSEWHEEL event carries no position in pygame 2, so the pointer is
        # asked for directly when the event has none.
        position = getattr(event, "pos", None) or pygame.mouse.get_pos()
        if not self.is_over(position):
            return
        if self.scroll_body_by(-int(getattr(event, "y", 0) or 0) * 2):
            raise constants.Handled

    def reset_scroll(self):
        if getattr(self, "scroll_lines", 0):
            self.scroll_lines = 0
            self.needs_redraw = True


class FastText(Text):
    """
       Reduces font searches by assuming a monospace font and single-line text.
    """
    _text = widget.call_on_change("__text", text_changed)
    old_len = 0
    maybe_needs_refont = False

class EditableText(widget.FocusWidget, Text):
    cursor_pos = widget.causes_redraw("_cursor_pos")
    def __init__(self, parent, *args, **kwargs):
        self.allows_new_line = kwargs.pop("allows_new_line", False)
        self.allowed_characters = kwargs.pop("allowed_characters", None)
        
        super(EditableText, self).__init__(parent, *args, **kwargs)

        if self.text is None:
            self.text = ""

        self.cursor_pos = len(self.text)

    def add_hooks(self):
        super(EditableText, self).add_hooks()
        self.parent.add_handler(constants.KEYDOWN, self.handle_key, 10)
        self.parent.add_handler(constants.CLICK, self.handle_click)

    def remove_hooks(self):
        super(EditableText, self).remove_hooks()
        self.parent.remove_handler(constants.KEYDOWN, self.handle_key)
        self.parent.remove_handler(constants.CLICK, self.handle_click)

    def handle_key(self, event, require_focus=True):
        if require_focus and not self.has_focus:
            return
        assert event.type == pygame.KEYDOWN
        if event.key == pygame.K_BACKSPACE:
            if self.cursor_pos > 0:
                self.text = self.text[:self.cursor_pos - 1] \
                            + self.text[self.cursor_pos:]
                self.cursor_pos -= 1
        elif event.key == pygame.K_DELETE:
            if self.cursor_pos < len(self.text):
                self.text = self.text[:self.cursor_pos] \
                + self.text[self.cursor_pos + 1:]
        elif event.key == pygame.K_LEFT:
            self.cursor_pos = max(0, self.cursor_pos - 1)
        elif event.key == pygame.K_RIGHT:
            self.cursor_pos = min(len(self.text), self.cursor_pos + 1)
        elif event.key in (pygame.K_UP, pygame.K_HOME):
            self.cursor_pos = 0
        elif event.key in (pygame.K_DOWN, pygame.K_END):
            self.cursor_pos = len(self.text)
        elif event.key == pygame.K_ESCAPE:
            return
        elif event.unicode:
            char = event.unicode
            if char in ("\r\n", "\n", "\r", "\v", "\f", "\x1e", 
                        "\x1c", "\x1d", "\x85", "\u2028", "\u2029"):
                if not self.allows_new_line:
                    return
                char = "\n"
            if self.allowed_characters is not None and char not in self.allowed_characters:
                return

            self.text = self.text[:self.cursor_pos] + char \
                        + self.text[self.cursor_pos:]
            self.cursor_pos += len(char)
        else:
            return

        raise constants.Handled

    hitbox = [0,0,0,0]

    def handle_click(self, event):
        if getattr(self, "collision_rect", None) is None:
            return
        elif not self.collision_rect.collidepoint(event.pos):
            return

        self.has_focus = True
        self.took_focus(self)

        self.font.set_bold(self.bold)

        click_x = event.pos[0] - self.collision_rect[0]
        click_y = event.pos[1] - self.collision_rect[1]

        if self.wrap:
            lines = split_wrap(self.text, self.font, self.real_size[0] - 4)
        else:
            lines = split_wrap(self.text, self.font, 0)

        line_size = self.font.get_linesize()
        self.hitbox[3] = line_size
        real_text_height = line_size * len(lines)

        line_y = 2
        if self.valign != constants.TOP \
           and real_text_height <= self.collision_rect.height - 4:
            excess_space = self.collision_rect.height - real_text_height
            if self.valign == constants.MID:
                line_y = excess_space // 2
            else: # self.valign == constants.BOTTOM
                line_y = excess_space

        char_offset = 0
        for line in lines:
            line_y += line_size
            char_offset += len(line)
            if line_y >= click_y:
                break

        char_offset -= len(line)

        self.hitbox[1] = line_y - line_size
        line_x = 3
        if self.align != constants.LEFT:
            line_width = self.font.size(line)[0]
            excess_space = self.collision_rect.width - line_width
            if self.align == constants.CENTER:
                line_x = excess_space // 2
            else: # self.align == constants.LEFT
                line_x = excess_space

        prev_width = 20000
        widths = get_widths(self.font, line)
        for index, width in enumerate(widths):
            if line_x + (width // 2) < click_x:
                line_x += width
                prev_width = width
            else:
                break
        else:
            index += 1
            width = 20000
        self.hitbox[0] = line_x - prev_width // 2
        self.hitbox[2] = prev_width - (prev_width // 2) + width // 2
        self.cursor_pos = char_offset + index

        self.font.set_bold(False)

    def redraw(self):
        super(EditableText, self).redraw()

        if self.wrap:
            lines = split_wrap(self.text, self.font, self.real_size[0] - 4)
        else:
            lines = split_wrap(self.text, self.font, 0)

        if not self.has_focus:
            return

        line_size = self.font.get_linesize()
        real_text_height = line_size * len(lines)

        line_y = 2
        if self.valign != constants.TOP \
           and real_text_height <= self.real_size[1] - 4:
            excess_space = self.real_size[1] - real_text_height
            if self.valign == constants.MID:
                line_y = excess_space // 2
            else: # self.valign == constants.BOTTOM
                line_y = excess_space

        char_offset = 0
        for line in lines:
            if char_offset + len(line) < self.cursor_pos:
                char_offset += len(line)
                line_y += line_size
            else:
                break

        after_char = self.cursor_pos - char_offset

        line_x = 3
        if self.align != constants.LEFT:
            line_width = self.font.size(line)[0]
            excess_space = self.real_size[0] - line_width
            if self.align == constants.CENTER:
                line_x = excess_space // 2
            else: # self.align == constants.LEFT
                line_x = excess_space

        line_x += self.font.size(line[:after_char])[0]

        self.surface.fill( self.resolved_color, (line_x, line_y, 1, line_size))

        if DEBUG:
            s = pygame.Surface(self.hitbox[2:]).convert_alpha()
            s.fill( (255,0,255,100) )
            self.surface.blit( s, self.hitbox)

class UpdateEditableText(EditableText):
    def _on_text_change(self):
        self.update_func(self.text)

    _text = widget.call_on_change("__text", _on_text_change)

    def __init__(self, *args, **kwargs):
        self.update_func = kwargs.pop("update_func", lambda value: None)
        super(UpdateEditableText, self).__init__(*args, **kwargs)

class SelectableText(Text):
    selected = widget.causes_redraw("_selected")

    selected_color = widget.auto_reconfig("_selected_color", "resolved", g.resolve_color_alias)
    resolved_selected_color = widget.causes_redraw("_resolved_selected_color")
    unselected_color = widget.auto_reconfig("_unselected_color", "resolved", g.resolve_color_alias)
    resolved_unselected_color = widget.causes_redraw("_resolved_unselected_color")

    def __init__(self, parent, pos, size, border_color = None,
                 unselected_color = None, selected_color = None, **kwargs):
        super(SelectableText, self).__init__(parent, pos, size, **kwargs)

        self.border_color = border_color or "text_border"
        self.selected_color = selected_color or "text_background_selected"
        self.unselected_color = unselected_color or "text_background_unselected"

        self.selected = False

    def redraw(self):
        if self.selected:
            self.background_color = self.selected_color
        else:
            self.background_color = self.unselected_color
        super(SelectableText, self).redraw()


class ProgressText(SelectableText):
    progress = widget.causes_redraw("_progress")
    
    progress_color = widget.auto_reconfig("_progress_color", "resolved", g.resolve_color_alias)
    resolved_progress_color = widget.causes_redraw("_resolved_progress_color")


    def __init__(self, parent, pos, size, *args, **kwargs):
        self.parent = parent
        self.progress = kwargs.pop("progress", 0)
        self.progress_color = kwargs.pop("progress", "progress_background_progress")
        kwargs.setdefault("border_color", "progress_border")
        kwargs.setdefault("selected_color", "progress_background_selected")
        kwargs.setdefault("unselected_color", "progress_background_unselected")
        super(ProgressText, self).__init__(parent, pos, size, **kwargs)

    def redraw(self):
        super(ProgressText, self).redraw()
        width, height = self.real_size
        self.surface.fill(self.resolved_progress_color,
                          (0, 0, width * self.progress, height))
        self.draw_borders()


class ChunkedText(Text):
    def update_text(self):
        self.text = "".join(self.chunks)

    chunks = widget.call_on_change("__chunks", update_text)

    def __init__(self, *args, **kwargs):
        chunks = kwargs.pop("chunks", ())
        super(ChunkedText, self).__init__(*args, **kwargs)

        self.chunks = chunks

class StyledText(ChunkedText):
    def resolve_styles(value):
        return tuple((g.resolve_color_alias(c), bg, u) for c, bg, u in value)
    
    styles = widget.auto_reconfig("_styles", "resolved", resolve_styles)
    resolved_styles = widget.causes_redraw("_resolved_styles")

    def __init__(self, *args, **kwargs):
        styles = kwargs.pop("styles", ())
        super(StyledText, self).__init__(*args, **kwargs)

        self.styles = styles

    def print_text(self):
        if self.styles:
            offset = 0
            styles = []
            for chunk, style in zip(self.chunks, self.resolved_styles):
                offset += len(chunk)
                styles.append(list(style) + [offset])
            styles[-1][-1] = 0

            print_string(self.surface, self.text, (3, 2), self.font, styles,
                         self.align, self.valign, self.real_size, self.wrap)
        else:
            super(StyledText, self).print_text()

class FastStyledText(FastText, StyledText):
    pass


def _make_prototype_handler(parent):
    def print_on_click(event):
        if event.button != 2 and not (event.button == 1
                                      and (pygame.key.get_mods() & pygame.KMOD_ALT)):
            return
        prefixes = ["|-", "| "]
        kids = [(child, 0) for child in parent.children]
        while kids:
            kid, depth = kids.pop()
            further_kids = [(child, depth+1) for child in kid.children]
            kids += further_kids

            prefix = ""
            if depth:
                prefix = prefixes[1] * (depth - 1) + prefixes[0]

            print(prefix + str(kid))
    return print_on_click

class ProtoWidget(EditableText):
    """Prototyping widget, for creating quick mockups.

       Usage:
       Type to name.
       Drag to move.
       Shift+Drag to resize.
       Control+Drag to duplicate. (children will not duplicate)
       Shift+Control+Drag to create a child.

       Right-click to delete.
       Middle-click or Alt+Click to write out location and size of each widget.
       """
    drag_state = -1

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("color", (0,0,0))
        kwargs.setdefault("border_color", (0,0,0))
        kwargs.setdefault("borders", constants.ALL)
        kwargs.setdefault("background_color", (255,255,255))
        super(ProtoWidget, self).__init__(*args, **kwargs)

    def add_hooks(self):
        super(ProtoWidget, self).add_hooks()
        self.parent.add_handler(constants.DRAG, self.handle_drag)
        self.parent.add_handler(constants.CLICK, self.handle_click)

        if not isinstance(self.parent, ProtoWidget) \
           and not getattr(self.parent, "demo_mode", False):
            self.parent.demo_mode = True
            self.parent.add_handler(constants.CLICK, _make_prototype_handler(self.parent))

    def remove_hooks(self):
        self.parent.remove_handler(constants.DRAG, self.handle_drag)
        self.parent.remove_handler(constants.CLICK, self.handle_click)
        super(ProtoWidget, self).remove_hooks()

    def handle_drag(self, event):
        if self.drag_state == -1:
            start_pos = tuple(event.pos[i]-event.rel[i] for i in range(2))
            if self.is_over(start_pos):
                for child in self.children:
                    if child.is_over(start_pos):
                        self.drag_state = 0
                        return
                real_pos = self.collision_rect[:2]
                self.mouse_rel = tuple(real_pos[i]-start_pos[i]
                                                     for i in range(2))

                mod_keys = pygame.key.get_mods()
                shift = mod_keys & pygame.KMOD_SHIFT
                control = mod_keys & pygame.KMOD_CTRL
                if shift and control:
                    self.drag_state = 0
                    new_size = tuple(d/2 for d in self.size)
                    pw=ProtoWidget(self, (0,0), new_size,
                                  self.anchor,
                                  background_color = self.background_color,
                                  border_color = self.border_color,
                                  borders = self.borders)
                    pw.drag_state = 0
                elif shift:
                    self.drag_state = 2
                elif control:
                    self.drag_state = 0
                    pw=ProtoWidget(self.parent, self.pos, self.size, self.anchor,
                                  background_color = self.background_color,
                                  border_color = self.border_color,
                                  borders = self.borders)
                    pw.drag_state = 1
                    pw.mouse_rel = self.mouse_rel
                else:
                    self.drag_state = 1
            else:
                self.drag_state = 0

        if self.drag_state <= 0:
            return

        if self.parent:
            parent_rect = self.parent.collision_rect
        else:
            parent_rect = pygame.Rect(g.layout_origin, g.real_screen_size)

        if self.drag_state == 1:
            mouse_pos = pygame.mouse.get_pos()
            new_real_pos = tuple(self.mouse_rel[i] + mouse_pos[i] for i in range(2))

            new_rel_pos = tuple(new_real_pos[i] - parent_rect[i] for i in range(2))

            new_unit_pos = tuple( max(0,(new_rel_pos[i] / float(g.real_screen_size[i])))
                                     for i in range(2))

            new_pct_pos = tuple( int( (new_unit_pos[i] * 100) + 0.5)
                                   for i in range(2))

            self.pos = tuple(new_pct_pos[i] / 100. for i in range(2))

            raise constants.Handled
        elif self.drag_state == 2:
            mouse_pos = pygame.mouse.get_pos()
            new_size = tuple(mouse_pos[i] - self.collision_rect[i] for i in range(2))

            unit_size = tuple(max(0,new_size[i] / float(g.real_screen_size[i]))
                                    for i in range(2))

            pct_size = tuple( int( (unit_size[i] * 100) + 0.5)
                                   for i in range(2))

            self.size = tuple(pct_size[i] / 100. for i in range(2))

            raise constants.Handled

    def handle_click(self, event):
        if event.button == 3 and self.is_over(event.pos):
            mine = True
            for child in self.children:
                if child.is_over(event.pos):
                    mine = False
                    break
            if mine:
                self.remove_hooks()
                self.parent.needs_redraw = True
        if self.drag_state > 0:
            self.drag_state = -1
            #raise constants.Handled
        else:
            self.drag_state = -1

    def __str__(self):
        return "%s pos: (%.2f, %.2f), size: (%.2f, %.2f)" % \
           ((self.text,) + self.pos +        self.size)
