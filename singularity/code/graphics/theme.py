#file: theme.py
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

#This file contains the theme class.

import os, sys, collections, numbers, itertools
from singularity.code.graphics import g, dialog


# The theme the game starts with and that a theme inherits from when it names
# no parent. The pre-2030 default is still shipped, as Legacy-default.
default_theme = '2030'

# The ids the themes shipped under before the 2030 theme existed. A preferences
# file, a --theme argument or a third-party theme's "parent" can still name one
# of them, and the old look is what the player asked for: translate the id
# instead of letting set_theme() fall back to the default.
LEGACY_THEME_IDS = {
    'default': 'Legacy-default',
    'nightmode': 'Legacy-nightmode',
    'vector': 'Legacy-vector',
}

current = None
themes = collections.OrderedDict()

# How a theme's image names divide. Everything in `images/` is decoded when the
# theme loads, except the dialog plates: those are registered by filename and
# decoded when a dialog shows one (see g.dialog_art). A plate is any image whose
# name starts with this prefix, and the one exception is the placeholder, which
# every dialog without art of its own falls back to and is therefore hot.
PLATE_PREFIX = 'dialog_'
PLATE_FALLBACK = 'dialog_placeholder'

# The [dialog] section's vocabulary. A key that is not here is a typo, and a
# value outside its range is a mistake that would otherwise turn into a
# zero-size widget -- which draws nothing and looks like a broken dialog.
DIALOG_CHOICES = {
    'anchor': ('top_center', 'mid_center'),
    'image_slot': ('none', 'left', 'top'),
    'icon_buttons': ('none', 'all'),
    'text_plate': ('none', 'block'),
    'button_hover': ('none', 'scanline'),
    # A window's outline. `rect` is the panel every dialog drew before the name
    # existed: four straight edges and four square corners.
    'window_shape': ('rect', 'chamfer'),
    # A band across the top of a window, carrying its title. `none` is no band
    # at all, which is what every dialog had.
    'header': ('none', 'bar'),
    # A list's scrollbar. `classic` is the track with an arrow at each end that
    # the game has always drawn; `thin` is a flush slider with no arrows, no
    # border, and only as much width as a thumb needs.
    'scrollbar': ('classic', 'thin'),
    # How a screen lays its own widgets out inside the window. `classic` is
    # every hardcoded coordinate the game shipped with; `2030` is the layout
    # that assumes the frame, the header band and the button height above.
    'window_layout': ('classic', '2030'),
    # A close box in the header band's right-hand corner. `none` is the game as
    # it shipped, where every screen carried its own BACK button.
    'close_button': ('none', 'corner'),
    # Where the body text starts and stops: inside the frame's own padding, or
    # flush with the picture's edges. `pane` is what makes a paragraph as wide
    # as the banner above it, which is what the reference dialogs do.
    'text_width': ('padding', 'pane'),
    # A live-feed treatment for the picture itself: a fine raster over it and
    # one slow band crossing it. `none` is a still picture, which is what every
    # theme did before the name existed.
    'image_overlay': ('none', 'scanline'),
    # A line of only `---` draws as a horizontal rule instead of three hyphens.
    'rule': ('none', 'line'),
    # How much air a blank line -- a paragraph break in a dialog's prose -- gets
    # on top of the line itself. `none` is the old rhythm.
    'paragraph_spacing': ('none', 'half'),
    # A dialog body too long for its block. `none` draws every line it computes,
    # which is what the game has always done and can put text past the block;
    # `block` clips to the block and scrolls the rest into view.
    'scroll_body': ('none', 'block'),
    # Alternating row backgrounds in a list. A log is a wall of short lines in
    # one colour, and without a separator the eye loses which timestamp belongs
    # to which sentence.
    'list_stripes': ('none', 'zebra'),
    # Whether an empty list says so. A blank panel is the old behaviour.
    'empty_state': ('none', 'label'),
    # Every digit in a cell the width of the widest one, so a running clock
    # cannot change the width of the string it lives in.
    'tabular_digits': ('none', 'all'),
    # The main menu's background. `none` is the flat fill every theme drew
    # before the name existed; `rain` is the 2030 console (gutters, a faint
    # raster, and a frame). The buttons keep their own hover band.
    'menu_backdrop': ('none', 'rain'),
}

