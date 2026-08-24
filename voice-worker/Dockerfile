# syntax=docker/dockerfile:1
ARG PYTHON_VERSION=3.11.6
FROM python:${PYTHON_VERSION}-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

ARG UID=10001
RUN adduser \
    --disabled-password \
    --gecos "" \
    --home "/home/appuser" \
    --shell "/sbin/nologin" \
    --uid "${UID}" \
    appuser

RUN apt-get update && \
    apt-get install -y \
    gcc \
    g++ \
    python3-dev \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

USER appuser

RUN mkdir -p /home/appuser/.cache
RUN chown -R appuser /home/appuser/.cache

WORKDIR /home/appuser

COPY requirements.txt .
RUN python -m pip install --user --no-cache-dir -r requirements.txt

# Pre-fetch model files (VAD, turn-detector, etc.) at build time so the
# always-on Cloud Run instance doesn't pay that latency on cold start.
RUN python -m livekit.agents download-files

COPY . .

# Cloud Run requires *something* listening on $PORT even for a worker
# service with no inbound traffic — the `start` subcommand exposes a
# lightweight health endpoint on it (see AGENTS.md's CLI docs).
ENV PORT=8080
EXPOSE 8080

ENTRYPOINT ["python", "worker.py"]
CMD ["start"]
