#file: widget.py
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

#This file contains the widget class.

import pygame
from numpy import array
from inspect import getmembers

from singularity.code import g
from singularity.code.graphics import g as gg, constants


def unmask(widget):
    """Causes the widget to exist above its parent's fade mask.  The widget's
       children will still be masked, unless they are unmasked themselves."""
    unmask_all(widget)
    widget.mask_children = True

def unmask_all(widget):
    """Causes the widget to exist above its parent's fade mask.  The widget's
       children will not be masked."""
    widget.self_mask = True
    widget.do_mask = lambda: None

def call_on_change(data_member, call_me, *args, **kwargs):
    """Creates a data member that calls a function when changed."""
    def get(self):
        return getattr(self, data_member)

    def set(self, my_value):
        if data_member in self.__dict__:
            change = (my_value != self.__dict__[data_member])
        else:
            change = True

        if change:
            setattr(self, data_member, my_value)
            call_me(self, *args, **kwargs)

    return property(get, set)

def set_on_change(data_member, set_me, set_value = True):
    """Creates a data member that sets another data member to a given value
       when changed."""
    return call_on_change(data_member, setattr, set_me, set_value)

def causes_rebuild(data_member):
    """Creates a data member that sets needs_rebuild to True when changed."""
    return set_on_change(data_member, "needs_rebuild")

def causes_redraw(data_member):
    """Creates a data member that sets needs_redraw to True when changed."""
    return set_on_change(data_member, "needs_redraw")

def causes_resize(data_member):
    """Creates a data member that sets needs_resize to True when changed."""
    return set_on_change(data_member, "needs_resize")

def causes_reposition(data_member):
    """Creates a data member that sets needs_reposition to True when changed."""
    return set_on_change(data_member, "needs_reposition")

def causes_update(data_member):
    """Creates a data member that sets needs_update to True when changed."""
    return set_on_change(data_member, "needs_update")

def propogate_need(data_member):
    """Creates a function that can be passed to call_on_change.  When the
       data member changes to True, needs_update is set, and the True value
       is passed to all descendants."""
    def do_propogate(self):
        if getattr(self, data_member, False):
            self.needs_update = True

            if hasattr(self, "children"):
                descendants = self.children[:]
                while descendants:
                    child = descendants.pop()
                    # Propogate to this child and its descendants, if needed.
                    if not getattr(child, data_member, False):
                        setattr(child, data_member, True)
                        child._needs_update = True
                        if hasattr(child, "children"):
                            descendants += child.children

    return do_propogate

# Previous attempt was to hide the raw value by resolving
# the value before returning it. However, there are legitimate
# reason to access the raw value. So, we need two property.
# Using a wrapper is not worth the trouble.
# I choose to let the unresolved value the default because
# in majority of it's what we want, and in other case,
# you must handle reconfig anyways.
class auto_reconfig(object):

    __slots__ = ["data_member", "reconfig_datamember", "reconfig_func"] # Avoid __dict__.

    def __init__(self, data_member, reconfig_prefix, reconfig_func):
        self.data_member = data_member
        self.reconfig_datamember = reconfig_prefix + data_member
        self.reconfig_func = reconfig_func

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        return getattr(obj, self.data_member)

    def __set__(self, obj, my_value):
        new_value = self.reconfig_func(my_value)

        setattr(obj, self.reconfig_datamember, new_value)
        setattr(obj, self.data_member, my_value)

    def reconfig(self, obj):
        updated_value = self.reconfig_func(getattr(obj, self.data_member))
        setattr(obj, self.reconfig_datamember, updated_value)


def _repaint_if_covered(child, painted):
    """Mark `child` for redraw when a sibling has already drawn over it.

    Children are drawn in order, so an earlier one owns the pixels it covers --
    and a child that has already been drawn is not drawn again when something
    later paints over it. Nothing used to repaint it at all, which is the map
    screen: the globe redraws as its terminator moves, the space buttons sit
    over it, and they vanished and came back in cycles.

    A redraw rather than a bare update, because the widget has real pixels to
    put back; `needs_redraw` carries the update flag with it.
    """
    if child.needs_update or child.collision_rect is None:
        return
    if any(child.collision_rect.colliderect(rect) for rect in painted):
        child.needs_redraw = True


