"""Adversarial tests for vad2mqtt.vad_engine.VADEngine's is_silence fallback.

The OPM plugin's real is_silence(chunk) takes one positional argument (int16
PCM bytes). These tests pin that contract against regression — the fallback
used to call is_silence(frame, sample_rate) with a float32 ndarray, which
always raised and silently degraded get_probability() to 0.0.
"""

from __future__ import annotations

import numpy as np
import pytest

from vad2mqtt.vad_engine import VADEngine


class _FakeEngine:
    """Stands in for an OPM VAD plugin instance."""

    def __init__(self, vad_raises=True, is_silence_return=False, is_silence_raises=False):
        self._vad_raises = vad_raises
        self._is_silence_return = is_silence_return
        self._is_silence_raises = is_silence_raises
        self.is_silence_calls = []
        self.sample_rate = 16000

    def vad(self, frame):
        if self._vad_raises:
            raise RuntimeError("boom")
        return np.array(0.9)

    def is_silence(self, *args):
        self.is_silence_calls.append(args)
        if self._is_silence_raises:
            raise RuntimeError("is_silence boom")
        return self._is_silence_return


def _make_engine(fake_engine) -> VADEngine:
    """Build a VADEngine without going through OVOSVADFactory / plugin loading."""
    engine = VADEngine.__new__(VADEngine)
    engine._engine = fake_engine
    engine.sample_rate = fake_engine.sample_rate
    engine.model_name = "fake-vad-plugin"
    return engine


class TestIsSilenceFallbackCallSignature:
    def test_fallback_calls_is_silence_with_single_positional_int16_bytes_arg(self):
        fake = _FakeEngine(vad_raises=True, is_silence_return=False)
        engine = _make_engine(fake)
        frame = np.zeros(320, dtype=np.float32)

        engine.get_probability(frame)

        assert len(fake.is_silence_calls) == 1
        call_args = fake.is_silence_calls[0]
        assert len(call_args) == 1  # exactly one positional arg
        chunk = call_args[0]
        assert isinstance(chunk, bytes)
        # int16 PCM: 320 samples * 2 bytes/sample
        assert len(chunk) == 320 * 2

    def test_fallback_speech_when_not_silent(self):
        fake = _FakeEngine(vad_raises=True, is_silence_return=False)
        engine = _make_engine(fake)
        frame = np.ones(160, dtype=np.float32) * 0.5

        prob = engine.get_probability(frame)

        assert prob == 1.0

    def test_fallback_silence_returns_zero(self):
        fake = _FakeEngine(vad_raises=True, is_silence_return=True)
        engine = _make_engine(fake)
        frame = np.zeros(160, dtype=np.float32)

        prob = engine.get_probability(frame)

        assert prob == 0.0

    def test_both_vad_and_is_silence_fail_returns_zero_not_raise(self):
        fake = _FakeEngine(vad_raises=True, is_silence_raises=True)
        engine = _make_engine(fake)
        frame = np.zeros(160, dtype=np.float32)

        prob = engine.get_probability(frame)

        assert prob == 0.0

    def test_primary_vad_path_used_when_available(self):
        fake = _FakeEngine(vad_raises=False)
        engine = _make_engine(fake)
        frame = np.zeros(160, dtype=np.float32)

        prob = engine.get_probability(frame)

        assert prob == pytest.approx(0.9)
        # is_silence should not have been consulted at all
        assert fake.is_silence_calls == []

    def test_is_speech_uses_is_silence_with_single_arg(self):
        fake = _FakeEngine(is_silence_return=False)
        engine = _make_engine(fake)
        frame = np.ones(160, dtype=np.float32) * 0.5

        assert engine.is_speech(frame) is True
        assert len(fake.is_silence_calls[-1]) == 1

    def test_is_speech_falls_back_to_probability_when_is_silence_raises(self):
        fake = _FakeEngine(vad_raises=False, is_silence_raises=True)
        engine = _make_engine(fake)
        frame = np.zeros(160, dtype=np.float32)

        # get_probability via vad() returns 0.9 >= default threshold 0.5
        assert engine.is_speech(frame) is True


class TestToPcm16:
    def test_clips_out_of_range_values(self):
        frame = np.array([2.0, -2.0, 0.0], dtype=np.float32)
        chunk = VADEngine._to_pcm16(frame)
        samples = np.frombuffer(chunk, dtype=np.int16)
        assert samples[0] == 32767
        assert samples[1] == -32767
        assert samples[2] == 0

    def test_empty_frame_produces_empty_bytes(self):
        frame = np.array([], dtype=np.float32)
        chunk = VADEngine._to_pcm16(frame)
        assert chunk == b""
