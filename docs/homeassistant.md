# Home Assistant integration

`vad2mqtt` publishes four entities via MQTT auto-discovery. No manual YAML
configuration is required.

## Occupancy detection — a complementary signal

If a device already has a microphone (smart speaker, SBC with a cheap USB mic,
intercom panel, etc.), VAD is a cheap *complementary* occupancy signal:

- **No extra hardware** — the mic is already there.
- **Privacy-first** — no audio leaves the device; only a 0–100 % probability
  value and a dB value are sent over MQTT.
- **Lightweight** — Silero VAD runs in ~1 ms per 30 ms frame on a Raspberry Pi.
- **Cloud-free** — 100 % local. No voice recognition, no transcription, no
  wake-word engine.

When someone speaks, `Speech Detected` flips to **ON**. When the room is silent
for a configurable duration, it flips to **OFF**. Used *alone*, this misses
people who are sitting quietly. Used *alongside* PIR, mmWave, door sensors,
etc., it dramatically reduces false negatives.

### Integration with Area Occupancy Detection

The [Area Occupancy Detection](https://github.com/Hankanman/Area-Occupancy-Detection)
integration fuses multiple sensors into a single probabilistic occupancy score.
It is configured entirely through the Home Assistant UI (no YAML).

Add `vad2mqtt` inputs via the integration's config flow:

1. **Binary sensor** — `binary_sensor.vad2mqtt_speech_detected`
   - Treat this as a *strong* indicator: high weight, high `probability_on`
     (someone is almost certainly present when speaking), low `probability_off`
     (silence does not mean absence).
2. **Noise level sensor** — `sensor.vad2mqtt_noise_level`
   - Treat this as a *weaker* continuous signal: lower weight, threshold around
     `-40` dB. Contributes even when no one is actively speaking (typing, chair
     squeaking, coffee grinder).

Pair these with your existing PIR, mmWave, door, or power-monitoring sensors.
The integration Bayesian-fuses everything into one `occupancy` probability.

## Entities

| Entity | Type | Purpose |
|--------|------|---------|
| VAD Probability | sensor | Raw 0–100 % speech probability |
| VAD Model | sensor | Which OPM plugin is running |
| Noise Level | sensor | Ambient RMS in dB |
| Speech Detected | binary_sensor | Occupancy proxy — ON when someone speaks |

## Automation example — room occupancy

```yaml
alias: "Office occupied"
trigger:
  - platform: state
    entity_id: binary_sensor.vad2mqtt_speech_detected
    to: "on"
condition: []
action:
  - service: input_boolean.turn_on
    target:
      entity_id: input_boolean.office_occupied

alias: "Office vacant"
trigger:
  - platform: state
    entity_id: binary_sensor.vad2mqtt_speech_detected
    to: "off"
    for: "00:00:30"
action:
  - service: input_boolean.turn_off
    target:
      entity_id: input_boolean.office_occupied
```

## Dashboard card — speech probability gauge

```yaml
type: gauge
entity: sensor.vad2mqtt_vad_probability
name: Speech Probability
min: 0
max: 100
unit: "%"
severity:
  green: 0
  yellow: 30
  red: 70
```

## Dashboard card — noise level history

```yaml
type: history-graph
entities:
  - sensor.vad2mqtt_noise_level
hours_to_show: 24
```

## Device placement tips

- **Point the mic at the room**, not at a speaker. If the VAD picks up TV audio,
  raise `VAD_THRESHOLD` or move the mic.
- **Small rooms** — a cheap USB mic on a Raspberry Pi works perfectly.
- **Noisy environments** (kitchen, workshop) — use `NOISE_LEVEL_DELTA` to ignore
  steady-state hum; VAD is triggered by *changes* in the audio spectrum, not
  absolute volume.
- **Privacy mode** — if you ever want to mute the sensor, stop the container.
  No audio is ever stored or streamed.
