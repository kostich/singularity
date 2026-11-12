#file: location.py
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

#This file is used to display the log of player action

from singularity.code import g, logmessage
from singularity.code.graphics import dialog, constants, text, button, listbox
# The graphics globals, which is where the theme's values live -- `g` above is
# the game's, and it has no dialog_style().
from singularity.code.graphics import g as gg


filtered_log_class = set()


class LogScreen(dialog.ChoiceDialog):
    # BACK closed the window and did nothing else; the close box replaces it.
    close_only_buttons = ("no_button",)
    # A single BACK, at the bottom centre: this screen's row is its own.
    owns_button_row = True

    def __init__(self, parent, pos=(.5, .5), size=(.73, .63), *args, **kwargs):
        super(LogScreen, self).__init__(parent, pos, size, *args, **kwargs)
        self.window_title = N_("LOG")
        self.key_list = []
        self.anchor = constants.MID_CENTER

        self.yes_button.parent = None
        self.no_button.pos = (-.5,-.99)
        self.no_button.icon = "icon_back"
        self.no_button.anchor = constants.BOTTOM_CENTER

        self.filter_log_dialog = FilterLogDialog(self)

        self.filter_log = button.FunctionButton(self,
                                                (-1.0, self.below_header(0.)),
                                                (-.18, -.08),
                                                autotranslate=True,
                                                icon="icon_filter",
                                                text=N_("Filters"),
                                                anchor=constants.TOP_RIGHT,
                                                function=self.show_filters)

        # Sits on the filter's row, in the space to its left. 2030 only: a
        # legacy log has no such line, and the row is just the Filters button.
        self.hint = text.Text(self, (0, self.below_header(0.)),
                              (-.80, -.08),
                              autotranslate=True,
                              text=N_("Double-click an entry to read it"),
                              color="text_disabled",
                              align=constants.LEFT,
                              valign=constants.MID,
                              background_color="clear")
        self.hint.visible = False

        # Shown when there is nothing to list. A blank panel reads as a screen
        # that failed to load; a word in the middle of it reads as "nothing has
        # happened yet", which is the truth.
        self.empty_text = text.Text(self, (0, self.below_header(-.09)),
                                    (-1, self.less_header(-.77)),
                                    text=_("Empty"),
                                    color="text_disabled",
                                    align=constants.CENTER,
                                    valign=constants.MID,
                                    background_color="clear")
        self.empty_text.visible = False

    def make_listbox(self):
        # No picture here, on purpose: the log is a list of things that already
        # happened, not a scene, so it has no art key and ChoiceDialog's
        # art_key = None stands. The numbers below are the ones this screen has
        # always used.
        return LogListbox(self, (0, self.below_header(-.09)),
                          (-1, self.less_header(-.77)),
                          list_item_height=0.04, list_item_shrink=1,
                          anchor=constants.TOP_LEFT, align=constants.LEFT,
                          on_double_click_on_item=self.handle_double_click,
                          item_borders=False, item_selectable=True)

    def handle_double_click(self, event):
        if self.listbox.is_over(event.pos) and 0 <= self.listbox.list_pos < len(self.key_list):
            message = self.key_list[self.listbox.list_pos]
            # use the MapScreen (our parent) as parent for the dialog to match
            # how it is originally shown (plus to avoid "cannot fit" warnings
            # when the dialog is larger than the log screen)
            #
            # The list itself has no picture -- it is a list of things that
            # already happened, not a scene -- but the *entry* does, and this is
            # the dialog that shows it. A message with no key of its own passes
            # None and keeps its pane off, exactly as before.
            message_dialog = dialog.MessageDialog(
                self.parent, text_size="dialog_text")
            message_dialog.set_art_key(message.art_key,
                                       fallbacks=message.art_fallbacks)
            message_dialog.text = message.full_message
            message_dialog.color = message.full_message_color

            # Because we need to use the MapScreen as parent, we need to juggle
            # things manually (as call_dialog works with a different assumption
            # than we need).
            try:
                self.visible = False
                dialog.call_dialog(message_dialog, self.parent)
            finally:
                self.visible = True
                self.needs_rebuild = True
                self.parent.needs_rebuild = True
                self.parent.lost_focus()
                self.regained_focus()

    def rebuild(self):
        self.key_list = [message for message in g.pl.log if not type(message) in filtered_log_class]
        self.list = [self.render_log_message(message) for message in self.key_list]
        self.default = len(self.list) - 1

        self.filter_log_dialog.needs_rebuild = True
        # Before the list rebuilds: the 2030 rows read the messages, not the
        # joined string.
        self.listbox.entries = self.key_list

        super(LogScreen, self).rebuild()

        shows_empty_state = (gg.dialog_style("empty_state", "none") == "label"
                             and not self.list)
        self.empty_text.text = _("Empty") if shows_empty_state else ""
        self.empty_text.visible = shows_empty_state
        self.hint.visible = (gg.dialog_style("window_layout", "classic")
                             == "2030")


    def show(self):
        self.listbox.has_focus = True
        return super(LogScreen, self).show()

    def show_filters(self):
        dialog.call_dialog(self.filter_log_dialog, self)
        self.needs_rebuild = True

    def render_log_message(self, message):
        log_emit_time = message.log_emit_time
        log_message = message.log_line
        return "%s -- %s" % (_("DAY") + " %04d, %02d:%02d:%02d" % log_emit_time, log_message)

