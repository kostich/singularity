"""Every translated string keeps the `&` marker its English original has.

The game takes a button's mnemonic from the translated text, not from the
English one: `HotkeyText._retranslate()` runs the msgstr through
`g.hotkey()`, and a msgstr with no marker yields an empty key, so the button
silently loses its keyboard shortcut and its underlined letter. Nothing warns
about that at runtime, so this is checked here instead.

One case per catalogue, so a failure names the language and the file.
"""

import glob
import os

import polib
import pytest

from singularity.code import dirs
from singularity.code.g import hotkey


def _i18n_dir():
    """The catalogues in the checkout, not whatever is installed."""
    return os.path.normpath(
        os.path.join(os.path.dirname(dirs.__file__), "..", "i18n"))


def _catalogs():
    root = _i18n_dir()
    return sorted(glob.glob(os.path.join(root, "lang_*", "*.po")))


def _id(path):
    return "%s/%s" % (os.path.basename(os.path.dirname(path)),
                      os.path.basename(path))


def _translations(entry):
    """The texts the game would show for this entry.

    An untranslated entry falls back to its msgid, which carries the marker
    already, so only real translations are worth checking. For a plural entry
    every non-empty form counts: the game picks one of them by number.
    """
    if entry.msgid_plural:
        return [text for text in entry.msgstr_plural.values() if text]
    return [entry.msgstr] if entry.msgstr else []


def _missing_markers(path):
    missing = []
    for entry in polib.pofile(path):
        if entry.obsolete:
            continue
        if not hotkey(entry.msgid)["keys"]:
            continue
        for text in _translations(entry):
            if not hotkey(text)["keys"]:
                missing.append((entry.msgid, text))
    return missing


@pytest.mark.parametrize("catalog", _catalogs(), ids=_id)
def test_catalog_keeps_hotkey_markers(catalog):
    missing = _missing_markers(catalog)
    assert not missing, (
        "%d translation(s) in %s drop the '&' marker, so their buttons have "
        "no mnemonic: %r"
        % (len(missing), _id(catalog), missing))
