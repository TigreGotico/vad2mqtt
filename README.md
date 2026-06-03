# vad2mqtt

> **Bring the entire OpenVoiceOS VAD ecosystem into Home Assistant as IoT sensors.**

`vad2mqtt` is a real-time Voice Activity Detection bridge built on
**ovos-plugin-manager**. It listens to any microphone, loads any OPM VAD
plugin, and publishes speech probability, noise level, and a speech-detected
binary sensor to MQTT — with full Home Assistant auto-discovery.

Because OPM plugins are interchangeable, **every current and future OVOS VAD
plugin instantly becomes a Home Assistant sensor** with zero code changes.
Install `ovos-vad-plugin-silero` today, swap to `ovos-vad-plugin-webrtcvad`
tomorrow, or drop in a community plugin next week — `vad2mqtt` adapts
automatically.

> **A complementary occupancy signal from the microphone you already own.**

## Why this exists — complementary occupancy detection

Most rooms already have a microphone (smart speakers, SBCs with a cheap USB
mic, intercom panels, old phones running Home Assistant Companion). A **Voice
Activity Detector** adds a privacy-respecting *complementary* occupancy signal
with zero extra hardware:

- **Complementary, not standalone.** VAD is one input among many (PIR, mmWave,
  door sensors, etc.). It feeds into a probabilistic occupancy estimator such
  as [Area Occupancy Detection](https://github.com/Hankanman/Area-Occupancy-Detection).
  Both the binary `Speech Detected` sensor and the continuous `Noise Level`
  sensor are useful inputs.
- **No audio ever leaves the device.** Only a 0–1 float (speech probability) and
  a dB value cross the wire. No transcription, no wake-word, no cloud.
- **Lightweight.** Silero VAD runs in ~1 ms per 30 ms frame on a Raspberry Pi.
  CPU usage is negligible.
- **Fills gaps PIR leaves behind.** PIR sensors need motion + heat. VAD catches
  presence when someone is sitting still at a desk or behind a PIR blind spot.
  It also *misses* people who are silent, which is why it must be fused with
  other sensors rather than used alone.

## What it does

1. **Real-time audio** — captures microphone input in small chunks (default 30 ms).
2. **OPM VAD plugin** — loads any `ovos-plugin-manager` VAD engine. Default is
   `ovos-vad-plugin-silero` (ONNX, lightweight).
3. **Speech probability** — publishes a 0.0–1.0 float every chunk.
4. **Noise level** — publishes RMS dB at a throttled interval.
5. **MQTT + Home Assistant** — 4 auto-discovered entities under one device.

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
| VAD Probability | sensor | `0.87` | 0.0–1.0, `state_class: measurement` |
| VAD Model | sensor | `ovos-vad-plugin-silero` | Static-ish, updates on startup |
| Noise Level | sensor | `-45.2` | dB, `device_class: sound_pressure` |
| Speech Detected | binary_sensor | `ON` / `OFF` | Derived from threshold |

## Configuration

Every runtime knob is an environment variable. Sane defaults mean it works out
of the box; tune only what you need.

| Variable | Default | Description |
|----------|---------|-------------|
| **MQTT** | | |
| `MQTT_HOST` | `localhost` | Broker host |
| `MQTT_PORT` | `1883` | Broker port |
| `MQTT_USER` | — | Auth user |
| `MQTT_PASSWORD` | — | Auth password |
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
| `SOUND_DEVICE` | — | PortAudio device index or substring (e.g. `3`, `C615`). Leave empty to use the ALSA `default` PCM |
| `ALSA_CARD` | — | ALSA card name (e.g. `C615`). Sets the system default capture card; does **not** pass the name to PortAudio |
| `CHUNK_DURATION_MS` | `30` | Frame size in milliseconds |
| **VAD Plugin** | | |
| `VAD_PLUGIN_MODULE` | `ovos-vad-plugin-silero` | OPM plugin module name |
| `VAD_PLUGIN_CONFIG` | — | JSON extra config for the plugin |
| `VAD_THRESHOLD` | `0.5` | Speech / silence probability cutoff |
| `REQUIRED_SPEECH_FRAMES` | `5` | Consecutive speech frames to flip binary ON |
| `REQUIRED_SILENCE_FRAMES` | `20` | Consecutive silence frames to flip binary OFF |
| **Home Assistant** | | |
| `HA_ENABLED` | `true` | Auto-discovery toggle |
| `HA_DISCOVERY_PREFIX` | `homeassistant` | HA MQTT discovery prefix |
| `DEVICE_NAME` | `vad2mqtt` | HA entity prefix |
| `DEVICE_ID` | `vad2mqtt_01` | HA device identifier |
| **Throttling** | | |
| `PUBLISH_INTERVAL` | `1.0` | Min seconds between VAD publishes |
| `NOISE_LEVEL_INTERVAL` | `2.0` | Min seconds between noise publishes |
| `NOISE_LEVEL_DELTA` | `3.0` | dB jump that bypasses the noise interval |
| **Logging** | | |
| `LOG_LEVEL` | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |

## Switching VAD plugins — the OPM advantage

Because `vad2mqtt` uses `ovos-plugin-manager`, you can swap VAD engines with
a single environment variable. Every current and future OVOS VAD plugin is
supported:

```bash
# Silero VAD — best accuracy, ONNX, ~1 ms/frame on Pi (default)
pip install ovos-vad-plugin-silero
VAD_PLUGIN_MODULE=ovos-vad-plugin-silero

# WebRTC VAD — lighter, no ML model
pip install ovos-vad-plugin-webrtcvad
VAD_PLUGIN_MODULE=ovos-vad-plugin-webrtcvad

# Noise-based VAD — threshold-based, minimal CPU
pip install ovos-vad-plugin-noise
VAD_PLUGIN_MODULE=ovos-vad-plugin-noise

# Future community plugins — just install and point VAD_PLUGIN_MODULE at them
```

This is the power of the OVOS plugin ecosystem: new VAD research (new ONNX
models, new algorithms) ships as a plain pip package. `vad2mqtt` consumes it
immediately with zero code changes.

## Architecture

```
Mic ──► sounddevice ──► 30 ms chunks ──► OPM VAD Plugin
                                               │
                    ┌──────────────────────────┘
                    ▼
            MQTT ──► Home Assistant
            │
            ├── vad_probability (continuous)
            ├── noise_level (throttled)
            ├── model_name (startup)
            └── speech_detected (binary, derived)
```

## Related

- [ovos-plugin-manager](https://github.com/OpenVoiceOS/ovos-plugin-manager)
- [ovos-vad-plugin-silero](https://github.com/OpenVoiceOS/ovos-vad-plugin-silero)
- [shazam2mqtt](https://github.com/TigreGotico/shazam2mqtt) — music recognition bridge
