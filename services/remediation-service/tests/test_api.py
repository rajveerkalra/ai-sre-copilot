"""Unit tests — mapper + approval gate."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.session import get_db, reset_engine
from app.main import create_app
from app.models import ActionType, ProposalStatus, RemediationProposal, RiskLevel
from app.services.mapper import map_rca_to_proposals


def test_map_error_storm_produces_clear_fault():
    props = map_rca_to_proposals(
        incident_id=uuid.uuid4(),
        investigation_id=uuid.uuid4(),
        rca={
            "root_cause": "Elevated application error rate (error storm)",
            "confidence": 85,
            "next_steps": ["Disable fault injection if demo", "Roll back if regression"],
            "evidence_ids": ["metric-error_rate"],
        },
    )
    types = {p["action_type"] for p in props}
    assert ActionType.CLEAR_FAULT in types
    clear = next(p for p in props if p["action_type"] == ActionType.CLEAR_FAULT)
    assert clear["parameters"]["fault"] == "error_storm"
    assert clear["requires_dry_run_default"] is False
    assert ActionType.ROLLBACK in types
    assert ActionType.RUNBOOK_MANUAL in types


def test_map_insufficient_evidence():
    props = map_rca_to_proposals(
        incident_id=uuid.uuid4(),
        investigation_id=None,
        rca={
            "root_cause": "Insufficient evidence",
            "confidence": 0,
            "next_steps": ["Re-run context collection"],
            "evidence_ids": [],
        },
    )
    assert len(props) == 1
    assert props[0]["action_type"] == ActionType.RUNBOOK_MANUAL
    assert props[0]["confidence"] == 0.0


@pytest_asyncio.fixture
async def client(tmp_path, monkeypatch):
    db_path = tmp_path / "rem.db"
    url = f"sqlite+aiosqlite:///{db_path}"
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("DATABASE_URL_SYNC", f"sqlite:///{db_path}")
    monkeypatch.setenv("RUN_MIGRATIONS_ON_STARTUP", "false")
    monkeypatch.setenv("EXECUTION_ENABLED", "true")
    monkeypatch.setenv("ALLOW_MUTATIONS", "false")
    from app.config import get_settings

    get_settings.cache_clear()
    await reset_engine()

    engine = create_async_engine(url, connect_args={"check_same_thread": False})
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

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
        yield ac, factory

    app.dependency_overrides.clear()
    await engine.dispose()
    await reset_engine()
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_execute_requires_approval(client):
    ac, factory = client
    incident_id = uuid.uuid4()

    async with factory() as session:
        prop = RemediationProposal(
            incident_id=incident_id,
            investigation_id=uuid.uuid4(),
            action_type=ActionType.CLEAR_FAULT,
            title="Clear error_storm",
            rationale="test",
            parameters={"fault": "error_storm"},
            confidence=90,
            risk_level=RiskLevel.LOW,
            requires_dry_run_default=False,
            status=ProposalStatus.PROPOSED,
            evidence_ids=["metric-error_rate"],
            root_cause="error storm",
        )
        session.add(prop)
        await session.commit()
        proposal_id = prop.id

    # Execute without approve → 409
    resp = await ac.post(f"/remediations/{proposal_id}/execute", json={})
    assert resp.status_code == 409

    with patch("app.services.orchestrator.clients.post_timeline_event", new=AsyncMock()):
        approved = await ac.post(
            f"/remediations/{proposal_id}/approve",
            json={"approved_by": "sre-oncall", "comment": "ok"},
        )
        assert approved.status_code == 200
        assert approved.json()["status"] == "approved"

        with patch(
            "app.services.executor._clear_fault",
            new=AsyncMock(return_value={"message": "cleared", "dry_run": False}),
        ):
            executed = await ac.post(
                f"/remediations/{proposal_id}/execute",
                json={"dry_run": False, "actor": "sre-oncall"},
            )
            assert executed.status_code == 200, executed.text
            assert executed.json()["status"] == "succeeded"

        # Idempotent: already succeeded
        again = await ac.post(f"/remediations/{proposal_id}/execute", json={})
        assert again.status_code == 409


@pytest.mark.asyncio
async def test_propose_uses_investigation(client):
    ac, factory = client
    incident_id = uuid.uuid4()
    inv_id = uuid.uuid4()

    async def fake_inv(_):
        return {"id": str(inv_id)}

    async def fake_rca(_):
        return {
            "root_cause": "Elevated application error rate (error storm)",
            "confidence": 85,
            "next_steps": ["Disable fault injection if demo"],
            "evidence_ids": ["metric-error_rate"],
        }

    with patch(
        "app.services.orchestrator.clients.fetch_latest_investigation",
        new=AsyncMock(side_effect=fake_inv),
    ):
        with patch(
            "app.services.orchestrator.clients.fetch_rca",
            new=AsyncMock(side_effect=fake_rca),
        ):
            with patch(
                "app.services.orchestrator.clients.post_timeline_event",
                new=AsyncMock(),
            ):
                resp = await ac.post(f"/incidents/{incident_id}/remediations/propose")
                assert resp.status_code == 200, resp.text
                body = resp.json()
                assert body["count"] >= 1
                assert any(p["action_type"] == "clear_fault" for p in body["proposals"])

    pending = await ac.get("/remediations/pending")
    assert pending.status_code == 200
    assert len(pending.json()) >= 1
