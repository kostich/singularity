#file: options.py
#Copyright (C) 2005 Evil Mr Henry, Phil Bordelon, FunnyMan3595, MestreLion
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

#This file is used to display the options screen.

import configparser
import pygame
import json

from singularity.code.graphics import constants, widget, dialog, button, listbox, slider, text, theme, g as gg
from singularity.code import g, dirs, i18n, mixer, data, warning


def window_layout_2030():
    """Whether the settings screen uses the 2030 arrangement.

    The classic numbers are the ones the screen shipped with, and they are
    fractions of the *screen* rather than of the window: they were tuned when
    the panel covered most of it. The 2030 layout speaks in shares of the
    window, so it survives the header band and a resized button row.
    """
    return gg.dialog_style("window_layout", "classic") == "2030"


def _place(widget_, pos, size, align=None):
    widget_.anchor = constants.TOP_LEFT
    widget_.pos = pos
    widget_.size = size
    if align is not None:
        widget_.align = align


class OptionsScreen(dialog.FocusDialog, dialog.YesNoDialog):
    # Settings are not a scene. This screen inherits YesNoDialog, and with it
    # the "dialog_confirm" art key, so a theme with image slots turned on drew
    # a picture frame down one side of the settings panel -- a frame with
    # nothing to put in it, because there is no picture of a resolution list.
    # The insets and the app-wide dialog text are a different matter; this is
    # the one thing the screen opts out of.
    art_key = None

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("yes_type", N_("&OK"))
        kwargs.setdefault("no_type", N_("&CANCEL"))
        super(OptionsScreen, self).__init__(*args, **kwargs)

        self.window_title = N_("OPTIONS")
        self.size = (.80, .85)
        self.pos = (.5, .5)
        self.anchor = constants.MID_CENTER
        self.background_color = "options_background"

        # Tabs panel
        self.general_pane   = GeneralPane(None, (0, .1), (.80, .75))
        self.video_pane     = VideoPane(None, (0, .1), (.80, .75))
        self.audio_pane     = AudioPane(None, (0, .1), (.80, .75))
        self.gui_pane       = GUIPane(None, (0, .1), (.80, .75))

        self.tabs_panes = (self.general_pane, self.video_pane, self.audio_pane, self.gui_pane)

        # Tabs buttons
        self.tabs_buttons = button.ButtonGroup()

        self.general_tab = OptionGroupButton(self, (-.135, .01), (-.240, .05),
                                             autotranslate=True,
                                             text=N_("&General"),
                                             anchor=constants.TOP_CENTER,
                                             function=self.set_tabs_pane, args=(self.general_pane,))
        self.tabs_buttons.add(self.general_tab)

        self.video_tab = OptionGroupButton(self, (-.3790, .01), (-.240, .05),
                                           autotranslate=True,
                                           text=N_("&Video"),
                                           anchor = constants.TOP_CENTER,
                                           function=self.set_tabs_pane, args=(self.video_pane,))
        self.tabs_buttons.add(self.video_tab)

        self.audio_tab = OptionGroupButton(self, (-.6230, .01), (-.240, .05),
                                           autotranslate=True,
                                           text=N_("&Audio"),
                                           anchor=constants.TOP_CENTER,
                                           function=self.set_tabs_pane, args=(self.audio_pane,))
        self.tabs_buttons.add(self.audio_tab)

        self.gui_tab = OptionGroupButton(self, (-.865, .01), (-.235, .05),
                                         autotranslate=True,
                                         text=N_("&Interface"),
                                         anchor=constants.TOP_CENTER,
                                         function=self.set_tabs_pane, args=(self.gui_pane,))
        self.tabs_buttons.add(self.gui_tab)

        self.general_tab.chosen_one()
        self.set_tabs_pane(self.general_pane)

        # YesNoDialog buttons
        self.yes_button.size = (.15, .05)
        self.no_button.size = (.15, .05)

        self.classic_layout = dialog.ClassicLayout(
            (self.general_tab, self.video_tab, self.audio_tab, self.gui_tab,
             self.general_pane, self.video_pane, self.audio_pane, self.gui_pane,
             self.yes_button, self.no_button))

    def rebuild(self):
        # The tabs do not always have a parent, so the automatic "needs_rebuild" magic
        # does not work.  Do it manually instead.
        for pane in self.tabs_panes:
            pane.needs_rebuild = True

        self.apply_window_layout()
        super(OptionsScreen, self).rebuild()

    def apply_window_layout(self):
        """A tab strip under the header, and a pane that fills the window.

        Under `window_layout = classic` this does nothing at all: every tab and
        pane keeps the coordinate the screen was built with.
        """
        if not window_layout_2030():
            self.classic_layout.restore()
            return

        header = self.header_fraction()
        gap = .012
        left = .02
        strip_top = header + gap
        strip_height = .062
        width = (1 - 2 * left - 3 * gap) / 4.0
        tabs = (self.general_tab, self.video_tab, self.audio_tab, self.gui_tab)
        for index, tab in enumerate(tabs):
            _place(tab, (-(left + index * (width + gap)), -strip_top),
                   (-width, -strip_height))

        # Everything from the strip's bottom edge down to the OK/CANCEL row
        # belongs to the pane -- which is the "too much space" this fixes: the
        # old panes stopped 25% short of the buttons and left a gap.
        pane_top = strip_top + strip_height + .022
        pane_bottom = .02 + strip_height + .018
        for pane in self.tabs_panes:
            _place(pane, (-left, -pane_top),
                   (-(1 - 2 * left), -(1 - pane_top - pane_bottom)))

    def place_button_row(self):
        """OK and CANCEL as one pair in the corner, clear of the cut corner.

        They used to sit at the two bottom edges, most of a window apart, which
        reads as two unrelated decisions; the corner where the window ends is
        where a player looks for the way out of it.

        The right inset is `Dialog.button_row_inset()`, the same rule every
        other pair in the theme uses. At the plain margin this pair ended one
        pixel inside the diagonal -- visually *on* the cut corner -- because the
        row sits low enough to be inside the cut's own height.
        """
        if not window_layout_2030():
            # `apply_window_layout()` has restored the pair it shipped with.
            return
        self.place_bottom_button_pair(self.yes_button, self.no_button,
                                      width=-.14, height=-.062)

    def reconfig(self):
        # The tabs do not always have a parent, so the automatic "needs_reconfig" magic
        # does not work.  Do it manually instead.
        for pane in self.tabs_panes:
            pane.needs_reconfig = True
        super(OptionsScreen, self).reconfig()

    def show(self):
        self.initial_options = dict(
            fullscreen      = gg.fullscreen,
            grab            = pygame.event.get_grab(),
            daynight        = g.daynight,
            resolution      = gg.screen_size,
            language        = i18n.language,
            theme           = theme.current.id,
            sound           = not mixer.nosound,
            gui_volume      = mixer.get_volume("gui"),
            music_volume    = mixer.get_volume("music"),
            soundbuf        = mixer.get_soundbuf(),
            warnings        = {warn.id: warn.active for warn in warning.warnings.values()}
        )

        self.set_options(self.initial_options)

        retval = super(OptionsScreen, self).show()
        if retval:
            self.apply_options()
            save_options()

        else:
            # Cancel, revert all options to initial state
            self.set_options(self.initial_options)

        return retval

    def set_tabs_pane(self, tabs_pane):
        for pane in self.tabs_panes:
            pane.parent = None

        tabs_pane.parent = self

    def set_options(self, options):
        for pane in self.tabs_panes:
            pane.set_options(options)

    def apply_options(self):
        for pane in self.tabs_panes:
            pane.apply_options()


