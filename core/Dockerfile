# Stage 1: Runtime & Verification Runner
FROM python:3.11-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080

RUN apt-get update && apt-get install -y --no-install-recommends curl perl-base bash && rm -rf /var/lib/apt/lists/* \
    && addgroup --system supremeai && adduser --system supremeai --ingroup supremeai

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir pytest pytest-asyncio pytest-cov pydantic fastapi httpx cryptography pyotp bandit pip-audit

COPY --chown=supremeai:supremeai . .
RUN mkdir -p /app/data /app/uploads /app/logs /app/tmp && chown -R supremeai:supremeai /app/data /app/uploads /app/logs /app/tmp

# =============================================================================
# RENDER HEAVY CI BATTERY: Runs Full Pytest, Migration, RLS, Secret, & Compile checks
# If any test fails, Render build terminates with failure and blocks the PR.
# =============================================================================
RUN chmod +x scripts/run_render_heavy_suite.sh && bash scripts/run_render_heavy_suite.sh

USER supremeai
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=5 \
  CMD python -c "import os, urllib.request; p=os.getenv('PORT','8080'); urllib.request.urlopen(f'http://127.0.0.1:{p}/health/live', timeout=4)" || exit 1

CMD ["python", "main.py"]
