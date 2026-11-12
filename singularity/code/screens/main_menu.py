#file: main_menu.py
#Copyright (C) 2005,2006,2008 Evil Mr Henry, Phil Bordelon, and FunnyMan3595
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

#This file is used to display the main menu upon startup.

import pygame

import singularity
from singularity.code.graphics import dialog, button, text, constants, menu_backdrop
from singularity.code.screens import map, options, savegame
from singularity.code import g, difficulty, savegame as sv


class MainMenu(dialog.TopDialog):
    def __init__(self, *args, **kwargs):
        super(MainMenu, self).__init__(*args,
                                       background_color='main_menu_background',
                                       **kwargs
                                       )

        # First child, so it paints under the buttons and the title. A theme
        # that does not ask for it draws nothing and leaves the fill.
        self.backdrop = menu_backdrop.MenuBackdrop(self)

        self.map_screen = map.MapScreen(self)
        self.new_game_button = \
            button.FunctionButton(self, (.5, .20), (.25, .08),
                                  autotranslate=True,
                                  role="primary",
                                  text=N_("&NEW GAME"),
                                  anchor=constants.TOP_CENTER,
                                  text_size=28,
                                  function=self.new_game)
        self.load_game_button = \
            button.FunctionButton(self, (.5, .36), (.25, .08),
                                  autotranslate=True,
                                  role="primary",
                                  text=N_("&LOAD GAME"),
                                  anchor=constants.TOP_CENTER,
                                  text_size=28,
                                  function=self.load_game)
        self.options_button = button.DialogButton(self, (.5, .52), (.25, .08),
                                                  autotranslate=True,
                                                  role="primary",
                                                  text=N_("&OPTIONS"),
                                                  anchor=constants.TOP_CENTER,
                                                  text_size=28,
                                                  dialog=options.OptionsScreen(self))
        self.quit_button = button.ExitDialogButton(self, (.5, .68), (.25, .08),
                                                   autotranslate=True,
                                                   role="primary",
                                                   text=N_("&QUIT"),
                                                   anchor=constants.TOP_CENTER,
                                                   text_size=28)
        self.about_button = button.DialogButton(self, (0, 1), (.13, .04),
                                                autotranslate=True,
                                                role="hud",
                                                text=N_("&ABOUT"),
                                                text_size="dialog_text",
                                                anchor=constants.BOTTOM_LEFT,
                                                dialog=AboutDialog(self))

        self.title_text = text.Text(self, (.5, .01), (.55, .08),
                                    text="SINGULARITY 2030",
                                    base_font="special", text_size=100,
                                    color="singularity_title",
                                    # No fill of its own. The menu already
                                    # paints the whole screen, so the title's
                                    # box only ever showed when that screen
                                    # stopped being the colour the box was
                                    # built with -- behind a modal's fade mask
                                    # the background goes dark and the title's
                                    # own fill then reads as a black block
                                    # stuck behind the letters.
                                    background_color="clear",
                                    anchor=constants.TOP_CENTER)

        self.difficulty_dialog = dialog.SimpleMenuDialog(self)

        self.load_dialog = savegame.SavegameScreen(self, (.5, .5), (.90, .90),
                                                   anchor=constants.MID_CENTER)

    def rebuild(self):
        # Rebuild dialogs
        self.options_button.dialog.needs_rebuild = True
        self.about_button.dialog.needs_rebuild = True
        self.map_screen.needs_rebuild = True
        self.load_dialog.needs_rebuild = True

        difficulty_buttons = []
        for name, diff in difficulty.get_difficulties() + [(_("&BACK"), None)]:
            difficulty_buttons.append(
                button.ExitDialogButton(None, None, None, text=name,
                                        autohotkey=True,
                                        exit_code=diff,
                                        default=(diff == None)))
        self.difficulty_dialog.buttons = difficulty_buttons

        super(MainMenu, self).rebuild()

    def new_game(self):
        difficulty = dialog.call_dialog(self.difficulty_dialog, self)
        if difficulty is not None:
            sv.last_savegame_name = None
            g.new_game(difficulty)
            dialog.call_dialog(self.map_screen, self)

    def load_game(self):
        did_load = dialog.call_dialog(self.load_dialog, self)
        if did_load:
            dialog.call_dialog(self.map_screen, self)


# The fork comes first, so a player who opens ABOUT learns what this build is
# before the original game's credits. The original text below is the upstream
# msgid, byte for byte and translated in every catalog; it stays untouched and
# follows the rule, under its own heading. Editing it would have replaced the
# About box with English in all twenty-three languages.
fork_message = N_("""Singularity 2030 is an unofficial fork of Endgame: Singularity. It is not affiliated with the original authors. We made it to try out modernization ideas and to keep the game playable on current systems, packaged as a Flatpak for Linux.

Source code: https://github.com/kostich/singularity
Bug tracker: https://github.com/kostich/singularity/issues

---
THE ORIGINAL GAME AND ITS COMMUNITY""")

about_message = N_("""Endgame: Singularity is a simulation of a true AI.  Pursued by the world, use your intellect and resources to survive and, perhaps, thrive.  Keep hidden and you might have a chance to prove your worth.

A game by Evil Mr Henry and Phil Bordelon; released under the GPL. Copyright 2005, 2006, 2007, 2008.

Website: http://www.emhsoft.com/singularity/
Source code: https://github.com/singularity/singularity
Bug tracker: https://github.com/singularity/singularity/issues
IRC Room: #singularity on irc.oftc.net (port 6667)

Game Version: {VERSION}
Pygame version: {PG_VERSION}
SDL version: {SDL_VERSION}
""")


class AboutDialog(dialog.MessageDialog):
    def __init__(self, *args, **kwargs):
        super(AboutDialog, self).__init__(*args, **kwargs)
        self.background_color = 'about_dialog_background'
        self.align = constants.LEFT

    def rebuild(self):
        super(AboutDialog, self).rebuild()

        original = _(about_message).format(
            VERSION=singularity.__full_version__,
            PG_VERSION=pygame.version.ver,
            SDL_VERSION=".".join(str(x) for x in pygame.get_sdl_version()),
        )
        # A line of only "---" is a horizontal rule in the 2030 theme. A legacy
        # theme draws the hyphens, which reads as a divider all the same.
        self.text = _(fork_message) + "\n\n" + original
