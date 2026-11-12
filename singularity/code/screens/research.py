#file: research_screen.py
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

#This file contains the global research screen.

from numpy import array, int64
import pygame

from singularity.code import i18n, g, task
from singularity.code.graphics import (dialog, button, slider, text, constants,
                                       listbox, g as gg)
from singularity.code.logmessage import plate_key


class ResearchScreen(dialog.ChoiceDescriptionDialog):
    # The picture across the top of the description, as a share of that pane.
    # The same strip the knowledge screen uses.
    ART_STRIP = 0.28
    # BACK closed the window and did nothing else, so the window's own close
    # box replaces it. The button stays as this screen's Escape path.
    close_only_buttons = ("no_button",)
    # A single BACK, at the bottom centre: this screen's row is its own.
    owns_button_row = True

    def __init__(self, parent, pos=(.5, .1), size=(.93, .63), *args, **kwargs):
        self.dirty_count = True
        super(ResearchScreen, self).__init__(parent, pos, size, *args, **kwargs)
        self.window_title = N_("RESEARCH")
        self.listbox.parent = None
        self.listbox = listbox.CustomListbox(self, (0, self.below_header(0)),
                                             (.53, .55),
                                             list_item_height=0.06,
                                             remake_func=self.make_item,
                                             rebuild_func=self.update_item,
                                             update_func=self.handle_update)
        self.description_pane.size = (.39, .55)

        self.desc_func = self.on_select

        self.help_dialog = dialog.MessageDialog(self)

        self.yes_button.parent = None
        self.no_button.pos = (-.5,-.99)
        self.no_button.anchor = constants.BOTTOM_CENTER

        self.add_handler(constants.KEY, self._got_key, priority=5)

    def _got_key(self, event):
        # If a valid slider is selected, we let it move first.
        if 0 <= self.listbox.list_pos < len(self.listbox.list):
            index = self.listbox.list_pos - self.listbox.scrollbar.scroll_pos
            canvas = self.listbox.display_elements[index]
            # Raises Handled for us if the key was relevant to the slider
            canvas.slider.handle_key(event)

        # Let the list box get the rest of the keys if it wants them
        self.listbox.got_key(event, require_focus=False)

    def on_select(self, description_pane, key):
        if key in g.pl.techs:
            description = g.pl.techs[key].get_info()
        elif key == "cpu_pool":
            template = "%s\n---\n%s"
            cpu_pool = task.get_current("cpu_pool")
            description = template % (cpu_pool.name, cpu_pool.description)
        elif key == "jobs":
            job = task.get_current("jobs")
            profit = job.get_profit()
            template = "%s\n" + ngettext("%s money per CPU per day.", "%s money per CPU per day.", profit) + "\n---\n%s"
            description = template % (job.name, profit, job.description)
        else:
            description = ""

        # A tech's description is prose with no length limit, and this pane is
        # a fixed part of the screen: it scrolls rather than shrinking its type
        # to an unreadable size or drawing over its own border.
        # In 2030 the entry's plate sits across the top and the text starts
        # under it. The pane's children are thrown away on every selection, so
        # the strip is built here rather than once.
        if gg.dialog_style("window_layout", "classic") == "2030":
            dialog.DialogArtPane(
                self.description_pane, (0, 0), (-1, -self.ART_STRIP),
                anchor=constants.TOP_LEFT,
                art_key=self._art_for(key),
                crop=True)
            text_pos = (0, -self.ART_STRIP)
            text_size = (-1, -(1 - self.ART_STRIP))
        else:
            text_pos = (0, 0)
            text_size = (-1, -1)
        text.ScrollableText(self.description_pane, text_pos, text_size,
                  text=description,
                  background_color="research_pane_background",
                  text_size="dialog_text",
                  align=constants.LEFT, valign=constants.TOP,
                  borders=constants.ALL).pad_from_theme()

    def _art_for(self, key):
        """The plate for the research row being read.

        A tech already has one. CPU Pool and Jobs are the two tasks, and the
        concept plates already show a processor rack and a night office, so
        they are reused rather than rendered a second time.
        """
        if key in g.pl.techs:
            return plate_key("dialog_tech_", key)
        if key == "cpu_pool":
            return "dialog_knowledge_processors"
        if key == "jobs":
            return "dialog_knowledge_jobs"
        return "dialog_placeholder"

    def make_item(self, canvas):
        # Dirty, underhanded trick to make the canvas into a progress bar.
        canvas.__class__ = text.ProgressText
        canvas.progress = 0
        canvas.progress_color = "progress_background_progress"

        canvas.research_name = text.Text(canvas, (-.01, -.01), (-.70, -.5),
                                         align=constants.LEFT,
                                         background_color="clear")
        canvas.research_name.visible = False
        canvas.alloc_cpus = text.Text(canvas, (-.99, -.01), (-.21, -.5),
                                      anchor=constants.TOP_RIGHT,
                                      text="1,000,000,000",
                                      align=constants.RIGHT,
                                      background_color="clear")
        canvas.alloc_cpus.visible = False
        canvas.slider = slider.UpdateSlider(canvas, (-.01, -.55), (-.98, -.40),
                                            anchor=constants.TOP_LEFT,
                                            horizontal=True, priority=150)
        canvas.slider.visible = False

        canvas.help_button = button.FunctionButton(canvas, (-.11, -.55),
                                                   (0, -.40), text=" ??? ",
                                                   text_shrink_factor=1,
                                                   base_font="normal",
                                                   function=self.show_help)
        self.style_help_button(canvas.help_button)

    # (role, text size, shrink factor) for the ??? box, per layout.
    HELP_STYLE_2030 = ("chrome", "dialog_text", .75)
    HELP_STYLE_CLASSIC = ("standard", "button", 1)

    def style_help_button(self, help_button):
        """Fit the ??? box to the row it lives in.

        It is a standard button, so the theme's one button height applies to it:
        40px, in the lower half of a 46px row. The box spilled out of its own
        row and the label was clipped by the surface it was drawn on -- "a
        button I can't fully see". In 2030 it takes the row's own height and a
        type size that fits that height.

        Set once per layout rather than on every rebuild, because `text_size` is
        a reconfig property and assigning it re-measures the widget.
        """
        if gg.dialog_style("window_layout", "classic") == "2030":
            style = self.HELP_STYLE_2030
        else:
            style = self.HELP_STYLE_CLASSIC
        if getattr(help_button, "_help_style", None) == style:
            return
        help_button._help_style = style
        help_button.role, help_button.text_size, help_button.shrink_factor = style
        help_button.needs_resize = True

    def cpu_for(self, key):
        return g.pl.get_allocated_cpu_for(key, 0)

    def update_item(self, canvas, name, key=None):
        visible = (key is not None)
        canvas.research_name.visible = visible
        canvas.alloc_cpus.visible = visible
        canvas.slider.visible = visible

        self.style_help_button(canvas.help_button)
        canvas.help_button.visible = False
        canvas.progress = 0

        if not visible:
            return

        danger = task.danger_for(key)
        if danger > 0 and g.pl.available_cpus[danger] == 0:
            canvas.help_button.visible = True
            canvas.help_button.args = (danger,)

        if key in g.pl.techs:
            canvas.progress = g.pl.techs[key].percent_complete().min()

        def my_slide(new_pos):
            self.handle_slide(key, new_pos)
            self.needs_rebuild = True
        canvas.slider.update_func = my_slide

        canvas.research_name.text = name

        if self.dirty_count:
            self.cpu_left = self.calc_cpu_left()
            self.dirty_count = False

        cpu = self.cpu_for(key)
        cpu_left = self.cpu_left[danger]
        total_cpu = cpu + cpu_left
        canvas.slider.slider_pos = cpu
        canvas.slider.slider_max = total_cpu
        canvas.slider.slider_size = ss = g.pl.available_cpus[0] // 10 + 1
        full_size = -.98
        if total_cpu:
            size_fraction = (total_cpu + ss) / float(g.pl.available_cpus[0] + ss)
        else:
            # If people put all their bases to sleep, then total_cpu (and
            # g.pl.available_cpus[0]) are both 0.  This causes size_fraction
            # to become 1 and the slider will then take the entire width of
            # the research screen.  However, that looks odd - especially with
            # a help button, so we special case this here to ensure it looks
            # reasonable.
            size_fraction = .10
        canvas.slider.size = (full_size * size_fraction, -.4)
        canvas.alloc_cpus.text = g.add_commas(cpu)

    def calc_cpu_left(self):
        cpu_count = array(g.pl.available_cpus, int64)
        for task_id, cpu in g.pl.get_cpu_allocations():
            danger = task.danger_for(task_id)
            cpu_count[:danger+1] -= cpu

        for i in range(1, 4):
            cpu_count[i] = min(cpu_count[i-1:i+1])

        return [int(c) for c in cpu_count]

    def handle_slide(self, key, new_pos):
        g.pl.set_allocated_cpu_for(key, new_pos)
        self.dirty_count = True
        self.needs_rebuild = True
        self.parent.needs_rebuild = True

    def show_help(self, danger_level):
        self.help_dialog.text = _("This technology is too dangerous to research on any of the computers I have. {TEXT}").format(
                                  TEXT=g.dangers[danger_level].research_desc)
        # The dialog says *why* the tech cannot be studied here, and each why is
        # its own place -- undersea, orbit, deep space, outside the universe --
        # so each names its own plate. `dialog_danger` is the generic hazard
        # door for a theme that has not rendered a level yet.
        self.help_dialog.set_art_key(
            plate_key("dialog_", g.dangers[danger_level].id),
            fallbacks=("dialog_danger", "dialog_message"))
        dialog.call_dialog(self.help_dialog, self)

    def show(self):
        techs = [tech for tech in g.pl.techs.values() if tech.available()
                                                      and not tech.done]
        techs.sort(key=lambda tech: i18n.lex_sorting_form(tech.spec.name))
        self.list = [_("CPU Pool"), task.get_current("jobs").name] + \
                    [_("Research %s") % tech.name for tech in techs]
        self.key_list = ["cpu_pool", "jobs"] + [tech.id for tech in techs]
        self.listbox.key_list = self.key_list

        self.dirty_count = True
        return super(ResearchScreen, self).show()
