# vad2mqtt

Voice Activity Detection to MQTT bridge using **ovos-plugin-manager**.

Listens to your microphone in real-time, runs any OPM VAD plugin (default:
Silero VAD), and publishes speech probability, model name, and noise level to
MQTT — with full Home Assistant auto-discovery.

> **The cheapest occupancy sensor is the microphone you already own.**

## Why this exists — occupancy detection

Most rooms already have a microphone: smart speakers, intercom panels, SBCs with
a cheap USB mic, or old phones running Home Assistant Companion. Adding a
**Voice Activity Detector** turns that mic into a privacy-respecting occupancy
sensor with zero extra hardware:

- **People speaking → room occupied.** The `Speech Detected` binary sensor flips
  to `ON` when someone talks and `OFF` after a configurable silence period.
- **No audio ever leaves the device.** Only a 0–1 float (speech probability) and
  a dB value cross the wire. No transcription, no wake-word, no cloud.
- **Lightweight.** Silero VAD runs in ~1 ms per 30 ms frame on a Raspberry Pi.
  CPU usage is negligible.
- **Works where PIR fails.** PIR sensors need motion + heat. VAD detects
  presence even when someone is sitting still at a desk. It also covers the
  blind spot where someone is behind a PIR sensor.

## What it does

1. **Real-time audio** — captures microphone input in small chunks (default 30 ms).
2. **OPM VAD plugin** — loads any `ovos-plugin-manager` VAD engine. Default is
   `ovos-vad-plugin-silero` (ONNX, lightweight).
3. **Speech probability** — publishes a 0.0–1.0 float every chunk.
4. **Noise level** — publishes RMS dB at a throttled interval.
5. **MQTT + Home Assistant** — 4 auto-discovered entities under one device.

## Quick start (Docker)

```bash
docker compose up -d
```

Edit `docker-compose.yml` to point `MQTT_HOST` at your broker.

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

All settings are environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `MQTT_HOST` | `localhost` | Broker host |
| `MQTT_PORT` | `1883` | Broker port |
| `MQTT_USER` | — | Auth user |
| `MQTT_PASSWORD` | — | Auth password |
| `MQTT_TOPIC_PREFIX` | `vad2mqtt` | Topic root |
| `SAMPLE_RATE` | `16000` | Audio sample rate |
| `SOUND_DEVICE` | — | `sounddevice` device index/name |
| `ALSA_CARD` | — | ALSA card string |
| `VAD_PLUGIN_MODULE` | `ovos-vad-plugin-silero` | OPM plugin module name |
| `VAD_PLUGIN_CONFIG` | — | JSON extra config for plugin |
| `VAD_THRESHOLD` | `0.5` | Speech / silence cutoff |
| `HA_ENABLED` | `true` | Auto-discovery toggle |
| `DEVICE_NAME` | `vad2mqtt` | HA entity prefix |
| `DEVICE_ID` | `vad2mqtt_01` | HA device identifier |
| `PUBLISH_INTERVAL` | `0.5` | Min seconds between VAD publishes |
| `NOISE_LEVEL_INTERVAL` | `2.0` | Min seconds between noise publishes |
| `NOISE_LEVEL_DELTA` | `3.0` | dB jump that bypasses interval |
| `LOG_LEVEL` | `INFO` | Logging level |

## Switching VAD plugins

Install any OPM-compatible VAD plugin and change the env var:

```bash
# WebRTC VAD (lighter, no ML)
pip install ovos-vad-plugin-webrtcvad
VAD_PLUGIN_MODULE=ovos-vad-plugin-webrtcvad

# Noise-based VAD
pip install ovos-vad-plugin-noise
VAD_PLUGIN_MODULE=ovos-vad-plugin-noise
```

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
