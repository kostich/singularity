#!/usr/bin/env python3
"""Build the 2030 theme's language-variant fonts as subsets.

The 2030 theme names a face per non-Latin language (theme_ar.dat, theme_ja.dat,
...). A full Noto face is 30 MB for CJK and carries every glyph the typeface
knows -- 65,000 of them -- of which the game draws a few hundred. pygame loads
the Regular instance of a variable font and never touches the weight axis, so
both the unused glyphs and the axis are dead weight in the Flatpak, which
bundles the whole checkout.

This script rebuilds each language face as a subset pinned to the characters
the shipped translations actually use, plus the Latin letters, digits and
punctuation the game draws under any language, and the two block glyphs the
map HUD renders as text. It is a build-time tool, like font_coverage.py: it
needs fontTools and the full Noto faces, neither of which is a dependency of
the game.

Usage:

    python3 utils/subset_fonts.py            # rebuild every language face
    python3 utils/subset_fonts.py --check    # report sizes, write nothing

Regenerate after adding translations or a new language: the subset covers the
catalogues as they are today, not the ones you will write. The source faces
are the distribution's Noto packages (Fedora names below).

Every subset draws the whole printable ASCII range, because the language menu
labels each row with its English name, an entry with no translation falls back
to the English source, and the readouts are digits and Latin labels. Every
subset also carries DejaVu's hollow box as its .notdef: the Noto faces leave
.notdef empty, so a character none of them could draw rendered as a gap the
width of a space, which reads as a typo rather than as a missing glyph.

Each subset is then completed from the theme's own DejaVu faces. A Noto script
face carries its script and not much else: none of the Arabic, Bengali or
Devanagari faces has Latin letters, none of the CJK faces has U+25AE at all,
and the game draws readouts, button labels and the map's speed glyphs in those
characters under every language. SDL_ttf takes one face per font slot and has
no per-character fallback, so a glyph the game draws has to live in the face
that draws it. Latin, digits, punctuation and U+25B6 are copied out of DejaVu;
U+25AE is drawn as a rectangle, because the CJK faces hold PostScript outlines
(CFF2) and a TrueType glyph cannot be copied into them.
"""

import os
import io
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
I18N = os.path.join(REPO_ROOT, "singularity", "i18n")
OUT_DIR = os.path.join(REPO_ROOT, "singularity", "data", "themes", "2030", "fonts")

# The characters every language face must draw on top of its own script.
#
# Printable ASCII is the floor, not a sample of it: the language menu shows each
# row as "Native (English)", an entry with no translation falls back to the
# English source, and every readout is digits and Latin labels. A translation is
# free to use punctuation outside it, so the marks the catalogues use are here
# too, as are the two block glyphs the map HUD draws as text (map.py). Whatever
# a source face lacks is completed from DejaVu below, so this is a promise the
# build keeps rather than a hope.
BASE = {chr(code) for code in range(0x20, 0x7F)} | set(
    "–—…‘’“”«»§¶†‡"
    "\u25ae\u25b6"
)

# (output filename, source basename, face index or None, languages it must
# cover, DejaVu face to complete it from)
# The CJK faces are a five-face collection (JP, KR, SC, TC, HK); the game only
# ships Japanese and Simplified Chinese, so those two faces are the ones kept.
# The monospace faces borrow from DejaVu Sans Mono Bold, so the completion of
# a label matches the weight of the label it sits in.
FACES = (
    ("NotoSansCJK-JP.ttf",       "NotoSansCJK-VF.ttc",        0, ("ja",),
     "DejaVuSans.ttf"),
    ("NotoSansCJK-SC.ttf",       "NotoSansCJK-VF.ttc",        2, ("zh_CN",),
     "DejaVuSans.ttf"),
    ("NotoSansMonoCJK-JP.ttf",   "NotoSansMonoCJK-VF.ttc",    0, ("ja",),
     "DejaVuSansMono-Bold.ttf"),
    ("NotoSansMonoCJK-SC.ttf",   "NotoSansMonoCJK-VF.ttc",    2, ("zh_CN",),
     "DejaVuSansMono-Bold.ttf"),
    ("NotoSansArabic.ttf",       "NotoSansArabic[wght].ttf",  None, ("ar",),
     "DejaVuSans.ttf"),
    ("NotoSansBengali.ttf",      "NotoSansBengali[wght].ttf", None, ("bn",),
     "DejaVuSans.ttf"),
    ("NotoSansDevanagari.ttf",   "NotoSansDevanagari[wght].ttf", None, ("hi",),
     "DejaVuSans.ttf"),
)

