"""Embedding Gateway entrypoint."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app import __version__
from app.api.routes import router
from app.config import get_settings
from app.metrics import init_metrics
from app.services.gateway import get_gateway

try:
    from libs.common.logging import configure_logging, get_logger
except ImportError:
    import logging
    import sys

    import structlog as _s

    def configure_logging(*, service_name: str, level: str = "INFO", environment: str = "local") -> None:
        logging.basicConfig(stream=sys.stdout, level=level)

    def get_logger(name=None):
        return _s.get_logger(name)


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
    gw = get_gateway()
    await gw.startup()
    log.info(
        "service_starting",
        version=__version__,
        provider=settings.embedding_provider,
        model=settings.embedding_model,
    )
    yield
    await gw.shutdown()
    log.info("service_stopping")


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title="AI SRE Copilot — Embedding Gateway",
        description="Provider-abstracted embeddings with Redis cache and resilience.",
        version=__version__,
        lifespan=lifespan,
    )
    application.include_router(router)

    @application.get("/metrics", include_in_schema=False)
    async def metrics() -> Response:
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    @application.get("/")
    async def root() -> dict:
        return {
            "service": settings.service_name,
            "version": __version__,
            "provider": settings.embedding_provider,
            "docs": "/docs",
        }

    return application


app = create_app()
