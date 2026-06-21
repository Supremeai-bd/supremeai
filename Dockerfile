# Stage 1: Build dependencies
FROM python:3.11-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y \
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


# Stage 2: Final minimal runner image
FROM python:3.11-slim AS runner

WORKDIR /app

# Install only runtime system dependencies
RUN apt-get update && apt-get install -y \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copy virtualenv and code from builder
COPY --from=builder /app/backend/.venv /app/backend/.venv
COPY . .

ENV PATH="/app/backend/.venv/bin:$PATH"
ENV PYTHONPATH="/app"
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Pre-download EasyOCR English & Bengali models during build and clean zip files to save space
RUN python -c "import easyocr; easyocr.Reader(['bn', 'en'])" && \
    rm -f /root/.EasyOCR/model/*.zip

WORKDIR /app/backend
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]