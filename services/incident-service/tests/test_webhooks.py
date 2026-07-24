"""Webhook ingestion and deduplication tests."""

from __future__ import annotations

import pytest

from tests.conftest import sample_alertmanager_payload


@pytest.mark.asyncio
async def test_webhook_creates_incident(client):
    payload = sample_alertmanager_payload()
    r = await client.post("/webhooks/alertmanager", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert body["accepted"] is True
    assert body["alert_count"] == 1
    assert body["results"][0]["action"] == "created"
    assert body["results"][0]["occurrence_count"] == 1

    incident_id = body["results"][0]["incident_id"]
    detail = await client.get(f"/incidents/{incident_id}")
    assert detail.status_code == 200
    data = detail.json()
    assert data["status"] == "open"
    assert data["severity"] == "critical"
    assert data["occurrence_count"] == 1
    assert data["title"] == "SampleAppHighErrorRate firing"
    assert len(data["timeline"]) >= 2
    types = [e["event_type"] for e in data["timeline"]]
    assert "incident_created" in types
    assert "alert_received" in types


@pytest.mark.asyncio
async def test_webhook_deduplication(client):
    payload = sample_alertmanager_payload()
    first = await client.post("/webhooks/alertmanager", json=payload)
    assert first.json()["results"][0]["action"] == "created"
    incident_id = first.json()["results"][0]["incident_id"]

    second = await client.post("/webhooks/alertmanager", json=payload)
    assert second.status_code == 200
    result = second.json()["results"][0]
    assert result["action"] == "deduplicated"
    assert result["incident_id"] == incident_id
    assert result["occurrence_count"] == 2

    third = await client.post("/webhooks/alertmanager", json=payload)
    assert third.json()["results"][0]["occurrence_count"] == 3

    detail = await client.get(f"/incidents/{incident_id}")
    assert detail.json()["occurrence_count"] == 3

    timeline = await client.get(f"/incidents/{incident_id}/timeline")
    assert timeline.status_code == 200
    events = timeline.json()
    repeated = [e for e in events if e["event_type"] == "alert_repeated"]
    assert len(repeated) == 2


@pytest.mark.asyncio
async def test_different_fingerprint_creates_new_incident(client):
    a = sample_alertmanager_payload(alertname="AlertA", pod="pod-a")
    b = sample_alertmanager_payload(alertname="AlertB", pod="pod-b")

    r1 = await client.post("/webhooks/alertmanager", json=a)
    r2 = await client.post("/webhooks/alertmanager", json=b)
    id1 = r1.json()["results"][0]["incident_id"]
    id2 = r2.json()["results"][0]["incident_id"]
    assert id1 != id2

    listing = await client.get("/incidents")
    assert listing.json()["total"] == 2


@pytest.mark.asyncio
async def test_resolved_webhook_resolves_incident(client):
    firing = sample_alertmanager_payload(status="firing")
    created = await client.post("/webhooks/alertmanager", json=firing)
    incident_id = created.json()["results"][0]["incident_id"]

    resolved = sample_alertmanager_payload(status="resolved")
    resolved["status"] = "resolved"
    r = await client.post("/webhooks/alertmanager", json=resolved)
    assert r.json()["results"][0]["action"] == "resolved"

    detail = await client.get(f"/incidents/{incident_id}")
    assert detail.json()["status"] == "resolved"
    assert detail.json()["resolved_at"] is not None


@pytest.mark.asyncio
async def test_multi_alert_payload(client):
    payload = sample_alertmanager_payload()
    second = sample_alertmanager_payload(
        alertname="SampleAppHighLatency",
        severity="warning",
        pod="sample-app-1",
    )["alerts"][0]
    payload["alerts"].append(second)

    r = await client.post("/webhooks/alertmanager", json=payload)
    assert r.status_code == 200
    assert r.json()["alert_count"] == 2
    assert len(r.json()["results"]) == 2
    assert {x["action"] for x in r.json()["results"]} == {"created"}
