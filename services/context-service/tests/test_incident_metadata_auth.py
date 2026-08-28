"""fetch_incident_metadata must authenticate to incident-service.

Regression test for a real bug found by tracing a "severity": "unknown"
event that should have been "critical": incident-service enforces auth on
GET /incidents/{id} (Phase 7), but context-service had no service-mesh
token configured at all -- every call silently 401'd and fell back to
unknown severity/service/alertname, for every incident, the whole time
auth has been enabled in the real stack.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.config import get_settings
from app.services.orchestrator import IncidentLookupError, fetch_incident_metadata


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


class _FakeResponse:
    def __init__(self, status_code: int, json_body: dict):
        self.status_code = status_code
        self._json = json_body

    def json(self):
        return self._json

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("error", request=None, response=self)  # type: ignore[arg-type]


def _fake_client(response: _FakeResponse, captured_calls: list):
    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url, headers=None):
            captured_calls.append({"url": url, "headers": headers or {}})
            return response

    return _FakeAsyncClient


@pytest.mark.asyncio
async def test_sends_service_token_header(monkeypatch):
    monkeypatch.setenv("INTERNAL_SERVICE_TOKEN", "test-service-token")
    get_settings.cache_clear()
    incident_id = uuid.uuid4()
    calls: list = []

    response = _FakeResponse(200, {"id": str(incident_id), "severity": "critical"})
    with patch("httpx.AsyncClient", _fake_client(response, calls)):
        result = await fetch_incident_metadata(incident_id)

    assert len(calls) == 1
    assert calls[0]["headers"]["X-Service-Token"] == "test-service-token"
    assert result["severity"] == "critical"


@pytest.mark.asyncio
async def test_missing_token_config_sends_no_header(monkeypatch):
    monkeypatch.setenv("INTERNAL_SERVICE_TOKEN", "")
    get_settings.cache_clear()
    incident_id = uuid.uuid4()
    calls: list = []

    response = _FakeResponse(200, {"id": str(incident_id), "severity": "critical"})
    with patch("httpx.AsyncClient", _fake_client(response, calls)):
        await fetch_incident_metadata(incident_id)

    assert "X-Service-Token" not in calls[0]["headers"]


@pytest.mark.asyncio
async def test_401_falls_back_to_unknown_not_a_crash(monkeypatch):
    # Reproduces the actual bug as observed: incident-service rejects an
    # unauthenticated/misconfigured call with 401, and the (pre-existing)
    # broad except in fetch_incident_metadata degrades to defaults rather
    # than raising -- documenting that behavior so a real fix regresses
    # loudly if this ever silently starts happening again.
    incident_id = uuid.uuid4()
    response = _FakeResponse(401, {"detail": "Bearer token required"})
    with patch("httpx.AsyncClient", _fake_client(response, [])):
        result = await fetch_incident_metadata(incident_id)

    assert result["severity"] == "unknown"


@pytest.mark.asyncio
async def test_404_raises_incident_lookup_error():
    incident_id = uuid.uuid4()
    response = _FakeResponse(404, {"detail": "not found"})
    with patch("httpx.AsyncClient", _fake_client(response, [])):
        with pytest.raises(IncidentLookupError):
            await fetch_incident_metadata(incident_id)
