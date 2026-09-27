"""Adversarial tests for vad2mqtt.utils."""

from __future__ import annotations

import numpy as np

from vad2mqtt.utils import Throttler, rms_dbfs


class TestRmsDbfs:
    def test_empty_array_returns_floor(self):
        assert rms_dbfs(np.array([], dtype=np.float32)) == -96.0

    def test_all_zeros_returns_floor(self):
        assert rms_dbfs(np.zeros(1024, dtype=np.float32)) == -96.0

    def test_full_scale_sine_near_zero_dbfs(self):
        t = np.linspace(0, 1, 16000, dtype=np.float64)
        sine = np.sin(2 * np.pi * 440 * t)
        db = rms_dbfs(sine)
        # RMS of a full-scale sine is ~1/sqrt(2) => ~-3 dBFS
        assert -4.0 < db < -2.0

    def test_negative_values_do_not_crash(self):
        samples = np.full(100, -0.5, dtype=np.float32)
        db = rms_dbfs(samples)
        assert db < 0.0

    def test_nan_input_returns_nan_not_raise(self):
        samples = np.array([np.nan, np.nan], dtype=np.float64)
        # sqrt(mean(nan**2)) is nan, log10(nan) is nan — must not raise.
        result = rms_dbfs(samples)
        assert np.isnan(result)


class TestThrottler:
    def test_first_call_always_publishes(self):
        t = Throttler(interval=1.0, delta=1.0)
        assert t.should_publish(10.0) is True

    def test_within_interval_and_within_delta_is_suppressed(self):
        t = Throttler(interval=1000.0, delta=5.0)
        assert t.should_publish(10.0) is True
        assert t.should_publish(11.0) is False

    def test_within_interval_but_delta_exceeded_publishes(self):
        t = Throttler(interval=1000.0, delta=1.0)
        assert t.should_publish(10.0) is True
        assert t.should_publish(50.0) is True

    def test_zero_delta_always_publishes_regardless_of_interval(self):
        # abs(diff) < delta is never true when delta == 0, so the delta
        # branch can never suppress a publish.
        t = Throttler(interval=1000.0, delta=0.0)
        assert t.should_publish(10.0) is True
        assert t.should_publish(10.0) is True

    def test_negative_delta_always_bypasses_interval(self):
        t = Throttler(interval=1000.0, delta=-1.0)
        assert t.should_publish(10.0) is True
        assert t.should_publish(10.0) is True

    def test_interval_elapsed_publishes_even_without_delta_change(self, monkeypatch):
        times = iter([100.0, 100.5, 200.0])

        def fake_time():
            return next(times)

        monkeypatch.setattr("vad2mqtt.utils.time.time", fake_time)
        t = Throttler(interval=1.0, delta=100.0)
        assert t.should_publish(10.0) is True  # t=100, first call
        assert t.should_publish(10.0) is False  # t=100.5, within interval+delta
        assert t.should_publish(10.0) is True  # t=200, interval elapsed
