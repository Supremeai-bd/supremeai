# ══════════════════════════════════════════════════════════
# SupremeAI 2.0 — Root Dockerfile (Distroless variant)
# Target: Maximum security with gcr.io/distroless
# ══════════════════════════════════════════════════════════

# Stage 1: Build dependencies
FROM python:3.14-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir poetry && poetry config virtualenvs.in-project true

# ── Install CPU-only PyTorch FIRST ──
WORKDIR /app/backend
RUN python -m venv /app/backend/.venv && \
    /app/backend/.venv/bin/pip install --no-cache-dir --upgrade pip && \
    /app/backend/.venv/bin/pip install --no-cache-dir \
        torch torchvision --index-url https://download.pytorch.org/whl/cpu && \
    /app/backend/.venv/bin/pip install --no-cache-dir "setuptools<82.0.0"

COPY backend/pyproject.toml ./
COPY backend/poetry.lock* ./
RUN poetry lock --no-update || true
RUN poetry install --no-interaction --no-ansi --no-root --only main --with ml || \
    poetry install --no-interaction --no-ansi --no-root --only main

# ── Force CPU torch, remove CUDA bloat ──
RUN /app/backend/.venv/bin/pip uninstall -y \
    nvidia-cuda-nvrtc-cu12 nvidia-cuda-runtime-cu12 nvidia-cuda-cupti-cu12 \
    nvidia-cudnn-cu12 nvidia-cublas-cu12 nvidia-cufft-cu12 nvidia-curand-cu12 \
    nvidia-cusolver-cu12 nvidia-cusparse-cu12 nvidia-nccl-cu12 nvidia-nvtx-cu12 \
    nvidia-nvjitlink-cu12 triton 2>/dev/null || true && \
    /app/backend/.venv/bin/pip install --no-cache-dir torch torchvision \
        --index-url https://download.pytorch.org/whl/cpu

# ── Pre-download EasyOCR models ──
RUN /app/backend/.venv/bin/pip install --no-cache-dir --no-build-isolation "openai-whisper==20240930" 2>/dev/null || true
RUN mkdir -p /root/.EasyOCR/model && \
    /app/backend/.venv/bin/python -c "import easyocr; easyocr.Reader(['bn', 'en'])" 2>/dev/null || true && \
    rm -f /root/.EasyOCR/model/*.zip 2>/dev/null || true

# ── Aggressive cleanup ──
RUN find /app/backend/.venv -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true && \
    find /app/backend/.venv -type d -name "tests" -exec rm -rf {} + 2>/dev/null || true && \
    find /app/backend/.venv -type d -name "test" -exec rm -rf {} + 2>/dev/null || true && \
    find /app/backend/.venv -type f -name "*.pyc" -delete 2>/dev/null || true && \
    rm -rf /app/backend/.venv/lib/python3.11/site-packages/torch/test 2>/dev/null || true && \
    rm -rf /app/backend/.venv/lib/python3.11/site-packages/caffe2 2>/dev/null || true


# Stage 2: Final minimal runner (Google Distroless)
FROM gcr.io/distroless/python3-debian12 AS runner

WORKDIR /app

COPY --from=builder /app/backend/.venv /app/backend/.venv
COPY backend /app/backend
COPY --from=builder /root/.EasyOCR /home/nonroot/.EasyOCR

ENV PATH="/app/backend/.venv/bin:$PATH"
ENV PYTHONPATH="/app/backend"
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

WORKDIR /app/backend

ENTRYPOINT ["/app/backend/.venv/bin/python", "main.py"]