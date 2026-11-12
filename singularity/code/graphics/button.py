#file: button.py
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

#This file contains the Button class.

import pygame

from singularity.code.graphics import constants, widget, text, image, g as gg


def hotkey_matches(hotkey, typed):
    """True when `typed` is the mnemonic `hotkey`.

    Case does not count. Serbian Gaj pairs match in both directions, one
    letter at a time, and so do the Russian letters whose Latin form is a
    single character that pair does not already use. љ њ џ are digraphs in
    Latin (lj, nj, dž) and are not paired with l, n or d. ё э щ ю я ъ ь are
    not paired with a Latin letter. ж ц ч ш use the Serbian letters ž c č š
    and are not also paired with z or s.
    """
    if not isinstance(hotkey, str) or not isinstance(typed, str):
        return False
    if (len(hotkey) != 1 or len(typed) != 1
            or not hotkey.isalpha() or not typed.isalpha()):
        return hotkey == typed

    letters = hotkey_matches.letters
    if letters is None:
        letters = {}
        # Serbian Gaj, then Russian й and ы. Shared letters are listed once.
        for cyr, lat in (
            ("а", "a"), ("б", "b"), ("в", "v"), ("г", "g"), ("д", "d"),
            ("ђ", "đ"), ("е", "e"), ("ж", "ž"), ("з", "z"), ("и", "i"),
            ("ј", "j"), ("к", "k"), ("л", "l"), ("м", "m"), ("н", "n"),
            ("о", "o"), ("п", "p"), ("р", "r"), ("с", "s"), ("т", "t"),
            ("ћ", "ć"), ("у", "u"), ("ф", "f"), ("х", "h"), ("ц", "c"),
            ("ч", "č"), ("ш", "š"), ("й", "j"), ("ы", "y"),
        ):
            letters[cyr.casefold()] = lat.casefold()
        hotkey_matches.letters = letters

    left = hotkey.casefold()
    right = typed.casefold()
    if len(left) == 1:
        left = letters.get(left, left)
    if len(right) == 1:
        right = letters.get(right, right)
    return left == right


hotkey_matches.letters = None