# Where the full Noto faces live on this machine (Fedora package names in
# parentheses). Extra --source-dir arguments are searched first.
SOURCE_DIRS = (
    "/usr/share/fonts/google-noto-sans-cjk-vf-fonts",
    "/usr/share/fonts/google-noto-sans-mono-cjk-vf-fonts",
    "/usr/share/fonts/google-noto-vf",
)
SOURCE_PACKAGES = (
    "google-noto-sans-cjk-vf-fonts",
    "google-noto-sans-mono-cjk-vf-fonts",
    "google-noto-sans-arabic-vf-fonts",
    "google-noto-sans-bengali-vf-fonts",
    "google-noto-sans-devanagari-vf-fonts",
)


def translation_characters():
    """Every character the catalogues use, per language, as sets.

    Parsed with `polib` rather than by hand, for the same reason font_coverage
    uses it: a raw decode corrupts UTF-8 and reports false gaps. `polib` is
    already a hard dependency of the game.
    """
    import polib

    used = {}
    for name in sorted(os.listdir(I18N)):
        language = os.path.join(I18N, name)
        if not os.path.isdir(language):
            continue
        characters = set()
        for filename in sorted(os.listdir(language)):
            if not filename.endswith(".po"):
                continue
            catalogue = polib.pofile(os.path.join(language, filename))
            for entry in catalogue:
                values = [entry.msgstr]
                values.extend((entry.msgstr_plural or {}).values())
                for value in values:
                    characters.update(ch for ch in (value or "") if ch.strip())
        if characters:
            used[name] = characters
    return used


def corpus_for(languages, used):
    """The characters one face must draw: its languages plus the base set."""
    chars = set(BASE)
    for language in languages:
        chars |= used.get("lang_" + language, set())
    return chars


def find_source(basename, extra_dirs):
    for directory in tuple(extra_dirs) + SOURCE_DIRS:
        path = os.path.join(directory, basename)
        if os.path.isfile(path):
            return path
    return None


def cmap_points(font):
    points = set()
    for table in font["cmap"].tables:
        points |= set(table.cmap.keys())
    return points


def load_donor(path, upem):
    """The DejaVu face, rescaled onto the host's units per em.

    DejaVu is drawn on a 2048-unit grid and every Noto face here on a 1000-unit
    one, so a glyph copied across without rescaling lands at twice its size.
    fontTools rescales the whole font at once, which also fixes the advance
    widths and the offsets inside composite glyphs.
    """
    from fontTools.ttLib import TTFont
    from fontTools.ttLib.scaleUpem import scale_upem

    donor = TTFont(path)
    if donor["head"].unitsPerEm != upem:
        scale_upem(donor, upem)
    return donor


def copy_glyphs(font, donor, codepoints):
    """Copy the glyphs for these codepoints out of DejaVu.

    Returns the codepoints DejaVu has no glyph for, which is the caller's cue
    to say so and stop. Both fonts must hold TrueType outlines, which the three
    script faces here do.

    A copied glyph loses its hinting program: TrueType instructions refer to
    the donor's control values and functions, and in a host that has neither
    they are worse than running unhinted.
    """
    from copy import deepcopy
    from fontTools.ttLib.tables import ttProgram

    donor_cmap = donor.getBestCmap()
    host_metrics = font["hmtx"].metrics
    order = list(font.getGlyphOrder())
    mapped = {}
    imported = {}

    def import_glyph(donor_name):
        if donor_name in imported:
            return imported[donor_name]
        host_name = "dv_" + donor_name
        imported[donor_name] = host_name
        glyph = deepcopy(donor["glyf"][donor_name])
        if glyph.isComposite():
            for component in glyph.components:
                component.glyphName = import_glyph(component.glyphName)
        glyph.program = ttProgram.Program()
        font["glyf"].glyphs[host_name] = glyph
        host_metrics[host_name] = donor["hmtx"][donor_name]
        order.append(host_name)
        return host_name

    left_over = set()
    for codepoint in sorted(codepoints):
        donor_name = donor_cmap.get(codepoint)
        if donor_name is None:
            left_over.add(codepoint)
            continue
        mapped[codepoint] = import_glyph(donor_name)

    for table in font["cmap"].tables:
        if table.isUnicode():
            table.cmap.update(mapped)
    font.setGlyphOrder(order)
    font["maxp"].numGlyphs = len(order)
    return left_over