class GeneralPane(widget.Widget):
    def __init__(self, *args, **kwargs):

        super(GeneralPane, self).__init__(*args, **kwargs)

        self.language_label = text.Text(self, (.01, .01), (.14, .05),
                                        autotranslate=True,
                                        text=N_("Language:"),
                                        align=constants.LEFT,
                                        background_color="clear")

        self.languages = get_languages_list()
        self.language_choice = \
            listbox.UpdateListbox(self, (.16, .01), (.20, .25),
                                  list=[lang[1] for lang in self.languages],
                                  update_func=self.set_language)

        self.theme_label = text.Text(self, (.46, .01), (.09, .05),
                                     autotranslate=True,
                                     text=N_("Theme:"),
                                     align=constants.LEFT,
                                     background_color="clear",
                                     )

        self.theme_choice = \
            listbox.UpdateListbox(self, (.56, .01), (.20, .25),
                                  update_func=theme.set_theme,
                                  list_pos=theme.get_theme_pos())

        self.classic_layout = dialog.ClassicLayout(
            (self.language_label, self.language_choice, self.theme_label,
             self.theme_choice))
        self.apply_window_layout()

    def apply_window_layout(self):
        """Two columns of list, each as tall as the pane allows."""
        if not window_layout_2030():
            self.classic_layout.restore()
            return
        _place(self.language_label, (-.02, -.02), (-.44, -.06),
               constants.LEFT)
        _place(self.language_choice, (-.02, -.09), (-.44, -.55))
        _place(self.theme_label, (-.52, -.02), (-.46, -.06), constants.LEFT)
        _place(self.theme_choice, (-.52, -.09), (-.46, -.55))

    def rebuild(self):
        self.apply_window_layout()
        self.theme_choice.list = theme.get_theme_list()

        super(GeneralPane, self).rebuild()

    def set_options(self, options):
        self.language_choice.list_pos = [i for i, (code, __)
                                         in enumerate(self.languages)
                                         if code == options['language']][0] or 0
        self.set_language(self.language_choice.list_pos)

        self.theme_choice.list_pos = theme.get_theme_pos()
        theme.set_theme(options['theme'], force_reload=True)

    def apply_options(self):
        pass

    def set_language(self, list_pos):
        if not getattr(self, "language_choice", None):
            return # Not yet initialized.

        if 0 <= list_pos < len(self.language_choice.list):
            language = self.languages[list_pos][0]
            if i18n.language != language:
                set_language_properly(language)


