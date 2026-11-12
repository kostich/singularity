#file: map_screen.py
#Copyright (C) 2005,2006,2008 Evil Mr Henry, Phil Bordelon, FunnyMan3595,
#and Anne M. Archibald.
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

#This file is used to display the World Map.

import pygame

from singularity.code import g, dirs, savegame as sv, mixer
from singularity.code import chance, logmessage, warning
from singularity.code.graphics import g as gg
from singularity.code.graphics import dialog, constants, image, button, text, widget
from singularity.code.screens import research, knowledge, report, log, message, savegame
from singularity.code.screens.cheat_menu import CheatMenuDialog
from singularity.code.screens.location import LocationScreen
from singularity.code.screens.options import OptionsScreen

import math
import time

from pygame.surfarray import pixels_alpha

from numpy import sin, cos, linspace, pi, tanh, round, newaxis, uint8


LOCATION_RECENT_DISCOVERIES_TO_TEXT_COLOR = (
    'location_name_normal',
    'location_name_prev_discover',
    'location_name_last_discover',
    'location_name_last_prev_discover',
)


# The world map art (earth.jpg and earth_night.jpg in every theme) is 2:1.
EARTH_ASPECT = 2.0

# Fraction of the window height the globe may use. The rest is left for the
# HUD strips along the top and the bottom of the map screen.
EARTH_HEIGHT_FRACTION = 0.74

# The speed level where the game clock stops being a clock: at 432000
# game-seconds per second it moves a sixth of a day per 30 fps tick, so the
# terminator would jump across the globe in six frames instead of sweeping.
# Above this level the *picture* is animated at a fixed rate instead.
HIGH_SPEED = 100000

# How long one full day/night sweep takes at that level, in real seconds. The
# fastest speed below it (7200 game-seconds a second) sweeps once per 12 s, so
# this is 3x that, which is what the top speed should look like -- a faster
# version of the level under it, not a strobe.
HIGH_SPEED_SWEEP_SECONDS = 4.0

# How long the band takes at least to slide onto the game clock when the
# player leaves the top speed, in real seconds. That is a floor, not the whole
# story: the sweep and the clock run at rates that have nothing to do with each
# other, so by the time the player slows down they are an arbitrary fraction of
# a day apart. The glide is sized by that gap -- see
# SWEEP_GLIDE_SECONDS_PER_GLOBE.
SWEEP_BLEND_SECONDS = 0.5

# The slowest a gap may be closed, in seconds per globe of travel. A smoothstep
# peaks at 1.5x its mean rate, so this keeps the band from ever turning faster
# while it settles than it did while it swept: the sweep covers a globe in
# HIGH_SPEED_SWEEP_SECONDS, and 1.5 of those is the same peak rate.
SWEEP_GLIDE_SECONDS_PER_GLOBE = 1.5 * HIGH_SPEED_SWEEP_SECONDS