def draw_charstrings(font, donor, codepoints):
    """Draw these glyphs into a face held in PostScript outlines.

    The CJK collection is CFF2, where a TrueType glyph cannot be pasted: the
    outlines are charstrings and the glyph order is an index. So the donor
    glyph is replayed through a pen and compiled instead. Curves arrive as
    cubics and round slightly differently, but the result is an ordinary static
    charstring that needs nothing from DejaVu when the game draws it.

    Returns the codepoints DejaVu has no glyph for, as the TrueType path does.
    """
    from fontTools.pens.t2CharStringPen import T2CharStringPen

    cff = font["CFF2"].cff
    top_dict = cff[cff.fontNames[0]]
    char_strings = top_dict.CharStrings
    global_subrs = top_dict.GlobalSubrs
    # Read now, while maxp still describes the file on disk: FDSelect carries
    # one entry per glyph and is decompiled against that count.
    fd_select = getattr(top_dict, "FDSelect", None)
    if hasattr(top_dict, "FDArray"):
        private = top_dict.FDArray[0].Private
    else:
        private = top_dict.Private

    donor_cmap = donor.getBestCmap()
    donor_set = donor.getGlyphSet()
    order = list(font.getGlyphOrder())
    horizontal = font["hmtx"].metrics
    vertical = font["vmtx"].metrics if "vmtx" in font else None
    # Vertical writing is not what the game does, but vmtx has to carry an
    # entry for every glyph or the table cannot be written at all.
    em = font["head"].unitsPerEm
    ascent = getattr(font["OS/2"], "sTypoAscender", font["head"].yMax)
    drawn = {}
    left_over = set()

    for codepoint in sorted(codepoints):
        donor_name = donor_cmap.get(codepoint)
        if donor_name is None:
            left_over.add(codepoint)
            continue
        advance, bearing = donor["hmtx"][donor_name]
        # A CFF2 charstring carries no width -- it comes from hmtx -- and the
        # pen refuses to write one, so it is given none.
        pen = T2CharStringPen(None, donor_set, CFF2=True)
        donor["glyf"][donor_name].draw(pen, donor["glyf"])
        # Named the way fontTools names a glyph it finds through the cmap, so
        # that the name still matches the cmap entry when the file is read back
        # (a CFF2 face stores no glyph names of its own).
        name = "uni%04X" % codepoint
        char_strings.charStringsIndex.append(
            pen.getCharString(private=private, globalSubrs=global_subrs))
        char_strings.charStrings[name] = len(char_strings.charStringsIndex.items) - 1
        if fd_select is not None:
            # One font dict for every glyph here, so the new glyph joins the
            # last one's.
            fd_select.append(fd_select[-1] if len(fd_select) else 0)
        order.append(name)
        horizontal[name] = (advance, bearing)
        if vertical is not None:
            vertical[name] = (em, ascent - donor["glyf"][donor_name].yMax)
        drawn[codepoint] = name

    for table in font["cmap"].tables:
        if table.isUnicode():
            table.cmap.update(drawn)
    font.setGlyphOrder(order)
    font["maxp"].numGlyphs = len(order)
    return left_over


def import_outlines(font, donor, codepoints):
    """Bring these glyphs across, whichever outline format the face holds."""
    if "glyf" in font:
        return copy_glyphs(font, donor, codepoints)
    return draw_charstrings(font, donor, codepoints)


