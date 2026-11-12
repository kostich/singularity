DejaVu Sans and DejaVu Sans Mono — the 2030 theme's body and display faces.

Upstream
--------
DejaVu fonts 2.37, by the DejaVu fonts team (c)2004-2016, based on Bitstream
Vera 1.10.

    https://dejavu-fonts.github.io/

Obtained from the distribution packages `dejavu-sans-fonts` and
`dejavu-sans-mono-fonts`, so what ships here is the same binary every Fedora
user has. `DejaVuSans.ttf` is copied unchanged from `Legacy-default/fonts/`: it
is the face this game has always used for its body text, and that is the point.

Licence
-------
Bitstream Vera plus public domain, reproduced in the repository's `LICENSE.txt`
(the DejaVu section). It permits use, modification and redistribution with this
game, including in a GPL-2+ work.

Why these faces
---------------
This theme used Exo 2 before, and the choice was re-measured against what the
game actually draws rather than against a marketing claim:

    python3 utils/font_coverage.py

    Exo 2              914 glyphs   Greek: no    Cyrillic: yes
    DejaVu Sans       5097 glyphs   Greek: yes   Cyrillic: yes
    DejaVu Sans Mono  3359 glyphs   Greek: yes   Cyrillic: yes

Exo 2 has no Greek at all, and a player is free to want it. DejaVu Sans Mono
covers every character in the corpus tests/test_theme_fonts.py checks -- every
non-space character in the shipped catalogues, the .dat content, and the two
block glyphs the map draws as text (U+25AE, U+25B6) -- at every size the theme
uses, with no patching.

The design direction counts as much as the coverage. The original game's display
face was a hand-drawn "sticker" font and its body face was DejaVu Sans. Moving
to a geometric humanist sans took the look a long way from that; a monospace
console face for the labels and the original body face for the prose takes it
back, and reads as the instrument panel this theme's frame and palette already
describe.

The monospace face settles a bug for free: its digits are all one width, so
"DAY 1111" and "DAY 8888" occupy the same cells and a centred clock cannot slide
sideways as it counts. [dialog] tabular_digits does the same for a theme that
names a face with proportional figures.

What is not here
----------------
Neither DejaVu file was modified. The two Exo 2 files that used to sit here
were removed with the move to DejaVu; they remain in the history if the decision
is ever revisited, and utils/font_coverage.py is how to re-take it.

The seven non-Latin faces
-------------------------
Those two files carry Latin, Greek and Cyrillic and nothing else, and the game
ships translations in Arabic, Bengali, Devanagari, Japanese and Simplified
Chinese. So the theme names a face per language (theme_ar.dat, theme_bn.dat,
theme_hi.dat, theme_ja.dat, theme_zh_CN.dat) and those seven files are it:

    NotoSansArabic.ttf      37 KB
    NotoSansBengali.ttf    139 KB
    NotoSansDevanagari.ttf 185 KB
    NotoSansCJK-JP.ttf     687 KB
    NotoSansCJK-SC.ttf     680 KB
    NotoSansMonoCJK-JP.ttf 655 KB
    NotoSansMonoCJK-SC.ttf 656 KB

Upstream is Google's Noto, under the SIL Open Font License 1.1. The CJK faces
come from the variable collections (NotoSansCJK-VF.ttc, NotoSansMonoCJK-VF.ttc)
pinned at wght=400, which is the only instance pygame ever loads. Each file is
a subset: a full CJK face is 30 MB and 65,000 glyphs, and the game draws a few
hundred. That is 2.97 MB in total instead of 64 MB, and it is what makes the
Flatpak self-contained: a variant names a plain filename, find_files() resolves
it to this directory, and no system font is consulted.

They also carry glyphs their own typeface has never had. SDL_ttf takes one face
per font slot and has no per-character fallback, so a glyph the game draws has
to be in the face that draws it, and the game puts scripts side by side: the
readout that reads "Money" in English reads অর্থ 1000 under Bengali, digits and
all; the language menu names every row in English as well as natively, so a
player already reading Japanese can still find Arabic and Russian in the list;
and map.py draws the pause bar as U+25AE and the speed arrows as U+25B6 in the
body face. So the build completes every subset from DejaVu, which is not a
patch but a second face's outlines: Latin, digits and the whole printable ASCII
range are copied in, and where the host holds PostScript outlines (CFF2, which
is every CJK face here) the donor glyph is replayed through a pen and compiled
to a charstring.

The fallback glyph is DejaVu's too. Every Noto face here ships .notdef with no
outline at all, so a character none of them could draw rendered as a gap the
width of a space -- indistinguishable from a typo. The build replaces index 0,
which is .notdef in every one of these faces, with DejaVu's hollow box. No
glyph is added or reordered by that.

    python3 utils/subset_fonts.py            # rewrite all seven
    python3 utils/subset_fonts.py --check    # sizes only, writes nothing

Rebuild after adding translations: the subsets cover the catalogues as they
stand, not the ones you will write. The tool needs fontTools and the
distribution's Noto packages, not the game:

    sudo dnf install -y google-noto-sans-cjk-vf-fonts \
        google-noto-sans-mono-cjk-vf-fonts google-noto-sans-arabic-vf-fonts \
        google-noto-sans-bengali-vf-fonts google-noto-sans-devanagari-vf-fonts

Licence: SIL OFL 1.1, reproduced in LICENSE.txt (the Noto section), together
with the copyright line of each upstream family.
