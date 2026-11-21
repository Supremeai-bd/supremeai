# SupremeAI Browser - lightweight Gemini cookie relay (no browser, ~30MB RAM)
FROM python:3.12-slim

WORKDIR /app

# Audit 2026-11-19 (#6): never run the relay as root.
RUN addgroup --system supremeai && adduser --system supremeai --ingroup supremeai

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=supremeai:supremeai *.py ./

ENV PYTHONUNBUFFERED=1
ENV PORT=8080

USER supremeai
EXPOSE 8080

# Audit 2026-11-19 (#6): Give Render an in-image liveness verdict.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health', timeout=4)" || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