def replace_notdef(font, donor):
    """Give the face DejaVu's hollow box where its own .notdef is empty.

    A character a face cannot draw falls back to .notdef, and the Noto faces
    here leave that glyph with no outline: the player sees a gap the width of a
    space, which reads as a typo or a lost character rather than as a missing
    glyph. DejaVu's .notdef is the drawn box the rest of the machine shows.

    .notdef is glyph 0 in every one of these faces, so this rewrites index 0
    and nothing else. No glyph is added, renamed or reordered, and the metrics
    arrays keep their lengths.
    """
    from fontTools.pens.t2CharStringPen import T2CharStringPen
    from fontTools.pens.ttGlyphPen import TTGlyphPen
    from fontTools.ttLib.tables import ttProgram

    notdef = font.getGlyphOrder()[0]
    donor_name = donor.getGlyphOrder()[0]
    source = donor["glyf"][donor_name]
    advance, bearing = donor["hmtx"][donor_name]

    if "glyf" in font:
        # Through a pen rather than a copy, so a composite donor glyph arrives
        # as plain contours instead of components naming glyphs this face has
        # not got.
        pen = TTGlyphPen(None)
        source.draw(pen, donor["glyf"])
        glyph = pen.glyph()
        glyph.program = ttProgram.Program()
        font["glyf"].glyphs[notdef] = glyph
    else:
        cff = font["CFF2"].cff
        top_dict = cff[cff.fontNames[0]]
        if hasattr(top_dict, "FDArray"):
            private = top_dict.FDArray[0].Private
        else:
            private = top_dict.Private
        pen = T2CharStringPen(None, donor.getGlyphSet(), CFF2=True)
        source.draw(pen, donor["glyf"])
        top_dict.CharStrings[notdef] = pen.getCharString(
            private=private, globalSubrs=top_dict.GlobalSubrs)

    font["hmtx"].metrics[notdef] = (advance, bearing)


def fill_gaps(font, needed, donor):
    """Make the face draw every character in `needed`, or say which it cannot.

    Returns the set of codepoints it could not draw. The face is a subset of
    one typeface, so what is missing after subsetting is exactly what the
    source face never had; this completes those from the theme's DejaVu.
    """
    missing = {ord(char) for char in needed} - cmap_points(font)
    if not missing:
        return set()
    return import_outlines(font, donor, missing)


def register_variation_indices(font, added, previous):
    """Give new glyphs an entry in the HVAR and VVAR delta-set maps.

    Those maps hold one index per glyph and are rebuilt at write time from a
    name-keyed dict, so a glyph the dict never mentions stops the font being
    written at all. The glyphs added here are static outlines with static
    advances and the game never applies a variation, so the index only has to
    be valid: they take the one the last source glyph already uses.
    """
    from fontTools.ttLib.tables.otTables import VarIdxMap

    if not added:
        return
    for tag in ("HVAR", "VVAR"):
        if tag not in font:
            continue
        for var_idx_map in vars(font[tag].table).values():
            if not isinstance(var_idx_map, VarIdxMap):
                continue
            if not getattr(var_idx_map, "mapping", None):
                continue
            fallback = var_idx_map.mapping[previous]
            for name in added:
                var_idx_map.mapping[name] = fallback


def problems_with(data, corpus):
    """Read the font back the way another tool would, and say what is wrong.

    A font can be written with a per-glyph table one entry short and still draw
    in FreeType, which guesses rather than complains; fontTools, ots and the
    rest of the toolchain will refuse it. The CJK faces carry three such arrays
    (hmtx, vmtx and the CFF2 FDSelect) and the build got the last of them wrong
    once, so it reads its own output before trusting it.
    """
    from fontTools.ttLib import TTFont

    problems = []
    reloaded = TTFont(io.BytesIO(data))
    order = reloaded.getGlyphOrder()
    if reloaded["maxp"].numGlyphs != len(order):
        problems.append("maxp says %d glyphs, the order has %d"
                        % (reloaded["maxp"].numGlyphs, len(order)))
    for tag in ("hmtx", "vmtx"):
        if tag in reloaded:
            entries = len(reloaded[tag].metrics)
            if entries != len(order):
                problems.append("%s has %d entries for %d glyphs"
                                % (tag, entries, len(order)))
    # A blank .notdef is worse than an ugly one: an undrawable character would
    # render as a space, so a translation with one gap looks like a typo rather
    # than like a font that is missing the glyph.
    notdef = order[0]
    if reloaded["hmtx"].metrics[notdef][0] <= 0:
        problems.append("the .notdef glyph has no advance width")
    if "glyf" in reloaded:
        empty = reloaded["glyf"][notdef].numberOfContours == 0
    else:
        # A CFF2 charstring read straight out of the index keeps its bytecode
        # but will not decompile without the private dict, so the bytecode is
        # what says whether there is an outline at all.
        cff = reloaded["CFF2"].cff
        char_strings = cff[cff.fontNames[0]].CharStrings
        empty = not char_strings.charStringsIndex[
            char_strings.charStrings[notdef]].bytecode
    if empty:
        problems.append("the .notdef glyph has no outline, so it draws as a "
                        "space")
    if "CFF2" in reloaded:
        cff = reloaded["CFF2"].cff
        top_dict = cff[cff.fontNames[0]]
        if len(top_dict.CharStrings) != len(order):
            problems.append("CFF2 has %d charstrings for %d glyphs"
                            % (len(top_dict.CharStrings), len(order)))
        if top_dict.FDSelect is not None and len(top_dict.FDSelect) != len(order):
            problems.append("CFF2 FDSelect has %d entries for %d glyphs"
                            % (len(top_dict.FDSelect), len(order)))
    missing = {ord(char) for char in corpus} - cmap_points(reloaded)
    if missing:
        problems.append("the font as read back cannot draw %r"
                        % "".join(sorted(chr(cp) for cp in missing))[:48])
    return problems


