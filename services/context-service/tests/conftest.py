"""Pytest fixtures with mocked upstreams."""

from __future__ import annotations

import os
import uuid
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

os.environ["RUN_MIGRATIONS_ON_STARTUP"] = "false"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["DATABASE_URL_SYNC"] = "sqlite://"
os.environ["LOG_LEVEL"] = "WARNING"
os.environ["ENABLE_DOCKER_COLLECTOR"] = "false"
os.environ["ENABLE_KUBERNETES_COLLECTOR"] = "false"
os.environ["COLLECTOR_RETRIES"] = "2"
os.environ["COLLECTOR_BACKOFF_BASE_SECONDS"] = "0.01"

from app.config import get_settings  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.session import get_db, get_engine, get_session_factory, reset_engine  # noqa: E402
from app.main import create_app  # noqa: E402
from app.models import CollectorError, CollectorRun, InvestigationContext  # noqa: E402, F401


@pytest.fixture(autouse=True)
def _clear_settings():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest_asyncio.fixture
async def db_engine():
    await reset_engine()
    get_settings.cache_clear()
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await reset_engine()


@pytest_asyncio.fixture
async def client(db_engine):
    app = create_app()

    async def _override_get_db():
        factory = get_session_factory()
        async with factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.fixture
def incident_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def mock_incident_meta(incident_id):
    return {
        "id": str(incident_id),
        "title": "SampleAppHighErrorRate firing",
        "status": "open",
        "severity": "critical",
        "alertname": "SampleAppHighErrorRate",
        "service": "sample-app",
        "namespace": "default",
        "fingerprint": "abc",
        "created_at": "2026-07-24T10:00:00+00:00",
    }