class Widget(object):
    """A Widget is a GUI element.  It can have one parent and any number of
       children."""

    needs_redraw = call_on_change("_needs_redraw",
                                  propogate_need("_needs_redraw"))

    needs_resize = call_on_change("_needs_resize",
                                  propogate_need("_needs_resize"))

    needs_reposition = call_on_change("_needs_reposition",
                                      propogate_need("_needs_reposition"))

    needs_rebuild = causes_update("_needs_rebuild")

    def _propogate_update(self):
        if self._needs_update:
            if hasattr(self, "parent"):
                target = self.parent
                while target and not target._needs_update:
                    target._needs_update = True
                    target = target.parent

    needs_update = call_on_change("_needs_update", _propogate_update)

    needs_reconfig = call_on_change("_needs_reconfig",
                                    propogate_need("_needs_reconfig"))

    pos = causes_reposition("_pos")
    size = causes_resize("_size")
    anchor = causes_reposition("_anchor")
    visible = causes_redraw("_visible")

    def __init__(self, parent, pos, size, anchor = constants.TOP_LEFT):
        self.parent = parent
        self.children = []

        self.pos = pos
        self.size = size
        self.anchor = anchor

        # "It's a widget!"
        self.add_hooks()

        self.is_above_mask = False
        self.self_mask = False
        self.mask_children = False
        self.visible = True

        self.needs_rebuild = True
        self.collision_rect = None

        # Set automatically by other properties.
        #self.needs_redraw = True
        #self.needs_full_redraw = True
        self.needs_reconfig = True

    @property
    def parent(self):
        return self._parent

    @parent.setter
    def parent(self, parent):
        if hasattr(self, 'children'):
            self.remove_hooks()

        if (hasattr(self, '_parent') and self._parent is not None):
            try:
                self._parent.children.remove(self)
            except ValueError:
                pass # Wasn't there to start with.

        self._parent = parent

        if self.parent is not None:
            self.parent.children.append(self)
            self.parent.needs_rebuild = True
            self.parent.needs_resize = True
            self.parent.needs_reposition = True
            self.parent.needs_redraw = True

        if hasattr(self, 'children'):
            self.add_hooks()

    def add_hooks(self):
        if self.parent is not None:
            # Won't trigger on the call from __init__, since there are no
            # children yet, but add_hooks may be explicitly called elsewhere to
            # undo remove_hooks.
            for child in self.children:
                child.add_hooks()

    def remove_hooks(self):
        # Localize the children list to avoid index corruption and O(N^2) time.
        children = self.children

        # Recurse to the children.
        for child in children:
            child.remove_hooks()

    def _parent_size(self):
        if self.parent == None:
            return gg.real_screen_size
        else:
            return self.parent.real_size

    def _calc_size(self):
        """Internal method.  Calculates and returns the real size of this
           widget.

           Override to create a dynamically-sized widget."""
        parent_size = self._parent_size()
        size = list(self.size)
        for i in range(2):
            if size[i] > 0:
                # Sizes and positions must use the same basis. get_real_pos()
                # measures from real_screen_size, so a size measured against
                # anything else makes widgets land outside their parent.
                size[i] = int(size[i] * gg.real_screen_size[i])
            elif size[i] < 0:
                size[i] = int( (-size[i]) * parent_size[i] )

        return tuple(size)

    def get_real_size(self):
        """Returns the real size of this widget.

           To implement a dynamically-sized widget, override _calc_size, which
           will be called whenever the widget is resized, and set needs_resize
           when appropriate."""
        return self._real_size

    real_size = property(get_real_size)

    def get_real_pos(self):
        """Returns the real position of this widget on its parent."""
        vanchor, hanchor = self.anchor
        parent_size = self._parent_size()
        my_size = self.real_size

        if self.pos[0] >= 0:
            hpos = int(self.pos[0] * gg.real_screen_size[0])
        else:
            hpos = - int(self.pos[0] * parent_size[0])

        if hanchor == constants.LEFT:
            pass
        elif hanchor == constants.CENTER:
            hpos -= my_size[0] // 2
        elif hanchor == constants.RIGHT:
            hpos -= my_size[0]

        if self.pos[1] >= 0:
            vpos = int(self.pos[1] * gg.real_screen_size[1])
        else:
            vpos = - int(self.pos[1] * parent_size[1])

        if vanchor == constants.TOP:
            pass
        elif vanchor == constants.MID:
            vpos -= my_size[1] // 2
        elif vanchor == constants.BOTTOM:
            vpos -= my_size[1]

        return (hpos, vpos)

    real_pos = property(get_real_pos)

    def _make_collision_rect(self):
        """Creates and returns a collision rect for this widget."""
        pos = array(self.real_pos)
        if self.parent:
            pos += self.parent.collision_rect[:2]
        else:
            # The top-level widget is drawn at the layout origin, which is not
            # (0, 0) when the window is wider than the layout. Offsetting the
            # root here gives every child a window-space hit box, so mouse
            # positions from pygame keep working unchanged.
            pos += gg.layout_origin

        return pygame.Rect(pos, self.real_size)

    def is_over(self, position):
        if not getattr(self, "collision_rect", None):
            return False
            
        if position != (0,0):
            return self.collision_rect.collidepoint(position)
        else:
            return False

    def remake_surfaces(self):
        """Recreates the surfaces that this widget will draw on."""
        size = self.real_size
        pos = self.real_pos

        if self.parent != None:
            try:
                self.surface = self.parent.surface.subsurface(pos + size)
            except (ValueError, pygame.error):
                # ValueError: the rect is outside the parent.
                # pygame.error: a width or height below zero ("Parameter
                # 'height' is invalid"), which pygame will not carve at all.
                # Only ValueError was caught, so a degenerate rect turned a
                # clipped widget into a dead game.
                if gg.strict_layout:
                    raise RuntimeError(
                        "%r does not fit on its parent: pos %r size %r, "
                        "parent pos %r size %r"
                        % (self, pos, size,
                           self.parent.real_pos, self.parent.real_size))

                print("Warning: %r can't fit on its parent." % self)
                print(pos, size, self.parent.real_pos, self.parent.real_size)

                wanted_rect = pos + size
                available_rect = self.parent.surface.get_rect()
                compromise = available_rect.clip(wanted_rect)

                # clip() of an empty rect at the far edge keeps its size, and a
                # degenerate size must not reach subsurface() a second time.
                compromise.size = (max(0, compromise.width),
                                   max(0, compromise.height))
                try:
                    self.surface = self.parent.surface.subsurface(compromise)
                except (ValueError, pygame.error):
                    # None of this widget is on its parent. Draw on a detached
                    # surface of the same shape rather than dying: the widget
                    # is invisible instead of the game being over.
                    self.surface = pygame.Surface(
                        (max(0, size[0]), max(0, size[1])), 0,
                        self.parent.surface)
        else:
            # The top-level widget covers the layout area, which is the whole
            # window unless the window is wider than LAYOUT_MAX_ASPECT; see
            # g.compute_layout().
            if gg.screen_surface is None:
                # Ensure that the screen is initialized
                gg.set_mode()
            if gg.screen_surface.get_size() == size:
                # We draw on a copy of the surface.  This is to avoid crashes
                # during draggable resizing (event.VIDEORESIZE) where the
                # screen size might change behind our backs while drawing
                # (event.VIDEORESIZE tells us that the screen has been updated
                # and we should catch up and not the other way around)
                self.surface = gg.screen_surface.copy()
            else:
                # Pillarboxed window: draw on a layout-sized surface instead.
                self.surface = pygame.Surface(size).convert()
            self.surface.fill( (0,0,0,255) )

            # SRCALPHA, not the gg.ALPHA *format*. A Surface passed as the
            # depth argument copies its pixel format but not its SRCALPHA flag,
            # so this mask used to come out opaque: pygame ignored the 175
            # alpha and blitted it as a solid black rectangle. Every widget
            # behind a dialog was wiped -- background and text together -- on
            # the first frame after the dialog opened, and stayed wiped until
            # it happened to be redrawn. That looks like "no fonts render when
            # I open a screen", while the dialog's own widgets draw after the
            # mask and look perfect.
            gg.fade_mask = pygame.Surface(size, pygame.SRCALPHA)
            # How dark the forgotten background goes. Upstream's value is
            # (0, 0, 0, 175) and stays the default; a theme may name a deeper
            # one, because "everything behind the dialog is dimmed" reads
            # differently against a near-black HUD than against the old blue.
            # A theme that does not define the colour gets upstream's exactly.
            mask_colour = (0, 0, 0, 175)
            try:
                mask_colour = tuple(gg.resolve_color_alias("fade_mask_color"))
            except KeyError:
                pass
            gg.fade_mask.fill(mask_colour)

    def prepare_for_redraw(self):
        # First, we handle config changes.
        if self.needs_reconfig:
            self.reconfig()
            self.needs_reconfig = False

        # Then any substance changes.
        if self.needs_rebuild:
            self.rebuild()
            self.needs_rebuild = False

        # Then size changes.
        if self.needs_resize:
            self.resize()
            self.needs_resize = False
            self.needs_reposition = True
            self.needs_redraw = True

        # Then position changes.
        if self.needs_reposition:
            self.needs_reposition = False
            self.reposition()

        # And finally we recurse to our descendants.
        for child in self.children:
            if child.visible:
                child.prepare_for_redraw()

    def maybe_update(self):
        # Once a frame, and only on the root: does the window still have the
        # size the UI is laid out in? A resize event can be lost, coalesced or
        # refused, and then the tree draws into an area smaller than the window
        # and the difference is uninitialised screen.
        if not self.parent and gg.reconcile_window_size():
            self.needs_resize = True
            self.needs_redraw = True

        if self.needs_update:
            self.update()

    def update(self):
        # First we prepare everything for its redraw (if needed).
        self.prepare_for_redraw()

        _, updated_rect = self._update()

        # Oh, and if this is the top-level widget, we should update the display.
        if not self.parent and gg.screen_surface:
            if gg.geometry_dirty:
                # The window changed size, and with it the buffer it presents.
                # Nothing has drawn into the new area yet, so presenting only
                # the rects that changed would leave the rest of the window as
                # whatever the compositor left in the reallocation -- the band
                # of green/black stripes down the side of a resized window.
                # Present all of it once, then go back to the cheap path.
                gg.geometry_dirty = False
                gg.screen_surface.blit(self.surface, gg.layout_origin)
                gg.clear_outside_layout()
                pygame.display.update()
                return

            # See g.layout_blit_pairs(): the rects are window space, while
            # self.surface covers only the layout area.
            gg.screen_surface.blits(
                ((self.surface, dest, area)
                 for dest, area in gg.layout_blit_pairs(updated_rect)),
                doreturn=0)

            if g.debug and updated_rect:
                # Outline the widgets that were updated. Drawn on the screen
                # surface, *after* the blit, because these rects must never
                # become blit source geometry: the old code drew into a copy of
                # the root and then added the previous frame's rings to
                # updated_rect, so each frame was assembled from regions chosen
                # in an earlier one. Once the geometry or the open dialog
                # changed, those regions were no longer widgets -- which is why
                # --debug showed black bars, partial labels and missing text
                # that did not appear without it.
                try:
                    # If the theme defines a color for this purpose, we will use it
                    widget_highlight_color = gg.resolve_color_alias('debug_mode_highlight_redrawn_widget')
                except KeyError:
                    # ... and for every thing else, there is the color red.
                    widget_highlight_color = 0xff, 0, 0, 0
                for rect in updated_rect:
                    pygame.draw.rect(gg.screen_surface, widget_highlight_color,
                                     rect, 1)

            pygame.display.update(updated_rect)

    def _update(self):
        redrew_self = self.needs_redraw
        update_full_rect = redrew_self
        affected_rects = []
        if self.needs_redraw:
            self.redraw()
            if getattr(self, "faded", False) and self.fades_own_chrome():
                # A window paints its frame, band and title into its own
                # surface, and a dialog is deliberately drawn *above* the
                # screen's fade mask -- which is what keeps it readable. Both
                # are right, and together they left a window opened from
                # another window at full brightness: its contents dimmed (they
                # are its children, and the mask reaches those) while its chrome
                # did not, so the level underneath still looked like the live
                # one. The mask is a flat colour, so blitting it at the
                # widget's own origin needs no alignment.
                self.surface.blit(gg.fade_mask, (0, 0))

        # Then we update any children below our fade mask.
        check_mask = []
        above_mask = []
        # The rects a sibling has drawn so far in this frame, for the check
        # below: an earlier sibling owns the pixels it covers, so anything it
        # painted over has to be laid down again afterwards.
        painted = []
        for child in self.children:
            if not child.visible:
                continue
            _repaint_if_covered(child, painted)
            if child.needs_update:
                if child.is_above_mask:
                    above_mask.append(child)
                else:
                    # update_full_rect = True  # We do not bother tracking this case
                    child_mask, child_rects = child._update()
                    check_mask.extend(child_mask)
                    if child_rects:
                        painted.append(child.collision_rect)
                    if child_rects and not update_full_rect:
                        affected_rects.extend(child_rects)

        # Next, we handle the fade mask.
        if getattr(self, "faded", False):
            while check_mask:
                child = check_mask.pop()
                if not child.self_mask:
                    # update_full_rect = True  # We do not bother tracking this case
                    child_rect = child.surface.blit(gg.fade_mask, (0,0))
                    if not update_full_rect:
                        affected_rects.append(child_rect)
                elif child.mask_children:
                    check_mask += child.children

        # And finally we update any children above the fade mask.
        for child in above_mask:
            _repaint_if_covered(child, painted)
            _, child_rects = child._update()
            if child_rects and not update_full_rect:
                affected_rects.extend(child_rects)

        # Update complete.
        self.needs_update = False

        # Any descendants we didn't check for masking get passed upwards.
        if redrew_self:
            # If we redrew this widget, we tell our parent to consider it
            # instead.  The parent will recurse down to any descendants if
            # needed, and redraw already propagated down to them.
            check_mask = [self]

        if update_full_rect:
            size = self.real_size
            pos = self.real_pos

            affected_rects = [self.collision_rect]

        return check_mask, affected_rects

    def reconfig(self):
        # Find reconfig property and update them.
        clazz = self.__class__
        for prop_name, prop in getmembers(clazz):
            if (isinstance(prop, auto_reconfig)):
                prop.reconfig(self)

    def rebuild(self):
        pass

    def resize(self):
        # A pixel size is never negative. Sizes are fractions of the layout or
        # of the parent, and a fraction built by subtraction -- Listbox.rebuild
        # makes "-1 + scrollbar_rel_width", Scrollbar.resize makes "(size * 2)
        # - 1" -- comes out negative when the thing it measures against is
        # degenerate. A negative size is not a widget that is merely small: it
        # is a rectangle pygame will not carve. subsurface() answers it with
        # "pygame.error: Parameter 'height' is invalid", which is not the
        # ValueError remake_surfaces() handled, so a redraw during a
        # resolution change ended the game.
        width, height = self._calc_size()
        self._real_size = (max(0, width), max(0, height))

    def reposition(self):
        old_rect = self.collision_rect
        self.collision_rect = self._make_collision_rect()

        if not self.parent:
            self.remake_surfaces()
            self.needs_redraw = True
        elif (   (getattr(self, "surface", None) is None)
              or (old_rect is None)
              or (self.surface.get_parent() is not self.parent.surface)
              or (not self.collision_rect.contains(old_rect))
             ):
            self.remake_surfaces()
            self.parent.needs_redraw = True
        elif self.collision_rect != old_rect:
            self.remake_surfaces()
            self.needs_redraw = True

    def redraw(self):
        self.needs_redraw = False
        if self.parent is None:
            self.surface.fill((0,0,0,255))

    def fades_own_chrome(self):
        """Whether this widget dims the pixels it paints for itself.

        The fade mask reaches a widget's children; it cannot reach what the
        widget draws straight into its own surface. That is the right default
        for everything that paints content -- a background behind a dialog is
        not inside it -- and wrong for the one widget that paints chrome.
        """
        return False

    def add_handler(self, *args, **kwargs):
        """Handler pass-through."""
        if self.parent:
            self.parent.add_handler(*args, **kwargs)

    def remove_handler(self, *args, **kwargs):
        """Handler pass-through."""
        if self.parent:
            self.parent.remove_handler(*args, **kwargs)

    def add_key_handler(self, *args, **kwargs):
        """Handler pass-through."""
        if self.parent:
            self.parent.add_key_handler(*args, **kwargs)

    def remove_key_handler(self, *args, **kwargs):
        """Handler pass-through."""
        if self.parent:
            self.parent.remove_key_handler(*args, **kwargs)

    def add_focus_widget(self, *args, **kwargs):
        """Focus pass-through."""
        if self.parent:
            self.parent.add_focus_widget(*args, **kwargs)

    def remove_focus_widget(self, *args, **kwargs):
        """Focus pass-through."""
        if self.parent:
            self.parent.remove_focus_widget(*args, **kwargs)

    def took_focus(self, *args, **kwargs):
        """Focus pass-through."""
        if self.parent:
            self.parent.took_focus(*args, **kwargs)
            
    def clear_focus(self, *args, **kwargs):
        """Focus pass-through."""
        if self.parent:
            self.parent.clear_focus(*args, **kwargs)


