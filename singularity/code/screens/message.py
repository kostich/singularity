#file: warning.py
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

#This file is used to display message dialogs.

import pygame

from singularity.code import g, warning
from singularity.code.graphics import dialog, constants, text, button
from singularity.code.graphics import g as gg


class MessageDialogs(object):

    def __init__(self, screen):
        self.screen = screen
        self.dialog = MessageListDialog(screen,
                                        yes_type=N_("&CONTINUE"),
                                        no_type=N_("&PAUSE"))

    def show_list(self, message_type, messages):
        if (len(messages) == 0):
            return

        self.dialog.type = message_type
        self.dialog.list = messages
        ret = dialog.call_dialog(self.dialog, self.screen)

        # Pause game
        if (not ret):
            g.pl.pause_game()
            return True

        # Continue
        return False

class MessageListDialog(dialog.YesNoDialog):
    art_key = "dialog_message_list"

    def __init__(self, *args, **kwargs):
        super(MessageListDialog, self).__init__(*args, **kwargs)
        # The band stays empty: this dialog's own title row already says which
        # page of which event this is, and a second heading above it would
        # repeat the message's own name.
        self.window_title = None

        # The frame, not the screen edge, is what these widgets sit in: a theme
        # may ask for a margin and for a picture pane, and they then start past
        # it. With the legacy values (margin .01, no pane) every number below
        # is the one that used to be hardcoded here.
        margin, left, top = self.content_margins()

        self.title = text.Text(self, (-left, -top),
                               (-(1 - left - margin), -.1),
                               background_color="clear",
                               anchor=constants.TOP_LEFT,
                               valign=constants.MID, align=constants.LEFT,
                               base_font="special", text_size=28)

        # A story event is the longest prose in the game, and this is where the
        # player reads it: the body scrolls rather than shrinking its type and
        # running under PREV/NEXT.
        self.body = text.ScrollableText(self,
                               (-left, -(top + .1)),
                               (-(1 - left - margin),
                                -(1 - margin - .05 - (top + .1))),
                               background_color="clear",
                               anchor=constants.TOP_LEFT,
                               valign=constants.TOP, align=constants.LEFT,
                               text_size="dialog_text")
        # The body is its own widget inside the dialog, so the button row it
        # has to clear is the dialog's, not its own.
        dialog.apply_text_plate(self.body)

        self.prev_button = button.FunctionButton(
                                                 self,
                                                 (-(1 - margin - .21), -top),
                                                 (-.2, -.1),
                                                 icon="icon_prev",
                                                 text=_("P&REV"), autohotkey=True,
                                                 anchor=constants.TOP_RIGHT,
                                                 text_size=28,
                                                 function=self.prev_message)

        self.next_button = button.FunctionButton(
                                                 self,
                                                 (-(1 - margin), -top),
                                                 (-.2, -.1),
                                                 icon="icon_next",
                                                 text=_("&NEXT"), autohotkey=True,
                                                 anchor=constants.TOP_RIGHT,
                                                 text_size=28,
                                                 function=self.next_message)
                               
        self.add_key_handler(pygame.K_LEFT, self.handle_key)
        self.add_key_handler(pygame.K_RIGHT, self.handle_key)
        
        # TODO: Add button "Do not show this message again"

    def rebuild(self):
        # 2030 puts the type in the header band and hides the caption. One
        # page then has nothing left in that row, so the body moves up into it.
        # A legacy theme keeps the caption where it has always been.
        compact = gg.dialog_style("window_layout", "classic") == "2030"
        single = len(self.list) <= 1
        margin, left, top = self.content_margins()
        caption = 0.0 if compact and single else 0.1
        self.title.visible = not compact
        self.body.pos = (-left, -(top + caption))
        self.body.size = (-(1 - left - margin),
                          -(1 - margin - .05 - (top + caption)))
        if compact:
            if single:
                self.window_title = self.type.title_simple()
            else:
                self.window_title = self.type.title_multiple().format(
                    CURRENT_PAGE=self.list_pos + 1, MAX_PAGE=len(self.list))
            self.chrome_tone = ("warning" if self.type is warning.Warning
                                else None)
        else:
            self.window_title = None
            self.chrome_tone = None
        self.needs_redraw = True

        super(MessageListDialog, self).rebuild()

        # The picture follows the page. A list of events is a list of different
        # situations, so showing one plate for all of them wastes the art; the
        # message knows its own key and the chain covers a theme that has not
        # rendered it.
        self.show_message_art(self.list[0] if len(self.list) == 1
                              else self.list[self.list_pos])

        if (len(self.list) == 1):
            self.title.text = self.type.title_simple()
            self.body.text = self.list[0].full_message
            self.prev_button.visible = False
            self.next_button.visible = False
        else:
            self.title.text = self.type.title_multiple().format(CURRENT_PAGE=self.list_pos + 1, MAX_PAGE=len(self.list))
            self.body.text  = self.list[self.list_pos].full_message
            self.body.color = self.list[self.list_pos].full_message_color
            self.prev_button.visible = True
            self.next_button.visible = True

        # A new page starts at its beginning, even when it is the same page.
        self.body.scroll_lines = 0

    def show_message_art(self, message):
        """Point the pane at the message's own picture."""
        key = getattr(message, "art_key", None) or self.__class__.art_key
        fallbacks = tuple(getattr(message, "art_fallbacks", ()))
        if self.__class__.art_key and self.__class__.art_key not in fallbacks:
            fallbacks = fallbacks + (self.__class__.art_key,)
        self.set_art_key(key, fallbacks=fallbacks)

    def prev_message(self):
        self.list_pos = max(self.list_pos - 1, 0)
        self.needs_rebuild = True

    def next_message(self):
        self.list_pos = min(self.list_pos + 1, len(self.list) - 1)
        self.needs_rebuild = True

    def handle_key(self, event):
        if event.key == pygame.K_LEFT:
            self.prev_message()
        elif event.key == pygame.K_RIGHT:
            self.next_message()
        
    def show(self):
        self.list_pos = 0
        return super(MessageListDialog, self).show()