class LogListbox(listbox.Listbox):
    """The log's list: alternating rows and an inset, if the theme asks.

    A log is a wall of short lines in one colour, and the eye loses which
    timestamp belongs to which sentence. This lives in the listbox rather than
    in the screen because a resize recreates every row: styling them once from
    `rebuild()` was thrown away the moment the listbox made its own elements.

    In 2030 a row is the time and the message side by side, at one type size,
    and it grows to the message's wrapped height. The `" -- "` string stays
    the legacy row.
    """

    def _uses_rows(self):
        return gg.dialog_style("window_layout", "classic") == "2030"

    def _row_font(self):
        size = text.convert_font_size(gg.resolve_text_size("dialog_text"))
        return gg.fonts["normal"][size]

    def _stamp(self, message):
        return _("DAY") + " %04d, %02d:%02d:%02d" % message.log_emit_time

    def _row_heights(self, width):
        """Pixel height of every entry, at the dialog type size, wrapped."""
        font = self._row_font()
        line = font.get_linesize()
        stamp = font.size(_("DAY") + " 8888, 88:88:88")[0] + 16
        message_width = max(40, width - stamp - 12)
        heights = []
        for message in getattr(self, "entries", ()) or ():
            lines = text.split_wrap(message.log_line or "", font, message_width)
            heights.append(max(line, len(lines) * line) + 8)
        return heights, stamp

    def make_element(self):
        if not self._uses_rows():
            return super(LogListbox, self).make_element()
        borders = (constants.LEFT,)
        row = text.SelectableText(self, None, None, anchor=constants.TOP_LEFT,
                                  borders=borders,
                                  shrink_factor=1,
                                  border_color=self.border_color,
                                  selected_color=self.selected_color,
                                  unselected_color=self.unselected_color,
                                  align=constants.LEFT)
        row.time_label = text.Text(row, (0, 0), (-.34, -1),
                                   align=constants.LEFT, valign=constants.MID,
                                   background_color="clear",
                                   color="text_disabled",
                                   text_size="dialog_text", shrink_factor=1,
                                   wrap=False)
        row.message_label = text.Text(row, (-.34, 0), (-.66, -1),
                                      align=constants.LEFT, valign=constants.TOP,
                                      background_color="clear", color="text",
                                      text_size="dialog_text", shrink_factor=1)
        return row

    def _fill_row(self, element, list_index, stamp_width, width):
        if not 0 <= list_index < len(getattr(self, "entries", ()) or ()):
            element.time_label.text = ""
            element.message_label.text = ""
            element.text = None
            return
        message = self.entries[list_index]
        # None, not "": an empty string is still text, and the row would then
        # shrink to it instead of keeping the height it was given.
        element.text = None
        element.time_label.text = self._stamp(message)
        element.message_label.text = message.log_line
        if width > 0:
            share = min(0.7, max(0.2, stamp_width / float(width)))
            element.time_label.pos = (0, 0)
            element.time_label.size = (-share, -1)
            element.message_label.pos = (-share, 0)
            element.message_label.size = (-(1 - share), -1)

    def _fit_count(self, start, heights, viewport):
        y = 0
        count = 0
        for height in heights[start:]:
            if count and y + height > viewport:
                break
            y += height
            count += 1
        return max(1, count) if heights else 1

    def find_item_under_mouse(self, event):
        if not getattr(self, "_row_mode", False):
            return super(LogListbox, self).find_item_under_mouse(event)
        local = event.pos[1] - self.collision_rect[1]
        for index, element in enumerate(self.display_elements):
            if not element.visible:
                continue
            top = element.real_pos[1]
            if top <= local < top + element.real_size[1]:
                return index
        return -1

    def _rebuild_rows(self):
        viewport = self.real_size[1]
        scrollbar_width = self.scrollbar.real_size[0]
        width = max(1, self.real_size[0] - scrollbar_width)
        heights, stamp = self._row_heights(width)
        self.remake_elements()

        self.scrollbar.elements = max(1, len(self.list))
        self.scrollbar.window = self._fit_count(
            self.scrollbar.scroll_pos, heights, viewport)
        if self.auto_scroll:
            self.auto_scroll = False
            self.scrollbar.center(self.list_pos)
        self.scrollbar.rebuild()

        scroll = self.scrollbar.scroll_pos
        rel_width = scrollbar_width / float(self.real_size[0] or 1)
        y = 0
        visible = 0
        for index, element in enumerate(self.display_elements):
            list_index = scroll + index
            if (list_index >= len(heights)
                    or (visible and y + heights[list_index] > viewport)):
                element.visible = False
                continue
            height = heights[list_index]
            element.visible = True
            element.pos = (0, 0 if viewport == 0 else -(y / float(viewport)))
            element.size = (-1 + rel_width,
                            -(height / float(viewport)) if viewport else -1)
            element.selected = (list_index == self.list_pos)
            self._fill_row(element, list_index, stamp, width)
            self.style_element(list_index, element)
            y += height
            visible += 1

        self.scrollbar.window = max(1, visible)
        self.scrollbar.rebuild()
        self.needs_redraw = True
        super(listbox.Listbox, self).rebuild()

    def rebuild(self):
        mode = self._uses_rows()
        if getattr(self, "_row_mode", None) != mode:
            for child in list(self.display_elements):
                child.parent = None
            self.display_elements = []
            self._row_mode = mode
        if not mode:
            super(LogListbox, self).rebuild()
            self.restyle()
            return
        self.list_pos = self.safe_pos(self.list_pos)
        if self.needs_resize:
            self.resize()
            return
        self._rebuild_rows()

    def style_element(self, index, element):
        if gg.dialog_style("list_stripes", "none") != "zebra":
            return
        padding = gg.dialog_style("content_padding", 0.0)
        element.unselected_color = ("text_background_unselected"
                                    if index % 2 == 0
                                    else "list_row_alternate")
        element.text_padding = (padding, 0.0, padding, 0.0)

    def restyle(self):
        for index, element in enumerate(self.display_elements):
            self.style_element(index, element)