class BorderedWidget(Widget):
    borders = causes_redraw("__borders")
    # A theme may ask for a heavier frame (see MODERNIZATION.md, "Dialog
    # geometry belongs to the theme too"). One pixel is what the game drew
    # before the key existed, and draw_borders() draws byte-identical pixels
    # for it, so a widget that says nothing is unchanged.
    border_width = causes_redraw("_border_width")

    border_color = auto_reconfig("_border_color", "resolved", gg.resolve_color_alias)
    background_color = auto_reconfig("_background_color", "resolved", gg.resolve_color_alias)
    resolved_border_color = causes_redraw("_resolved_border_color")
    resolved_background_color = causes_redraw("_resolved_background_color")

    def __init__(self, parent, *args, **kwargs):
        self.borders = kwargs.pop("borders", ())
        self.border_width = kwargs.pop("border_width", 1)
        self.border_color = kwargs.pop("border_color", "widget_border")
        self.background_color = kwargs.pop("background_color", "widget_background")

        super(BorderedWidget, self).__init__(parent, *args, **kwargs)

    def rebuild(self):
        super(BorderedWidget, self).rebuild()
        if self.parent and self.resolved_background_color == gg.colors["clear"]:
            self.parent.needs_redraw = True

    def reposition(self):
        super(BorderedWidget, self).reposition()
        if self.parent and self.resolved_background_color == gg.colors["clear"]:
            self.parent.needs_redraw = True

    def redraw(self):
        super(BorderedWidget, self).redraw()

        # TODO: Transparency do not work correctly.
        # First: fill cannot use alpha channel with current surface.
        # Second: Transparency needs the parent redraw to work correctly.
        # It make transparency unusable with some widget.

        # Fill the background.
        if self.resolved_background_color != gg.colors["clear"]:
            self.surface.fill( self.resolved_background_color )

        self.draw_borders()

    def draw_borders(self):
        my_size = self.real_size
        # A frame wider than half the widget would paint over all of it, and a
        # zero-pixel frame is not a frame; one pixel is the floor.
        width = max(1, min(int(self.border_width), max(1, min(my_size) // 2)))

        for edge in self.borders:
            if edge == constants.TOP:
                self.surface.fill(self.resolved_border_color,
                                  (0, 0, my_size[0], width) )
            elif edge == constants.LEFT:
                self.surface.fill(self.resolved_border_color,
                                  (0, 0, width, my_size[1]) )
            elif edge == constants.RIGHT:
                self.surface.fill(self.resolved_border_color,
                                  (my_size[0]-width, 0, width, my_size[1]))
            elif edge == constants.BOTTOM:
                self.surface.fill(self.resolved_border_color,
                                  (0, my_size[1]-width, my_size[0], width))


class FocusWidget(Widget):
    has_focus = causes_redraw("_has_focus")
    def __init__(self, *args, **kwargs):
        super(FocusWidget, self).__init__(*args, **kwargs)
        self.has_focus = False
        
        self.add_handler(constants.CLICK, self.handle_click, 0)

    def add_hooks(self):
        super(FocusWidget, self).add_hooks()
        if self.parent is not None:
            self.parent.add_focus_widget(self)

    def remove_hooks(self):
        super(FocusWidget, self).remove_hooks()
        if self.parent is not None:
            self.parent.remove_focus_widget(self)

    def handle_click(self, event):
        if not self.is_over(event.pos):
            self.clear_focus(self)