class VideoPane(widget.Widget):
    def __init__(self, *args, **kwargs):
        super(VideoPane, self).__init__(*args, **kwargs)

        self.resolution_initialized = False

        self.resolution_label = text.Text(self, (.01, .01), (.14, .05),
                                          autotranslate=True,
                                          text=N_("Resolution:"),
                                          align=constants.LEFT,
                                          background_color="clear")

        self.resolution_choice = \
            listbox.UpdateListbox(self, (.16, .01), (.20, .25),
                                  update_func=self.update_resolution)

        self.resolution_custom = button.HotkeyText(self, (.01, .28), (.14, .05),
                                                   autotranslate=True,
                                                   text=N_("&Custom:"),
                                                   align=constants.LEFT,
                                                   background_color="clear")

        self.resolution_custom_horiz = \
            text.EditableText(self, (.16, .28), (.14, .05),
                              text=str(gg.default_screen_size[0]),
                              allowed_characters=constants.DIGIT_CHARS,
                              borders=constants.ALL)

        self.resolution_custom_X = text.Text(self,
                                             (.30, .28),
                                             (.02, .05),
                                             text="X",
                                             base_font="special",
                                             background_color="clear")

        self.resolution_custom_vert = \
            text.EditableText(self, (.32, .28), (.14, .05),
                              text=str(gg.default_screen_size[1]),
                              allowed_characters=constants.DIGIT_CHARS,
                              borders=constants.ALL)

        self.resolution_custom_ok = button.FunctionButton(self, (.47, .28), (.14, .05),
                                                          autotranslate=True,
                                                          autohotkey=False,
                                                          text=N_("OK"),
                                                          function=self.set_resolution_custom)
        self.resolution_custom.hotkey_target = self.resolution_custom_ok

        self.fullscreen_label = button.HotkeyText(self, (.40, .01), (.30, .05),
                                                  autotranslate=True,
                                                  text=N_("&Fullscreen:"),
                                                  align=constants.LEFT,
                                                  background_color="clear")
        self.fullscreen_toggle = OptionButton(self, (.715, .01), (.07, .05),
                                              autotranslate=True,
                                              autohotkey=False,
                                              text_shrink_factor=.75,
                                              force_underline=-1,
                                              function=self.set_fullscreen,
                                              args=(button.TOGGLE_VALUE,))
        self.fullscreen_label.hotkey_target = self.fullscreen_toggle

        self.daynight_label = button.HotkeyText(self, (.40, .08), (.30, .05),
                                                autotranslate=True,
                                                text=N_("Da&y/night display:"),
                                                align=constants.LEFT,
                                                background_color="clear")
        self.daynight_toggle = OptionButton(self, (.715, .08), (.07, .05),
                                            autotranslate=True,
                                            autohotkey=False,
                                            text_shrink_factor=.75,
                                            force_underline=-1,
                                            function=self.set_daynight,
                                            args=(button.TOGGLE_VALUE,))
        self.daynight_label.hotkey_target = self.daynight_toggle

        self.grab_label = button.HotkeyText(self, (.40, .15), (.30, .05),
                                            autotranslate=True,
                                            text=N_("&Mouse grab:"),
                                            align=constants.LEFT,
                                            background_color="clear")
        self.grab_toggle = OptionButton(self, (.715, .15), (.07, .05),
                                        autotranslate=True,
                                        autohotkey=False,
                                        text_shrink_factor=.75,
                                        force_underline=-1,
                                        function=self.set_grab,
                                        args=(button.TOGGLE_VALUE,))
        self.grab_label.hotkey_target = self.grab_toggle

        self.classic_layout = dialog.ClassicLayout(
            (self.resolution_label, self.resolution_choice,
             self.resolution_custom, self.resolution_custom_horiz,
             self.resolution_custom_X, self.resolution_custom_vert,
             self.resolution_custom_ok, self.fullscreen_label,
             self.fullscreen_toggle, self.daynight_label,
             self.daynight_toggle, self.grab_label, self.grab_toggle))
        self.apply_window_layout()

    def apply_window_layout(self):
        """The resolution list on the left, the three toggles on a grid right.

        The custom-resolution row sits under the list rather than beside the
        toggles: those two columns used to run into each other at every size.
        """
        if not window_layout_2030():
            self.classic_layout.restore()
            return
        _place(self.resolution_label, (-.02, -.02), (-.46, -.06),
               constants.LEFT)
        _place(self.resolution_choice, (-.02, -.09), (-.46, -.50))
        _place(self.resolution_custom, (-.02, -.62), (-.16, -.06),
               constants.LEFT)
        _place(self.resolution_custom_horiz, (-.19, -.62), (-.14, -.06))
        _place(self.resolution_custom_X, (-.34, -.62), (-.04, -.06))
        _place(self.resolution_custom_vert, (-.39, -.62), (-.14, -.06))
        _place(self.resolution_custom_ok, (-.55, -.62), (-.13, -.06))
        for label, toggle, row in ((self.fullscreen_label,
                                    self.fullscreen_toggle, -.02),
                                   (self.daynight_label,
                                    self.daynight_toggle, -.11),
                                   (self.grab_label, self.grab_toggle, -.20)):
            _place(label, (-.56, row), (-.30, -.06), constants.LEFT)
            _place(toggle, (-.88, row), (-.08, -.06))

    def resize(self):
        super(VideoPane, self).resize()
        self.update_resolution_list()

    def rebuild(self):
        self.apply_window_layout()
        self.update_resolution_list()

        self.fullscreen_toggle.active = gg.fullscreen
        self.grab_toggle.active = pygame.event.get_grab()
        super(VideoPane, self).rebuild()

    def set_options(self, options):
        self.set_fullscreen(options['fullscreen'])
        self.fullscreen_toggle.active = options['fullscreen']

        self.set_grab(options['grab'])
        self.grab_toggle.active = options['grab']

        self.set_daynight(options['daynight'])
        self.daynight_toggle.active = options['daynight']

        self.update_resolution_list(options['resolution'])
        self.set_resolution(options['resolution'])

    def apply_options(self):
        # Apply CUSTOM choice.
        if self.resolution_choice.list_pos == 0:
            try:
                old_size = gg.screen_size
                gg.set_screen_size((int(self.resolution_custom_horiz.text),
                                    int(self.resolution_custom_vert.text)))
                if gg.screen_size != old_size:
                    dialog.Dialog.top.needs_resize = True
            except ValueError:
                pass

    def update_resolution_list(self, current_res=None):
        self.resolution_initialized = False

        if (current_res == None):
            current_res = (int(gg.screen_size[0]), int(gg.screen_size[1]))

        self.resolutions = gg.get_screen_size_list()
        self.resolution_choice.list = [_("CUSTOM")] + ["%sx%s" % res for res in self.resolutions]

        custom = True
        for i, res in enumerate(self.resolutions):
            if res == current_res:
                self.resolution_choice.list_pos = i + 1
                custom = False
        if custom:
            self.resolution_choice.list_pos = 0
            self.resolution_custom_horiz.text = str(current_res[0])
            self.resolution_custom_vert.text = str(current_res[1])

        self.resolution_initialized = True

    def set_fullscreen(self, value):
        if gg.fullscreen != value:
            applied = gg.set_fullscreen(value)
            # The button follows the game's state, whichever path was taken: an
            # immediate switch, or a request that waits for a restart.
            self.fullscreen_toggle.active = gg.fullscreen
            if applied:
                # The window changed size, so the whole tree must catch up.
                dialog.Dialog.top.needs_resize = True

    def set_grab(self, value):
        pygame.event.set_grab(value)

    def set_daynight(self, value):
        g.daynight = value

    def set_resolution(self, value):
        if gg.screen_size != value:
            gg.set_screen_size(value)
            # Resize the existing window rather than recreating it. A display
            # that cannot records the choice, and the next start applies it.
            if gg.apply_display_request() and not gg.fullscreen:
                dialog.Dialog.top.needs_resize = True

    def update_resolution(self, list_pos):
        if not self.resolution_initialized:
            return # Not yet initialized.

        if (list_pos == 0):
            self.set_resolution_custom()
        else:
            res = self.resolutions[list_pos - 1]
            self.set_resolution(res)

    def set_resolution_custom(self):
        try:
            screen_size = (int(self.resolution_custom_horiz.text),
                           int(self.resolution_custom_vert.text))
            self.set_resolution(screen_size)
            self.resolution_choice.list_pos = 0
        except ValueError:
            pass


