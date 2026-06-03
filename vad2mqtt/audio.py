"""Audio capture and VAD processing loop."""

from __future__ import annotations

import logging
import threading
import time

import numpy as np
import sounddevice as sd

from .config import Config
from .utils import Throttler, rms_dbfs
from .vad_engine import VADEngine

LOG = logging.getLogger(__name__)


class AudioMonitor:
    """Continuously captures audio, runs VAD, and emits callbacks."""

    def __init__(
        self,
        on_vad: callable,
        on_noise: callable,
        on_error: callable | None = None,
    ) -> None:
        self.vad = VADEngine()
        self.on_vad = on_vad
        self.on_noise = on_noise
        self.on_error = on_error
        self._running = False
        self._thread: threading.Thread | None = None
        self._noise_throttler = Throttler(
            interval=Config.NOISE_LEVEL_INTERVAL,
            delta=Config.NOISE_LEVEL_DELTA,
        )

    def start(self) -> None:
        LOG.info(
            "Starting audio monitor — device=%s rate=%s chunk=%s",
            Config.SOUND_DEVICE or "default",
            self.vad.sample_rate,
            Config.chunk_samples(),
        )
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        LOG.info("Stopping audio monitor")
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)

    def _loop(self) -> None:
        def callback(indata, frames, time_info, status):
            if status:
                LOG.warning("Audio status: %s", status)
            if not self._running:
                raise sd.CallbackStop
            if indata.ndim == 1:
                frame = indata.copy()
            else:
                frame = indata[:, 0].copy()
            prob = self.vad.get_probability(frame)
            self.on_vad(prob)
            db = rms_dbfs(frame)
            if self._noise_throttler.should_publish(db):
                self.on_noise(db)

        kwargs = {
            "samplerate": self.vad.sample_rate,
            "channels": 1,
            "dtype": "float32",
            "blocksize": Config.chunk_samples(),
            "callback": callback,
        }
        if Config.SOUND_DEVICE:
            kwargs["device"] = Config.SOUND_DEVICE
        if Config.ALSA_CARD:
            sd.default.device = Config.ALSA_CARD

        try:
            with sd.InputStream(**kwargs):
                while self._running:
                    time.sleep(0.1)
        except Exception as exc:
            LOG.error("Audio stream error: %s", exc)
            if self.on_error:
                self.on_error(exc)
