Lucide — the 2030 theme's button glyphs.

Upstream
--------
Lucide, tag 0.469.0.

    https://lucide.dev/
    https://github.com/lucide-icons/lucide/tree/0.469.0

These `.svg` files are the vendored sources, copied unchanged from that tag.
`utils/make_icon_set.py` rasterises them into `../images/icon_*.png`, which is
what the game actually loads; the SVGs are here so the artwork can be rebuilt
without a network, and so what the game ships is auditable.

Licence
-------
ISC — see `LICENSE` in this directory, which is the upstream file.

    Copyright (c) for portions of Lucide are held by Cole Bemis 2013-2022 as
    part of Feather (MIT). All other copyright (c) for Lucide are held by
    Lucide Contributors 2022.

ISC is why this set was chosen. It permits use, modification and redistribution
for any purpose provided the notice is kept, which is compatible with shipping
these inside a GPL-2+ game. Several better-known icon packs are not:
Papirus is GPL-3, Breeze is LGPL-3, and this project is GPL-2+ — a licence
question that cannot be resolved by attribution alone.

Which drawing becomes which glyph
---------------------------------
The name on the left is the art key the game asks for (`icon="icon_ok"`), so
replacing the artwork changed no call site. The name on the right is the file
in this directory.

    icon_ok         check               icon_save     save
    icon_cancel     x                   icon_delete   trash-2
    icon_back       chevron-left        icon_stats    chart-column
    icon_forward    chevron-right
    icon_prev       skip-back           icon_filter   filter
    icon_next       skip-forward        icon_warning  triangle-alert
    icon_play       play                icon_options  sliders-horizontal
    icon_pause      pause               icon_exit     log-out
    icon_load       folder-open         icon_report   file-text
    icon_research   flask-conical
    icon_knowledge  book-open
    icon_log        scroll-text

What this replaced
------------------
Fifteen glyphs were drawn from primitives in `utils/make_2030_art.py`: strokes
and polygons assembled by hand, then supersampled. They were consistent and
readable, and they were also fifteen small inventions standing in for a solved
problem — a set drawn by people who do this for a living, in the same style,
with the licence to prove it.

The stroke colour is substituted at build time (`currentColor` is a web-only
concept) with the theme's `ui_edge_bright`, `#5FE3FF`. The files are rasterised
at 256px and downsampled to the 64px a button asks for, with the alpha scaled
and the colour laid on flat — scaling a colour image averages RGB as well as
alpha and tints every edge.
