# Stage 1: Builder
FROM python:3.11-slim-bookworm AS builder
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    POETRY_HTTP_TIMEOUT=300

WORKDIR /app
RUN pip install --no-cache-dir --default-timeout=120 poetry
RUN poetry config virtualenvs.in-project true

# Cache layer: install only main dependencies (tools group excluded to save space on Render free tier)
COPY backend/pyproject.toml backend/poetry.lock* ./
RUN poetry install --no-interaction --no-ansi --no-root --only main && python -m compileall .venv


# Stage 2: Runner
FROM python:3.11-slim AS runner
WORKDIR /app

# Install runtime dependencies securely (curl added for container HEALTHCHECK)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get purge -y --auto-remove -o APT::AutoRemove::RecommendsImportant=false

# Create non-root user with home directory
RUN adduser --disabled-password --gecos '' --home /home/appuser appuser

# Copy virtual environment from builder and application source code from workspace
COPY --from=builder --chown=appuser:appuser /app/.venv /app/.venv
COPY --chown=appuser:appuser backend/ /app/
# বাংলা: scripts/ রুট-লেভেলে (backend/-এর বাইরে) থাকে, কিন্তু core/lifespan.py (BugProphet)
# এবং core/error_remediation.py (RefactorWiz) রানটাইমে এটা ইম্পোর্ট/এক্সিকিউট করে —
# আগে এটা image-এ কপি হতো না, ফলে production-এ "No module named 'scripts.devops'"
# ওয়ার্নিং দিয়ে ওই ফিচারগুলো নিঃশব্দে বন্ধ থাকত।
COPY --chown=appuser:appuser scripts/ /app/scripts/




# Security hardening: remove sensitive files
RUN rm -rf /app/.git /app/.env* /app/.env /app/secrets.sh || true

# Set working directory with proper permissions
WORKDIR /app

# Create secrets directory and grant ownership to non-root appuser
RUN mkdir -p /etc/secrets && chown -R appuser:appuser /etc/secrets

# Security: non-root user
USER appuser

# Environment variables
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH="/app" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# বাংলা মন্তব্য: .venv-এ হাজার হাজার ফাইলের ওপর chmod -R চালানো overlayfs-এ ডিস্ক I/O হ্যাং করে,
# আর এটি ইতিমধ্যেই --chown=appuser:appuser দিয়ে সুরক্ষিত, তাই অপ্রয়োজনীয় chmod বাদ দেওয়া হলো।

# Expose port
EXPOSE 8080

# Health check with security considerations
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD curl -sf http://localhost:${PORT:-8080}/health || exit 1

# Security: Run application with proper user privileges
CMD ["sh", "-c", "exec python main.py"]
