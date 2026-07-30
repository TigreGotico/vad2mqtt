# Home Assistant integration

`vad2mqtt` publishes 4 entities through MQTT auto-discovery. No manual YAML
configuration is needed.

## Occupancy detection

If a device already has a microphone (smart speaker, single-board computer
with a USB mic, intercom panel), VAD gives a complementary occupancy signal:

- No extra hardware. The mic is already there.
- No audio leaves the device. Only a 0-100% probability value and a dB value
  go over MQTT.
- Silero VAD runs in about 1 ms per 30 ms frame on a Raspberry Pi.
- The detector works fully local. There is no voice recognition, no
  transcription, and no wake-word engine.

When someone speaks, `Speech Detected` flips to **ON**. When the room stays
silent for a configurable duration, it flips to **OFF**. Used alone, this
signal misses people who sit quietly. Used with PIR, mmWave, or door sensors,
it reduces false negatives.

### Integration with Area Occupancy Detection

The
[Area Occupancy Detection](https://github.com/Hankanman/Area-Occupancy-Detection)
integration fuses multiple sensors into one probabilistic occupancy score.
Configure it through the Home Assistant UI. It needs no YAML.

Add `vad2mqtt` inputs through the integration's config flow:

1. `binary_sensor.vad2mqtt_speech_detected`: treat this as a strong
   indicator: set a high weight and a high `probability_on` (someone is
   almost certainly present when speaking), and a low `probability_off`
   (silence does not mean absence).
2. `sensor.vad2mqtt_noise_level`: treat this as a weaker continuous signal:
   set a lower weight and a threshold around `-40` dB. It contributes even
   when no one speaks (typing, a chair squeaking, a coffee grinder).

Pair these with existing PIR, mmWave, door, or power-monitoring sensors. The
integration fuses everything into one `occupancy` probability using a
Bayesian model.

## Entities

| Entity | Type | Purpose |
|--------|------|---------|
| VAD Probability | sensor | Raw 0-100% speech probability |
| VAD Model | sensor | Which OPM plugin is running |
| Noise Level | sensor | Ambient RMS in dB |
| Speech Detected | binary_sensor | Occupancy proxy: ON when someone speaks |

## Automation example: room occupancy

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

## Dashboard card: speech probability gauge

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

## Dashboard card: noise level history

```yaml
type: history-graph
entities:
  - sensor.vad2mqtt_noise_level
hours_to_show: 24
```

## Device placement tips

- Point the mic at the room, not at a speaker. If the VAD picks up TV audio,
  raise `VAD_THRESHOLD` or move the mic.
- In small rooms, a cheap USB mic on a Raspberry Pi works well.
- In noisy environments (kitchen, workshop), use `NOISE_LEVEL_DELTA` to
  ignore steady-state hum. VAD triggers on changes in the audio spectrum, not
  on absolute volume.
- To mute the sensor, stop the container. No audio is ever stored or
  streamed.

---
[Home](../README.md)
