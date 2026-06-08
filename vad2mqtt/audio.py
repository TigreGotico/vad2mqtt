"""Audio capture and VAD processing loop."""

from __future__ import annotations

import logging
import subprocess
import threading
import time

import numpy as np
import sounddevice as sd

from .config import Config
from .utils import Throttler, rms_dbfs
from .vad_engine import VADEngine

LOG = logging.getLogger(__name__)


def _list_input_devices() -> list[str]:
    """Return human-readable input device names."""
    lines = []
    try:
        for i, dev in enumerate(sd.query_devices()):
            if dev["max_input_channels"] > 0:
                lines.append(f"  [{i}] {dev['name']}")
    except Exception as exc:
        lines.append(f"  (could not enumerate: {exc})")
    return lines


def _resolve_alsa_hw(name: str) -> str | None:
    """Try to map an ALSA card name (e.g. 'C615') to hw:X,Y via arecord -l."""
    try:
        output = subprocess.check_output(["arecord", "-l"], text=True, timeout=5)
        for line in output.splitlines():
            if line.startswith("card ") and name in line:
                card_part = line.split(":")[0]
                card_num = card_part.replace("card ", "").strip()
                return f"hw:{card_num},0"
    except Exception:
        pass
    return None


class AudioMonitor:
    """Captures audio and periodically runs VAD inference at the publish interval."""

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
        self._worker: threading.Thread | None = None
        # Shared latest frame — audio callback writes, worker reads.
        self._latest_frame: np.ndarray | None = None
        self._frame_lock = threading.Lock()
        self._noise_throttler = Throttler(
            interval=Config.NOISE_LEVEL_INTERVAL,
            delta=Config.NOISE_LEVEL_DELTA,
        )

    def start(self) -> None:
        LOG.info(
            "Starting audio monitor — device=%s rate=%s chunk=%s publish_interval=%ss",
            Config.SOUND_DEVICE or "default (ALSA_CARD=%s)" % (Config.ALSA_CARD or "not set"),
            self.vad.sample_rate,
            Config.chunk_samples(),
            Config.PUBLISH_INTERVAL,
        )
        self._running = True
        self._worker = threading.Thread(target=self._process_loop, daemon=True)
        self._worker.start()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        LOG.info("Stopping audio monitor")
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
        if self._worker:
            self._worker.join(timeout=2.0)

    def _open_stream(self, kwargs: dict):
        """Open the stream, trying device name then ALSA hw fallback then default."""
        device = kwargs.pop("device", None)
        if device is None:
            return sd.InputStream(**kwargs)

        try:
            return sd.InputStream(**kwargs, device=device)
        except sd.PortAudioError as exc:
            err_msg = str(exc).lower()
            if "no input device matching" in err_msg or "invalid device" in err_msg:
                LOG.debug("PortAudio does not enumerate '%s', trying ALSA hw fallback", device)
            else:
                raise

        hw_id = _resolve_alsa_hw(device)
        if hw_id:
            LOG.info("Resolved ALSA card '%s' → '%s', retrying", device, hw_id)
            try:
                return sd.InputStream(**kwargs, device=hw_id)
            except sd.PortAudioError as exc2:
                LOG.warning("Failed to open ALSA hw '%s': %s", hw_id, exc2)

        LOG.warning(
            "Failed to open device '%s'. Falling back to default.\n"
            "Available input devices:\n%s",
            device,
            "\n".join(_list_input_devices()),
        )
        return sd.InputStream(**kwargs)

    def _process_loop(self) -> None:
        """Worker: sleep PUBLISH_INTERVAL, run one inference, publish. Nothing else."""
        while self._running:
            time.sleep(Config.PUBLISH_INTERVAL)
            with self._frame_lock:
                frame = self._latest_frame
            if frame is None:
                continue
            try:
                prob = self.vad.get_probability(frame)
                self.on_vad(prob)
                db = rms_dbfs(frame)
                if self._noise_throttler.should_publish(db):
                    self.on_noise(db)
            except Exception as exc:
                LOG.warning("VAD processing error: %s", exc)

    def _loop(self) -> None:
        def callback(indata, frames, time_info, status):
            if status:
                LOG.warning("Audio status: %s", status)
            if not self._running:
                raise sd.CallbackStop
            frame = indata[:, 0].copy() if indata.ndim > 1 else indata.copy()
            with self._frame_lock:
                self._latest_frame = frame

        device = Config.SOUND_DEVICE or None
        blocksize = int(self.vad.sample_rate * Config.CHUNK_DURATION_MS / 1000)

        kwargs = {
            "samplerate": self.vad.sample_rate,
            "channels": 1,
            "dtype": "float32",
            "blocksize": blocksize,
            "callback": callback,
        }
        if device:
            kwargs["device"] = device

        try:
            with self._open_stream(kwargs):
                while self._running:
                    time.sleep(0.1)
        except Exception as exc:
            LOG.error("Audio stream error: %s", exc)
            if self.on_error:
                self.on_error(exc)
