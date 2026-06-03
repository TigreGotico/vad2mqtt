"""vad2mqtt configuration — all settings via environment variables."""

import os


class Config:
    """Static config holder populated once at startup."""

    # Audio
    SAMPLE_RATE: int = int(os.getenv("SAMPLE_RATE", "16000"))
    SOUND_DEVICE: str | None = os.getenv("SOUND_DEVICE") or None
    ALSA_CARD: str | None = os.getenv("ALSA_CARD") or None
    CHUNK_DURATION_MS: int = int(os.getenv("CHUNK_DURATION_MS", "30"))

    # VAD Plugin (ovos-plugin-manager)
    VAD_PLUGIN_MODULE: str = os.getenv("VAD_PLUGIN_MODULE", "ovos-vad-plugin-silero")
    VAD_PLUGIN_CONFIG: str = os.getenv("VAD_PLUGIN_CONFIG", "")
    VAD_THRESHOLD: float = float(os.getenv("VAD_THRESHOLD", "0.5"))

    # MQTT
    MQTT_HOST: str = os.getenv("MQTT_HOST", "localhost")
    MQTT_PORT: int = int(os.getenv("MQTT_PORT", "1883"))
    MQTT_USER: str | None = os.getenv("MQTT_USER") or None
    MQTT_PASSWORD: str | None = os.getenv("MQTT_PASSWORD") or None
    MQTT_TOPIC_PREFIX: str = os.getenv("MQTT_TOPIC_PREFIX", "vad2mqtt")
    MQTT_CLIENT_ID: str = os.getenv("MQTT_CLIENT_ID", "vad2mqtt-client")
    MQTT_QOS: int = int(os.getenv("MQTT_QOS", "0"))
    MQTT_RETAIN: bool = os.getenv("MQTT_RETAIN", "true").lower() == "true"
    MQTT_KEEPALIVE: int = int(os.getenv("MQTT_KEEPALIVE", "60"))
    MQTT_RETRY_COUNT: int = int(os.getenv("MQTT_RETRY_COUNT", "5"))
    MQTT_RETRY_MAX_BACKOFF: int = int(os.getenv("MQTT_RETRY_MAX_BACKOFF", "30"))
    MQTT_CONNECT_TIMEOUT: float = float(os.getenv("MQTT_CONNECT_TIMEOUT", "2.0"))

    # Home Assistant
    HA_ENABLED: bool = os.getenv("HA_ENABLED", "true").lower() == "true"
    HA_DISCOVERY_PREFIX: str = os.getenv("HA_DISCOVERY_PREFIX", "homeassistant")
    DEVICE_NAME: str = os.getenv("DEVICE_NAME", "vad2mqtt")
    DEVICE_ID: str = os.getenv("DEVICE_ID", "vad2mqtt_01")

    # Throttling
    PUBLISH_INTERVAL: float = float(os.getenv("PUBLISH_INTERVAL", "1.0"))
    NOISE_LEVEL_INTERVAL: float = float(os.getenv("NOISE_LEVEL_INTERVAL", "2.0"))
    NOISE_LEVEL_DELTA: float = float(os.getenv("NOISE_LEVEL_DELTA", "3.0"))

    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()

    @classmethod
    def chunk_samples(cls) -> int:
        return int(cls.SAMPLE_RATE * cls.CHUNK_DURATION_MS / 1000)
