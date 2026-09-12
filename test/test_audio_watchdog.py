"""Adversarial tests for AudioMonitor's watchdog and frame-consumption fix.

Constructed without opening a real audio stream (no hardware / no ALSA in
CI): VADEngine plugin loading is monkeypatched out, and sounddevice is a
stub injected by conftest.py before this module imports vad2mqtt.audio.
"""

from __future__ import annotations

import numpy as np
import pytest

import vad2mqtt.audio as audio_mod
from vad2mqtt.audio import AudioMonitor
from vad2mqtt.config import Config


class _FakeVADEngine:
    sample_rate = 16000
    model_name = "fake-vad-plugin"


@pytest.fixture(autouse=True)
def no_real_plugin(monkeypatch):
    """AudioMonitor.__init__ instantiates VADEngine() — replace with a stub
    so no OPM plugin is loaded and no model file is fetched."""
    monkeypatch.setattr(audio_mod, "VADEngine", lambda: _FakeVADEngine())


def _make_monitor() -> AudioMonitor:
    return AudioMonitor(on_vad=lambda p: None, on_noise=lambda d: None)


class TestIsHealthy:
    def test_unhealthy_before_start_no_started_ts(self):
        mon = _make_monitor()
        # Never started: _started_ts is None -> `now` used as `started`,
        # so is_healthy() is trivially True right at "now - now < timeout".
        assert mon._started_ts is None
        assert mon._last_frame_ts is None
        assert mon.is_healthy() is True

    def test_healthy_during_startup_grace_period_with_no_frame_yet(self, monkeypatch):
        mon = _make_monitor()
        monkeypatch.setattr(Config, "WATCHDOG_TIMEOUT", 30.0)
        fake_now = [1000.0]
        monkeypatch.setattr(audio_mod.time, "monotonic", lambda: fake_now[0])
        mon._started_ts = 1000.0
        fake_now[0] = 1000.0 + 10.0  # 10s in, well within 30s grace
        assert mon.is_healthy() is True

    def test_unhealthy_after_startup_grace_period_expires_with_no_frame(self, monkeypatch):
        mon = _make_monitor()
        monkeypatch.setattr(Config, "WATCHDOG_TIMEOUT", 30.0)
        fake_now = [1000.0]
        monkeypatch.setattr(audio_mod.time, "monotonic", lambda: fake_now[0])
        mon._started_ts = 1000.0
        fake_now[0] = 1000.0 + 31.0  # past the 30s grace, still no frame
        assert mon.is_healthy() is False

    def test_healthy_when_frame_arrived_recently(self, monkeypatch):
        mon = _make_monitor()
        monkeypatch.setattr(Config, "WATCHDOG_TIMEOUT", 30.0)
        fake_now = [2000.0]
        monkeypatch.setattr(audio_mod.time, "monotonic", lambda: fake_now[0])
        mon._last_frame_ts = 2000.0
        fake_now[0] = 2000.0 + 5.0
        assert mon.is_healthy() is True

    def test_unhealthy_when_last_frame_older_than_timeout(self, monkeypatch):
        mon = _make_monitor()
        monkeypatch.setattr(Config, "WATCHDOG_TIMEOUT", 30.0)
        fake_now = [2000.0]
        monkeypatch.setattr(audio_mod.time, "monotonic", lambda: fake_now[0])
        mon._last_frame_ts = 2000.0
        fake_now[0] = 2000.0 + 30.1  # just past the timeout
        assert mon.is_healthy() is False

    def test_last_frame_ts_takes_priority_over_started_ts(self, monkeypatch):
        """Once a frame has arrived, further health checks must use
        _last_frame_ts, not fall back to the startup grace period."""
        mon = _make_monitor()
        monkeypatch.setattr(Config, "WATCHDOG_TIMEOUT", 30.0)
        fake_now = [5000.0]
        monkeypatch.setattr(audio_mod.time, "monotonic", lambda: fake_now[0])
        mon._started_ts = 0.0  # ancient startup, would fail grace period alone
        mon._last_frame_ts = 4999.0  # but a frame just arrived
        assert mon.is_healthy() is True


class TestFrameConsumption:
    def test_process_loop_clears_frame_after_reading_it(self, monkeypatch):
        """Regression test for the stale-frame-reprocessing bug: once the
        worker reads _latest_frame it must clear it under the lock so a dead
        callback (no new frames) does not cause endless re-scoring of the
        same stale frame."""
        mon = _make_monitor()
        monkeypatch.setattr(Config, "VAD_SAMPLE_INTERVAL", 0.0)
        monkeypatch.setattr(Config, "PUBLISH_INTERVAL", 999.0)

        mon._latest_frame = np.zeros(160, dtype=np.float32)
        mon._running = True

        call_count = {"n": 0}

        def fake_get_probability(frame):
            call_count["n"] += 1
            mon._running = False  # stop the loop right after the first score
            return 0.0

        mon.vad.get_probability = fake_get_probability

        mon._process_loop()

        # The frame must have been consumed (set to None) after being read.
        assert mon._latest_frame is None
        # And with no new frame ever arriving, only the first iteration
        # should have actually scored something.
        assert call_count["n"] == 1

    def test_no_frame_available_does_not_call_vad(self, monkeypatch):
        mon = _make_monitor()
        mon._latest_frame = None
        mon._running = True

        calls = []
        mon.vad.get_probability = lambda frame: calls.append(frame)

        # Loop would spin forever with frame=None; bound iterations via a
        # fake time.sleep instead of relying on vad() ever being called.
        iterations = [0]

        def bounded_sleep(_secs):
            iterations[0] += 1
            if iterations[0] > 5:
                mon._running = False

        monkeypatch.setattr(audio_mod.time, "sleep", bounded_sleep)

        mon._process_loop()

        assert calls == []