class EarthImage(image.Image):
    def __init__(self, parent):
        super(EarthImage, self).__init__(parent, (.5,.5), (1,.667),
                                         constants.MID_CENTER,
                                         'earth')
        self._sin_latitude = None
        self._cos_longitude_x_cos_latitiude = None
        self.needs_resize = True
        self.sun_radius = 0.5*pi/360
        self.night_image = None
        # The top-speed sweep: a fraction of the day in [0, 1), and the day of
        # the year the mask belongs to while it lasts. Both None below
        # HIGH_SPEED, where the clock drives the picture.
        self.high_speed_phase = None
        self.high_speed_day = None
        # The glide back onto the clock: how far the band is *behind* the
        # clock, in days (never ahead -- see end_high_speed_animation()), the
        # weight that runs 1 -> 0 as the gap is closed, and how much of that
        # weight one tick takes. The drawn fraction is clock + residual *
        # weight.
        self.sweep_residual = 0.0
        self.sweep_blend = 0.0
        self.sweep_blend_step = 0.0
        # The fraction of the day the last frame was drawn at, so a speed
        # change can continue the picture where it was.
        self.last_drawn_portion = None

    def _calc_size(self):
        # The globe keeps the 2:1 aspect of the art. Sizing it as a plain
        # fraction of the screen stretched it on anything wider than 4:3: at
        # 1920x1080 it used to be 1920x720, i.e. 2.67:1, and the night mask
        # along with it. At 4:3 this still returns exactly the old 1024x512.
        return gg.fit_aspect_size(self._parent_size(), EARTH_ASPECT,
                                  EARTH_HEIGHT_FRACTION)

    def rescale(self):
        super(EarthImage, self).rescale()
        self.night_image = image.scale(gg.images['earth_night'],
                                       self.real_size).convert_alpha()

    def reconfig(self):
        super(EarthImage, self).reconfig()

        self.resize()

        self.rescale()
        self.needs_rebuild = True
        self.needs_resize = True
        self.needs_redraw = True

    def resize(self):
        super(EarthImage, self).resize()
        self.reset_night_mask_computation()
        width, height = self.real_size
        latitude = linspace(-pi/2, pi/2, height)[newaxis,:]
        longitude = linspace(0, 2*pi, width)[:,newaxis]
        self._cos_longitude_x_cos_latitiude = cos(longitude) * cos(latitude)
        self._sin_latitude = sin(latitude)
        # The sweep is a fraction of a day, so it survives a resize: the next
        # redraw rebuilds the mask for the new size from the same phase.

    night_mask_day_of_year = None
    night_mask_dim = None
    night_mask = None
    next_night_mask = None
    next_night_mask_ready = False
    next_night_mask_step = 0
    step_night_alphas = None
    step_round_light = None

    start_day = None
    start_second = None

    def _day_portion(self):
        """How much of the day has passed, for the terminator's position.

        Offset by the second the game was started, so the band sits where the
        player's own clock would put it. That offset is read once and kept, so
        the band does not drift as the game runs.
        """
        if self.start_second is None:
            t = time.gmtime()
            self.start_second = t[5] + 60*(t[4]+60*t[3])
        return (((g.pl.raw_min+self.start_second//60)
                    % g.minutes_per_day)
                 / float(g.minutes_per_day))

    def compute_day_of_year(self):
        if self.high_speed_day is not None:
            # Held for the length of the sweep: at the top speed the clock
            # crosses five years' worth of days a second, and a mask rebuilt
            # that often is the flicker this animation exists to avoid.
            return self.high_speed_day
        day_of_year = (g.pl.time_day+g.pl.start_day) % 365 # no leap years, sorry
        return day_of_year

    def on_tick(self, event):
        if self.next_night_mask_ready or self.high_speed_day is not None:
            # Nothing to pre-compute for a mask that is not going to change:
            # the top-speed sweep holds its season until the speed drops, and
            # by then tomorrow's mask is the wrong day anyway.
            return
        width, height = self.real_size
        day_of_year = self.compute_day_of_year()
        # Prepare a part of the next night mask to avoid lagging at end of day
        # on game speed high speed.
        self._compute_night_mask_step(width, height, day_of_year + 1)

    def _compute_night_mask_step(self, width, height, next_day_of_year):
        if self.next_night_mask_ready:
            return
        if self.next_night_mask_step == 0:
            self.next_night_mask = pygame.Surface((width, height), 0, gg.ALPHA)
            self.step_sun_declination = (-23.45/360.*2*math.pi *
                               math.cos(2*math.pi/365.*(next_day_of_year + 10)))

        elif self.next_night_mask_step == 1:
            self.step_sin_sun_altitude = (self._cos_longitude_x_cos_latitiude * cos(self.step_sun_declination)
                                          + self._sin_latitude * sin(self.step_sun_declination))
        elif self.next_night_mask_step == 2:
            self.step_light = 0.5*(tanh(self.step_sin_sun_altitude/self.sun_radius)+1)
        elif self.next_night_mask_step == 3:
            max_alpha = 255
            self.step_night_alphas = pixels_alpha(self.next_night_mask)
            self.step_round_light = round(max_alpha*self.step_light).astype(uint8)
        elif self.next_night_mask_step == 4:
            self.step_night_alphas[...] = self.step_round_light
            self.next_night_mask_ready = True

        self.next_night_mask_step = (self.next_night_mask_step + 1) % 5

    def reset_night_mask_computation(self):
        self.night_mask = None
        # Forget what the mask was built for, or the size check in
        # get_night_mask() sees an unchanged size and hands back self.night_mask
        # -- which this method has just set to None. That path only stayed
        # hidden while night_mask_dim was never assigned at all.
        self.night_mask_dim = None
        self.night_mask_day_of_year = None
        self.next_night_mask_ready = False
        self.next_night_mask_step = 0
        # Drop the pixel views as well. pygame.surfarray.pixels_alpha() locks
        # the surface it reads and only releases it when the array is freed, so
        # a view left in an attribute is a surface that stays locked -- and, if
        # the surface is replaced first, a view pointing at a buffer nobody
        # owns any more. Nothing here may outlive the surface it was taken from.
        self.step_night_alphas = None
        self.step_round_light = None

    def get_night_mask(self):
        width, height = self.real_size
        day_of_year = self.compute_day_of_year()

        if day_of_year != self.night_mask_day_of_year:
            self.night_mask = None
            # Force a rebuild.  In most cases, it will be ready at ahead of time
            # but if any steps are missing, we force a rebuild now at cost of
            # rebuild.
        elif self.night_mask_dim != (width, height):
            # Force a rebuild from scratch at cost of frame-rate
            self.reset_night_mask_computation()
        else:
            return self.night_mask

        while not self.next_night_mask_ready:
            self._compute_night_mask_step(width, height, day_of_year)
        self.night_mask = self.next_night_mask
        # These two were never assigned, so both tests above were dead: the day
        # always looked changed and the size never looked cached. Every redraw
        # therefore rebuilt the whole mask from scratch -- five steps, a fresh
        # full-size surface and its pixel array, thrown away and rebuilt on the
        # next frame (1.7 MB a frame at 1024x600, 8.6 MB at 3440x1440). Nothing
        # was ever cached, and the allocator was churned with a large block per
        # frame for no reason.
        self.night_mask_day_of_year = day_of_year
        self.night_mask_dim = (width, height)
        self.next_night_mask_ready = False

        return self.night_mask

    def compute_night_start(self):
        width = self.real_size[0]
        day_portion = self._drawn_day_portion()
        # What was actually drawn, so the next speed change can continue from
        # it instead of from the clock.
        self.last_drawn_portion = day_portion
        return int(width * (0.5 - day_portion)) % width

    def _sweep_weight(self):
        """How much of the leftover offset is still on screen: 1 -> 0."""
        blend = self.sweep_blend
        # Smoothstep, so the glide does not start or stop with a jerk: the
        # derivative is zero at both ends.
        return blend * blend * (3.0 - 2.0 * blend)

    def _drawn_day_portion(self):
        """The fraction of the day the band is drawn at, glide included."""
        if self.high_speed_phase is not None:
            return self.high_speed_phase
        if self.sweep_blend <= 0.0:
            return self._day_portion()
        return (self._day_portion()
                + self.sweep_residual * self._sweep_weight()) % 1.0

    def end_high_speed_animation(self):
        """Hand the band back to the clock without moving it on screen.

        The sweep runs at its own rate, so by the time the player slows down it
        is somewhere the game clock is not -- an arbitrary fraction of a day
        away, because the two rates have nothing to do with each other. Using
        the clock again from one frame to the next is therefore a jump. Keep
        the gap instead and make it up over a glide.

        The gap has two readings and only one of them is forward. The band is
        a periodic picture, so being a fifth of a day *ahead* of the clock is
        the same picture as being four fifths *behind* it. Behind makes
        ``clock + residual * weight`` rise as the weight falls, so every frame
        of the glide advances the day/night; ahead makes it fall, so the band
        slides backwards -- visibly, and at random, depending on where the
        sweep happened to be when the speed changed.

        Called on every tick below the top speed, so it must be idempotent: a
        glide already under way is left alone.
        """
        if self.high_speed_phase is None:
            return

        # How far the band is behind the clock, in [0, 1) of a day: the only
        # reading of a periodic gap whose closing runs the day/night forward.
        gap = (self._day_portion() - self.high_speed_phase) % 1.0

        self.high_speed_phase = None
        self.high_speed_day = None
        self.sweep_residual = -gap
        # A short gap is made up quickly; a long one may not be closed faster
        # than the sweep itself was turning, or the band would whip round.
        seconds = max(SWEEP_BLEND_SECONDS,
                      SWEEP_GLIDE_SECONDS_PER_GLOBE * gap)
        self.sweep_blend = 1.0
        self.sweep_blend_step = 1.0/(gg.FPS * seconds)

    def advance_sweep_blend(self):
        """Decay the glide by one tick. True while the band is still settling.

        The map screen calls this on every tick, before its early return: at
        speed 1 that return skips most ticks, and a glide that only stepped
        once a second would be as visible as the strobing this replaces.
        """
        if self.sweep_blend <= 0.0:
            return False

        self.sweep_blend = max(0.0, self.sweep_blend - self.sweep_blend_step)
        if self.sweep_blend <= 0.0:
            self.sweep_residual = 0.0
            self.sweep_blend_step = 0.0
        return True

    def advance_high_speed_phase(self):
        """Step the top-speed sweep by one tick's worth of a day.

        The game clock is no help here: it advances curr_speed / FPS seconds
        per tick, which at 432000 is a sixth of a day. So the globe follows a
        fixed rate instead -- one sweep per HIGH_SPEED_SWEEP_SECONDS -- while
        gameplay time keeps racing underneath it.
        """
        if g.curr_speed < HIGH_SPEED:
            self.end_high_speed_animation()
            return

        if self.high_speed_phase is None:
            # Entering the level: start from the last frame that was drawn, not
            # from the clock. The tick that got us here has already moved the
            # clock a sixth of a day -- that is what this speed does -- and
            # following it would be exactly the jump the sweep exists to avoid.
            if self.last_drawn_portion is not None:
                self.high_speed_phase = self.last_drawn_portion
            else:
                self.high_speed_phase = self._drawn_day_portion()
            self.high_speed_day = self.compute_day_of_year()
            self.sweep_residual = 0.0
            self.sweep_blend = 0.0
            self.sweep_blend_step = 0.0
            return

        self.high_speed_phase = (self.high_speed_phase
                                 + 1.0/(gg.FPS * HIGH_SPEED_SWEEP_SECONDS)) % 1.0

    def redraw(self):
        width = self.real_size[0]

        self.night_start = self.compute_night_start()

        super(EarthImage, self).redraw()

        if not g.daynight:
            return

        # Turn half of the map to night, with blended borders.
        night_mask = self.get_night_mask()
        mask_alphas = pixels_alpha(night_mask)
        night_alphas = pixels_alpha(self.night_image)

        right_width = width - self.night_start
        night_alphas[self.night_start:] = mask_alphas[:right_width]
        if self.night_start != 0:
            night_alphas[:self.night_start]  = mask_alphas[right_width:]

        del night_alphas, mask_alphas
        self.surface.blit(self.night_image, (0,0))

    night_start = None
    def rebuild(self):
        super(EarthImage, self).rebuild()

        if not g.daynight:
            return

        old_night_start = self.night_start
        if old_night_start is None or self.needs_redraw:
            return

        width = self.real_size[0]
        self.night_start = self.compute_night_start()

        movement = (old_night_start - self.night_start) % width
        if movement == 0 \
           and self.compute_day_of_year() == self.night_mask_day_of_year:
            return

        self.redraw()

        # Redraw children.
        for child in self.children:
            if child.visible:
                child.redraw()


class GameMenuDialog(dialog.SimpleMenuDialog):

    def __init__(self, map_screen):
        super(GameMenuDialog, self).__init__(parent=map_screen)
        self._map_screen = map_screen
        self.options_dialog = OptionsScreen(self)
        self.savename_dialog = dialog.TextEntryDialog(self)
        self.load_dialog = savegame.SavegameScreen(self,
                                                   (.5, .5), (.90, .90),
                                                   anchor=constants.MID_CENTER)
        self._buttons = [
            button.FunctionButton(None, None, None,
                                  icon="icon_save",
                                  text=_("&SAVE GAME"), autotranslate=True,
                                  function=self.save_game),
            button.FunctionButton(None, None, None,
                                  icon="icon_load",
                                  text=_("&LOAD GAME"), autotranslate=True,
                                  function=self.load_game),
            button.DialogButton(None, None, None,
                                icon="icon_options",
                                text=_("&OPTIONS"), autotranslate=True,
                                dialog=self.options_dialog),
            button.ExitDialogButton(None, None, None,
                                    icon="icon_exit",
                                    text=_("&QUIT"), autotranslate=True,
                                    exit_code=True, default=False),
            button.ExitDialogButton(None, None, None, text=_("&BACK"), autotranslate=True,
                                    icon="icon_back",
                                    exit_code=False),
        ]
        # Hide hotkeys (#289) to avoid confusion due to poor focus visibility
        self.savename_dialog.ok_button.force_underline = -1
        self.savename_dialog.cancel_button.force_underline = -1

        # The difficulty, above the buttons rather than on the map. It is one
        # of the two things a player wants to check on opening this menu (the
        # other is the date, which the HUD already shows), and it was paying
        # for that glance with a permanent row on the play screen.
        self.header_text = text.FastText(self.button_panel, (.01, .01),
                                         (self.width, .05),
                                         wrap=False, base_font="special",
                                         text_size=24,
                                         color="text_disabled",
                                         align=constants.CENTER,
                                         background_color="clear")

        self.needs_rebuild = True

    def header_is_shown(self):
        """The difficulty line is part of the compact map screen only."""
        return (self.header_text is not None
                and gg.hud_style("layout", "classic") == "compact")

    def rebuild(self):
        self.options_dialog.needs_rebuild = True
        self.savename_dialog.text = _("Enter a name for this save.")
        if self.header_text is not None:
            self.header_text.text = g.strip_hotkey(g.pl.difficulty.name)
        super(GameMenuDialog, self).rebuild()

    def load_game(self):
        did_load = dialog.call_dialog(self.load_dialog, self)
        if did_load:
            self._map_screen.force_update()
            raise constants.ExitDialog(False)

    def check_filename(self, event):
        """Disables the OK button and shows an error message if filename in self.savename_dialog is illegal"""
        filename = self.savename_dialog.text_field.text.strip()
        error_message = sv.check_filename_illegal(dirs.get_writable_file_in_dirs(filename, "saves"), filename, '.s2')
        if error_message:
            self.savename_dialog.ok_button.enabled = False
            self.savename_dialog.text = _("Enter a name for this save.") + "\n" + error_message
        else:
            self.savename_dialog.ok_button.enabled = True
            self.savename_dialog.text = _("Enter a name for this save.")

    def suggested_save_name(self):
        """The name the save dialog offers.

        A loaded game, or one already saved this session, keeps that file's
        name so the next save updates it. A game with no name yet is offered
        the current day and the difficulty, and that is recomputed every time
        the dialog opens until the player actually saves.
        """
        if sv.last_savegame_name:
            return sv.last_savegame_name
        return _("DAY") + " %04d %s" % (
            g.pl.time_day, g.strip_hotkey(g.pl.difficulty.name))

    def save_game(self):
        self.savename_dialog.default_text = self.suggested_save_name()
        self.savename_dialog.add_handler(constants.KEYUP, self.check_filename)
        self.savename_dialog.text_field.has_focus = True

        name = dialog.call_dialog(self.savename_dialog, self).strip()
        if name:
            if sv.savegame_exists(name):
                yn = dialog.YesNoDialog(self, pos=(-.5,-.5), size=(-.5,-.5),
                                        anchor=constants.MID_CENTER,
                                        text=_("A savegame with the same name exists.\n"
                                               "Are you sure to overwrite the saved game ?"))
                overwrite = dialog.call_dialog(yn, self)
                if not overwrite:
                    self.save_game()

            sv.create_savegame(name)
            raise constants.ExitDialog(False)

speeds = [0, 1, 60, 7200, 432000]


class MapScreen(dialog.Dialog):
    # The play screen fills the area; it is not a window on anything.
    window_frame = False

    def __init__(self, parent=None, pos=(0, 0), size=(1, 1),
                 anchor = constants.TOP_LEFT,  *args, **kwargs):

        super(MapScreen, self).__init__(parent, pos, size, anchor,
                                        *args, **kwargs)

        g.map_screen = self

        self.background_color = "map_background"
        self.add_handler(constants.TICK, self.on_tick)

        self.map = EarthImage(self)

        self.location_buttons = {}
        for loc in g.locations.values():
            if loc.absolute:
                button_parent = self
            else:
                button_parent = self.map
            b = button.FunctionButton(button_parent, (loc.x, loc.y),
                                      anchor=constants.MID_CENTER,
                                      role="hud",
                                      function=self.open_location,
                                      text_size=28, # Make extraterrestrial locations fit
                                      args=(loc.id,))
            self.location_buttons[loc.id] = b

        self.location_dialog = LocationScreen(self)

        self.suspicion_bar = \
            text.FastStyledText(self, (0,.92), (1, .04), base_font="special",
                                wrap=False,
                                text_size="suspicion_bar",
                                background_color="pane_background_empty",
                                border_color="pane_border",
                                borders=constants.ALL, align=constants.LEFT)

        self.danger_bar = \
            text.FastStyledText(self, (0,.96), (1, .04), base_font="special",
                                wrap=False,
                                text_size="suspicion_bar",
                                background_color="pane_background_empty",
                                border_color="pane_border",
                                borders=constants.ALL, align=constants.LEFT)

        self.report_button = button.DialogButton(self, (0, 0.88),
                                                 (0.15, 0.04),
                                                 role="hud",
                                                 text=N_("R&EPORTS"),
                                                 autotranslate=True,
                                                 icon="icon_report",
                                                 dialog=report.ReportScreen(self))

        self.knowledge_button = button.DialogButton(self, (1, 0.88),
                                                    (0.15, 0.04),
                                                    role="hud",
                                                    text=N_("&KNOWLEDGE"),
                                                    autotranslate=True,
                                                    icon="icon_knowledge",
                                                    anchor=constants.TOP_RIGHT,
                                                    dialog=knowledge.KnowledgeScreen(self))

        self.log_button = button.DialogButton(self, (0.5, 0.88),
                                              (0.15, 0.04),
                                              role="hud",
                                              text=N_("LO&G"),
                                              autotranslate=True,
                                              icon="icon_log",
                                              anchor=constants.TOP_CENTER,
                                              dialog=log.LogScreen(self))

        # Create cheat menu
        # Cheat menu button must be created before menu button to avoid bug.
        # It is always built now (upstream a60a8c4) so that F11 can show and
        # hide it during play instead of only at start-up.
        self.cheat_dialog = CheatMenuDialog(self)
        self.cheat_button = button.DialogButton(
            self, (0, 0), (.01, .01),
            text="",
            enabled=g.cheater,
            # Translators: hotkey to open the cheat screen menu.
            # Should preferably be near the ESC key, and it must not be a
            # dead key (ie, it must print a char with a single keypress)
            hotkey=_("`"),
            dialog=self.cheat_dialog)
        self.cheat_button.visible = g.cheater

        self.menu_dialog = GameMenuDialog(self)
        def show_menu():
            exit = dialog.call_dialog(self.menu_dialog, self)
            if exit:
                raise constants.ExitDialog
        self.menu_button = button.FunctionButton(self, (0, 0), (0.13, 0.04),
                                                 role="hud",
                                                 text=N_("&MENU"),
                                                 autotranslate=True,
                                                 function=show_menu)

        # Display current game difficulty right below the 'Menu' button
        # An alternative location is above 'Reports': (0, 0.84), (0.15, 0.04)
        self.difficulty_display = \
            text.FastText(self, (0, 0.05), (0.13, 0.04),
                          wrap=False,
                          base_font="special",
                          text_size=36,
                          background_color="pane_background_empty",
                          border_color="pane_border")

        self.time_display = text.FastText(self, (.14, 0), (0.23, 0.04),
                                          wrap=False,
                                          text=_("DAY")+" 0000, 00:00:00",
                                          base_font="special",
                                          text_size="time_display",
                                          background_color="pane_background_empty",
                                          border_color="pane_border",
                                          borders=constants.ALL)

        self.research_button = \
            button.DialogButton(self, (.14, 0.05), (0, 0.04),
                                role="hud",
                                text=N_("&RESEARCH"),
                                autotranslate=True,
                                icon="icon_research",
                                dialog=research.ResearchScreen(self))

        bar = "\u25AE"
        arrow = "\u25B6"
        speed_button_souls = [ (bar * 2, .025, speeds[0]), (arrow, .024, speeds[1]),
                              (arrow * 2, .033, speeds[2]), (arrow * 3, .044, speeds[3]),
                              (arrow * 4, .054, speeds[4]) ]

        self.speed_buttons = button.ButtonGroup()
        hpos = .38
        for index, (text_, hsize, speed) in enumerate(speed_button_souls):
            hotkey = str(index)
            b = SpeedButton(self, (hpos, 0), (hsize, .04),
                            role="hud",
                            text=text_, hotkey=hotkey,
                            base_font="normal", text_shrink_factor=.75,
                            align=constants.CENTER,
                            function=self.on_speed_button, args=(speed,))
            hpos += hsize
            self.speed_buttons.add(b)

        self.info_window = \
            widget.BorderedWidget(self, (1, 0), (.44, .10),
                                  anchor=constants.TOP_RIGHT,
                                  background_color="pane_background_empty",
                                  border_color="pane_border",
                                  borders=constants.ALL)

        self.cash_display = \
            text.FastText(self.info_window, (0, 0), (-1, -.33),
                          wrap=False,
                          base_font="special", shrink_factor=.7,
                          borders=constants.ALL,
                          text_size="resource_display",
                          background_color="pane_background_empty",
                          border_color="pane_border")

        self.cpu_display = \
            text.FastText(self.info_window, (0, -.33), (-1, -.33),
                          wrap=False,
                          base_font="special", shrink_factor=.7,
                          borders=(constants.LEFT, constants.RIGHT, constants.BOTTOM),
                          text_size="resource_display",
                          background_color="pane_background_empty",
                          border_color="pane_border")

        self.base_display = \
            text.FastText(self.info_window, (0, -.67), (-1, -.33),
                          wrap=False,
                          base_font="special", shrink_factor=.7,
                          borders=
                          (constants.LEFT, constants.RIGHT, constants.BOTTOM),
                          background_color="pane_background_empty",
                          border_color="pane_border")

        self.message_dialog = dialog.MessageDialog(self,
                                                   text_size="dialog_text")

        # The four readouts a player watches change while they look at them: the
        # clock counts seconds, and cash, CPU and the base count move every tick.
        # A running number in proportional figures is a number whose string
        # changes width, and these are laid out inside fixed boxes -- so the
        # clock slid sideways as it counted and the readouts shuffled. `tabular`
        # asks the theme to draw their digits in equal-width cells; a theme that
        # does not offer it (`tabular_digits = none`) draws them as before.
        for readout in (self.time_display, self.cash_display,
                        self.cpu_display, self.base_display):
            readout.tabular = True

        self.messages = message.MessageDialogs(self)
        self.needs_warning = True
        # The warning ids shown last, so an unchanged set is not repeated.
        # None means "nothing shown yet", which makes the first check show.
        self.shown_warnings = None

        self.add_key_handler(pygame.K_ESCAPE, self.got_escape)
        self.add_key_handler(pygame.K_SPACE, self.toggle_pause)

        self.add_key_handler(constants.XO1_X, self.got_XO1)
        self.add_key_handler(constants.XO1_O, self.got_XO1)
        self.add_key_handler(constants.XO1_SQUARE, self.got_XO1)

    def got_escape(self, event):
        self.menu_button.activate_with_sound(event)

    def got_XO1(self, event):
        if event.key == constants.XO1_X:
            self.adjust_speed(faster=False)
        elif event.key == constants.XO1_O:
            self.adjust_speed(faster=True)
        elif event.key == constants.XO1_SQUARE:
            self.set_speed(0)

    def show_message(self, message, color=None, art_key=None, fallbacks=(),
                     title=None, tone=None):
        """Show one message, with the picture that belongs to it.

        `art_key` is the situation's own plate -- an event's, a base's -- and
        `None` means the generic frame. It is set on *every* call, not only when
        one is given: this is one reused dialog, so a later generic message
        would otherwise keep the picture of whatever was shown last.

        `tone` is "warning" or "alert". In 2030 it recolours the frame and the
        header title, and the body stays the normal text colour. A legacy theme
        ignores it and keeps the body colour it was given.
        """
        self.message_dialog.text = message
        if color == None:
            color = "text"
        if gg.dialog_style("window_layout", "classic") == "2030":
            self.message_dialog.chrome_tone = tone
            self.message_dialog.window_title = title or N_("MESSAGE")
            if tone:
                color = "text"
        else:
            self.message_dialog.chrome_tone = None
            self.message_dialog.window_title = N_("MESSAGE")
        self.message_dialog.color = color
        self.message_dialog.needs_redraw = True
        self.message_dialog.set_art_key(
            art_key or dialog.MessageDialog.art_key,
            fallbacks=tuple(fallbacks))
        dialog.call_dialog(self.message_dialog, self)

    def on_speed_button(self, speed):
        """A speed button sets that level. In 2030 the pause button toggles.

        Pause is speed 0. On a legacy theme that button means "set speed to
        0", so a second click while already paused stays paused. 2030 treats
        it the way Space works: the same control undoes itself. The theme is
        read here, at the click, so changing it in Options applies next time.
        """
        from singularity.code.graphics import theme
        if speed == 0 and getattr(theme.current, "id", None) == "2030":
            self.toggle_pause(None)
            return
        self.set_speed(speed, False)

    def set_speed(self, speed, find_button=True):
        old_speed = g.curr_speed
        # Remember the level to unpause to.  Pause itself is not a level.
        if speed != 0:
            g.last_speed = speed
        g.curr_speed = speed
        # Only the map's animation state is touched here, never the speed
        # bookkeeping: leaving the top speed starts the glide back onto the
        # clock, and the sweep is seeded from wherever the band then is.
        self.map.end_high_speed_animation()
        if speed == 0:
            self.needs_timer = False
            self.stop_timer()
        else:
            self.needs_timer = True
            self.start_timer()

        # Leaving pause is when the warnings are re-checked.  show_warnings()
        # then decides whether they are worth a dialog: unpausing must not
        # repeat a warning the player has already read.
        if old_speed == 0 and speed != 0:
            self.needs_warning = True

        if find_button:
            self.find_speed_button()

        self.needs_redraw = True

    def apply_hud_layout(self):
        """Arrange the top strip and the HUD readouts for the current theme.

        Every value here belongs to the theme's [hud] section, and the `classic`
        branch is the map screen exactly as it has always been -- which is what
        the three legacy themes pin. So a legacy theme enters this method and
        leaves it with every widget where the code used to hardcode it.

        Called from rebuild(), not from __init__: a theme switch has to re-apply
        it, and rebuild() is what a theme switch triggers.
        """
        compact = gg.hud_style("layout", "classic") == "compact"

        if compact:
            # The difficulty moves into the in-game menu (GameMenuDialog), and
            # the four screen buttons take the row it frees. They were on three
            # different rows -- research under the clock, reports bottom-left,
            # log bottom-centre, knowledge bottom-right -- which is most of why
            # the screen read as busy.
            self.difficulty_display.visible = False

            # Centred in the band the row occupies, not sitting on its top edge.
            # The band runs from 0.05 to 0.05 + the strip's own height (0.05),
            # so a 0.04-tall button is centred by starting half the leftover
            # below: 0.04 of 0.05 leaves 0.01, and half of that is 0.005.
            row = 0.055
            # The group stays 0.44 wide, so it is still the same width as the
            # resources window above it, and it is *centred* on the screen
            # rather than pinned to the left edge: 0.28 to 0.72, whose midpoint
            # is the screen's. Pinned left, the four buttons read as a list
            # hanging off the corner.
            column, gap = 0.105, (0.44 - 4 * 0.105) / 3.0
            start = 0.5 - 0.44 / 2.0
            for index, widget_ in enumerate((self.research_button,
                                             self.report_button,
                                             self.log_button,
                                             self.knowledge_button)):
                widget_.anchor = constants.TOP_LEFT
                widget_.pos = (start + index * (column + gap), row)
                widget_.size = (column, 0.04)

            # The speed chooser takes the left edge, and MENU takes the space the
            # speed chooser used to hold. A control the player reaches for by
            # feel belongs against a screen edge; MENU is deliberate, so it
            # belongs further in.
            hpos = 0.0
            for speed_button in self.speed_buttons:
                speed_button.anchor = constants.TOP_LEFT
                speed_button.pos = (hpos, 0)
                hpos += speed_button.size[0]

            self.time_display.anchor = constants.TOP_LEFT
            self.time_display.pos = (0.19, 0)
            self.time_display.size = (0.23, 0.04)

            self.menu_button.anchor = constants.TOP_LEFT
            self.menu_button.pos = (0.425, 0)
            self.menu_button.size = (0.13, 0.04)
        else:
            self.difficulty_display.visible = True
            self.difficulty_display.pos = (0, 0.05)
            self.difficulty_display.size = (0.13, 0.04)

            hpos = .38
            for speed_button in self.speed_buttons:
                speed_button.anchor = constants.TOP_LEFT
                speed_button.pos = (hpos, 0)
                hpos += speed_button.size[0]

            self.time_display.anchor = constants.TOP_LEFT
            self.time_display.pos = (.14, 0)
            self.time_display.size = (0.23, 0.04)

            self.menu_button.anchor = constants.TOP_LEFT
            self.menu_button.pos = (0, 0)
            self.menu_button.size = (0.13, 0.04)

            self.research_button.anchor = constants.TOP_LEFT
            self.research_button.pos = (.14, 0.05)
            self.research_button.size = (0, 0.04)

            self.report_button.anchor = constants.TOP_LEFT
            self.report_button.pos = (0, 0.88)
            self.report_button.size = (0.15, 0.04)

            self.log_button.anchor = constants.TOP_CENTER
            self.log_button.pos = (0.5, 0.88)
            self.log_button.size = (0.15, 0.04)

            self.knowledge_button.anchor = constants.TOP_RIGHT
            self.knowledge_button.pos = (1, 0.88)
            self.knowledge_button.size = (0.15, 0.04)

        self.apply_resource_layout()
        self.apply_vitals_layout()
        self.apply_modal_dim()

    def apply_modal_dim(self):
        """Whether the readouts stay lit while a window is open.

        `[hud] modal_dim = normal` keeps them above the fade mask -- the game
        has always done that, so cash, CPU and bases stay readable behind a
        dialog. `dim` lets them go down with everything else, which is what a
        window in this theme implies: a readout that stays lit while the rest of
        the console is out of play looks live when it is not.
        """
        dimmed = gg.hud_style("modal_dim", "normal") == "dim"
        for widget_ in (self.suspicion_bar, self.danger_bar,
                        self.info_window):
            widget_.self_mask = not dimmed
            widget_.mask_children = False

    def apply_resource_layout(self):
        """Cash, CPU and bases: three rows in a corner, or one line across."""
        if gg.hud_style("resources", "stacked") != "line":
            self.info_window.size = (.44, .10)
            self.cash_display.pos = (0, 0)
            self.cash_display.size = (-1, -.33)
            self.cpu_display.pos = (0, -.33)
            self.cpu_display.size = (-1, -.33)
            self.cpu_display.borders = (constants.LEFT, constants.RIGHT,
                                        constants.BOTTOM)
            self.base_display.pos = (0, -.67)
            self.base_display.size = (-1, -.33)
            self.base_display.borders = (constants.LEFT, constants.RIGHT,
                                         constants.BOTTOM)
            self.cash_display.borders = constants.ALL
            self.cash_display.align = constants.CENTER
            self.cpu_display.align = constants.CENTER
            self.base_display.align = constants.CENTER
            return

        # One line. The three stay separate widgets because their *colours*
        # carry meaning -- `cpu_warning` when the pool goes short,
        # `base_situation_*` when the count does -- and a single merged label
        # could not colour one third of itself.
        #
        # The window is as wide as the four screen buttons above it (0.44), so
        # the play screen reads as one grid: two blocks of the same width, one
        # over the other, both ending at the frame's right edge.
        #
        # One row tall, not 0.05: it sits in the same strip as the DAY box,
        # which is 0.04, and two heights in one strip read as two strips.
        self.info_window.size = (.44, 0.04)
        third = -1 / 3.0
        self.cash_display.pos = (0, 0)
        self.cash_display.size = (third, -1)
        self.cash_display.borders = (constants.LEFT, constants.TOP,
                                     constants.BOTTOM)
        self.cpu_display.pos = (third, 0)
        self.cpu_display.size = (third, -1)
        self.cpu_display.borders = (constants.TOP, constants.BOTTOM)
        self.base_display.pos = (2 * third, 0)
        self.base_display.size = (third, -1)
        self.base_display.borders = (constants.RIGHT, constants.TOP,
                                     constants.BOTTOM)
        for widget_ in (self.cash_display, self.cpu_display,
                        self.base_display):
            widget_.align = constants.CENTER

    def apply_vitals_layout(self):
        """The suspicion and detection figures, on one baseline."""
        centred = gg.hud_style("vitals", "classic") == "centre"
        for bar in (self.suspicion_bar, self.danger_bar):
            bar.align = constants.CENTER if centred else constants.LEFT
            bar.valign = constants.BOTTOM if centred else constants.MID

    def equalise_resource_fonts(self):
        """Give the three readings one type size.

        Each of them auto-fits its own string, so `BASES: 1 / 1 (0)` -- the
        longest -- came out several points smaller than `CPU: 1 (1)`, and three
        readouts of three sizes side by side look like three unrelated labels.
        One size has to be chosen for the group: the largest at which all three
        still fit their third of the window.

        Only under `resources = line`; the stacked layout has a whole row per
        reading, so nothing has to agree.
        """
        if gg.hud_style("resources", "stacked") != "line":
            return

        displays = (self.cash_display, self.cpu_display, self.base_display)
        fonts = self.cash_display.resolved_base_font
        # Computed from the window width, not from `real_size`: this runs inside
        # `rebuild()`, which is called while the tree is preparing to redraw, and
        # the widgets have no resolved size at that point. The fraction is the
        # one `apply_resource_layout()` just gave the window.
        cell = gg.real_screen_size[0] * 0.44 / 3.0
        # Measured against the cell's *inner* width, not against
        # `shrink_factor` of it. That factor exists so a widget picking a size
        # for itself leaves itself room; here the size is chosen for the group
        # and every string has to fit, so the real constraint is the cell.
        usable = int(cell) - 6
        if usable < 8:
            return

        # Ceiling is the theme's own size for these readouts: the equaliser may
        # lower it so the three agree, never raise it above what the theme asked
        # for, or a row of readings would outgrow the strip it sits in.
        ceiling = min(len(fonts) - 1, self.cash_display.max_size)
        chosen = 1
        for size in range(ceiling, 0, -1):
            if all(fonts[size].size(display.text or "")[0] <= usable
                   for display in displays):
                chosen = size
                break

        for display in displays:
            # The widget still bisects for itself inside `pick_font`, and it does
            # that against `shrink_factor` of its box. Left at the constructor's
            # 0.7 it would shrink past the size just chosen for the group -- and
            # by a different amount per string, which is the problem this method
            # exists to fix. At 1.0 its own search agrees with this one.
            display.shrink_factor = 1.0
            # `chosen` is a size in the font list, which is already scaled to
            # this window; `text_size` is a *design* size that gets scaled when
            # it is read. Writing one into the other is what made 2030's row
            # pick 35 when 25 had been chosen, so it is converted back here.
            design = int(round(chosen * gg.default_screen_size[1]
                               / float(max(1, gg.real_screen_size[1]))))
            design = max(1, design)
            if display.text_size != design:
                display.text_size = design

    def adjust_speed(self, faster):
        old_index = -1
        if g.curr_speed in speeds:
            old_index = speeds.index(g.curr_speed)
        if faster:
            new_index = old_index + 1
        else:
            new_index = old_index - 1

        new_index = min(len(speeds)-1, max(0, new_index))

        self.set_speed(speeds[new_index])

    def toggle_pause(self, event):
        if g.curr_speed == 0:
            self.set_speed(g.last_speed)
        else:
            self.set_speed(0)

    def open_location(self, location):
        self.location_dialog.location = g.pl.locations[location]
        dialog.call_dialog(self.location_dialog, self)
        return

    def find_speed_button(self):
        for sb in self.speed_buttons:
            if sb.args[0] == g.curr_speed:
                sb.chosen_one()
                break
        else:
            for sb in self.speed_buttons:
                sb.set_active(False)

    def force_update(self):
        # Entering the map -- a new game, a load, recovering from an error --
        # tells the player what is currently wrong, even if that set of
        # warnings is the same one the previous game ended with.
        self.needs_warning = True
        self.shown_warnings = None

        self.find_speed_button()
        if g.curr_speed:
            self.needs_timer = True
            self.start_timer()
        else:
            self.needs_timer = False
            self.stop_timer()
        self.needs_rebuild = True

    def show_story_section(self, name):
        section = list(g.get_story_section(name))

        # A story page is prose, not a notice: it is the one dialog a player
        # reads a paragraph in, and in this theme it gets a taller box instead
        # of scrolling. `.56 x .62` with the theme's type is the smallest box
        # that holds the longest page of the intro in every shipped
        # translation, at every supported resolution; a legacy theme keeps the
        # box it has always had.
        size = self.story_dialog_size()
        box = {} if size is None else {"size": size}

        # The story is the one place a picture belongs: these are the beats the
        # player remembers, so they get their own art names rather than the
        # generic dialog frames.
        #
        # Each *page* gets one, not each section: the intro is five dialogs and
        # a single picture behind all five is the same waste as a section of
        # text with one illustration. The section's own pool and then the
        # generic story plate are the fallbacks.
        section_slug = logmessage.art_slug(name)
        fallbacks = ("dialog_story_" + section_slug, "dialog_story")
        first_dialog = dialog.YesNoDialog(self, yes_type=N_("&CONTINUE"),
                                          no_type=N_("&SKIP"),
                                          art_key="dialog_story", **box)
        last_dialog = dialog.MessageDialog(self, ok_type=N_("&OK"),
                                           art_key="dialog_story", **box)
        self._apply_story_chrome((first_dialog, last_dialog), name)

        for num, segment in enumerate(section):
            story_dialog = first_dialog if num != len(section) - 1 else last_dialog
            story_dialog.text = segment
            story_dialog.set_art_key("dialog_story_%s_%d" % (section_slug,
                                                             num + 1),
                                     fallbacks=fallbacks)

            if not dialog.call_dialog(story_dialog, self):
                break

        first_dialog.parent = None
        last_dialog.parent = None

    @staticmethod
    def _apply_story_chrome(dialogs, name):
        """A loss is a red window titled DEFEAT. Every other story stays as it was."""
        if name not in ("Lost No Bases", "Lost Suspicion"):
            return
        if gg.dialog_style("window_layout", "classic") != "2030":
            return
        for story_dialog in dialogs:
            story_dialog.chrome_tone = "alert"
            story_dialog.window_title = N_("DEFEAT")
            story_dialog.needs_redraw = True

    @staticmethod
    def story_dialog_size():
        """The box a story page is shown in, or None for the dialog's default.

        Measured, not chosen: every intro page, in every shipped translation,
        at every one of the resolutions the gate renders, fits inside this box
        at the theme's dialog type size. The shipped box was half the screen
        across and half of it down, and a page of prose overflowed it.
        """
        if gg.dialog_style("window_layout", "classic") != "2030":
            return None
        return (.56, .62)

    def show(self):
        self.force_update()

        from singularity.code.safety import safe_call
        # By using safe call here (and only here), if an error is raised
        # during the game, it will drop back out of all the menus, without
        # doing anything, and open the pause dialog, so that the player can
        # save or quit even if the error occurs every game tick.
        while safe_call(super(MapScreen, self).show, on_error=True):
            for child in self.children:
                if isinstance(child, dialog.Dialog):
                    child.visible = False

            # Display a message so the player understand better what happened.
            msg = _("""
An error has occurred. The game will automatically pause and open the game menu. You can continue and save or quit immediately.

A report was written out to%s
Please create a issue with this report at github:
https://github.com/singularity/singularity
""" % (":\n" + g.logfile if g.logfile is not None else " console output."))
            d = dialog.YesNoDialog(self, pos=(-.5,-.5), size=(-.5,-.5),
                                   anchor=constants.MID_CENTER,
                                   yes_type=N_("&CONTINUE"),
                                   no_type=N_("&QUIT"),
                                   text=msg
                                   )
            cont = dialog.call_dialog(d, self)

            if not cont:
                raise SystemExit

            exit = dialog.call_dialog(self.menu_dialog, self)
            if exit:
                self.visible = False
                return

    def show_warnings(self):
        """Show the active warnings, unless they are the ones already shown.

        Upstream opened this dialog on every transition out of pause, so a key
        that toggles pause turned into one dialog per press -- and the dialog
        also stops the game.  A warning the player has just read says nothing
        new, so an unchanged set is shown once; one that appears, changes or
        clears is shown again.
        """
        current = warning.refresh_warnings()
        ids = tuple(w.id for w in current)
        if ids == self.shown_warnings:
            return

        self.shown_warnings = ids
        self.messages.show_list(warning.Warning, current)

    leftovers = 1
    def on_tick(self, event):
        old_speed = g.curr_speed

        if not g.pl.intro_shown:
            g.pl.intro_shown = True
            self.needs_warning = False
            self.show_story_section("Intro")

        if self.needs_warning:
            self.needs_warning = False
            self.show_warnings()

        mins_passed = 0

        # Both of these run on every tick, before the early return below. The
        # handover is checked here as well as at the bottom of the method
        # because a pause sets curr_speed directly (Player.pause_game()), and
        # because at speed 1 the return below skips most ticks: a glide that
        # stepped once a second would be as visible as the strobing it
        # replaces. Both calls are idempotent.
        if g.curr_speed < HIGH_SPEED:
            self.map.end_high_speed_animation()
        if self.map.advance_sweep_blend():
            self.map.needs_redraw = True

        if g.curr_speed != 0:
            self.leftovers += g.curr_speed / float(gg.FPS)
            if self.leftovers < 1:
                return

            self.needs_rebuild = True

            secs = int(self.leftovers)
            self.leftovers %= 1

            # Run this tick.
            mins_passed = g.pl.give_time(secs)

            # Display any message stacked.
            self.messages.show_list(logmessage.AbstractLogMessage, g.pl.curr_log)

        if old_speed != g.curr_speed:
            self.find_speed_button()

        # Update the day/night image every minute of game time -- and, at the
        # top speed, every tick: there the clock is useless for this (it
        # jumps a sixth of a day per frame), so the globe sweeps at a fixed
        # rate and every frame shows a different slice of it.
        if g.curr_speed >= HIGH_SPEED:
            self.map.advance_high_speed_phase()
            self.map.needs_redraw = True
        else:
            # Below the top speed the clock is the picture's clock again. The
            # sweep was ended at the top of this method, so all that is left to
            # do is draw; what it handed over glides away (see
            # advance_sweep_blend()).
            if g.curr_speed == 0 or mins_passed:
                self.map.needs_redraw = True
            else:
                # Smear the cost of rendering the night mask over several
                # ticks to avoid FPS-stalls at end of day at high game
                # speed.
                self.map.on_tick(event)

        lost = g.pl.lost_game()
        if lost > 0:
            lost_story = ["", "Lost No Bases", "Lost Suspicion"]

            mixer.play_music("lose")
            self.show_story_section(lost_story[lost])
            raise constants.ExitDialog

    def on_theme(self):
        """Not a true handler: must be called and propagated manually"""
        self.map.on_theme()
        self.needs_redraw = True

    def reconfig(self):
        # Pass on needs_reconfig to dialogs (it is not passed automatically for some reason
        # Rebuild dialogs
        self.location_dialog.needs_reconfig = True
        self.research_button.dialog.needs_reconfig = True
        self.knowledge_button.dialog.needs_reconfig = True
        self.menu_dialog.needs_reconfig = True

        if g.cheater:
            self.cheat_dialog.needs_reconfig = True

        super(MapScreen, self).reconfig()

    def rebuild(self):
        # Rebuild dialogs
        self.location_dialog.needs_rebuild = True
        self.research_button.dialog.needs_rebuild = True
        self.knowledge_button.dialog.needs_rebuild = True
        self.menu_dialog.needs_rebuild = True

        if g.cheater:
            self.cheat_dialog.needs_rebuild = True

        super(MapScreen, self).rebuild()

        # Re-applied on every rebuild, because a theme switch reconfigures the
        # tree and this is where the [hud] keys are read.
        self.apply_hud_layout()

        self.difficulty_display.text = g.strip_hotkey(g.pl.difficulty.name)
        self.time_display.text = _("DAY") + " %04d, %02d:%02d:%02d" % \
              (g.pl.time_day, g.pl.time_hour, g.pl.time_min, g.pl.time_sec)

        cash_flow_1d_data, cpu_flow_1d_data = g.pl.compute_future_resource_flow(g.seconds_per_day)
        cash_flow_1d = cash_flow_1d_data.difference
        cpu_flow_1d = cpu_flow_1d_data.difference

        self.cash_display.text = _("CASH")+": %s (%s)" % \
              (g.to_money(g.pl.cash), g.to_money(cash_flow_1d, fixed_size=True))

        total_cpu = g.pl.available_cpus[0] + g.pl.sleeping_cpus
        detects_per_day = {group_id: 0 for group_id in g.pl.groups}
        total_bases = 0
        active_bases = 0
        idle_bases_unable_to_sustain_singularity = 0
        for base in g.all_bases():
            total_bases += 1
            maintains_singularity = base.maintains_singularity
            if maintains_singularity:
                active_bases += 1
            elif base.done and not base.is_building():
                idle_bases_unable_to_sustain_singularity += 1

            if base.has_grace():
                # It cannot be detected, so it doesn't contribute to
                # detection odds calculation
                continue
            detect_chance = base.get_detect_chance()
            for group_id in g.pl.groups:
                detects_per_day[group_id] = \
                    chance.add(detects_per_day[group_id], detect_chance[group_id] / 10000.)

        self.cpu_display.color = "cpu_normal"
        self.cpu_display.text = _("CPU")+": %s (%s)" % \
              (g.to_money(total_cpu), g.to_money(cpu_flow_1d))

        if active_bases == 1 and not g.pl.apotheosis:
            self.base_display.color = 'base_situation_one_active_base'
        elif idle_bases_unable_to_sustain_singularity > 0:
            self.base_display.color = 'base_situation_idle_incomplete_bases'
        elif total_bases > 10 and not g.pl.apotheosis:
            self.base_display.color = 'base_situation_many_bases'
        else:
            self.base_display.color = 'base_situation_normal'

        self.base_display.text = _("BASES") + ": %s / %s (%s)" % (active_bases,
                                                                  total_bases,
                                                                  idle_bases_unable_to_sustain_singularity
                                                                  )

        # After all three texts are set, because the size is chosen for the
        # group and the longest string is what decides it.
        self.equalise_resource_fonts()

        # What we display in the suspicion section depends on whether
        # Advanced Socioanalytics has been researched.  If it has, we
        # show the standard percentages.  If not, we display a short
        # string that gives a range of 25% as to what the suspicions
        # are.
        # A similar system applies to the danger levels shown.
        normal = (self.suspicion_bar.color, None, False)

        # The two leading spaces indent a left-aligned line away from the pane's
        # border. A centred line already has that margin, and keeping them would
        # push the visible text off the middle by their width -- which is why
        # the suspicion row and the detection row would sit a few pixels apart
        # when `vitals = centre` asks them to share a centre.
        indent = "  " if self.suspicion_bar.align == constants.LEFT else ""
        suspicion_bar_chunks = [indent + "["+_("SUSPICION")+"]"]
        suspicion_bar_styles = [normal]
        danger_bar_chunks = ["["+_("DETECT RATE")+"]"]
        danger_bar_styles = [normal]

        for group in g.pl.groups.values():
            suspicion = group.suspicion
            suspicion_color = gg.resolve_color_alias("danger_level_%d"
                                                     % g.suspicion_to_danger_level(suspicion))

            detects = detects_per_day[group.spec.id]
            danger_level = group.detects_per_day_to_danger_level(detects)
            detects_color = gg.resolve_color_alias("danger_level_%d" % danger_level)

            if g.pl.display_discover == "full":
                suspicion_display = g.to_percent(suspicion, True)
                danger_display = g.to_percent(detects*10000, True)
            elif g.pl.display_discover == "partial":
                # Rounded to the nearest 5% / 1% already, so two decimals would
                # claim a precision the number does not have: 5.23% was shown
                # as "5.00%".  `to_percent` prints a whole number for a whole
                # one, and this is the place that decides.
                suspicion_display = g.to_percent(g.nearest_percent(suspicion, 500))
                danger_display = g.to_percent(g.nearest_percent(detects*10000, 100))
            else:
                suspicion_display = g.suspicion_to_detect_str(suspicion)
                danger_display = g.danger_level_to_detect_str(danger_level)

            suspicion_bar_chunks.extend((" " + group.name + ":\xA0", suspicion_display))
            suspicion_bar_styles.extend((normal, (suspicion_color, None, False)))

            danger_bar_chunks.extend((" " + group.name + ":\xA0", danger_display))
            danger_bar_styles.extend((normal, (detects_color, None, False)))

        self.suspicion_bar.visible = not g.pl.had_grace
        self.suspicion_bar.chunks = tuple(suspicion_bar_chunks)
        self.suspicion_bar.styles = tuple(suspicion_bar_styles)

        self.danger_bar.visible = not g.pl.had_grace
        self.danger_bar.chunks = tuple(danger_bar_chunks)
        self.danger_bar.styles = tuple(danger_bar_styles)

        for id, location_button in self.location_buttons.items():
            location = g.pl.locations[id]
            danger_level = 0
            if g.pl.display_discover in ('full', 'partial'):
                if g.pl.last_discovery == location:
                    danger_level += 2
                # Partial only gets last discovery
                if g.pl.display_discover == 'full' and g.pl.prev_discovery == location:
                    danger_level += 1

            location_button.text = "%s (%d)" % (location.name, len(location.bases))
            location_button.hotkey = location.hotkey
            location_button.visible = location.available()
            location_button.color = LOCATION_RECENT_DISCOVERIES_TO_TEXT_COLOR[danger_level]


class SpeedButton(button.ToggleButton, button.FunctionButton):
    pass
