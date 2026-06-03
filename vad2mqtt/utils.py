"""Utility helpers for vad2mqtt."""

import math
import time
from dataclasses import dataclass

import numpy as np


def rms_dbfs(samples: np.ndarray) -> float:
    """Compute RMS in dBFS (full-scale)."""
    if samples.size == 0:
        return -96.0
    rms = np.sqrt(np.mean(samples.astype(np.float64) ** 2))
    if rms == 0:
        return -96.0
    return 20.0 * math.log10(rms)


@dataclass
class Throttler:
    """Throttle MQTT publishes by interval and delta."""

    interval: float
    delta: float
    _last_time: float = 0.0
    _last_value: float | None = None

    def should_publish(self, value: float) -> bool:
        now = time.time()
        if now - self._last_time < self.interval:
            if self._last_value is not None and abs(value - self._last_value) < self.delta:
                return False
        self._last_time = now
        self._last_value = value
        return True
