# Home Assistant integration

`vad2mqtt` publishes four entities via MQTT auto-discovery. No manual YAML
configuration is required.

## Occupancy detection — a complementary signal

If a device already has a microphone (smart speaker, SBC with a cheap USB mic,
intercom panel, etc.), VAD is a cheap *complementary* occupancy signal:

- **No extra hardware** — the mic is already there.
- **Privacy-first** — no audio leaves the device; only a 0–1 probability float
  and a dB value are sent over MQTT.
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
`vad2mqtt` provides two useful inputs:

```yaml
# configuration.yaml
binary_sensor:
  - platform: area_occupancy
    name: "Office Occupancy"
    inputs:
      - entity_id: binary_sensor.vad2mqtt_speech_detected
        weight: 1.0
        probability_on: 0.95
        probability_off: 0.10
      - entity_id: sensor.vad2mqtt_noise_level
        weight: 0.5
        probability_threshold: -40.0
        probability_above: 0.70
        probability_below: 0.15
      - entity_id: binary_sensor.office_pir
        weight: 1.0
        probability_on: 0.90
        probability_off: 0.05
```

In this example the VAD binary sensor is a *strong* indicator of occupancy,
while the noise level adds a *weaker* continuous signal that still contributes
even when no one is actively speaking (e.g. typing, chair squeaking).

## Entities

| Entity | Type | Purpose |
|--------|------|---------|
| VAD Probability | sensor | Raw 0.0–1.0 speech probability |
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
max: 1
severity:
  green: 0.0
  yellow: 0.3
  red: 0.7
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
