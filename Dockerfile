FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN pip install poetry && poetry config virtualenvs.create false

COPY backend/pyproject.toml backend/poetry.lock* ./backend/
WORKDIR /app/backend
RUN poetry install --no-interaction --no-ansi --no-root

WORKDIR /app
COPY . .

WORKDIR /app/backend
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]