"""Incident Service FastAPI entrypoint."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app import __version__
from app.api import health, incidents, webhooks
from app.config import get_settings
from app.metrics import init_metrics
from app.middleware import ObservabilityMiddleware

try:
    from libs.common.logging import configure_logging, get_logger
    from libs.common.otel import instrument_fastapi, setup_otel
except ImportError:
    import logging
    import sys

    import structlog as _structlog

    def configure_logging(*, service_name: str, level: str = "INFO", environment: str = "local") -> None:
        logging.basicConfig(stream=sys.stdout, level=level)
        _structlog.configure(
            processors=[
                _structlog.processors.TimeStamper(fmt="iso"),
                _structlog.processors.JSONRenderer(),
            ]
        )

    def get_logger(name: str | None = None):
        return _structlog.get_logger(name)

    def setup_otel(**kwargs):
        return False

    def instrument_fastapi(app, **kwargs):
        return False


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(
        service_name=settings.service_name,
        level=settings.log_level,
        environment=settings.environment,
    )
    log = get_logger(__name__)
    init_metrics(settings.version, settings.environment)

    setup_otel(
        service_name=settings.service_name,
        environment=settings.environment,
        endpoint=settings.otel_exporter_otlp_endpoint,
        enabled=settings.otel_traces_exporter.lower() not in {"none", "false", "0", ""},
    )

    if settings.run_migrations_on_startup:
        log.info("running_migrations")
        from app.db.migrate import run_migrations

        run_migrations()
        log.info("migrations_complete")

    from app.services.eventbus_client import close_event_bus, connect_event_bus

    await connect_event_bus()

    log.info("service_starting", version=__version__)
    yield
    await close_event_bus()
    log.info("service_stopping")


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title="AI SRE Copilot — Incident Service",
        description=(
            "Alertmanager webhook ingestion, fingerprint-based deduplication, "
            "incident timeline persistence, and REST APIs."
        ),
        version=__version__,
        lifespan=lifespan,
    )
    application.add_middleware(ObservabilityMiddleware)
    application.include_router(health.router)
    application.include_router(webhooks.router)
    application.include_router(incidents.router)
    application.include_router(incidents.v1_router)
    instrument_fastapi(application, service_name=settings.service_name)

    @application.get("/metrics", include_in_schema=False)
    async def metrics() -> Response:
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    @application.get("/")
    async def root() -> dict:
        return {
            "service": settings.service_name,
            "version": __version__,
            "docs": "/docs",
            "health": "/health",
            "webhooks": "/webhooks/alertmanager",
            "incidents": "/incidents",
        }

    return application


app = create_app()
