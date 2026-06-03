# Backlog / TODO

## Features

- [ ] Support `VAD_PLUGIN_CONFIG` JSON for plugin-specific tuning (e.g. Silero
      threshold, WebRTC aggressiveness mode)
- [ ] Add `listen_now` MQTT command topic (like shazam2mqtt) to force a
      one-shot high-confidence capture for automation triggers
- [ ] Expose VAD probability history as a small in-memory ring buffer for
      smoother binary_sensor state (hysteresis over N frames)
- [ ] Support multiple audio backends: JACK, PulseAudio direct, WASAPI
- [ ] Add `docker-compose.yml` variant for pure ALSA (Raspberry Pi) with
      `devices: /dev/snd:/dev/snd` uncommented by default
- [ ] Publish PyPI package (`publish_stable.yml` should handle this once
      public and `dev` gets a version bump)

## Documentation

- [ ] Add screenshot/gif of Home Assistant dashboard cards in action
- [ ] Document Area Occupancy Detection config-flow screenshots once tested
- [ ] Add troubleshooting section: "PortAudio sees no devices" → check
      PipeWire vs ALSA, show `arecord -l` output

## Engineering

- [ ] Smoke tests for MQTT client (mock broker)
- [ ] Smoke tests for VADEngine with dummy audio frames
- [ ] Smoke tests for AudioMonitor loop start/stop
- [ ] CI: the `docker.yml` workflow is hand-copied from shazam2mqtt; should
      be added to `shared-gh-workflows` templates instead
- [ ] Evaluate `ovos-vad-plugin-silero` vs newer Silero models (v4, v5)
