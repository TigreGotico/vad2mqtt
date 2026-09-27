"""Test setup shared across the suite.

Injects a stub ``sounddevice`` module before anything imports
``vad2mqtt.audio`` — the real package requires libportaudio, which is not
installed in CI / sandboxed test environments and no audio hardware is
available anyway.
"""

from __future__ import annotations

import sys
import types


def _install_sounddevice_stub() -> None:
    if "sounddevice" in sys.modules:
        return

    stub = types.ModuleType("sounddevice")

    class PortAudioError(Exception):
        pass

    class CallbackStop(Exception):
        pass

    class _FakeInputStream:
        """No-op context manager standing in for sd.InputStream."""

        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs

        def __enter__(self):
            return self

        def __exit__(self, *exc_info):
            return False

    def query_devices():
        return []

    stub.PortAudioError = PortAudioError
    stub.CallbackStop = CallbackStop
    stub.InputStream = _FakeInputStream
    stub.query_devices = query_devices

    sys.modules["sounddevice"] = stub


_install_sounddevice_stub()