class HotkeyText(text.Text):

    force_underline = widget.causes_rebuild("_force_underline")

    def __init__(self, *args, **kwargs):
        # Force early initialization of _hotkey
        self._hotkey = None
        self.hotkey_func = kwargs.pop('hotkey_func', False)
        self.hotkey_target = kwargs.pop('hotkey_target', None)

        # Auto-translatable defaults to auto-hotkey as it is the most sane default in that case
        self.autohotkey = kwargs.pop('autohotkey', kwargs.get('autotranslate', False))

        self.force_underline = kwargs.pop('force_underline', None)
        self.priority = kwargs.pop('priority', 100)
        
        hotkey = kwargs.pop('hotkey', False)

        super(HotkeyText, self).__init__(*args, **kwargs)

        # Do not use hotkey with auto-hotkey
        if not self.autohotkey:
            self.hotkey = hotkey
        elif hotkey:
            raise ValueError("Cannot use hotkey with automatic hotkey")

    def add_hooks(self):
        super(text.Text, self).add_hooks()
        if self.parent is not None:
            if self._hotkey:
                self.parent.add_key_handler(self._hotkey, self.handle_hotkey, self.priority)

    def remove_hooks(self):
        super(text.Text, self).remove_hooks()
        if self.parent is not None:
            if self._hotkey:
                self.parent.remove_key_handler(self._hotkey, self.handle_hotkey)

    @property
    def hotkey_target(self):
        return self._hotkey_target

    @hotkey_target.setter
    def hotkey_target(self, target):
        self._hotkey_target = target
        if self.hotkey_target is not None:
            self._hotkey_target.hotkey = self._hotkey

    @property
    def hotkey(self):
        return self._hotkey

    @hotkey.setter
    def hotkey(self, hotkey):
        if getattr(self, 'autohotkey', False):
            raise ValueError("Cannot change hotkey with automatic hotkey")
        self._new_hotkey(hotkey)

    def _new_hotkey(self, hotkey):
        old_hotkey = self._hotkey
        self._hotkey = hotkey

        if self.parent is not None:
            if self.hotkey_func is not None:
                if old_hotkey:
                    self.parent.remove_key_handler(old_hotkey, self.handle_hotkey)
                if hotkey:
                    self.parent.add_key_handler(hotkey, self.handle_hotkey, self.priority)
            elif self.hotkey_target is not None:
                self.hotkey_target.hotkey = self._hotkey

        self.needs_rebuild = True

    def _extract_and_set_hotkey(self, text_value):
        from singularity.code.g import hotkey
        parsed_hotkey = hotkey(text_value)
        self._new_hotkey(parsed_hotkey['key'])
        return parsed_hotkey['text']

    def handle_hotkey(self, event):
        if event.type == pygame.KEYDOWN:
            typed = event.unicode
            matched = self.hotkey in (typed, event.key)
            if not matched and isinstance(self.hotkey, str) and typed:
                matched = hotkey_matches(self.hotkey, typed)
            if self.visible and self.enabled and matched:
                if self.hotkey_func:
                    self.hotkey_func(event)

    def _retranslate(self):
        new_text = _(self._untranslated_text)
        if self.autohotkey and new_text is not None:
            new_text = self._extract_and_set_hotkey(new_text)
        self._text = new_text

    @text.Text.text.setter
    def text(self, value):
        if self.autotranslate:
            raise ValueError("Cannot change text for an automatic translatable text widget")

        if self.autohotkey and value is not None:
            value = self._extract_and_set_hotkey(value)
        self._text = value

    def calc_underline(self):
        if self.force_underline is not None:
            self.underline = self.force_underline
        elif self.text and self.hotkey and isinstance(self.hotkey, str):
            if self.hotkey in self.text:
                self.underline = self.text.index(self.hotkey)
            elif self.hotkey.lower() in self.text.lower():
                self.underline = self.text.lower().index(self.hotkey.lower())
        else:
            self.underline = -1

    def rebuild(self):
        old_underline = self.underline
        self.calc_underline()
        if self.underline != old_underline:
            self.needs_redraw = True

        super(HotkeyText, self).rebuild()


