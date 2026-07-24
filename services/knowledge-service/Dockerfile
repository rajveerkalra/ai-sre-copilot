# syntax=docker/dockerfile:1.7

FROM python:3.12-slim-bookworm AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app:/libs

RUN groupadd --gid 10001 app \
    && useradd --uid 10001 --gid app --shell /usr/sbin/nologin --create-home app \
    && mkdir -p /data/chroma /seed \
    && chown -R app:app /data /seed

WORKDIR /app

FROM base AS deps
COPY services/knowledge-service/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

FROM deps AS runtime
COPY libs /libs
COPY services/knowledge-service/app ./app
COPY runbooks /seed/runbooks
COPY services/knowledge-service/seed /seed/extra

USER app
EXPOSE 8030

ENV SEED_DIR=/seed

HEALTHCHECK --interval=20s --timeout=10s --start-period=60s --retries=8 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8030/ready', timeout=5)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8030"]
