"""Integration tests with mocked model gateway, context, and knowledge."""

from __future__ import annotations

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
from app.services.evidence import build_evidence_catalog
from tests.test_fallback import SAMPLE_CONTEXT


@pytest_asyncio.fixture
async def db_engine(tmp_path, monkeypatch):
    db_path = tmp_path / "inv.db"
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


@pytest.mark.asyncio
async def test_health(client: AsyncClient):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["service"] == "investigation-service"


@pytest.mark.asyncio
async def test_investigate_with_mocked_context(client: AsyncClient):
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
        assert inc_id == incident_id
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

    with patch("app.services.orchestrator.fetch_context", side_effect=fake_fetch):
        with patch(
            "app.services.resilient_http.get_json_post",
            new=AsyncMock(side_effect=fake_search),
        ):
            resp = await client.post(f"/incidents/{incident_id}/investigate", json={})
            assert resp.status_code == 200, resp.text
            body = resp.json()
            assert body["accepted"] is True
            assert body["used_fallback"] is True
            assert body["root_cause"]
            assert body["root_cause"] != "Insufficient evidence"
            assert body["confidence"] and body["confidence"] > 0
            inv_id = body["investigation_id"]

    rca = await client.get(f"/investigations/{inv_id}/rca")
    assert rca.status_code == 200
    assert "metric-error_rate" in rca.json()["evidence_ids"]

    evidence = await client.get(f"/investigations/{inv_id}/evidence")
    assert evidence.status_code == 200
    assert evidence.json()["count"] >= 3


@pytest.mark.asyncio
async def test_investigate_missing_context(client: AsyncClient):
    incident_id = uuid.uuid4()

    async def missing(_):
        from app.services.orchestrator import ContextMissingError

        raise ContextMissingError("No investigation context available")

    with patch("app.services.orchestrator.fetch_context", side_effect=missing):
        resp = await client.post(f"/incidents/{incident_id}/investigate", json={})
        assert resp.status_code == 409


@pytest.mark.asyncio
async def test_graph_produces_citations():
    from app.graph.workflow import investigation_graph

    evidence = build_evidence_catalog(SAMPLE_CONTEXT)
    state = {
        "incident_id": str(uuid.uuid4()),
        "investigation_id": str(uuid.uuid4()),
        "correlation_id": "test",
        "context": SAMPLE_CONTEXT,
        "evidence": evidence,
        "errors": [],
    }

    async def fake_search(*args, **kwargs):
        return {"results": []}

    with patch(
        "app.services.resilient_http.get_json_post",
        new=AsyncMock(side_effect=fake_search),
    ):
        final = await investigation_graph.ainvoke(state)

    assert final.get("report")
    assert final.get("used_fallback") is True
    for eid in final["report"]["evidence_ids"]:
        assert eid in {e["evidence_id"] for e in final["aggregated_evidence"]}