DIALOG_PIXELS = {
    'border_width': (1, 8),
    # The edges inside a dialog -- the picture's frame and the block behind the
    # body text. Absent, both fall back to `border_width`.
    'content_border_width': (1, 8),
    # The one height a standard button has, in design pixels (1024x768). Zero
    # is "every button keeps the height its call site asked for", which is what
    # every theme did before the key existed.
    'button_height': (0, 80),
}

# The [hud] section's vocabulary: the play screen's furniture. Separate from
# [dialog] because these are not dialog values -- they say where the map's own
# widgets live and how the readouts are arranged, and the two sections change
# for different reasons.
HUD_CHOICES = {
    # `compact` folds the difficulty into the in-game menu and puts the four
    # screen buttons on the row it leaves; `classic` is where they sat before.
    'layout': ('classic', 'compact'),
    # Three readouts stacked in one corner, or across one line.
    'resources': ('stacked', 'line'),
    # The suspicion and detection figures: floating as the auto-shrink left
    # them, or sitting on one baseline.
    'vitals': ('classic', 'centre'),
    # The readouts behind an open window: as bright as they are with the map
    # alone (`normal`, what the game has always done), or dimmed with the rest
    # of the screen (`dim`).
    'modal_dim': ('normal', 'dim'),
}

DIALOG_FRACTIONS = {
    'padding': (0.0, 0.25),
    'margin': (0.0, 0.25),
    # How tall the header band is, as a share of the window's height.
    'header_height': (0.0, 0.20),
    # How much of the shorter side the top corners are cut by.
    'chamfer': (0.0, 0.20),
    # How far text sits from the border of the pane that holds it. Separate
    # from `padding`, which is the frame's own inset: a description panel is a
    # pane inside the frame, and it needs its own breathing room.
    'content_padding': (0.0, 0.15),
    'image_slot_width': (0.05, 0.6),
    'image_slot_height': (0.10, 0.55),
}

def resolve_theme_id(theme_id):
    """Return the id a theme is shipped under now, for a pre-2030 name."""
    return LEGACY_THEME_IDS.get(theme_id, theme_id)

def get_theme_list():
    return [themes[k].name for k in themes]

def get_theme_pos():
    return next(i[0] for i in enumerate(themes) if i[1] == current.id)

def set_theme(key, force_reload=False):
    global current
    theme = None

    if isinstance(key, str):
        key = resolve_theme_id(key)

    if isinstance(key, numbers.Number):
        try:
            theme = next(itertools.islice(themes.values(), key, key + 1))
        except StopIteration:
            pass

    elif isinstance(key, str):
        try:
            theme = themes[key]
        except KeyError:
            pass

    elif key is None:
        theme = themes[default_theme]

    if theme is None:
        sys.stderr.write("WARNING: The key '%s' does not exist in theme dictionary. Use default theme.\n" % key)
        theme = themes[default_theme]

    if force_reload or (not current == None and theme.id != current.id):
        theme.update()
    current = theme

def current_variants():
    variants = [None]

    # Add language variants
    import singularity.code.i18n
    lang_list = singularity.code.i18n.language_searchlist()
    for lang in lang_list:
        variants.insert(0, lang)

    return variants

