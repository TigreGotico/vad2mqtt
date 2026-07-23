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

RSS_LOG_INTERVAL = 3600.0  # seconds


def _log_rss() -> None:
    """Log the process' resident set size, read from /proc/self/status.

    Dependency-free timestamp of memory usage — useful for pinpointing when
    a leak starts growing without needing psutil or similar.
    """
    try:
        with open("/proc/self/status") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    LOG.info("memory usage: %s", line.split(":", 1)[1].strip())
                    return
    except OSError as exc:
        LOG.debug("could not read /proc/self/status: %s", exc)


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

    monitor = AudioMonitor(
        on_vad=lambda prob: mqtt_client.publish_vad(prob),
        on_noise=lambda db: mqtt_client.publish_noise(db),
        on_error=lambda exc: LOG.error("Monitor error: %s", exc),
    )

    # Publish model name once on startup
    mqtt_client.publish_model(monitor.vad.model_name)

    def _shutdown(signum: int, frame: Any) -> None:
        LOG.info("Received signal %s, shutting down", signum)
        monitor.stop()
        mqtt_client.disconnect()
        sys.exit(0)

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    monitor.start()
    LOG.info("vad2mqtt running — listening via %s", monitor.vad.model_name)

    last_rss_log = time.monotonic()
    try:
        while True:
            time.sleep(1.0)
            if time.monotonic() - last_rss_log >= RSS_LOG_INTERVAL:
                last_rss_log = time.monotonic()
                _log_rss()
            if not monitor.is_healthy():
                LOG.critical(
                    "audio stream dead for >%ss, exiting so the container "
                    "restart policy can recover",
                    Config.WATCHDOG_TIMEOUT,
                )
                monitor.stop()
                mqtt_client.disconnect()
                sys.exit(1)
    except KeyboardInterrupt:
        _shutdown(signal.SIGINT, None)


if __name__ == "__main__":
    main()
