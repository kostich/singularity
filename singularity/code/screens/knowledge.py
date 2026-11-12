#file: knowledge.py
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

#This file is used to display the knowledge lists.

import collections

import pygame

from singularity.code import i18n, g
from singularity.code.graphics import (text, button, dialog, widget, constants,
                                       listbox, g as gg)
from singularity.code.logmessage import plate_key


class KnowledgeScreen(dialog.FocusDialog):
    # BACK closed the window and did nothing else, and this screen had no other
    # way out at all -- not even Escape. The close box replaces the button, and
    # the key handler below is what makes the button safe to hide.
    close_only_buttons = ("back_button",)

    # How much of the description pane the picture takes, in the 2030 layout.
    # The plate is 4:1 and the pane is nearly square, so a bit over a quarter
    # of the pane is the strip; the text has the rest.
    ART_STRIP = 0.28

    def __init__(self, *args, **kwargs):
        super(KnowledgeScreen, self).__init__(*args, **kwargs)

        self.knowledge_types = collections.OrderedDict()
        self.knowledge_type_index = collections.defaultdict(int)
        self.cur_knowledge_type = ""
        self.cur_knowledge = None
        self.knowledge_inner_list = ()
        self.knowledge_inner_list_key = ()

        self.knowledge_choice_title = button.HotkeyText(self, (.08, .04), (.42, .05),
                                                        autotranslate=True,
                                                        text=N_("&Sections:"),
                                                        align=constants.LEFT,
                                                        background_color="clear")
        self.knowledge_choice = \
            listbox.UpdateListbox(self, (.08, .09), (.42, .22),
                                  update_func=self.set_knowledge_type)
        self.knowledge_choice_title.hotkey_func = lambda e: self.took_focus(self.knowledge_choice)

        self.knowledge_inner_title = button.HotkeyText(self, (.08, .35), (.42, .05),
                                                       autotranslate=True,
                                                       text=N_("&Entries:"),
                                                       align=constants.LEFT,
                                                       background_color="clear")
        self.knowledge_inner = \
            listbox.UpdateListbox(self, (.08, .40), (.42, .22),
                                  update_func=self.set_knowledge)
        self.knowledge_inner_title.hotkey_func = lambda e: self.took_focus(self.knowledge_inner)

        self.description_pane = \
            widget.BorderedWidget(self, (.54, .04), (.38, .70),
                                  anchor = constants.TOP_LEFT)

        # One widget for every entry, rather than a fresh `Text` per selection:
        # the description is replaced, and a new child each time left the old
        # ones attached -- a leak that also registered one wheel handler per
        # entry once the description learned to scroll.
        self.description_text = \
            text.ScrollableText(self.description_pane, (0, 0), (-1, -1),
                                text="",
                                background_color="knowledge_pane_background",
                                text_size="dialog_text",
                                align=constants.LEFT, valign=constants.TOP,
                                borders=constants.ALL).pad_from_theme()

        # The picture for the entry being read. It lives in the description
        # pane so it moves with that pane; the 2030 layout shows it and the
        # classic layout hides it and gives the text the whole pane back.
        self.description_art = dialog.DialogArtPane(
            self.description_pane, (0, 0), (-1, -self.ART_STRIP),
            anchor=constants.TOP_LEFT,
            art_key="dialog_placeholder",
            crop=True)
        self.description_art.visible = False

        self.back_button = button.ExitDialogButton(self, (.18, .68), (.22, .06),
                                                   autotranslate=True,
                                                   text=N_("&BACK"),
                                                   anchor=constants.TOP_LEFT,
                                                   autohotkey=True)

        self.window_title = N_("KNOWLEDGE")
        self.classic_layout = dialog.ClassicLayout(
            (self.knowledge_choice_title, self.knowledge_choice,
             self.knowledge_inner_title, self.knowledge_inner,
             self.description_pane, self.back_button))
        self.apply_window_layout()
        self.add_key_handler(pygame.K_ESCAPE,
                             self.back_button.activate_with_sound)
        self.took_focus(self.knowledge_choice)

    def apply_window_layout(self):
        """Two lists and a description, inside the window and under its header.

        The shipped layout mixes shares of the screen (the lists) with shares of
        the window (the pane), which is why the pane ran under the BACK button
        and the last rows of the second list sat against the frame. This speaks
        in shares of the window only, and gives the description everything the
        lists do not use.
        """
        if gg.dialog_style("window_layout", "classic") != "2030":
            self.classic_layout.restore()
            self._place_reading(False)
            return

        header = self.header_fraction()
        left, width = -.02, -.46
        self.knowledge_choice_title.anchor = constants.TOP_LEFT
        self.knowledge_choice_title.pos = (left, -(header + .01))
        self.knowledge_choice_title.size = (width, -.06)
        self.knowledge_choice.anchor = constants.TOP_LEFT
        self.knowledge_choice.pos = (left, -(header + .07))
        self.knowledge_choice.size = (width, -.26)

        self.knowledge_inner_title.anchor = constants.TOP_LEFT
        self.knowledge_inner_title.pos = (left, -(header + .34))
        self.knowledge_inner_title.size = (width, -.06)
        self.knowledge_inner.anchor = constants.TOP_LEFT
        self.knowledge_inner.pos = (left, -(header + .40))
        self.knowledge_inner.size = (width, -.34)

        # The description owns the right-hand side, from under the header down
        # to just above the button row.
        bottom = .10
        if self.close_only_buttons and self.has_close_box():
            # The row is gone -- the close box replaced it -- so the pane takes
            # the space back instead of leaving a strip of nothing.
            bottom = .04
        self.description_pane.anchor = constants.TOP_LEFT
        self.description_pane.pos = (-.51, -(header + .01))
        self.description_pane.size = (-.47, -(1 - header - .01 - bottom))

        self.back_button.anchor = constants.BOTTOM_LEFT
        # A BOTTOM anchor still measures its `pos` from the top, so the row's
        # bottom edge is 98% down -- the same expression the dialog buttons use.
        self.back_button.pos = (left, -(1 - .02))
        self.back_button.size = (-.24, -.062)
        self._place_reading(True)

    def _place_reading(self, strip):
        """The picture above the text, or the text alone.

        The classic layout has no picture, and a theme switch has to put the
        text back where it was: the pane's children are not part of
        `classic_layout`, so restoring the pane does not restore them.
        """
        if strip:
            self.description_art.visible = True
            self.description_art.pos = (0, 0)
            self.description_art.size = (-1, -self.ART_STRIP)
            self.description_text.pos = (0, -self.ART_STRIP)
            self.description_text.size = (-1, -(1 - self.ART_STRIP))
        else:
            self.description_art.visible = False
            self.description_text.pos = (0, 0)
            self.description_text.size = (-1, -1)

    def rebuild(self):
        self.apply_window_layout()
        # Update knowledge lists
        self.knowledge_types = collections.OrderedDict()
        self.knowledge_types.update([(_("Techs"), "techs"),
                                     (_("Bases"), "bases"),
                                     (_("Items"), "items")])
        self.knowledge_types.update(
            (knowledge.name, knowledge_id)
            for knowledge_id, knowledge in g.knowledge.items()
        )

        self.knowledge_choice.list = list(self.knowledge_types)
        self.knowledge_choice.needs_rebuild = True

        super(KnowledgeScreen, self).rebuild()

    #fill the right-hand listbox
    def set_inner_list(self, item_type):
        item_type = self.knowledge_types.get(item_type)

        if item_type == "techs":
            items = [[tech.name, tech.id ] for tech in g.pl.techs.values()
                                           if tech.available()]
        elif item_type == "bases":
            items = [[base.name, base.id ] for base in g.base_type.values()
                                           if base.available()]
        elif item_type == "items":
            items = [[item.name, item.id ] for item in g.items.values()
                                           if item.available()]
        elif item_type is not None:
            items = [
                [item.name, id]
                for id, item in g.knowledge[item_type].help_entries.items()
            ]

        else:
            items = []

        items.sort(key=lambda item: i18n.lex_sorting_form(item[0]))

        return_list1 = []
        return_list2 = []
        for name, id in items:
            return_list1.append(id)
            return_list2.append(name)
        return return_list1, return_list2

    # Make sure the left listbox is correct after moving around.
    def set_knowledge_type(self, list_pos):
        if getattr(self, "knowledge_choice", None) is None:
            return  # Not yet initialized.
        prev_know = self.cur_knowledge_type
        if list_pos == -1:
            prev_know = ""
            list_pos = 0
        if 0 <= list_pos < len(self.knowledge_choice.list):
            self.cur_knowledge_type = self.knowledge_choice.list[list_pos]
        if prev_know != self.cur_knowledge_type:
            self.knowledge_type_index[prev_know] = self.knowledge_inner.list_pos
            index = self.knowledge_type_index[self.cur_knowledge_type]
            self.knowledge_inner_list_key, self.knowledge_inner.list = \
                        self.set_inner_list(self.cur_knowledge_type)
            self.knowledge_inner.list_pos = index
            if self.knowledge_inner.list:
                self.set_knowledge(0)
            else:
                # Nothing to read in this section. The previous entry's text
                # and picture must not stay up under an empty list.
                self.cur_knowledge = None
                self.description_text.text = ""
                self._show_art("dialog_placeholder")

    # Make sure the right-hand listbox is correct.
    def set_knowledge(self, list_pos):
        if getattr(self, "knowledge_inner", None) is None:
            return  # Not yet initialized.
        prev_know = self.cur_knowledge
        if 0 <= list_pos < len(self.knowledge_inner.list):
            self.cur_knowledge = self.knowledge_inner.list[list_pos]
        if prev_know != self.cur_knowledge:
            self.show_info(self.cur_knowledge_type,
                    self.knowledge_inner_list_key[list_pos])

    #print information to the right.
    def show_info(self, knowledge_type, knowledge_key):
        knowledge_type = self.knowledge_types.get(knowledge_type)
        desc_text = ""

        if knowledge_type == "techs":
            desc_text = g.pl.techs[knowledge_key].name + "\n\n"

            # Cost
            desc_text += _("Research Cost:")+"\n"
            desc_text += self._desc_cost(g.pl.techs[knowledge_key].total_cost)  # Research cost
            desc_text += "\n"

            danger_level = g.pl.techs[knowledge_key].danger
            desc_text += g.dangers[danger_level].knowledge_desc

            if g.pl.techs[knowledge_key].done:
                desc_text += " " + _("Research complete.")

            desc_text += "\n\n"+g.techs[knowledge_key].description

            if g.pl.techs[knowledge_key].done:
                desc_text += "\n\n"+g.techs[knowledge_key].result

        elif knowledge_type == "bases":
            base = g.base_type[knowledge_key]

            desc_text = base.name + "\n\n"
            desc_text += _("Building Cost:")+"\n"
            desc_text += self._desc_cost(base.cost) #Building cost
            desc_text += "\n"
            desc_text += _("Maintenance Cost:")+"\n"
            desc_text += self._desc_maint(base.maintenance) #Maintenance cost
            desc_text += "\n"
            if base.size > 1:
                desc_text +=  _("Size: %d") % base.size + "\n"

            desc_text += base.get_detect_info()

            desc_text += "\n" + base.description

        elif knowledge_type == "items":
            item = g.items[knowledge_key]

            desc_text = item.name + "\n\n"
            desc_text += _("Building Cost:")+"\n"
            desc_text += self._desc_cost(item.cost)  # Building cost
            desc_text += "\n"
            desc_text += g.items[knowledge_key].get_quality_info()
            desc_text += "\n" + item.description

        elif knowledge_type is not None:
            help_entry = g.knowledge[knowledge_type].help_entries[knowledge_key]
            desc_text = help_entry.name + "\n\n" + help_entry.description

        self.description_text.text = desc_text
        self._show_art(self._art_for(knowledge_type, knowledge_key))

    def _art_for(self, knowledge_type, knowledge_key):
        """The plate for the entry being read.

        Techs, bases and items already have plates. A concept entry's plate is
        named from its data id, the same way, so a translation cannot change
        which picture is shown.
        """
        if knowledge_type == "techs":
            return plate_key("dialog_tech_", knowledge_key)
        if knowledge_type == "bases":
            return plate_key("dialog_base_", knowledge_key)
        if knowledge_type == "items":
            return plate_key("dialog_item_", knowledge_key)
        if knowledge_type is not None and knowledge_key:
            return plate_key("dialog_knowledge_", knowledge_key)
        return "dialog_placeholder"

    def _show_art(self, key):
        pane = self.description_art
        pane.art_key = key
        pane.reset_glitch()
        pane._scaled = None
        pane.needs_redraw = True

    def _desc_maint(self, maintenance):
        maint = maintenance[:]
        # describe_cost() expects CPU-seconds, not CPU-days
        maint[1] *= g.seconds_per_day
        return self._desc_cost(maint)

    def _desc_cost(self, cost):
        desc_text = _("%s Money") % g.to_money(cost[0])
        if cost[1] > 0:
            desc_text += ", "
            desc_text += _("%s CPU") % g.to_cpu(cost[1])
        if cost[2] > 0:
            desc_text += ", "
            desc_text += g.to_time(cost[2])

        return desc_text

    def show(self):
        self.set_knowledge_type(-1)
        self.knowledge_choice.list_pos = 0
        self.knowledge_inner.list_pos = 0
        return super(KnowledgeScreen, self).show()
