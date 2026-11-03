FROM python:3.11-slim
WORKDIR /app

COPY requirements*.txt /app/
RUN pip install --no-cache-dir -r requirements.txt || pip install --no-cache-dir fastapi uvicorn httpx pydantic pyyaml

COPY contracts/ /app/contracts/
COPY config/ /app/config/
COPY middleware/ /app/gateway/middleware/
COPY service/ /app/gateway/service/
COPY gateway/ /app/gateway/
COPY runtime/ /app/runtime/

ENV PYTHONPATH="/app"
EXPOSE 8787

CMD ["sh", "-c", "(python runtime/infisical_bootstrap.py uvicorn gateway.service.app:app --host 0.0.0.0 --port ${PORT:-8787}) || (uvicorn gateway.service.app:app --host 0.0.0.0 --port ${PORT:-8787})"]
