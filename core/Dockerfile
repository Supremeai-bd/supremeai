# Stage 1: Runtime & Verification Runner
FROM python:3.11-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080 \
    PYTHONPATH=/opt

RUN apt-get update && apt-get install -y --no-install-recommends curl perl-base bash && rm -rf /var/lib/apt/lists/* \
    && addgroup --system supremeai && adduser --system supremeai --ingroup supremeai

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir pytest pytest-asyncio pytest-cov pydantic fastapi httpx cryptography pyotp bandit pip-audit

# Fail the image build rather than production boot if SQLAlchemy's async
# runtime dependency or required route packages are missing.
RUN python -c "import aiohttp, boto3, bs4, email_validator, greenlet, sse_starlette; from sqlalchemy.ext.asyncio import create_async_engine; print('Runtime dependencies available')"

COPY --chown=supremeai:supremeai . .
RUN mkdir -p /app/data /app/uploads /app/logs /app/tmp && chown -R supremeai:supremeai /app/data /app/uploads /app/logs /app/tmp

# Make `core` an importable package at runtime (main.py uses `from core.xxx`).
# Docker WORKDIR is /app (= core contents), so expose a real `core` package under
# /opt (persistent, not /tmp which may be cleared at runtime) and put /opt on
# PYTHONPATH so `import core` resolves. PYTHONPATH=/opt keeps /opt on sys.path.
RUN rm -rf /opt/core && mkdir -p /opt/core && cp -r /app/. /opt/core/ && touch /opt/core/__init__.py

# Heavy verification belongs to the dedicated CI runner, not the production
# image build. Keeping it here makes every Render auto-deploy run the full
# suite and consumes the free build-minute budget twice when a CI API trigger
# is also present.

USER supremeai
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=5 \
  CMD python -c "import os, urllib.request; p=os.getenv('PORT','8080'); urllib.request.urlopen(f'http://127.0.0.1:{p}/health/live', timeout=4)" || exit 1

CMD ["python", "main.py"]
