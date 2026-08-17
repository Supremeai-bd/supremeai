# apps/hf-space/Dockerfile
# বাংলা মন্তব্য: Text Generation Inference (TGI)-এর পরিবর্তে কাস্টম পাইথন সার্ভার রান করা হচ্ছে।
# সিকিউরিটি সুরক্ষার জন্য non-root appuser তৈরি করা হয়েছে।

FROM python:3.10-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    MODEL_PATH=/models/supreme-hybrid-8b-q4.gguf

RUN apt-get update && apt-get install -y --no-install-recommends build-essential && \
    rm -rf /var/lib/apt/lists/* && \
    pip install --no-cache-dir llama-cpp-python fastapi uvicorn loguru structlog

RUN useradd -m -u 1000 appuser

COPY supreme-hybrid-8b-q4.gguf /models/
COPY server.py /app/

USER appuser
EXPOSE 80

CMD ["uvicorn", "app.server:app", "--host", "0.0.0.0", "--port", "80"]
