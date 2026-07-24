"""Knowledge Service entrypoint."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app import __version__
from app.api.routes import router
from app.config import get_settings

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
    from app.services.store import get_store

    store = get_store()
    await store.ensure_cache()
    if settings.seed_on_startup:
        # Wait briefly for embedding-gateway model warmup
        import asyncio

        for attempt in range(1, 6):
            try:
                n = await store.seed_from_directory(settings.seed_dir)
                log.info("knowledge_seeded", count=n, documents=store.count())
                break
            except Exception as exc:  # noqa: BLE001
                log.warning("knowledge_seed_retry", attempt=attempt, error=str(exc))
                if attempt == 5:
                    log.error("knowledge_seed_failed", error=str(exc))
                    raise
                await asyncio.sleep(min(30, 2 ** attempt))
    log.info("service_starting", version=__version__)
    yield
    await store.close()
    log.info("service_stopping")


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title="AI SRE Copilot — Knowledge Service",
        description="Runbook indexing + semantic search via Embedding Gateway + ChromaDB.",
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
            "docs": "/docs",
            "search": "POST /search",
            "embedding_gateway": settings.embedding_gateway_url,
        }

    return application


app = create_app()
