# Stage 1: Runtime
FROM python:3.11-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080

RUN apt-get update && apt-get install -y --no-install-recommends curl perl-base && rm -rf /var/lib/apt/lists/* \
    && addgroup --system supremeai && adduser --system supremeai --ingroup supremeai

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=supremeai:supremeai . .
RUN mkdir -p /app/data /app/uploads /app/logs /app/tmp && chown -R supremeai:supremeai /app/data /app/uploads /app/logs /app/tmp

USER supremeai
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=5 \
  CMD python -c "import os, urllib.request; p=os.getenv('PORT','8080'); urllib.request.urlopen(f'http://127.0.0.1:{p}/health/live', timeout=4)" || exit 1

CMD ["python", "main.py"]
