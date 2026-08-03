# CastIron — container image for Railway (or any Docker host).
# Stateful FastAPI backend: SSE stage-rail, background episode runs, ffmpeg mixing.
FROM python:3.11-slim

# ffmpeg powers the audio fixtures + mixing — required at runtime.
RUN apt-get update \
 && apt-get install -y --no-install-recommends ffmpeg \
 && rm -rf /var/lib/apt/lists/*

# uv for reproducible, lockfile-pinned installs.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

WORKDIR /app

# Dependency layer first (cached across source changes). --frozen honors uv.lock.
# NOTE: dev deps are installed on purpose — the OFFLINE/demo engine uses
# genblaze_core.testing (Mock providers), whose module imports `pytest`, so pytest
# is a *runtime* dependency of the credential-free demo path, not just a test tool.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project

# App source, then install the project itself.
COPY . .
RUN uv sync --frozen

# OFFLINE by default: mock providers + LocalDirBackend, zero credentials → the
# always-green demo path. To run LIVE, set B2_KEY_ID / B2_APP_KEY (+ a TTS key)
# as service env vars — the app auto-detects credentials and switches to real B2.
ENV OFFLINE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

EXPOSE 8000

# Railway injects $PORT. Bind 0.0.0.0 and run the venv uvicorn directly (uv run
# would re-sync at boot). Shell form so ${PORT} expands.
CMD .venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
