"""CLI entry point for vad2mqtt."""

from __future__ import annotations

import logging
import signal
import sys
import time
from typing import Any

from .audio import AudioMonitor
from .config import Config
from .mqtt_client import MQTTClient
from .version import __version__

LOG = logging.getLogger("vad2mqtt")


def setup_logging() -> None:
    logging.basicConfig(
        level=getattr(logging, Config.LOG_LEVEL, logging.INFO),
        format="%(asctime)s %(name)s [%(levelname)s] %(message)s",
    )


def main() -> None:
    setup_logging()
    LOG.info("vad2mqtt %s starting", __version__)

    mqtt_client = MQTTClient()
    mqtt_client.connect()

    # Publish model name once on startup
    from .vad_engine import VADEngine
    engine = VADEngine()
    mqtt_client.publish_model(engine.model_name)

    monitor = AudioMonitor(
        on_vad=lambda prob: mqtt_client.publish_vad(prob),
        on_noise=lambda db: mqtt_client.publish_noise(db),
        on_error=lambda exc: LOG.error("Monitor error: %s", exc),
    )

    def _shutdown(signum: int, frame: Any) -> None:
        LOG.info("Received signal %s, shutting down", signum)
        monitor.stop()
        mqtt_client.disconnect()
        sys.exit(0)

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    monitor.start()
    LOG.info("vad2mqtt running — listening via %s", engine.model_name)

    try:
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        _shutdown(signal.SIGINT, None)


if __name__ == "__main__":
    main()
