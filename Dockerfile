FROM python:3.14-slim

# Install ALSA / audio libraries
# pipewire-alsa enables ALSA apps to talk to a host PipeWire server
RUN apt-get update && apt-get install -y --no-install-recommends \
    libportaudio2 \
    libportaudiocpp0 \
    libsndfile1 \
    alsa-utils \
    pipewire-alsa \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml README.md ./
COPY vad2mqtt/ ./vad2mqtt/

RUN pip install --no-cache-dir -e .

CMD ["python", "-m", "vad2mqtt"]
