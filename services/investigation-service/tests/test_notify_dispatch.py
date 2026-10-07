"""Completed investigations fire an RCA-complete notification via
NotificationDispatcher -- fire-and-forget, never blocking the response."""

from __future__ import annotations

import asyncio
import uuid
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.session import get_db, reset_engine
from app.main import create_app
from tests.test_fallback import SAMPLE_CONTEXT


@pytest_asyncio.fixture
async def db_engine(tmp_path, monkeypatch):
    db_path = tmp_path / "inv_notify.db"
    url = f"sqlite+aiosqlite:///{db_path}"
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("DATABASE_URL_SYNC", f"sqlite:///{db_path}")
    monkeypatch.setenv("RUN_MIGRATIONS_ON_STARTUP", "false")
    monkeypatch.setenv("LLM_ENABLED", "false")
    monkeypatch.setenv("CACHE_ENABLED", "false")
    monkeypatch.setenv("AUTO_COLLECT_CONTEXT_IF_MISSING", "false")
    from app.config import get_settings

    get_settings.cache_clear()
    await reset_engine()

    engine = create_async_engine(url, connect_args={"check_same_thread": False})
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine
    await engine.dispose()
    await reset_engine()
    get_settings.cache_clear()


@pytest_asyncio.fixture
async def client(db_engine):
    factory = async_sessionmaker(bind=db_engine, class_=AsyncSession, expire_on_commit=False)

    async def _override_db():
        async with factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app = create_app()
    app.dependency_overrides[get_db] = _override_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


async def _drain_background_tasks() -> None:
    # The notification is dispatched via asyncio.create_task rather than
    # awaited inline (see orchestrator._fire_rca_notification), so give the
    # event loop a couple of turns to run it before asserting.
    for _ in range(5):
        await asyncio.sleep(0)


@pytest.mark.asyncio
async def test_completed_investigation_dispatches_rca_notification(client: AsyncClient):
    incident_id = uuid.uuid4()
    context_payload = {
        "context": SAMPLE_CONTEXT,
        "metrics": SAMPLE_CONTEXT["metrics"],
        "logs": SAMPLE_CONTEXT["logs"],
        "kubernetes": SAMPLE_CONTEXT["kubernetes"],
        "deployment": SAMPLE_CONTEXT["deployment"],
        "system": SAMPLE_CONTEXT["system"],
        "metadata": SAMPLE_CONTEXT["metadata"],
    }

    async def fake_fetch(inc_id: uuid.UUID) -> dict[str, Any]:
        return context_payload

    async def fake_search(*args, **kwargs):
        return {
            "results": [
                {
                    "id": "rb-high-error",
                    "title": "High Error Rate",
                    "content": "Investigate elevated 5xx",
                    "score": 0.91,
                    "evidence_id": "runbook-rb-high",
                }
            ]
        }

    fake_dispatcher = AsyncMock()
    fake_dispatcher.any_enabled = True

    with patch("app.services.orchestrator.fetch_context", side_effect=fake_fetch):
        with patch(
            "app.services.resilient_http.get_json_post",
            new=AsyncMock(side_effect=fake_search),
        ):
            with patch(
                "app.services.orchestrator.get_notification_dispatcher",
                return_value=fake_dispatcher,
            ):
                resp = await client.post(f"/incidents/{incident_id}/investigate", json={})
                assert resp.status_code == 200, resp.text
                await _drain_background_tasks()

    fake_dispatcher.notify_rca_complete.assert_called_once()
    _, kwargs = fake_dispatcher.notify_rca_complete.call_args
    assert kwargs["incident_id"] == str(incident_id)
    assert kwargs["used_fallback"] is True


@pytest.mark.asyncio
async def test_no_notification_dispatch_when_nothing_configured(client: AsyncClient):
    incident_id = uuid.uuid4()
    context_payload = {
        "context": SAMPLE_CONTEXT,
        "metrics": SAMPLE_CONTEXT["metrics"],
        "logs": SAMPLE_CONTEXT["logs"],
        "kubernetes": SAMPLE_CONTEXT["kubernetes"],
        "deployment": SAMPLE_CONTEXT["deployment"],
        "system": SAMPLE_CONTEXT["system"],
        "metadata": SAMPLE_CONTEXT["metadata"],
    }

    async def fake_fetch(inc_id: uuid.UUID) -> dict[str, Any]:
        return context_payload

    async def fake_search(*args, **kwargs):
        return {"results": []}

    fake_dispatcher = AsyncMock()
    fake_dispatcher.any_enabled = False

    with patch("app.services.orchestrator.fetch_context", side_effect=fake_fetch):
        with patch(
            "app.services.resilient_http.get_json_post",
            new=AsyncMock(side_effect=fake_search),
        ):
            with patch(
                "app.services.orchestrator.get_notification_dispatcher",
                return_value=fake_dispatcher,
            ):
                resp = await client.post(f"/incidents/{incident_id}/investigate", json={})
                assert resp.status_code == 200, resp.text
                await _drain_background_tasks()

    fake_dispatcher.notify_rca_complete.assert_not_called()
