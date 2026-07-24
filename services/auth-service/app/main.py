from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app import __version__
from app.api.routes import router
from app.config import get_settings
from app.metrics import init_metrics

try:
    from libs.common.logging import configure_logging, get_logger
    from libs.common.otel import instrument_fastapi, setup_otel
except ImportError:
    import logging
    import sys

    import structlog as _s

    def configure_logging(*, service_name: str, level: str = "INFO", environment: str = "local") -> None:
        logging.basicConfig(stream=sys.stdout, level=level)

    def get_logger(name=None):
        return _s.get_logger(name)

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
        enabled=settings.otel_traces_exporter.lower() not in {"none", "false", "0"},
    )
    log.info("service_starting", version=__version__)
    yield
    log.info("service_stopping")


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title="AI SRE Copilot — Auth Service",
        description="JWT authentication, identity, and RBAC claims (Phase 7).",
        version=__version__,
        lifespan=lifespan,
    )
    application.include_router(router)
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
            "login": "POST /auth/login",
            "api_v1": "/api/v1/auth/login",
        }

    return application


app = create_app()