class FilterLogDialog(dialog.MessageDialog):
    # A filter panel is a setting, not a scene: it takes no picture, so the
    # theme's image slot leaves it alone.
    art_key = None

    def __init__(self, parent, *args, **kwargs):
        kwargs["ok_type"] = N_("&BACK")
        super(FilterLogDialog, self).__init__(parent, *args, **kwargs)
        self.window_title = N_("FILTERS")

        self.log_class_labels = {}
        self.log_class_toggles = {}

        # The header band takes the top of the window, so the rows start below
        # it and the panel grows by the same amount -- this dialog is sized
        # from its own last row, so the two have to be decided together.
        top = .03 if gg.dialog_style("header", "none") == "bar" else .01
        for i, (log_type, log_class) in enumerate(logmessage.SAVEABLE_LOG_MESSAGES.items()):
            y = top + i * .06

            self.log_class_labels[log_type] = text.Text(self, (-.01, y), (-.70, .05),
                                                        align = constants.LEFT,
                                                        background_color="clear")
            self.log_class_toggles[log_type] = FilterButton(self, (-.71, y), (-.28, .05),
                                                            autotranslate=True,
                                                            autohotkey=False,
                                                            on_text=N_('SHOW'),
                                                            off_text=N_('HIDE'),
                                                            text_shrink_factor=.75,
                                                            force_underline=-1,
                                                            function=self.toggle_log_class,
                                                            args=(button.TOGGLE_VALUE, log_class))

        self.pos = (-.50, 0)
        self.size = (-.50, (y + .07) / .9)
        self.anchor = constants.TOP_LEFT

    def rebuild(self):
        for log_type, log_class in logmessage.SAVEABLE_LOG_MESSAGES.items():
            self.log_class_labels[log_type].text = log_class.log_name()
            self.log_class_toggles[log_type].active = log_class not in filtered_log_class

        super(FilterLogDialog, self).rebuild()

    def toggle_log_class(self, value, log_class):
        if value:
            filtered_log_class.remove(log_class)
        else:
            filtered_log_class.add(log_class)


class FilterButton(button.StickyOnOffButton, button.FunctionButton):
    pass