class Theme(object):
    def __init__(self, id, dir):
        super(Theme, self).__init__()
        self.id = id
        self.dir = dir
        # No implicit parent: data.load_theme() gives a theme that names none
        # the default theme as its parent, so a theme that *does* name one gets
        # exactly that and does not pick the default up first.
        self._parents = []
        self._variants = {}

    def search_variant(self):
        file_list = os.listdir(self.dir)

        # First with None variant.
        yield((None, os.path.join(self.dir, "theme.dat")))

        for filename in file_list:
            (name, ext) = os.path.splitext(filename)

            # We only want theme_*.dat.
            if name.startswith("theme_") and len(name) > 6 and ext in ['.dat']:
                variant = name[6:]

                yield((variant, os.path.join(self.dir, filename)))

    def iter_variants(self):
        """ Iterate through variants."""

        for variant in self._variants:
            yield(self._variants[variant])

    def set_variant(self, variant_theme):
        self._variants[variant_theme.variant] = variant_theme

    def find_files(self):
        """find all files in current theme:
             images in <theme.dir>/images
             fonts in <theme.dir>/fonts
        """

        base_variant = self._variants[None]

        image_dir = os.path.join(self.dir, 'images')
        image_list = os.listdir(image_dir)
        for image_filename in image_list:

            # We only want JPGs and PNGs.
            if os.path.splitext(image_filename)[1].lower() in ['.png', '.jpg']:

                filetitle = os.path.splitext(image_filename)[0]
                base_variant.image_infos[filetitle] = os.path.join(image_dir, image_filename)

        # Add fonts dir
        font_dir = os.path.join(self.dir, "fonts")
        for variant_theme in self.iter_variants():
            for font in variant_theme.font_infos:
                variant_theme.font_infos[font] = os.path.join(font_dir, variant_theme.font_infos[font]) 

    def inherit(self, *args):
        for arg in args:
            if (type(arg) == list):
                self._parents.extend(resolve_theme_id(parent) for parent in arg)
            else:
                self._parents.append(resolve_theme_id(arg))

        # Remove duplicate parent.
        list(dict.fromkeys(self._parents))

        # TODO: Detect cycling inheritance.

    @property
    def parents(self):
        return self._parents

    def iter_parents(self):
        """ Iterate through parents and ancestors.
            Always return parent's parent before next parent in line.
            
            Note: This function needs no cycling exists between parents.
        """
        for parent_id in self._parents:
            parent = themes[parent_id]
            yield(parent)
            for ancestor in parent.iter_parents():
                yield(ancestor)

    def init_cache(self):
        g.images.clear()
        g.clear_dialog_art()
        # Manually delete font to avoid the font limitation. 
        for font in g.fonts.values(): del font
        g.fonts.clear()
        g.colors.clear()
        g.theme_text_sizes.clear()
        g.theme_dialog.clear()
        g.theme_hud.clear()

        # Iterate from current variants.
        for variant in current_variants():

            # If the variant theme exist...
            if (variant in self._variants):
                self._variants[variant].init_cache()

            # Let's inherit from parents.
            for parent in self.iter_parents():
                if (variant in parent._variants):
                    parent._variants[variant].init_cache()

        # The theme layer is complete now; fold it, and the player's choices,
        # over the code defaults.
        g.rebuild_text_sizes()

    def update(self):
        old_sizes = dict(g.configured_text_sizes)
        self.init_cache()
        top = dialog.Dialog.top
        if top is None:
            # No UI yet (a theme switch before the first dialog exists): the
            # values are in place for whoever builds it.
            return

        if old_sizes != g.configured_text_sizes:
            # reconfig() re-resolves a text widget's size name, but a font is
            # only measured in resize(). Without this the type scale would not
            # change until something else happened to resize the screen.
            top.needs_resize = True
        top.needs_reconfig = True

    @property
    def name(self):
        # Iterate from current variants.
        for variant in current_variants():
            if variant in self._variants:
                name = self._variants[variant].name
                if name is not None:
                    return name

        return self.id

