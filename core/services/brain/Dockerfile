# SupremeAI Tiny Brain (core/services/brain) — 512MB micro-service image.
# Render service config: rootDir=core/services/brain, dockerfilePath=./Dockerfile
# ROOT-CAUSE FIX (render-brain build_failed 2026-11-01): the Render service
# builds from this directory but no Dockerfile existed here, so every
# autodeploy failed with "failed to read dockerfile: open Dockerfile: no
# such file or directory". This file restores the build contract.

FROM python:3.12-slim@sha256:5e2bdb1b0d542d5039cffb8181c65930093949194a65c365dfb1b0fe13a4fa5b

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Audit 2026-11-19 (#6): never run as root.
RUN addgroup --system supremeai && adduser --system supremeai --ingroup supremeai

# Runtime deps only — exact pinned closure (matches browser/requirements.txt)
RUN pip install --no-cache-dir "fastapi==0.162.0" "uvicorn==0.54.0" "pydantic==2.14.1"

COPY --chown=supremeai:supremeai main.py ./

USER supremeai
EXPOSE 8000

# Audit 2026-11-19 (#6): in-image liveness probe.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4)" || exit 1

# Render injects $PORT; local runs default to 8000.
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
