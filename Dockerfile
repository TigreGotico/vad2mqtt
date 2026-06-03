FROM python:3.11-slim

# Install ALSA / audio libraries
RUN apt-get update && apt-get install -y --no-install-recommends \
    libportaudio2 \
    libportaudiocpp0 \
    libsndfile1 \
    alsa-utils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml README.md ./
COPY vad2mqtt/ ./vad2mqtt/

RUN pip install --no-cache-dir -e .

# Run as non-root
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

CMD ["python", "-m", "vad2mqtt"]
