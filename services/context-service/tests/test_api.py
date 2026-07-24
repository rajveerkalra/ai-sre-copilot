"""API / orchestrator integration tests with collector mocks."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.collectors.base import CollectorResult


def _ok(name: str) -> CollectorResult:
    return CollectorResult(
        collector_name=name,
        status="success",
        duration_ms=12.0,
        attempt_count=1,
        data={"available": True, "collector": name},
    )


def _fail(name: str) -> CollectorResult:
    return CollectorResult(
        collector_name=name,
        status="failed",
        duration_ms=5.0,
        attempt_count=2,
        data={"available": False},
        error="boom",
        errors=[{"attempt": 1, "error_type": "RuntimeError", "error_message": "boom"}],
    )


@pytest.mark.asyncio
async def test_collect_and_get_context(client, incident_id, mock_incident_meta):
    with patch(
        "app.services.orchestrator.fetch_incident_metadata",
        new=AsyncMock(return_value=mock_incident_meta),
    ), patch(
        "app.services.orchestrator.ALL_COLLECTORS",
        new=[],
    ):
        # Manually patch gather path by replacing collector classes with stubs
        pass

    class StubCollector:
        name = "metrics"

        def __init__(self, settings=None):
            self.name = type(self).name

        async def run(self, request):
            return _ok(self.name)

    class StubLogs(StubCollector):
        name = "logs"

    class StubK8s(StubCollector):
        name = "kubernetes"

    class StubDeploy(StubCollector):
        name = "deployment"

    class StubSystem(StubCollector):
        name = "system"

    stubs = [StubCollector, StubLogs, StubK8s, StubDeploy, StubSystem]

    with patch(
        "app.services.orchestrator.fetch_incident_metadata",
        new=AsyncMock(return_value=mock_incident_meta),
    ), patch(
        "app.services.orchestrator.ALL_COLLECTORS",
        stubs,
    ):
        r = await client.post(f"/incidents/{incident_id}/collect", json={})
        assert r.status_code == 200
        body = r.json()
        assert body["accepted"] is True
        assert body["status"] in {"completed", "partial"}
        assert body["incident_id"] == str(incident_id)

        ctx = await client.get(f"/incidents/{incident_id}/context")
        assert ctx.status_code == 200
        data = ctx.json()
        assert data["metrics"]["available"] is True
        assert data["logs"]["available"] is True
        assert len(data["collector_runs"]) == 5

        metrics = await client.get(f"/incidents/{incident_id}/metrics")
        assert metrics.status_code == 200
        assert "metrics" in metrics.json()

        logs = await client.get(f"/incidents/{incident_id}/logs")
        assert logs.status_code == 200

        k8s = await client.get(f"/incidents/{incident_id}/kubernetes")
        assert k8s.status_code == 200

        dep = await client.get(f"/incidents/{incident_id}/deployment")
        assert dep.status_code == 200


@pytest.mark.asyncio
async def test_partial_when_one_collector_fails(client, incident_id, mock_incident_meta):
    class Ok:
        name = "metrics"

        def __init__(self, settings=None):
            pass

        async def run(self, request):
            return _ok(self.name)

    class Fail:
        name = "logs"

        def __init__(self, settings=None):
            pass

        async def run(self, request):
            return _fail(self.name)

    class Ok2(Ok):
        name = "kubernetes"

    class Ok3(Ok):
        name = "deployment"

    class Ok4(Ok):
        name = "system"

    with patch(
        "app.services.orchestrator.fetch_incident_metadata",
        new=AsyncMock(return_value=mock_incident_meta),
    ), patch(
        "app.services.orchestrator.ALL_COLLECTORS",
        [Ok, Fail, Ok2, Ok3, Ok4],
    ):
        r = await client.post(f"/incidents/{incident_id}/collect")
        assert r.status_code == 200
        assert r.json()["status"] == "partial"


@pytest.mark.asyncio
async def test_context_not_found(client):
    r = await client.get(f"/incidents/{uuid.uuid4()}/context")
    assert r.status_code == 404
