"""The freeze diagnostics must install handlers that survive a blocked thread.

Ctrl+C cannot interrupt a blocked SDL call: Python only runs its signal handler
between bytecodes, and the call never returns to the interpreter. That is why a
frozen game ignored Ctrl+C. faulthandler's handlers are C, so they run anyway.
"""

import faulthandler
import signal

from singularity.code import diagnostics


def test_installs_the_signal_handlers():
    installed = diagnostics.enable_freeze_diagnostics()

    assert "SIGQUIT" in installed
    assert "SIGUSR1" in installed
    assert faulthandler.is_enabled()


def test_survives_a_platform_without_those_signals(monkeypatch):
    monkeypatch.delattr(signal, "SIGQUIT", raising=False)
    monkeypatch.delattr(signal, "SIGUSR1", raising=False)

    # Must not raise, and must say that it registered nothing.
    assert diagnostics.enable_freeze_diagnostics() == ()


def test_enabling_twice_is_harmless():
    diagnostics.enable_freeze_diagnostics()
    installed = diagnostics.enable_freeze_diagnostics()

    assert "SIGQUIT" in installed
    assert faulthandler.is_enabled()


def test_the_hint_names_the_signal_and_this_process():
    hint = diagnostics.freeze_diagnostics_hint()

    # The player has to be able to act on it without knowing what faulthandler
    # is, so both the key and a copy-pasteable command must be there.
    assert "kill -USR1" in hint
    assert str(__import__("os").getpid()) in hint
