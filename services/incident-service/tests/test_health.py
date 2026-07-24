"""Health endpoint tests."""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_health(client):
    r = await client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "healthy"
    assert body["service"] == "incident-service"


@pytest.mark.asyncio
async def test_live(client):
    r = await client.get("/live")
    assert r.status_code == 200
    assert r.json()["status"] == "healthy"


@pytest.mark.asyncio
async def test_ready(client):
    r = await client.get("/ready")
    assert r.status_code == 200
    assert r.json()["db"] == "ok"


@pytest.mark.asyncio
async def test_metrics(client):
    r = await client.get("/metrics")
    assert r.status_code == 200
    assert "http_requests_total" in r.text