class Button(text.SelectableText, HotkeyText):

    # How this button's box is decided.
    #
    #   standard -- the theme's one height ([dialog] button_height), so a row
    #               of dialog buttons is a row instead of five different boxes
    #   hud      -- the play screen's strip, where buttons are placed on a grid
    #               whose cells are as tall as the strip, not as tall as a row
    #   primary  -- the main menu, where the buttons are the screen
    #   chrome   -- not a button at all: a slider handle, a scrollbar arrow
    #
    # `standard` is the default because most buttons in this game are dialog
    # buttons and those are the ones that were all over the place.
    role = "standard"

    # The glyph drawn beside the label, as a name in g.images. A theme turns
    # the whole set on with `icon_buttons = all`; a button with no icon, or a
    # theme without the key, or an icon whose file is not there, all draw the
    # label alone -- which is what every button did before the key existed.
    icon = None

    # A theme may give a hovered button a CRT overlay: fine scanlines and one
    # soft band travelling down its face. `button_hover = none` is the old
    # behaviour, and the old behaviour is no animation at all.
    scanline_color = widget.auto_reconfig("_scanline_color", "resolved",
                                         gg.resolve_color_alias)
    resolved_scanline_color = widget.causes_redraw("_resolved_scanline_color")
    sweep_color = widget.auto_reconfig("_sweep_color", "resolved",
                                       gg.resolve_color_alias)
    resolved_sweep_color = widget.causes_redraw("_resolved_sweep_color")

    # Milliseconds for one sweep to cross the button.
    HOVER_PERIOD = 1400

    # The gap between a glyph and the label it belongs to. Named because two
    # places have to agree on it: `content_extra_left()` reserves exactly this
    # much beside the text, and `redraw()` leaves exactly this much between the
    # glyph and the first letter.
    GLYPH_GAP = 4

    # Rewrite .hotkey, to update key handlers.
    def _new_hotkey(self, value):
        if self.parent and value != self._hotkey:
            if self._hotkey:
                self.parent.remove_key_handler(self._hotkey, self.handle_event)
            if value:
                self.parent.add_key_handler(value, self.handle_event)
        super(Button, self)._new_hotkey(value)

    def __init__(self, parent, pos, size = (0, .045), base_font = None,
                 borders = constants.ALL, text_shrink_factor = .825,
                 icon = None, **kwargs):
        self.role = kwargs.pop("role", "standard")
        self.parent = parent
        self.icon = icon
        self._icon_scaled = None
        self._hovered = False
        self._hover_ticks = 0

        self.scanline_color = None
        self.sweep_color = None
        self._scanlines = None
        self._sweep = None
        self._hover_hooked = False

        kwargs.setdefault('text_size', 'button')
        super(Button, self).__init__(parent, pos, size, **kwargs)

        self.base_font = base_font or "special"
        self.borders = borders
        self.shrink_factor = text_shrink_factor

        self.hotkey_func = self.activate_with_sound
        self.selected = False

    @staticmethod
    def standard_height():
        """The theme's one button height in pixels, or 0 for "as asked".

        A design size, converted like every other pixel measurement in the UI,
        so a button is the same fraction of the window at every resolution
        instead of growing with whichever box it happens to sit in.
        """
        design = gg.dialog_style("button_height", 0)
        if not design:
            return 0
        return max(1, int(design * gg.real_screen_size[1]
                           / float(gg.default_screen_size[1]) + .5))

    def override_size(self, dimensions):
        if self.role != "standard":
            return dimensions
        height = self.standard_height()
        if not height:
            return dimensions
        return (dimensions[0], height)

    def icon_glyph(self, dimensions=None):
        """The scaled glyph this button draws, or None if it draws none."""
        if not self.icon or gg.dialog_style("icon_buttons", "none") == "none":
            return None

        art = gg.images.get(self.icon)
        if art is None:
            return None

        if dimensions is None:
            width, height = self.real_size
        else:
            width, height = dimensions

        # 60% of the button's height: readable at 40px, never so large that the
        # glyph becomes the button.
        side = int(height * .60)
        if side < 8:
            return None
        # The width guard exists to leave the label room, so a button with no
        # label -- a window's close box is a glyph in a square -- does not need
        # it: at a square's proportions the glyph is always wider than half the
        # button, and the guard would hide it for ever.
        if self.text and width < side * 2:
            return None

        key = (id(art), side)
        if self._icon_scaled is None or self._icon_scaled[0] != key:
            self._icon_scaled = (key, image.scale(art, (side, side)))
        return self._icon_scaled[1]

    def content_extra_left(self, dimensions=None):
        glyph = self.icon_glyph(dimensions)
        if glyph is None:
            return 0
        return glyph.get_width() + self.GLYPH_GAP

    @staticmethod
    def hover_effect_enabled():
        # Both halves have to be there: the theme asking for the effect, and the
        # colour it is drawn in. A theme that opts in without defining the
        # colour gets no animation rather than a KeyError while drawing.
        return (gg.dialog_style("button_hover", "none") == "scanline"
                and "button_scanline" in gg.colors)

    def _set_hover_colours(self):
        """Point the overlay at the theme's colours, or at nothing at all."""
        if self.hover_effect_enabled():
            self.scanline_color = "button_scanline"
            self.sweep_color = "button_scanline_sweep"
        else:
            self.scanline_color = None
            self.sweep_color = None

    def hover_sweep_phase(self):
        """Where the sweep band is: 0 at the top of the button, 1 past it.

        Counted in ticks rather than read from the clock, for two reasons. A
        frame rendered without a tick -- which is every frame the snapshot tool
        and the tests draw -- is then reproducible, instead of showing whatever
        the wall clock happened to say. And the band advances because the
        button was *drawn* again, which is what an animation is; wall-clock
        time would let it jump a third of the way down a face that has not been
        on screen yet.
        """
        step = 1000.0 / max(1, gg.FPS)
        return ((self._hover_ticks * step) % self.HOVER_PERIOD) \
            / float(self.HOVER_PERIOD)

    def watch_hover(self, event):
        """Track the pointer, separately from `.selected`.

        `.selected` is not the same question: a toggle button stays selected
        while it is the active tab, so animating on it would leave the settings
        screen's chosen tab crawling for as long as it is open. Hover is its
        own state and its own handler.
        """
        hovered = bool(self.visible and self.enabled
                       and getattr(self, "collision_rect", None)
                       and self.is_over(pygame.mouse.get_pos()))
        if hovered != self._hovered:
            self._hovered = hovered
            if hovered:
                self._hover_ticks = 0
            self.needs_redraw = True

    def handle_hover_tick(self, event):
        """Advance the band, and ask for a redraw, only while hovered.

        The tick is the only clock the widget tree has. Nothing is flagged when
        the pointer is elsewhere, so a menu of buttons costs nothing until one
        of them is under it.
        """
        if not self._hovered or not self.hover_effect_enabled():
            return
        self._hover_ticks += 1
        self.needs_redraw = True

    def _sync_hover_handler(self):
        """Add or drop the tick handler to match the current theme.

        Needed as well as add_hooks(): a theme switch arrives through
        reconfig(), and the main menu's buttons outlive it.
        """
        self._set_hover_colours()
        if self.parent is None:
            return
        wanted = self.hover_effect_enabled()
        if wanted and not self._hover_hooked:
            self.parent.add_handler(constants.TICK, self.handle_hover_tick)
            self._hover_hooked = True
        elif not wanted and self._hover_hooked:
            self.parent.remove_handler(constants.TICK, self.handle_hover_tick)
            self._hover_hooked = False

    def reconfig(self):
        super(Button, self).reconfig()
        self._sync_hover_handler()

    def _scanline_layer(self, size):
        colour = self.resolved_scanline_color
        if colour is None:
            return None
        key = (size, colour)
        if self._scanlines is None or self._scanlines[0] != key:
            layer = pygame.Surface(size, pygame.SRCALPHA)
            for y in range(0, size[1], 3):
                layer.fill(colour, (0, y, size[0], 1))
            self._scanlines = (key, layer)
        return self._scanlines[1]

    def _sweep_band(self, size):
        colour = self.resolved_sweep_color
        if colour is None:
            return None
        key = (size, colour)
        if self._sweep is not None and self._sweep[0] == key:
            return self._sweep[1]

        width, height = size
        band_height = max(4, height // 2)
        red, green, blue, alpha = colour
        band = pygame.Surface((width, band_height), pygame.SRCALPHA)
        for row in range(band_height):
            # A triangular profile, so the band has no hard top or bottom edge.
            across = row / float(max(1, band_height - 1))
            fade = 1.0 - abs(across * 2.0 - 1.0)
            band.fill((red, green, blue, int(alpha * fade)), (0, row, width, 1))
        self._sweep = (key, band)
        return band

    def draw_hover_effect(self):
        """The CRT overlay a hovered button wears, if the theme asks for one."""
        if not self._hovered or not self.hover_effect_enabled():
            return
        size = self.real_size
        if size[0] < 4 or size[1] < 4:
            return

        scanlines = self._scanline_layer(size)
        if scanlines is not None:
            self.surface.blit(scanlines, (0, 0))

        band = self._sweep_band(size)
        if band is not None:
            # From entirely above the button to entirely below it, so the band
            # enters and leaves instead of appearing in the middle.
            span = size[1] + band.get_height()
            offset = int(self.hover_sweep_phase() * span) - band.get_height()
            self.surface.blit(band, (0, offset))

    def redraw(self):
        # The label is centred in what the glyph leaves, not pushed along by
        # it: the gutter is an inset on the text, and the frame does not move.
        glyph = self.icon_glyph()
        super(Button, self).redraw()
        if glyph is not None:
            # Beside the label, not at the button's edge. The gutter is part of
            # the *measurement* (`content_extra_left`), so a label centred in
            # what is left sits further in than the gutter's width -- which left
            # a glyph pinned at x=3 with a gap of dead space between it and its
            # word on a short label and a wider one on the same button. Placing
            # it against the label's own first pixel keeps the pair together and
            # keeps the pair centred, because the reserved gutter is what the
            # centring was computed from.
            x = self.first_glyph_x() - self.GLYPH_GAP - glyph.get_width()
            self.surface.blit(
                glyph, (max(0, x),
                        (self.real_size[1] - glyph.get_height()) // 2))
        # Over the label, because that is what a CRT overlay does: the effect
        # has to read as something between the eye and the screen.
        self.draw_hover_effect()

    def add_hooks(self):
        super(Button, self).add_hooks()
        if self.parent:
            self.parent.add_handler(constants.MOUSEMOTION, self.watch_mouse,
                                    self.priority)
            self.parent.add_handler(constants.MOUSEMOTION, self.watch_hover,
                                    self.priority)
            self.parent.add_handler(constants.CLICK, self.handle_event,
                                self.priority)
            self._sync_hover_handler()

    def remove_hooks(self):
        super(Button, self).remove_hooks()
        if self.parent:
            self.parent.remove_handler(constants.MOUSEMOTION, self.watch_mouse)
            self.parent.remove_handler(constants.MOUSEMOTION, self.watch_hover)
            self.parent.remove_handler(constants.CLICK, self.handle_event)
            self.parent.remove_handler(constants.TICK, self.handle_hover_tick)
            self._hover_hooked = False

    def watch_mouse(self, event):
        """Selects the button if the mouse is over it."""
        if self.visible and getattr(self, "collision_rect", None):
            # This gets called a lot, so it's been optimized.
            select_now = self.is_over(pygame.mouse.get_pos())
            if self.enabled and (self._selected ^ select_now):  # If there's a change.
                self.selected = select_now

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONUP:
            if self.visible and self.enabled and self.is_over(event.pos):
                self.activate_with_sound(event)

    def activate_with_sound(self, event):
        """Called when the button is pressed or otherwise triggered.

           This method is called directly by the GUI handler, and should be
           overwritten only to remove the click it plays."""

        # Sometimes other GUI widgets trigger an activation; ignore
        # it if the button is disabled
        if not self.enabled:
            return
        from singularity.code.mixer import play_sound
        play_sound("click")
        self.activated(event)

    def activated(self, event):
        """Called when the button is pressed or otherwise triggered."""

        # Sometimes other GUI widgets trigger an activation; ignore
        # it if the button is disabled
        if not self.enabled:
            return
        raise constants.Handled


class ImageButton(Button):

    def __init__(self, *args, **kwargs):
        image_surface = kwargs.pop("image", None)

        super(ImageButton, self).__init__(*args, **kwargs)

        self.image = image.Image(self, (-.5, -.5), (-.9, -.9),
                                 anchor = constants.MID_CENTER,
                                 image = image_surface)


class FunctionButton(Button):
    def __init__(self, *args, **kwargs):
        self.function = kwargs.pop("function", lambda *args, **kwargs: None)
        self.args = kwargs.pop("args", ())
        self.kwargs = kwargs.pop("kwargs", {})
        super(FunctionButton, self).__init__(*args, **kwargs)

    def activated(self, event):
        """FunctionButton's custom activated menu.  Makes the given function
           call and raises Handled if it returns without incident."""
        self.function(*self.args, **self.kwargs)
        raise constants.Handled


class ExitDialogButton(FunctionButton):
    def __init__(self, *args, **kwargs):
        self.exit_code = kwargs.pop("exit_code", None)
        self.exit_code_func = kwargs.pop("exit_code_func", None)
        self.default = kwargs.pop("default", True)
        super(ExitDialogButton, self).__init__(*args, **kwargs)
        self.function = self.exit_dialog

    def add_hooks(self):
        super(ExitDialogButton, self).add_hooks()
        if self.parent:
            self.parent.add_key_handler(pygame.K_ESCAPE, self.activate_default)

    def remove_hooks(self):
        super(ExitDialogButton, self).remove_hooks()
        if self.parent:
            self.parent.remove_key_handler(pygame.K_ESCAPE, self.activate_default)

    def activate_default(self, event):
        if not self.default:
            return

        return self.activate_with_sound(event)

    def exit_dialog(self):
        """Closes the dialog with the given exit code."""
        if self.exit_code_func:
            raise constants.ExitDialog(self.exit_code_func())
        else:
            raise constants.ExitDialog(self.exit_code)

class DialogButton(FunctionButton):
    def __init__(self, *args, **kwargs):
        self.dialog = kwargs.pop("dialog", None)
        super(DialogButton, self).__init__(*args, **kwargs)
        self.function = self.show_dialog

    def show_dialog(self):
        """When the assigned dialog exits, raises Handled with the dialog's
           exit code as a parameter.  Subclass if you care what the code was."""
        if not self.dialog:
            raise constants.Handled
        else:
            from singularity.code.graphics import dialog
            raise constants.Handled(dialog.call_dialog(self.dialog, self))


TOGGLE_VALUE = object()
WIDGET_SELF = object()


class _FunctionButtonSupportShim(object):

    active = False
    _args = ()

    def replace_args(self, value):
        if value is TOGGLE_VALUE:
            return self.active
        elif value is WIDGET_SELF:
            return self
        else:
            return value

    def get_args(self):
        return tuple(self.replace_args(value) for value in self._args)

    def set_args(self, args):
        self._args = args

    args = property(get_args, set_args)


# "On/Off" button that "stays" in its current activation status until it is
# clicked/"activated"
class StickyOnOffButton(Button, _FunctionButtonSupportShim):

    def __init__(self, *args, **kwargs):
        self._active = kwargs.pop('active', False)
        self._on_text = kwargs.pop('on_text', N_('YES'))
        self._off_text = kwargs.pop('off_text', N_('NO'))
        kwargs['text'] = self._on_text if self.active else self._off_text
        super(StickyOnOffButton, self).__init__(*args, **kwargs)

    @property
    def active(self):
        return self._active

    @active.setter
    def active(self, new_value):
        self._active = new_value
        self.selected = new_value
        new_text = self._on_text if self.active else self._off_text
        if self.autotranslate:
            self._untranslated_text = new_text
            new_text = _(new_text)
        self._text = new_text
        if hasattr(self, "_collision_rect"):
            self.watch_mouse(None)

    def activated(self, event):
        self.active = not self.active
        super(StickyOnOffButton, self).activated(event)

    def watch_mouse(self, event):
        if not self.active:
            super(StickyOnOffButton, self).watch_mouse(event)


# Grouped "On/Off" button that "stays" in its current activation status until
# it is clicked/"activated" OR another button in its group is clicked/activated
class ToggleButton(Button, _FunctionButtonSupportShim):
    active = False
    button_group = None

    def chosen_one(self):
        if self.button_group is not None:
            for button in self.button_group:
                button.set_active(False)
            self.set_active(True)
        else:
            self.set_active(not self.active)

    def set_active(self, active):
        self.active = active
        self.selected = active
        if hasattr(self, "_collision_rect"):
            self.watch_mouse(None)

    def activated(self, event):
        self.chosen_one()
        super(ToggleButton, self).activated(event)

    def watch_mouse(self, event):
        if not self.active:
            super(ToggleButton, self).watch_mouse(event)


class ButtonGroup(list):
    def add(self, button):
        button.button_group = self
        super(ButtonGroup, self).append(button)

    def remove(self, button):
        button.button_group = None
        super(ButtonGroup, self).remove(button)