def main(argv):
    check_only = "--check" in argv
    extra_dirs = []
    for arg in argv:
        if arg == "--source-dir":
            continue
        if arg.startswith("--source-dir="):
            extra_dirs.append(arg.split("=", 1)[1])

    from fontTools import subset
    from fontTools.ttLib import TTFont, TTCollection

    used = translation_characters()

    total = 0
    for out_name, src_name, face, languages, donor_name in FACES:
        corpus = corpus_for(languages, used)
        source = find_source(src_name, extra_dirs)
        if source is None:
            sys.stderr.write(
                "source face %s not found; install one of: %s\n"
                % (src_name, ", ".join(SOURCE_PACKAGES)))
            return 1

        if face is None:
            font = TTFont(source)
        else:
            font = TTCollection(source, lazy=True).fonts[face]

        options = subset.Options()
        options.instance = "wght=400"   # pin the variable font to Regular
        options.glyph_names = False
        runner = subset.Subsetter(options)
        runner.populate(text="".join(sorted(corpus)))
        runner.subset(font)

        # Whatever the source face could not draw is drawn in from DejaVu. The
        # invariant afterwards is the strong one: the face draws the whole
        # corpus, not merely as much of it as its typeface happens to have.
        donor_path = os.path.join(OUT_DIR, donor_name)
        if not os.path.isfile(donor_path):
            sys.stderr.write(
                "completion face %s not found in %s\n"
                % (donor_name, OUT_DIR))
            return 1
        before = {ord(char) for char in corpus} - cmap_points(font)
        original_order = font.getGlyphOrder()
        last_source_glyph = original_order[-1]
        donor = load_donor(donor_path, font["head"].unitsPerEm)
        left_over = fill_gaps(font, corpus, donor)
        if left_over:
            sys.stderr.write(
                "%s: no face on hand can draw %d corpus characters: %r\n"
                % (out_name, len(left_over),
                   "".join(sorted(chr(cp) for cp in left_over))[:48]))
            return 1
        known = set(original_order)
        added = [name for name in font.getGlyphOrder() if name not in known]
        register_variation_indices(font, added, last_source_glyph)
        unfilled = {ord(char) for char in corpus} - cmap_points(font)
        if unfilled:
            sys.stderr.write(
                "%s: still cannot draw %d corpus characters: %r\n"
                % (out_name, len(unfilled),
                   "".join(sorted(chr(cp) for cp in unfilled))[:48]))
            return 1

        # An undrawable character has to look like a box, not like a space.
        replace_notdef(font, donor)

        # hhea and vhea are written before hmtx and vmtx, and those two tables
        # set the long-metric count as they compile. Compile them once here so
        # the header ends up carrying the count the table is written with.
        for metrics_tag in ("hmtx", "vmtx"):
            if metrics_tag in font:
                font[metrics_tag].compile(font)

        if check_only:
            # Measure the subset without writing it: serialize to memory.
            buffer = io.BytesIO()
            font.save(buffer)
            data = buffer.getvalue()
        else:
            out_path = os.path.join(OUT_DIR, out_name)
            font.save(out_path)
            with open(out_path, "rb") as fd:
                data = fd.read()
        total += len(data)

        problems = problems_with(data, corpus)
        if problems:
            for problem in problems:
                sys.stderr.write("%s: %s\n" % (out_name, problem))
            return 1

        if check_only:
            print("%-24s %8.0f KB   (from %s, corpus %d chars, %d from %s)"
                  % (out_name, len(data) / 1024, src_name, len(corpus),
                     len(before), donor_name))
        else:
            print("%-24s %8.0f KB   -> %s"
                  % (out_name, len(data) / 1024, out_name))

    verb = "would write" if check_only else "wrote"
    print("\n%s %d faces, %.2f MB total" % (verb, len(FACES), total / 1024 / 1024))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
