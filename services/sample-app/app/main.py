"""Sample application entrypoint."""

from __future__ import annotations

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app import __version__
from app.config import get_settings
from app.metrics import init_metrics
from app.middleware import ObservabilityMiddleware
from app.routes_api import router as api_router
from app.routes_faults import router as faults_router
from app.routes_health import router as health_router
from app.telemetry import setup_telemetry

# Import shared logging from mounted libs volume / PYTHONPATH
try:
    from libs.common.logging import configure_logging, get_logger
except ImportError:  # local pytest without compose mount
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
    setup_telemetry(settings)
    init_metrics(settings.version, settings.environment)
    log = get_logger(__name__)
    log.info(
        "service_starting",
        version=__version__,
        environment=settings.environment,
    )
    yield
    log.info("service_stopping")


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title="AI SRE Copilot — Sample App",
        description=(
            "Demo FastAPI workload with structured logging, Prometheus metrics, "
            "OpenTelemetry hooks, and fault injection for incident simulations."
        ),
        version=__version__,
        lifespan=lifespan,
    )
    application.add_middleware(ObservabilityMiddleware)
    application.include_router(health_router)
    application.include_router(api_router)
    application.include_router(faults_router)

    @application.get("/metrics", include_in_schema=False)
    async def metrics() -> Response:
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    @application.get("/")
    async def root() -> dict:
        return {
            "service": settings.service_name,
            "version": __version__,
            "docs": "/docs",
            "metrics": "/metrics",
            "faults": "/faults",
            "health": "/healthz",
        }

    return application


app = create_app()