class AudioPane(widget.Widget):
    def __init__(self, *args, **kwargs):
        super(AudioPane, self).__init__(*args, **kwargs)

        self.sound_label = button.HotkeyText(self, (-.49, .01), (.10, .05),
                                             autotranslate=True,
                                             text=N_("&Sound:"),
                                             anchor=constants.TOP_RIGHT,
                                             align=constants.LEFT,
                                             autohotkey=True,
                                             background_color="clear")
        self.sound_toggle = OptionButton(self, (-.51, .01), (.07, .05),
                                         autotranslate=True,
                                         autohotkey=False,
                                         anchor = constants.TOP_LEFT,
                                         text_shrink_factor=.75,
                                         force_underline=-1,
                                         function=self.set_sound,
                                         args=(button.TOGGLE_VALUE,))
        self.sound_label.hotkey_target = self.sound_toggle

        self.gui_label = text.Text(self, (.01, .08), (.22, .05),
                                   autotranslate=True,
                                   text=N_("GUI Volume:"),
                                   anchor=constants.TOP_LEFT,
                                   align=constants.LEFT,
                                   background_color="clear")
        self.gui_slider = slider.UpdateSlider(self, (.24, .08), (.545, .05),
                                              anchor = constants.TOP_LEFT,
                                              horizontal=True, priority=150,
                                              slider_max=100, slider_size=5)
        self.gui_slider.update_func = self.on_gui_volume_change

        self.music_label = text.Text(self, (.01, .15), (.22, .05),
                                     autotranslate=True,
                                     text=N_("Music Volume:"),
                                     anchor=constants.TOP_LEFT,
                                     align=constants.LEFT,
                                     background_color="clear")
        self.music_slider = slider.UpdateSlider(self, (.24, .15), (.545, .05),
                                                anchor = constants.TOP_LEFT,
                                                horizontal=True, priority=150,
                                                slider_max=100, slider_size=5)
        self.music_slider.update_func = self.on_music_volume_change

        self.soundbuf_label = text.Text(self, (.01, .22), (.25, .05),
                                        autotranslate=True,
                                        text=N_("Sound buffering:"),
                                        align=constants.LEFT,
                                        background_color="clear")
        self.soundbuf_group = button.ButtonGroup()

        self.soundbuf_low = OptionGroupButton(self, (.24, .22), (.145, .05),
                                              text=_("&LOW"), autotranslate=True,
                                              function=self.set_soundbuf,
                                              args=(1024,))
        self.soundbuf_group.add(self.soundbuf_low)

        self.soundbuf_normal = OptionGroupButton(self, (.425, .22), (.175, .05),
                                                 text=_("&NORMAL"), autotranslate=True,
                                                 function=self.set_soundbuf,
                                                 args=(1024*2,))
        self.soundbuf_group.add(self.soundbuf_normal)

        self.soundbuf_high = OptionGroupButton(self, (.64, .22), (.145, .05),
                                               text=_("&HIGH"), autotranslate=True,
                                               function=self.set_soundbuf,
                                               args=(1024*4,))
        self.soundbuf_group.add(self.soundbuf_high)

        self.classic_layout = dialog.ClassicLayout(
            (self.sound_label, self.sound_toggle, self.gui_label,
             self.gui_slider, self.music_label, self.music_slider,
             self.soundbuf_label, self.soundbuf_low, self.soundbuf_normal,
             self.soundbuf_high))
        self.apply_window_layout()

    def apply_window_layout(self):
        """Three rows, each a label and its control on one grid."""
        if not window_layout_2030():
            self.classic_layout.restore()
            return
        _place(self.sound_label, (-.02, -.02), (-.30, -.06), constants.LEFT)
        _place(self.sound_toggle, (-.34, -.02), (-.08, -.06))
        _place(self.gui_label, (-.02, -.11), (-.24, -.06), constants.LEFT)
        _place(self.gui_slider, (-.28, -.11), (-.70, -.06))
        _place(self.music_label, (-.02, -.20), (-.24, -.06), constants.LEFT)
        _place(self.music_slider, (-.28, -.20), (-.70, -.06))
        _place(self.soundbuf_label, (-.02, -.29), (-.26, -.06),
               constants.LEFT)
        _place(self.soundbuf_low, (-.30, -.29), (-.16, -.06))
        _place(self.soundbuf_normal, (-.48, -.29), (-.18, -.06))
        _place(self.soundbuf_high, (-.68, -.29), (-.16, -.06))

    def rebuild(self):
        self.sound_toggle.active = not mixer.nosound
        super(AudioPane, self).rebuild()

    def set_options(self, options):
        self.set_sound(options['sound'])
        self.sound_toggle.active = options['sound']

        self.set_soundbuf(options["soundbuf"])
        if (options["soundbuf"] == 1024*1):
            self.soundbuf_low.chosen_one()
        elif (options["soundbuf"] == 1024*2):
            self.soundbuf_normal.chosen_one()
        elif (options["soundbuf"] == 1024*4):
            self.soundbuf_high.chosen_one()

        self.gui_slider.slider_pos = options["gui_volume"]
        self.music_slider.slider_pos = options["music_volume"]

    def apply_options(self):
        pass

    def set_sound(self, value):
        mixer.set_sound(value)

    def on_gui_volume_change(self, value):
        mixer.set_volume("gui", value)

    def on_music_volume_change(self, value):
        mixer.set_volume("music", value)

    #TODO: Show a 2-second "Please wait" dialog when reinitializing mixer,
    #      otherwise its huge lag might confuse users
    def set_soundbuf(self, value):
        mixer.set_soundbuf(value)

