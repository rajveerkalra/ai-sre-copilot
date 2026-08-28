"""Investigation Service entrypoint."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app import __version__
from app.api.routes import router
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
    from app.services.dispatch import run_dispatch_consumer, run_investigation_worker

    stop_event = asyncio.Event()
    background_tasks = [asyncio.create_task(run_dispatch_consumer(stop_event))]
    for worker_id in range(settings.max_concurrent_investigations):
        background_tasks.append(
            asyncio.create_task(run_investigation_worker(worker_id, stop_event))
        )

    log.info(
        "service_starting",
        version=__version__,
        llm_model=settings.llm_model,
        llm_enabled=settings.llm_enabled,
        model_gateway=settings.model_gateway_url,
        max_concurrent_investigations=settings.max_concurrent_investigations,
    )
    yield
    stop_event.set()
    for task in background_tasks:
        try:
            await asyncio.wait_for(task, timeout=5.0)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            task.cancel()
    log.info("service_stopping")


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title="AI SRE Copilot — Investigation Service",
        description=(
            "Evidence-cited AI investigation via LangGraph multi-agent workflow. "
            "Reasons only from collected context; never invents causes."
        ),
        version=__version__,
        lifespan=lifespan,
    )
    application.add_middleware(ObservabilityMiddleware)
    application.include_router(router)

    @application.get("/metrics", include_in_schema=False)
    async def metrics() -> Response:
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    @application.get("/")
    async def root() -> dict:
        return {
            "service": settings.service_name,
            "version": __version__,
            "docs": "/docs",
            "investigate": "POST /incidents/{id}/investigate",
            "model": settings.llm_model,
            "model_gateway": settings.model_gateway_url,
        }

    return application


app = create_app()
