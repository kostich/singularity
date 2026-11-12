#!/usr/bin/env python3
"""Measure a candidate font against the characters this game actually draws.

"Supports Cyrillic" is a marketing claim. What matters is whether the glyphs
exist for the strings the shipped translations contain, at the sizes the theme
uses, in the two faces the theme names. This script answers that question and
nothing else, and it exists because the answer was surprising twice:

* the original theme's `special` face, `acknowtt.ttf`, has **no Cyrillic and no
  Greek at all** -- 259 glyphs, Latin only;
* the 2030 theme's face, Exo 2, has Cyrillic but **no Greek**.

Neither is a crash, because a missing glyph renders as a blank or a box and the
game keeps running, which is precisely why it goes unnoticed.

Usage:

    python3 utils/font_coverage.py                       # the shipped themes
    python3 utils/font_coverage.py path/to/Font.ttf ...  # candidates

Needs `fontTools`, which is not a dependency of the game -- it is a build-time
tool, like the art generators. It reads the `.po` catalogues directly, so no
translation is compiled for it to work, and it writes nothing.
"""

import os
import sys
import unicodedata

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
I18N = os.path.join(REPO_ROOT, "singularity", "i18n")
THEMES = os.path.join(REPO_ROOT, "singularity", "data", "themes")


def translation_characters():
    """Every character the catalogues actually use, per language, as sets.

    Parsed with `polib` rather than by hand. The first version of this decoded
    the raw file with `unicode_escape`, which round-trips ASCII but corrupts
    UTF-8: every Cyrillic character came back as a control code, and the report
    duly announced that the shipped font was missing all 32 of them. `polib` is
    already a hard dependency of the game, so it is the honest parser to use.
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


def font_coverage(path):
    """(name, glyph count, set of code points) for one font file."""
    from fontTools.ttLib import TTFont

    font = TTFont(path, fontNumber=0)
    points = set()
    for table in font["cmap"].tables:
        points |= set(table.cmap.keys())
    return font["name"].getDebugName(1), points


def scripts_of(characters):
    """Group characters by the script Unicode says they belong to."""
    groups = {}
    for character in characters:
        try:
            name = unicodedata.name(character)
        except ValueError:
            continue
        script = name.split(" ", 1)[0]
        groups.setdefault(script, set()).add(character)
    return groups


def report(path, used):
    try:
        name, points = font_coverage(path)
    except Exception as error:                       # noqa: BLE001 - reported
        print("%-42s could not be read: %s" % (os.path.basename(path), error))
        return False

    print("%s" % (os.path.basename(path),))
    print("  family      %s" % (name,))
    print("  glyphs      %d" % (len(points),))

    ok = True
    for language in sorted(used):
        characters = used[language]
        missing = {ch for ch in characters if ord(ch) not in points}
        scripts = scripts_of(characters)
        summary = ", ".join("%s %d" % (script, len(chars))
                            for script, chars in sorted(scripts.items()))
        if missing:
            ok = False
            print("  %-12s MISSING %3d of %3d  (%s)"
                  % (language.replace("lang_", ""), len(missing),
                     len(characters),
                     "".join(sorted(missing))[:48]))
        else:
            print("  %-12s complete    %3d  (%s)"
                  % (language.replace("lang_", ""), len(characters), summary))
    return ok


def shipped_faces():
    """Every face the shipped themes name, as absolute paths."""
    faces = []
    for theme_id in sorted(os.listdir(THEMES)):
        path = os.path.join(THEMES, theme_id, "theme.dat")
        if not os.path.exists(path):
            continue
        directory = os.path.join(THEMES, theme_id, "fonts")
        with open(path, "r", encoding="utf-8") as handle:
            for line in handle:
                if "=" not in line or line.lstrip().startswith("#"):
                    continue
                key, value = line.split("=", 1)
                if key.strip() not in ("normal", "special"):
                    continue
                filename = value.strip()
                for candidate in (os.path.join(directory, filename),
                                  os.path.join(directory, "..", filename)):
                    if os.path.exists(candidate):
                        faces.append((theme_id + " " + key.strip(),
                                      os.path.abspath(candidate)))
                        break
    return faces


def main(argv):
    used = translation_characters()
    total = set()
    for characters in used.values():
        total |= characters
    print("%d languages, %d distinct characters between them\n"
          % (len(used), len(total)))

    if argv:
        candidates = [(os.path.basename(path), path) for path in argv]
    else:
        candidates = shipped_faces()

    failures = 0
    for label, path in candidates:
        print("=== %s" % (label,))
        if not report(path, used):
            failures += 1
        print()
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
