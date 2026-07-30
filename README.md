# vad2mqtt

`vad2mqtt` is a real-time Voice Activity Detection (VAD) bridge built on
[ovos-plugin-manager](https://github.com/OpenVoiceOS/ovos-plugin-manager)
(OPM). It listens to a microphone, loads an OPM VAD plugin, and publishes
speech probability, noise level, and a speech-detected binary sensor to MQTT,
with Home Assistant auto-discovery.

Because OPM plugins are interchangeable, any current or future OVOS VAD
plugin works as a Home Assistant sensor with no code changes. Install
`ovos-vad-plugin-silero` today, or switch to `ovos-vad-plugin-webrtcvad`
later, and `vad2mqtt` adapts.

## Why this exists

Many rooms already have a microphone: smart speakers, single-board computers
with a USB mic, intercom panels, or old phones running Home Assistant
Companion. A VAD adds an occupancy signal with no extra hardware:

- It is a complementary signal, not a standalone one. VAD is one input among
  several (PIR, mmWave, door sensors). It feeds a probabilistic occupancy
  estimator such as
  [Area Occupancy Detection](https://github.com/Hankanman/Area-Occupancy-Detection).
  Both the binary `Speech Detected` sensor and the continuous `Noise Level`
  sensor are useful inputs.
- No audio leaves the device. Only a 0-100% value (speech probability) and a
  dB value cross the wire. There is no transcription, no wake-word, and no
  cloud.
- Silero VAD runs in about 1 ms per 30 ms frame on a Raspberry Pi. CPU use is
  low.
- VAD fills gaps that PIR sensors leave. PIR sensors need motion and heat.
  VAD detects presence when someone sits still at a desk or outside a PIR
  blind spot. VAD also misses people who stay silent, so fuse it with other
  sensors rather than use it alone.

## What it does

1. Captures microphone input in small chunks (default 30 ms).
2. Loads an `ovos-plugin-manager` VAD plugin. The default is
   `ovos-vad-plugin-silero` (ONNX, low resource use).
3. Publishes a speech probability value (0-100%) every second, throttled.
4. Publishes an RMS noise level in dB, throttled.
5. Publishes 4 auto-discovered entities under one Home Assistant device over
   MQTT.

## Quick start (Docker)

```bash
# PipeWire / PulseAudio host (most modern desktops)
vim docker-compose.yml   # set MQTT_HOST
docker compose up -d
```

```bash
# Pure ALSA host (e.g. Raspberry Pi)
# Uncomment the `devices:` line in docker-compose.yml and set ALSA_CARD
vim docker-compose.yml
docker compose up -d
```

## Quick start (pip)

```bash
pip install vad2mqtt
vad2mqtt
```

## Home Assistant entities (4 under one device)

| Entity | Type | Payload | Note |
|--------|------|---------|------|
| VAD Probability | sensor | `87.0` | 0-100%, `unit_of_measurement: %`, `state_class: measurement` |
| VAD Model | sensor | `ovos-vad-plugin-silero` | Updates on startup |
| Noise Level | sensor | `-45.2` | dB, `device_class: sound_pressure` |
| Speech Detected | binary_sensor | `ON` / `OFF` | Derived from threshold |

## Configuration

Every runtime setting is an environment variable. The defaults work without
changes. Tune only what you need.

| Variable | Default | Description |
|----------|---------|-------------|
| **MQTT** | | |
| `MQTT_HOST` | `localhost` | Broker host |
| `MQTT_PORT` | `1883` | Broker port |
| `MQTT_USER` | - | Auth user |
| `MQTT_PASSWORD` | - | Auth password |
| `MQTT_TOPIC_PREFIX` | `vad2mqtt` | Topic root |
| `MQTT_CLIENT_ID` | `vad2mqtt-client` | MQTT client identifier |
| `MQTT_QOS` | `0` | MQTT QoS (0, 1, or 2) |
| `MQTT_RETAIN` | `true` | Retain flag for state messages |
| `MQTT_KEEPALIVE` | `60` | MQTT keepalive interval (seconds) |
| `MQTT_RETRY_COUNT` | `5` | Connection retry attempts on startup |
| `MQTT_RETRY_MAX_BACKOFF` | `30` | Max seconds between retries |
| `MQTT_CONNECT_TIMEOUT` | `2.0` | Seconds to wait per connection attempt |
| **Audio** | | |
| `SAMPLE_RATE` | `16000` | Audio sample rate |
| `SOUND_DEVICE` | - | PortAudio device index or substring (e.g. `3`, `C615`). Leave empty to use the ALSA `default` PCM |
| `ALSA_CARD` | - | ALSA card name (e.g. `C615`). Sets the system default capture card. Does not pass the name to PortAudio |
| `CHUNK_DURATION_MS` | `30` | Frame size in milliseconds |
| **VAD Plugin** | | |
| `VAD_PLUGIN_MODULE` | `ovos-vad-plugin-silero` | OPM plugin module name |
| `VAD_PLUGIN_CONFIG` | - | JSON extra config for the plugin |
| `VAD_THRESHOLD` | `0.5` | Speech / silence probability cutoff |
| `REQUIRED_SPEECH_FRAMES` | `5` | Consecutive speech frames needed to set the binary sensor ON |
| `REQUIRED_SILENCE_FRAMES` | `20` | Consecutive silence frames needed to set the binary sensor OFF |
| **Home Assistant** | | |
| `HA_ENABLED` | `true` | Auto-discovery toggle |
| `HA_DISCOVERY_PREFIX` | `homeassistant` | HA MQTT discovery prefix |
| `DEVICE_NAME` | `vad2mqtt` | HA entity prefix |
| `DEVICE_ID` | `vad2mqtt_01` | HA device identifier |
| **Throttling** | | |
| `PUBLISH_INTERVAL` | `1.0` | Minimum seconds between VAD publishes |
| `NOISE_LEVEL_INTERVAL` | `2.0` | Minimum seconds between noise publishes |
| `NOISE_LEVEL_DELTA` | `3.0` | dB jump that bypasses the noise interval |
| **Logging** | | |
| `LOG_LEVEL` | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |

## Switching VAD plugins

Because `vad2mqtt` uses `ovos-plugin-manager`, you can switch VAD engines by
setting one environment variable. Every current and future OVOS VAD plugin
works this way:

```bash
# Silero VAD - best accuracy, ONNX, ~1 ms/frame on Pi (default)
pip install ovos-vad-plugin-silero
VAD_PLUGIN_MODULE=ovos-vad-plugin-silero

# WebRTC VAD - lighter, no ML model
pip install ovos-vad-plugin-webrtcvad
VAD_PLUGIN_MODULE=ovos-vad-plugin-webrtcvad

# Noise-based VAD - threshold-based, minimal CPU
pip install ovos-vad-plugin-noise
VAD_PLUGIN_MODULE=ovos-vad-plugin-noise

# Community plugins - install the package and point VAD_PLUGIN_MODULE at it
```

A new VAD model or algorithm ships as a plain pip package. `vad2mqtt` uses it
with no code changes, once installed and referenced by
`VAD_PLUGIN_MODULE`.

## Architecture

```
Mic ──► sounddevice ──► 30 ms chunks ──► OPM VAD Plugin
                                               │
                    ┌──────────────────────────┘
                    ▼
            MQTT ──► Home Assistant
            │
            ├── vad_probability (continuous, 0-100%)
            ├── noise_level (throttled, dB)
            ├── model_name (startup)
            └── speech_detected (binary, derived)
```

## Related

- [ovos-plugin-manager](https://github.com/OpenVoiceOS/ovos-plugin-manager)
- [ovos-vad-plugin-silero](https://github.com/OpenVoiceOS/ovos-vad-plugin-silero)
- [shazam2mqtt](https://github.com/TigreGotico/shazam2mqtt): music recognition bridge
