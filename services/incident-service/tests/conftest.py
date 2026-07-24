"""Pytest fixtures — in-memory SQLite for unit tests."""

from __future__ import annotations

import os

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

# Configure env BEFORE importing app modules that read settings
os.environ["RUN_MIGRATIONS_ON_STARTUP"] = "false"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["DATABASE_URL_SYNC"] = "sqlite://"
os.environ["LOG_LEVEL"] = "WARNING"

from app.config import get_settings  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.session import get_db, get_engine, get_session_factory, reset_engine  # noqa: E402
from app.main import create_app  # noqa: E402
from app.models import AlertPayload, Incident, TimelineEvent  # noqa: E402, F401


@pytest.fixture(autouse=True)
def _clear_settings_cache():
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
async def db_session(db_engine) -> AsyncSession:
    factory = get_session_factory()
    async with factory() as session:
        yield session
        await session.rollback()


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


def sample_alertmanager_payload(
    *,
    alertname: str = "SampleAppHighErrorRate",
    severity: str = "critical",
    status: str = "firing",
    service: str = "sample-app",
    instance: str = "sample-app:8080",
    namespace: str = "default",
    pod: str = "sample-app-0",
) -> dict:
    return {
        "version": "4",
        "groupKey": f'{{}}:{alertname}',
        "status": status,
        "receiver": "critical-webhook",
        "groupLabels": {"alertname": alertname},
        "commonLabels": {
            "alertname": alertname,
            "severity": severity,
            "service": service,
        },
        "commonAnnotations": {
            "summary": f"{alertname} firing",
            "description": "Error rate exceeded threshold",
        },
        "externalURL": "http://alertmanager:9093",
        "alerts": [
            {
                "status": status,
                "labels": {
                    "alertname": alertname,
                    "severity": severity,
                    "service": service,
                    "instance": instance,
                    "namespace": namespace,
                    "pod": pod,
                    "team": "sre",
                },
                "annotations": {
                    "summary": f"{alertname} firing",
                    "description": "Error rate exceeded threshold",
                },
                "startsAt": "2026-07-24T10:00:00Z",
                "endsAt": "0001-01-01T00:00:00Z",
                "generatorURL": "http://prometheus:9090/graph",
                "fingerprint": "abc123",
            }
        ],
    }
