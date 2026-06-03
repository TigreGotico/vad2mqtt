"""MQTT client with Home Assistant MQTT auto-discovery."""

from __future__ import annotations

import json
import logging
import time

import paho.mqtt.client as mqtt

from .config import Config
from .version import __version__

LOG = logging.getLogger(__name__)


class MQTTClient:
    """Publishes VAD metrics to MQTT and optionally registers HA discovery."""

    def __init__(self) -> None:
        self.client = mqtt.Client(client_id=Config.MQTT_CLIENT_ID)
        if Config.MQTT_USER and Config.MQTT_PASSWORD:
            self.client.username_pw_set(Config.MQTT_USER, Config.MQTT_PASSWORD)
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self._connected = False
        self._prefix = Config.MQTT_TOPIC_PREFIX
        self._device_name = Config.DEVICE_NAME
        self._device_id = Config.DEVICE_ID
        self._last_vad_publish = 0.0
        self._last_vad_prob = 0.0
        self._last_speech_state = False
        self._consecutive_speech = 0
        self._consecutive_silence = 0

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            LOG.info("MQTT connected to %s:%s", Config.MQTT_HOST, Config.MQTT_PORT)
            self._connected = True
            if Config.HA_ENABLED:
                self._publish_discovery()
        else:
            LOG.warning("MQTT connection failed, rc=%s", rc)

    def _on_disconnect(self, client, userdata, rc):
        LOG.warning("MQTT disconnected, rc=%s", rc)
        self._connected = False

    def connect(self) -> None:
        LOG.info("Connecting to MQTT broker %s:%s", Config.MQTT_HOST, Config.MQTT_PORT)
        for attempt in range(1, Config.MQTT_RETRY_COUNT + 1):
            try:
                self.client.connect(Config.MQTT_HOST, Config.MQTT_PORT, keepalive=Config.MQTT_KEEPALIVE)
                self.client.loop_start()
                # Wait briefly for connection
                deadline = time.time() + Config.MQTT_CONNECT_TIMEOUT
                while time.time() < deadline:
                    if self._connected:
                        return
                    time.sleep(0.1)
                LOG.warning("MQTT connection timeout, retrying...")
            except Exception as exc:
                LOG.warning("MQTT connection attempt %s/%s failed: %s", attempt, Config.MQTT_RETRY_COUNT, exc)
                time.sleep(min(2 ** attempt, Config.MQTT_RETRY_MAX_BACKOFF))
        LOG.error("MQTT failed to connect after %s attempts, continuing anyway", Config.MQTT_RETRY_COUNT)

    def disconnect(self) -> None:
        self.client.loop_stop()
        self.client.disconnect()

    def publish_vad(self, probability: float) -> None:
        now = time.time()
        raw_speech = probability >= Config.VAD_THRESHOLD

        # Update consecutive-frame counters
        if raw_speech:
            self._consecutive_speech += 1
            self._consecutive_silence = 0
        else:
            self._consecutive_silence += 1
            self._consecutive_speech = 0

        # Debounce: require N consecutive frames to flip the binary state
        speech_confirmed = self._last_speech_state
        if self._consecutive_speech >= Config.REQUIRED_SPEECH_FRAMES:
            speech_confirmed = True
        elif self._consecutive_silence >= Config.REQUIRED_SILENCE_FRAMES:
            speech_confirmed = False

        # Publish immediately on debounced state transitions so the binary
        # sensor is responsive; otherwise throttle probability to PUBLISH_INTERVAL.
        state_changed = speech_confirmed != self._last_speech_state
        interval_elapsed = now - self._last_vad_publish >= Config.PUBLISH_INTERVAL

        if not state_changed and not interval_elapsed:
            self._last_vad_prob = probability
            return

        # Use the most recent probability
        prob = probability if interval_elapsed else self._last_vad_prob
        self._last_vad_publish = now
        self._last_vad_prob = probability
        self._last_speech_state = speech_confirmed

        # Probability is published as 0-100 % so Home Assistant renders it as a
        # gauge with a proper unit of measurement.
        pct = round(prob * 100, 2)
        self._publish(
            f"{self._prefix}/vad_probability",
            json.dumps({"probability": pct}),
        )
        self._publish(
            f"{self._prefix}/state",
            json.dumps({
                "probability": pct,
                "speech": speech_confirmed,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            }),
        )

    def publish_noise(self, db: float) -> None:
        self._publish(f"{self._prefix}/noise_level", json.dumps({"db": round(db, 2)}))

    def publish_model(self, model_name: str) -> None:
        self._publish(f"{self._prefix}/model_name", json.dumps({"model": model_name}))

    def _publish(self, topic: str, payload: str) -> None:
        if not self._connected:
            LOG.debug("MQTT not connected, dropping message to %s", topic)
            return
        self.client.publish(
            topic,
            payload,
            qos=Config.MQTT_QOS,
            retain=Config.MQTT_RETAIN,
        )

    def _publish_discovery(self) -> None:
        """Publish Home Assistant MQTT discovery payloads."""
        device = {
            "identifiers": [self._device_id],
            "name": self._device_name,
            "model": "VAD2MQTT",
            "manufacturer": "TigreGotico",
            "sw_version": __version__,
        }

        # VAD Probability sensor
        self._discovery_sensor(
            name="VAD Probability",
            object_id="vad_probability",
            state_topic=f"{self._prefix}/vad_probability",
            value_template="{{ value_json.probability }}",
            device=device,
            unit_of_measurement="%",
            state_class="measurement",
            icon="mdi:account-voice",
        )

        # Model Name sensor
        self._discovery_sensor(
            name="VAD Model",
            object_id="vad_model",
            state_topic=f"{self._prefix}/model_name",
            value_template="{{ value_json.model }}",
            device=device,
            icon="mdi:cpu-64-bit",
        )

        # Noise Level sensor
        self._discovery_sensor(
            name="Noise Level",
            object_id="noise_level",
            state_topic=f"{self._prefix}/noise_level",
            value_template="{{ value_json.db }}",
            device=device,
            unit_of_measurement="dB",
            state_class="measurement",
            device_class="sound_pressure",
            icon="mdi:volume-medium",
        )

        # Speech Detected binary_sensor
        self._discovery_binary_sensor(
            name="Speech Detected",
            object_id="speech_detected",
            state_topic=f"{self._prefix}/state",
            value_template="{{ 'ON' if value_json.speech else 'OFF' }}",
            device=device,
            device_class="sound",
        )

        LOG.info("Home Assistant discovery payloads published")

    def _discovery_sensor(
        self,
        name: str,
        object_id: str,
        state_topic: str,
        value_template: str,
        device: dict,
        unit_of_measurement: str | None = None,
        state_class: str | None = None,
        device_class: str | None = None,
        icon: str | None = None,
    ) -> None:
        payload = {
            "name": f"{self._device_name} {name}",
            "unique_id": f"{self._device_id}_{object_id}",
            "state_topic": state_topic,
            "value_template": value_template,
            "device": device,
        }
        if unit_of_measurement:
            payload["unit_of_measurement"] = unit_of_measurement
        if state_class:
            payload["state_class"] = state_class
        if device_class:
            payload["device_class"] = device_class
        if icon:
            payload["icon"] = icon
        topic = f"{Config.HA_DISCOVERY_PREFIX}/sensor/{self._device_id}/{object_id}/config"
        self.client.publish(topic, json.dumps(payload), qos=1, retain=True)

    def _discovery_binary_sensor(
        self,
        name: str,
        object_id: str,
        state_topic: str,
        value_template: str,
        device: dict,
        device_class: str | None = None,
    ) -> None:
        payload = {
            "name": f"{self._device_name} {name}",
            "unique_id": f"{self._device_id}_{object_id}",
            "state_topic": state_topic,
            "value_template": value_template,
            "device": device,
        }
        if device_class:
            payload["device_class"] = device_class
        topic = f"{Config.HA_DISCOVERY_PREFIX}/binary_sensor/{self._device_id}/{object_id}/config"
        self.client.publish(topic, json.dumps(payload), qos=1, retain=True)