class GUIPane(widget.Widget):
    def __init__(self, *args, **kwargs):
        super(GUIPane, self).__init__(*args, **kwargs)

        self.warning_title = text.Text(self, (.13, .01), (.14, .05),
                                       autotranslate=True,
                                       text=N_("WARNING"),
                                       align=constants.LEFT,
                                       background_color="clear")

        self.warning_labels = {}
        self.warning_toggles = {}

        for i, (warn_id, warn) in enumerate(warning.warnings.items()):
            x = .01
            y = .08 + i * .06

            self.warning_labels[warn_id] = text.Text(self, (x, y), (.30, .05),
                                                     align=constants.LEFT,
                                                     background_color="clear")
            self.warning_toggles[warn_id] = OptionButton(self, (x + .30, y), (.07, .05),
                                                         autotranslate=True,
                                                         autohotkey=False,
                                                         text_shrink_factor=.75,
                                                         force_underline=-1,
                                                         function=self.set_warning,
                                                         args=(button.TOGGLE_VALUE, warn))

        self.classic_layout = dialog.ClassicLayout(
            [self.warning_title] + list(self.warning_labels.values())
            + list(self.warning_toggles.values()))
        self.apply_window_layout()

    def apply_window_layout(self):
        """One warning per row, on one grid, with room to read the name."""
        if not window_layout_2030():
            self.classic_layout.restore()
            return
        _place(self.warning_title, (-.02, -.02), (-.46, -.06), constants.LEFT)
        for index, warn_id in enumerate(self.warning_labels):
            row = -.09 - index * .08
            _place(self.warning_labels[warn_id], (-.02, row), (-.55, -.06),
                   constants.LEFT)
            _place(self.warning_toggles[warn_id], (-.60, row), (-.08, -.06))

    def rebuild(self):
        self.apply_window_layout()
        super(GUIPane, self).rebuild()

        for warn_id, warn in warning.warnings.items():
            self.warning_labels[warn_id].text = warn.name
            self.warning_toggles[warn_id].active = warn.active

    def set_warning(self, value, warn):
        warn.active = value

    def set_options(self, options):
        for warn_id, warn_active in options["warnings"].items():
            warn = warning.warnings[warn_id]
            warn.active = warn_active
            self.warning_toggles[warn_id].active = warn_active

    def apply_options(self):
        pass


