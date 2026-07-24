"""Context Service entrypoint."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app import __version__
from app.api import context as context_api
from app.api import health
from app.config import get_settings
from app.metrics import init_metrics
from app.middleware import ObservabilityMiddleware

try:
    from libs.common.logging import configure_logging, get_logger
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
    if settings.run_migrations_on_startup:
        log.info("running_migrations")
        from app.db.migrate import run_migrations

        run_migrations()
        log.info("migrations_complete")
    log.info("service_starting", version=__version__)
    yield
    log.info("service_stopping")


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title="AI SRE Copilot — Context Service",
        description=(
            "Automated evidence collection from Prometheus, Loki, Kubernetes, "
            "deployments, and system state. Feeds Phase 4 AI investigation."
        ),
        version=__version__,
        lifespan=lifespan,
    )
    application.add_middleware(ObservabilityMiddleware)
    application.include_router(health.router)
    application.include_router(context_api.router)

    @application.get("/metrics", include_in_schema=False)
    async def metrics() -> Response:
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    @application.get("/")
    async def root() -> dict:
        return {
            "service": settings.service_name,
            "version": __version__,
            "docs": "/docs",
            "collect": "POST /incidents/{id}/collect",
            "context": "GET /incidents/{id}/context",
        }

    return application


app = create_app()
