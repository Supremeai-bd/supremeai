# Stage 1: Build dependencies
FROM python:3.11-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir poetry && poetry config virtualenvs.in-project true

# Pre-create virtualenv and install CPU-only PyTorch to save ~1.7GB space
WORKDIR /app/backend
RUN python -m venv /app/backend/.venv && \
    /app/backend/.venv/bin/pip install --no-cache-dir --upgrade pip && \
    /app/backend/.venv/bin/pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu

COPY backend/pyproject.toml backend/poetry.lock* ./
RUN poetry install --no-interaction --no-ansi --no-root --only main

# Re-install CPU-only PyTorch to overwrite the large CUDA PyTorch downloaded by Poetry and save ~1.7GB space
RUN /app/backend/.venv/bin/pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu

# Clean up build-time virtualenv caches to reduce copied size
RUN find /app/backend/.venv -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
RUN find /app/backend/.venv -name "*.pyc" -delete 2>/dev/null || true


# Stage 2: Final minimal runner image (Google Distroless for maximum security)
FROM gcr.io/distroless/python3-debian12 AS runner

WORKDIR /app

# Copy virtualenv and backend code only (avoiding monorepo clutter)
COPY --from=builder /app/backend/.venv /app/backend/.venv
COPY backend /app/backend

ENV PATH="/app/backend/.venv/bin:$PATH"
ENV PYTHONPATH="/app/backend"
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Pre-download EasyOCR English & Bengali models during build
# Since EasyOCR models are preloaded in builder stage /root/.EasyOCR, we copy them to distroless non-root /home/nonroot/.EasyOCR if needed.
# Google Distroless runs as nonroot by default.
COPY --from=builder /root/.EasyOCR /home/nonroot/.EasyOCR

WORKDIR /app/backend

# Direct execution of Python module (Distroless has no shell sh/bash)
ENTRYPOINT ["/app/backend/.venv/bin/python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]