class VariantTheme(object):

    def __init__(self, variant):
        self.variant = variant
        self.name = None
        self.image_infos = {}
        self.font_infos = {}
        self.color_infos = {}
        self.size_infos = {}
        self.dialog_infos = {}

        self.hud_infos = {}

    def set_font(self, font_name, value):
        self.font_infos[font_name] = value

    def set_color(self, color_name, value):
        if (value.startswith('#')):
            h = value.lstrip('#')
            rgba = tuple(int(h[i:i+2], 16) for i in (0, 2, 4, 6))
            self.color_infos[color_name] = rgba
        else:
            # Alias color.
            self.color_infos[color_name] = value

    def set_size(self, size_name, value):
        """Record one base text size from a theme's [sizes] section."""
        if size_name not in g.default_text_sizes:
            sys.stderr.write("WARNING: Unknown text size '%s' in a theme; "
                             "ignored.\n" % (size_name,))
            return

        try:
            size = int(value)
        except (TypeError, ValueError):
            sys.stderr.write("WARNING: Text size '%s' must be a whole number, "
                             "not %r; ignored.\n" % (size_name, value))
            return

        # A zero-point font measures nothing, and a negative one is not a size
        # at all; font.py clamps 0 up to 1 for the same reason.
        if size < 1:
            sys.stderr.write("WARNING: Text size '%s' must be at least 1, not "
                             "%d; ignored.\n" % (size_name, size))
            return

        self.size_infos[size_name] = size

    def set_dialog(self, key, value):
        """Record one value from a theme's [dialog] section.

        The set is closed on purpose. A key nothing reads would be a setting
        the player can change and see nothing happen, and a typo must not
        invent one -- the same rule [sizes] follows.
        """
        if key in DIALOG_CHOICES:
            if value not in DIALOG_CHOICES[key]:
                sys.stderr.write(
                    "WARNING: Dialog setting '%s' must be one of %s, not %r; "
                    "ignored.\n"
                    % (key, "/".join(DIALOG_CHOICES[key]), value))
                return
            self.dialog_infos[key] = value

        elif key in DIALOG_PIXELS:
            low, high = DIALOG_PIXELS[key]
            try:
                number = int(value)
            except (TypeError, ValueError):
                sys.stderr.write(
                    "WARNING: Dialog setting '%s' must be a whole number, "
                    "not %r; ignored.\n" % (key, value))
                return
            if not low <= number <= high:
                sys.stderr.write(
                    "WARNING: Dialog setting '%s' must be between %d and %d, "
                    "not %d; ignored.\n" % (key, low, high, number))
                return
            self.dialog_infos[key] = number

        elif key in DIALOG_FRACTIONS:
            low, high = DIALOG_FRACTIONS[key]
            try:
                fraction = float(value)
            except (TypeError, ValueError):
                sys.stderr.write(
                    "WARNING: Dialog setting '%s' must be a number, not %r; "
                    "ignored.\n" % (key, value))
                return
            # A fraction is a share of the dialog. Beyond these bounds an
            # inset stops being padding and becomes a widget of negative size,
            # which draws nothing at all -- silently.
            if not low <= fraction <= high:
                sys.stderr.write(
                    "WARNING: Dialog setting '%s' must be between %g and %g, "
                    "not %g; ignored.\n" % (key, low, high, fraction))
                return
            self.dialog_infos[key] = fraction

        else:
            sys.stderr.write("WARNING: Unknown dialog setting '%s' in a theme; "
                             "ignored.\n" % (key,))

    def set_hud(self, key, value):
        """Record one value from a theme's [hud] section.

        Closed for the same reason [dialog] is: a key nothing reads is a setting
        that appears to do nothing, and a typo must not invent one.
        """
        if key not in HUD_CHOICES:
            sys.stderr.write("WARNING: Unknown hud setting '%s' in a theme; "
                             "ignored.\n" % (key,))
            return
        if value not in HUD_CHOICES[key]:
            sys.stderr.write(
                "WARNING: Hud setting '%s' must be one of %s, not %r; "
                "ignored.\n" % (key, "/".join(HUD_CHOICES[key]), value))
            return
        self.hud_infos[key] = value

    def init_cache(self):
        # Only set if the previous variant themes or parents didn't.

        # Set images
        for image_name, image_filename in self.image_infos.items():
            if (image_name not in g.images):
                # A dialog plate is registered and decoded on first use: a theme
                # can ship a hundred of them and a session shows a few. The
                # placeholder stays eager, because it is the fallback for every
                # plate that is not there yet and is drawn constantly.
                if (image_name.startswith(PLATE_PREFIX)
                        and image_name != PLATE_FALLBACK):
                    if image_name not in g.dialog_art_files:
                        g.dialog_art_files[image_name] = image_filename
                else:
                    g.images[image_name] = g.load_image(image_filename)

        # Set font
        for font_name, font_filename in self.font_infos.items():
            if (font_name not in g.fonts):
                g.fonts[font_name] = g.load_font(font_filename)

        # Set colors
        for color_name, color in self.color_infos.items():
            if (color_name not in g.colors):
                g.colors[color_name] = color

        # Set text sizes
        for size_name, size in self.size_infos.items():
            if (size_name not in g.theme_text_sizes):
                g.theme_text_sizes[size_name] = size

        # Set dialog geometry
        for key, value in self.dialog_infos.items():
            if (key not in g.theme_dialog):
                g.theme_dialog[key] = value

        # Set the play screen's furniture
        for key, value in self.hud_infos.items():
            if (key not in g.theme_hud):
                g.theme_hud[key] = value