class OptionGroupButton(button.ToggleButton, button.FunctionButton):
    pass


class OptionButton(button.StickyOnOffButton, button.FunctionButton):
    pass


def set_language_properly(language):
    i18n.set_language(language)
    data.reload_all_def()

    theme.current.update()
    dialog.Dialog.top.needs_reconfig = True
    dialog.Dialog.top.needs_rebuild = True
    dialog.Dialog.top.needs_redraw = True


def save_options():
    # Build a ConfigParser for writing the various preferences out.
    prefs = configparser.ConfigParser()
    prefs.add_section("Preferences")
    prefs.set("Preferences", "fullscreen",   str(bool(gg.fullscreen)))
    prefs.set("Preferences", "nosound",      str(bool(mixer.nosound)))
    prefs.set("Preferences", "grab",         str(bool(pygame.event.get_grab())))
    prefs.set("Preferences", "daynight",     str(bool(g.daynight)))
    prefs.set("Preferences", "xres",         str(int(gg.screen_size[0])))
    prefs.set("Preferences", "yres",         str(int(gg.screen_size[1])))
    prefs.set("Preferences", "soundbuf",     str(mixer.get_soundbuf()))
    prefs.set("Preferences", "lang",         str(i18n.language))
    prefs.set("Preferences", "theme",        str(theme.current.id))

    for name in sorted(mixer.itervolumes()):
        prefs.set("Preferences", name + "_volume", str(mixer.get_volume(name)))

    prefs.add_section("Warning")
    for warn_id, warn in sorted(warning.warnings.items()):
        prefs.set("Warning", warn_id, str(bool(warn.active)))

    prefs.add_section("Textsizes")
    # Only the sizes the player chose, not the merged values: what the theme
    # picked would otherwise be written out as if it were a preference and
    # then applied on top of whichever theme is chosen next.
    for text_size_id, text_size in sorted(gg.user_text_sizes.items()):
        prefs.set("Textsizes", text_size_id, str(text_size))

    # Actually write the preferences out.
    save_loc = dirs.get_writable_file_in_dirs("prefs.dat", "pref")
    # Explicit encoding: main() reads this file back as UTF-8, so letting the
    # locale pick the codec here could break the round-trip.
    with open(save_loc, 'w', encoding='utf-8') as savefile:
        prefs.write(savefile)


