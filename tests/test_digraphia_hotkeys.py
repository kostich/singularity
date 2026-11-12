"""A mnemonic fires for the letter the layout produced, in either script.

No real keyboard layout is involved. The event carries the character
pygame would put in `event.unicode`, and the key code is left unknown so
the match cannot cheat by looking at a scancode.
"""

import pygame

from singularity.code.graphics import button, dialog


def _fired(hotkey, typed):
    """Which button, marked `hotkey`, runs when `typed` arrives."""
    top = dialog.Dialog()
    top.visible = True
    hit = []
    button.FunctionButton(
        top, (0, 0), (0.1, 0.05),
        text=hotkey, hotkey=hotkey,
        function=lambda: hit.append(hotkey))
    top.handle(pygame.event.Event(
        pygame.KEYDOWN, {"key": pygame.K_UNKNOWN, "unicode": typed}))
    top.visible = False
    return hit


def test_cyrillic_i_matches_latin_i_and_itself(graphics):
    assert _fired("И", "i") == ["И"]
    assert _fired("И", "и") == ["И"]
    assert _fired("И", "a") == []
    assert _fired("И", "р") == []


def test_latin_r_matches_cyrillic_er_and_r(graphics):
    assert _fired("R", "р") == ["R"]
    assert _fired("R", "r") == ["R"]


def test_lja_does_not_match_l(graphics):
    assert _fired("љ", "l") == []
    assert _fired("l", "љ") == []
    assert _fired("љ", "љ") == ["љ"]


def test_je_matches_e_and_backwards_e_does_not(graphics):
    assert _fired("е", "e") == ["е"]
    assert _fired("э", "e") == []
    assert _fired("э", "э") == ["э"]


def test_hotkey_case_is_ignored(graphics):
    assert _fired("И", "I") == ["И"]
    assert _fired("и", "И") == ["и"]
    assert _fired("R", "Р") == ["R"]
    assert _fired("r", "R") == ["r"]
    assert _fired("ђ", "Đ") == ["ђ"]
    assert _fired("Đ", "ђ") == ["Đ"]
