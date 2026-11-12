#file: listbox.py
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

#This file contains the listbox widget.

import math
import time

import pygame

from singularity.code.graphics import g, constants, widget, text, scrollbar


# The only mouse button that chooses a row. Buttons 4-7 are the wheel axes on
# X11, and some mice and drivers add more; none of them is a click.
PRIMARY_BUTTON = 1


class Listbox(widget.FocusWidget, text.SelectableText):
    list = widget.causes_rebuild("_list")
    align = widget.causes_redraw("_align")
    list_size = widget.causes_rebuild("_list_size")
    list_pos = widget.causes_rebuild("_list_pos")
    list_item_shrink = widget.causes_rebuild("_list_item_shrink")

    # How soon after a click on a row a second click on the *same* row counts as
    # a double-click on it. How far apart the two land is deliberately not part
    # of the test.
    #
    # `Dialog.handle()` decides a double-click by comparing the time and the
    # position of two releases, and it wants them within ten pixels of each
    # other in total. Ten pixels is nothing when the target is a row hundreds of
    # pixels wide: six pixels right and six down -- an ordinary hand on a
    # trackpad -- is a taxicab distance of twelve and the pair is dropped, so
    # double-clicking a base does nothing at all. The row that was hit is what
    # the player aimed at, and the list is the only thing that knows which row a
    # position means.
    #
    # 0.6 and not the dialog's 0.5, because a dialog's loop sleeps 1/FPS for
    # every MOUSEMOTION it handles -- it is compressing them -- so a moving hand
    # spends part of the interval before the player's own second click is even
    # counted.
    DOUBLE_CLICK_SECONDS = .6

    def __init__(self, parent, pos, size, anchor=constants.TOP_LEFT, list=None,
                 list_pos=0, list_item_height=0.03, list_item_shrink=1, borders=constants.ALL,
                 item_borders=True, item_selectable=True,
                 align=constants.CENTER, on_double_click_on_item=None, **kwargs):
        super(Listbox, self).__init__(parent, pos, size, anchor = anchor,
                                      **kwargs)

        self.display_elements = []
        self.borders = borders

        self.item_borders = item_borders
        self.item_selectable = item_selectable

        self.item_borders = item_borders
        self.align = align
        self.list_item_height = list_item_height
        self.list_item_shrink = list_item_shrink
        self.list_pos = list_pos
        self.list = list or []

        self.auto_scroll = True

        self.on_double_click_on_item = on_double_click_on_item

        # Wheel movement that has not yet added up to a whole row.
        self._wheel_remainder = 0.0

        # The row and the time of the last click that landed on one, for
        # deciding a double-click. See repeats_a_click().
        self._last_row_click = None

        self.scrollbar = scrollbar.UpdateScrollbar(self,
                                                   update_func = self.on_scroll)

    def add_hooks(self):
        super(Listbox, self).add_hooks()
        if self.parent is not None:
            self.parent.add_handler(constants.CLICK, self.on_click, 90)
            self.parent.add_handler(constants.MOUSEWHEEL, self.on_mousewheel, 200)
            self.parent.add_key_handler(pygame.K_UP, self.got_key)
            self.parent.add_key_handler(pygame.K_DOWN, self.got_key)
            self.parent.add_key_handler(pygame.K_PAGEUP, self.got_key)
            self.parent.add_key_handler(pygame.K_PAGEDOWN, self.got_key)

    def remove_hooks(self):
        super(Listbox, self).remove_hooks()
        if self.parent is not None:
            self.parent.remove_handler(constants.CLICK, self.on_click)
            self.parent.remove_handler(constants.MOUSEWHEEL, self.on_mousewheel)
            self.parent.remove_key_handler(pygame.K_UP, self.got_key)
            self.parent.remove_key_handler(pygame.K_DOWN, self.got_key)
            self.parent.remove_key_handler(pygame.K_PAGEUP, self.got_key)
            self.parent.remove_key_handler(pygame.K_PAGEDOWN, self.got_key)

    def on_scroll(self, scroll_pos):
        self.needs_rebuild = True

    def on_click(self, event):
        # A row is chosen by a click on it, and by nothing else. Anything that
        # merely carries a position -- a wheel notch, a tilt, or the button
        # event some drivers report alongside one -- may only scroll the view
        # (see on_mousewheel). Without this guard, scrolling with the pointer
        # resting over the list selected whichever row was under it, and the
        # report is exactly that: "the option changes only if I scroll while
        # the cursor is within the list". On the Options screen list_pos is not
        # a cursor position at all, it is the setting, so selecting a row
        # reapplies a resolution and resizes the real window.
        if getattr(event, "button", None) != PRIMARY_BUTTON:
            return

        if self.collision_rect.collidepoint(event.pos):
            self.has_focus = True
            self.took_focus(self)

            if (self.item_selectable):
                # Figure out which element was clicked...
                index = self.find_item_under_mouse(event)
                # ... and select it.
                self.list_pos = self.safe_pos(index + self.scrollbar.scroll_pos)
                # ... and, if this is the second click on that same row, open
                # it. The time is compared here rather than by the dialog
                # because only the list knows which row a position means.
                if self.repeats_a_click(index):
                    self.on_double_click(event)

    def repeats_a_click(self, index):
        """Whether this click completes a double-click on the row it hit.

        Called from `on_click()`, so the click has already been mapped to a row:
        two clicks on one row are a double-click on that row however far apart
        they land, and two clicks on different rows never are. Both are what a
        player means by double-clicking an item.

        A click past the last row is not aimed at a row at all. It still selects
        the first one, which is the behaviour it has always had, but it must not
        pair up with another such click and open something nobody clicked.
        """
        now = time.time()
        previous = self._last_row_click
        self._last_row_click = (self.list_pos, now) if index > -1 else None

        if index < 0 or previous is None:
            return False
        if previous[0] != self.list_pos:
            return False
        if now - previous[1] > self.DOUBLE_CLICK_SECONDS:
            return False

        # Consumed: a third click starts a new pair.
        self._last_row_click = None
        return True

    def on_double_click(self, event):
        if self.on_double_click_on_item is None:
            return
        # Same rule as on_click(): a double-click is two clicks of the same
        # button, so a wheel button that repeats must not count as one. The
        # list only ever calls this for a primary click -- `repeats_a_click()`
        # decides the pair -- but the method is the widget's own answer to "a
        # double-click landed on me", so it keeps its own guard.
        if getattr(event, "button", None) != PRIMARY_BUTTON:
            return
        if self.collision_rect.collidepoint(event.pos) and self.item_selectable:
            index = self.find_item_under_mouse(event)
            if index > -1:
                self.on_double_click_on_item(event)

    def current_item(self):
        if 0 <= self.list_pos < len(self.list):
            return self.list[self.list_pos]
        return None

    def find_item_under_mouse(self, event):
        local_vert_abs = event.pos[1] - self.collision_rect[1]
        local_vert_pos = local_vert_abs / float(self.collision_rect.height)
        index = int(local_vert_pos * len(self.display_elements))
        if 0 <= index < len(self.list):
            return index
        return -1

    def safe_pos(self, raw_pos):
        return max(0, min(len(self.list) - 1, raw_pos))

    def on_mousewheel(self, event):
        """Scroll the view by the wheel's own delta, never the selection.

        A wheel is not a page key. This used to read only the *sign* of the
        event and move a whole window (window - 1 items) per event, through
        _scroll_to_and_raise_event_handled(), which sets list_pos -- and on a
        list wired up with UpdateListbox that is not a cursor move at all: it
        is the setting. Selecting a resolution calls gg.set_screen_size() and
        then apply_display_request(), which resizes the real window.

        A free-spinning wheel sends tens of events per flick, so one gesture
        reallocated the window dozens of times while the list "kept scrolling
        over and over". Modern wheels and touchpads also report a fraction of a
        row per event in precise_y, which the sign test threw away.

        So the view moves and the selection does not: list_pos changes only
        when the player clicks a row or presses a key, which is also what makes
        the resolution list safe to scroll past.
        """
        precise = getattr(event, "precise_y", None)
        delta = precise if precise else float(event.y)

        if not delta:
            # A horizontal-only gesture, or a wheel that reports nothing.
            return

        if event.flipped:
            delta = -delta

        # Accumulate the fraction, so a slow gesture moves the list once it has
        # travelled a whole row instead of once per event.
        self._wheel_remainder += delta
        rows = int(self._wheel_remainder)
        if not rows:
            return
        self._wheel_remainder -= rows

        # One event may not cross the whole list, whatever the wheel claims.
        window = max(1, self.scrollbar.window)
        rows = max(-window, min(window, rows))

        # Wheel up (positive y) goes towards the first row. This is the
        # direction the game has always used, kept so nothing feels inverted.
        direction = -1 if rows > 0 else 1
        new_pos = self.scrollbar.scroll_pos + direction * abs(rows)
        # The scrollbar owns the range; the bound lives on its slider, and
        # Scrollbar.rebuild() clamps scroll_pos to it as well.
        self.scrollbar.scroll_pos = max(0, min(new_pos,
                                               self.scrollbar.slider.slider_max))

        # The rows are laid out from scroll_pos in rebuild(); the scrollbar
        # owns the clamping above, and this asks the listbox to redraw.
        self.needs_rebuild = True

    def got_key(self, event, require_focus=True):
        if not self.item_selectable:
            return
        if require_focus and not self.has_focus:
            return

        if event.key == pygame.K_UP:
            new_pos = self.list_pos - 1
        elif event.key == pygame.K_DOWN:
            new_pos = self.list_pos + 1
        elif event.key == pygame.K_PAGEUP:
            new_pos = self.list_pos - (self.scrollbar.window - 1)
        elif event.key == pygame.K_PAGEDOWN:
            new_pos = self.list_pos + (self.scrollbar.window - 1)
        else:
            return

        self._scroll_to_and_raise_event_handled(new_pos)

    def _scroll_to_and_raise_event_handled(self, new_pos):
        self.list_pos = self.safe_pos(new_pos)
        self.scrollbar.scroll_to(self.list_pos)
        raise constants.Handled

    def num_elements(self):
        # TODO: If needed, add a paramater to display a fixed number of element.
        
        rect = self._make_collision_rect()
        
        list_item_height = self.list_item_height
        
        # Calculate the min height of one element. 
        if list_item_height > 0:
            min_height = list_item_height * g.real_screen_size[1]
        else:
            min_height = -list_item_height * rect.height
        
        # Display a number calculate by the size of one item.
        list_size = max(1, rect.height // min_height)

        return int(math.ceil(list_size))

    def remake_elements(self):
        list_size = self.num_elements()
        current_size = len(self.display_elements)

        if current_size > list_size:
            # Remove the excess ones.
            for child in self.display_elements[list_size:]:
                child.parent = None
            del self.display_elements[list_size:]
        elif current_size < list_size:
            if current_size > 0:
                if (self.item_borders):
                    self.display_elements[-1].borders = (constants.LEFT, constants.TOP)
                else:
                    self.display_elements[-1].borders = (constants.LEFT,)

            # Create the new ones.
            self.display_elements.extend(self.make_element() for _ in
                                         range(list_size - current_size))

        if (self.item_borders):
            self.display_elements[-1].borders = (constants.TOP, constants.LEFT,
                                                 constants.BOTTOM)
        else:
            self.display_elements[0].borders = (constants.TOP, constants.LEFT)
            self.display_elements[-1].borders = (constants.LEFT, constants.BOTTOM)

        # Move the scrollbar to the end so that it gets drawn on top.
        self.children.remove(self.scrollbar)
        self.children.append(self.scrollbar)

    def make_element(self):
        borders = (constants.TOP, constants.LEFT) if self.item_borders else (constants.LEFT,)
        return text.SelectableText(self, None, None, anchor=constants.TOP_LEFT,
                                   borders=borders,
                                   shrink_factor=self.list_item_shrink,
                                   border_color=self.border_color,
                                   selected_color=self.selected_color,
                                   unselected_color=self.unselected_color,
                                   align=self.align)

    def resize(self):
        super(Listbox, self).resize()

        if self.num_elements() != len(self.display_elements):
            self.remake_elements()

        self.scrollbar.resize()

        # FIXME: resize should not call rebuild
        self.needs_resize = False
        self.rebuild()

    def rebuild(self):
        self.list_pos = self.safe_pos(self.list_pos)

        if self.needs_resize:
            self.resize()
            return

        window_size = len(self.display_elements)
        list_size = len(self.list)

        self.scrollbar.window = len(self.display_elements)
        self.scrollbar.elements = list_size

        self.scrollbar.rebuild()

        if self.auto_scroll:
            self.auto_scroll = False
            self.scrollbar.center(self.list_pos)

        scrollbar_width = self.scrollbar.real_size[0]
        my_width = self.real_size[0]
        scrollbar_rel_width = scrollbar_width / float(my_width)

        offset = self.scrollbar.scroll_pos
        for index, element in enumerate(self.display_elements):
            list_index = index + offset

            # Position and size the element.
            element.pos = (0, -index / float(window_size))
            element.size = (-1 + scrollbar_rel_width, -1 / float(window_size))

            if (self.item_selectable):
                element.selected = (list_index == self.list_pos)

            # Set up the element contents.
            self.update_element(element, list_index)

        self.needs_redraw = True
        super(Listbox, self).rebuild()

    def update_element(self, element, list_index):
        if 0 <= list_index < len(self.list):
            element.text = self.list[list_index]
        else:
            element.text = ""


class UpdateListbox(Listbox):
    """Listbox with a function called on selection change"""
    def _on_selection_change(self):
        self.update_func(self.list_pos)

    _list_pos = widget.call_on_change("__list_pos", _on_selection_change)
    _list = widget.call_on_change("__list", _on_selection_change)

    def __init__(self, *args, **kwargs):
        self.update_func = kwargs.pop("update_func", lambda value: None)
        super(UpdateListbox, self).__init__(*args, **kwargs)


class CustomListbox(UpdateListbox):
    remake_func = widget.causes_rebuild("_remake_func")
    rebuild_func = widget.causes_rebuild("_rebuild_func")

    def __init__(self, parent, *args, **kwargs):
        self.parent = parent
        self.key_list = kwargs.pop("key_list", None)
        self.remake_func = kwargs.pop("remake_func", lambda value: None)
        self.rebuild_func = kwargs.pop("rebuild_func", lambda *args: None)
        super(CustomListbox, self).__init__(parent, *args, **kwargs)

    def make_element(self):
        base = super(CustomListbox, self).make_element()
        self.remake_func(base)
        return base

    def update_element(self, element, list_index):
        if 0 <= list_index < len(self.list):
            if (self.key_list is not None):
                self.rebuild_func(element, self.list[list_index],
                                  self.key_list[list_index])
            else:
                self.rebuild_func(element, self.list[list_index])
        else:
            if (self.key_list is not None):
                self.rebuild_func(element, None, None)
            else:
                self.rebuild_func(element, None)
