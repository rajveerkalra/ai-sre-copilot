"""Health endpoint tests."""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_health(client):
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json()["service"] == "context-service"


@pytest.mark.asyncio
async def test_ready(client):
    r = await client.get("/ready")
    assert r.status_code == 200
    assert r.json()["db"] == "ok"


@pytest.mark.asyncio
async def test_metrics_endpoint(client):
    r = await client.get("/metrics")
    assert r.status_code == 200
    assert "collector_duration_seconds" in r.text or "http_requests_total" in r.text
