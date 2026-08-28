# syntax=docker/dockerfile:1.7

FROM python:3.12-slim-bookworm AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    APP_HOME=/app \
    PYTHONPATH=/app:/

RUN groupadd --gid 10001 app \
    && useradd --uid 10001 --gid app --shell /usr/sbin/nologin --create-home app \
    && apt-get update \
    && apt-get install -y --no-install-recommends libpq5 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR ${APP_HOME}

FROM base AS deps
COPY services/context-service/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

FROM deps AS runtime
COPY libs /libs
COPY services/context-service/app ./app
COPY services/context-service/alembic ./alembic
COPY services/context-service/alembic.ini ./alembic.ini

# Docker socket access requires group; run as root for local Compose docker collector,
# or mount socket with appropriate perms. Prefer non-root where possible.
USER app

EXPOSE 8020

HEALTHCHECK --interval=15s --timeout=5s --start-period=35s --retries=5 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8020/ready', timeout=3)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8020", "--proxy-headers", "--forwarded-allow-ips", "*"]
