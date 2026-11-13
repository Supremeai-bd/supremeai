# STATUS NOTE (audit F-9): currently ORPHANED — no compose file, workflow or doc
# references this Dockerfile. Verify intent before use; see production audit F-9.
# Issue #514 (BE-08): keep this image on the same interpreter minor as the
# core/scraper Dockerfiles and the CI runner toolchain (3.12) — avoids
# behavioral drift across Python minor versions between worker and API images.
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
# Create and switch to non-root user for security compliance (Trap #97)
RUN addgroup --system supremeai && adduser --system supremeai --ingroup supremeai && \
    chown -R supremeai:supremeai /app
USER supremeai

CMD ["python", "main.py"]
