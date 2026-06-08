"""VAD engine wrapper using ovos-plugin-manager."""

from __future__ import annotations

import json
import logging

import numpy as np

# Intercept onnxruntime before any plugin imports it so all sessions are
# created with a 1-thread pool.  Without this, ORT allocates one thread per
# CPU core and busy-waits between calls, burning the machine.
try:
    import onnxruntime as _ort

    _orig_session = _ort.InferenceSession

    def _single_threaded_session(model, *args, sess_options=None, **kwargs):
        opts = _ort.SessionOptions()
        opts.intra_op_num_threads = 1
        opts.inter_op_num_threads = 1
        return _orig_session(model, *args, sess_options=opts, **kwargs)

    _ort.InferenceSession = _single_threaded_session
except ImportError:
    pass

from ovos_plugin_manager.vad import OVOSVADFactory

from .config import Config

LOG = logging.getLogger(__name__)


class VADEngine:
    """Wraps any OPM VAD plugin and extracts speech probability."""

    def __init__(self) -> None:
        self._factory = OVOSVADFactory()
        config = self._build_config()
        LOG.info("Loading VAD plugin: %s", Config.VAD_PLUGIN_MODULE)
        self._engine = self._factory.create(config=config)
        self.sample_rate = getattr(self._engine, "sample_rate", Config.SAMPLE_RATE)
        self.model_name = Config.VAD_PLUGIN_MODULE
        LOG.info("VAD plugin loaded — model=%s sample_rate=%s", self.model_name, self.sample_rate)

    def _build_config(self) -> dict:
        """Build the OPM config dict from env vars."""
        cfg: dict = {"module": Config.VAD_PLUGIN_MODULE}
        if Config.VAD_PLUGIN_CONFIG:
            try:
                extra = json.loads(Config.VAD_PLUGIN_CONFIG)
                cfg.update(extra)
            except json.JSONDecodeError:
                LOG.warning("VAD_PLUGIN_CONFIG is not valid JSON: %s", Config.VAD_PLUGIN_CONFIG)
        # Inject threshold into plugin-specific namespace
        cfg.setdefault(Config.VAD_PLUGIN_MODULE, {})
        cfg[Config.VAD_PLUGIN_MODULE]["threshold"] = Config.VAD_THRESHOLD
        return cfg

    def get_probability(self, frame: np.ndarray) -> float:
        """Return speech probability in [0.0, 1.0]."""
        # Try the raw underlying VAD callable first (silero returns ndarray)
        if hasattr(self._engine, "vad") and callable(self._engine.vad):
            try:
                result = self._engine.vad(frame)
                if isinstance(result, np.ndarray):
                    return float(result.item())
                return float(result)
            except Exception:
                pass
        # Fallback: is_silence boolean → 0.0 / 1.0
        try:
            is_silence = self._engine.is_silence(frame, self.sample_rate)
            return 0.0 if is_silence else 1.0
        except Exception as exc:
            LOG.debug("is_silence fallback failed: %s", exc)
            return 0.0

    def is_speech(self, frame: np.ndarray) -> bool:
        """Return True if frame contains speech (uses plugin threshold)."""
        try:
            return not self._engine.is_silence(frame, self.sample_rate)
        except Exception:
            return self.get_probability(frame) >= Config.VAD_THRESHOLD

    def reset(self) -> None:
        """Reset internal VAD state."""
        if hasattr(self._engine, "reset"):
            try:
                self._engine.reset()
            except Exception:
                pass