def get_languages_list():
    gamelangs = [(code.split("_", 1)[0], code)
                 for code in i18n.available_languages()]

    langcount = {}
    for language, _ in gamelangs:

        #language++
        langcount[language] = langcount.get(language, 0) + 1

    #Load languages data
    with open(dirs.get_readable_file_in_dirs("languages.json", "i18n"),
              encoding='utf-8') as langdata:
        languages = json.load(langdata)

    output = []
    for language, code in gamelangs:
        if langcount[language] > 1:
            # There are more countries with this base language.
            # Use full language+country locale name
            name = languages.get(code, code)
        else:
            #This is the only country using that base language.
            #Use the (shorter) base language name
            name = languages.get(language, language)

        # The row carries the English name beside the native one: Српски
        # (Serbian). The list is drawn in the face of whichever language is
        # selected, so a player already in Japanese sees العربية and Русский as
        # boxes; the ASCII name is the part that stays readable. A name that is
        # already English does not repeat itself.
        native = name[1] or name[0]
        english = name[0]
        label = native if native == english else "%s (%s)" % (native, english)
        output.append((code, label, native))
    # Sort by the Latin reading of the native name, never by the label: adding
    # the English name to a row must not move it. The code breaks a tie, which
    # is what keeps Српски (sr) beside Srpski (sr_Latn), in that order.
    output.sort(key=lambda lang_info: (
        i18n.language_menu_sort_key(lang_info[2]),
        lang_info[0],
    ))
    return [(code, label) for code, label, _native in output]
