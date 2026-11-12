#file: font.py
#Copyright (C) 2005,2006,2007,2008 Evil Mr Henry, Phil Bordelon, Brian Reid,
#                        and FunnyMan3595
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

#This file contains class to handle font.

import io

import pygame

# Largest glyph size a FontList can produce.
#
# Text sizes are scaled from the 1024x768 baseline by the window height
# (text.convert_font_size), so a tall window asks for sizes well past 100: at
# 7680x4320 the default 20px text wants 112px and the button text wants 202px.
# The old ceiling of 100 silently clamped those, which froze the UI at its 4K
# appearance and made text look small on 5K and 8K screens.
#
# The list is filled lazily, so a high ceiling costs nothing for the sizes that
# are never used.
MAX_FONT_SIZE = 512

def init():
    # We could use ftfont or freetype in the future.
    pygame.font.init()

def generate_from_cache(filename):
    """ Yields a stream of the font file, one per pygame.font.Font

    The face is read once and every stream is its own io.BytesIO over those
    bytes. This replaces a hand-written file object that had picked up three
    Python 2 habits: it reported one byte less than the file, it dropped that
    byte from every read, and it never advanced its position. SDL_ttf seeks
    around the face and reads each table the first time a point size needs it,
    so a stream that lies about its length and does not advance is not the
    file on disk. io.BytesIO is the type pygame documents for this and it gets
    all three of those right.

    The file is still opened once per FontList, which is what keeps the file
    descriptor count down (see GH#156): no font holds a descriptor.
    """
    with open(filename, 'rb') as fd:
        font_content = fd.read()

    while True:
        yield io.BytesIO(font_content)

class FontList(object):
    """ List object used to store font

    We use a lazy loader for fonts so that a point size is only built when
    something asks for it.
    """

    def __init__(self, filename, max_size=MAX_FONT_SIZE):
        self._font_cache = {}
        self._max_size = max_size
        self._generator = generate_from_cache(filename)

    def __len__(self):
        return self._max_size

    def __contains__(self, item):
        return 1 <= item < self._max_size

    def __getitem__(self, item):
        # There is no usable zero-point face. SDL_ttf builds one whose glyphs
        # measure zero, and the size search in text.py can ask for it whenever
        # a widget's own rect has collapsed: do_bisect() answers 0 when nothing
        # fits. One point is the smallest size that still measures something.
        if item < 1:
            item = 1

        if self._max_size <= item:
            raise IndexError(item)
                
        font = self._font_cache.get(item)
        if font is None:
            font = pygame.font.Font(next(self._generator), item)
            self._font_cache[item] = font
        return font
