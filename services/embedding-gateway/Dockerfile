# syntax=docker/dockerfile:1.7

FROM python:3.12-slim-bookworm AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    APP_HOME=/app \
    PYTHONPATH=/app:/libs

RUN groupadd --gid 10001 app \
    && useradd --uid 10001 --gid app --shell /usr/sbin/nologin --create-home app \
    && apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /data \
    && chown -R app:app /data

WORKDIR ${APP_HOME}

FROM base AS deps
COPY services/embedding-gateway/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

FROM deps AS runtime
COPY libs /libs
COPY services/embedding-gateway/app ./app

# Pre-download ONNX MiniLM so first request does not trip circuit breaker
RUN python -c "from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2; ONNXMiniLM_L6_V2()(['warmup'])" \
    && chown -R app:app /home/app /data || true

USER app
EXPOSE 8041

HEALTHCHECK --interval=15s --timeout=5s --start-period=60s --retries=8 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8041/ready', timeout=3)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8041"]
