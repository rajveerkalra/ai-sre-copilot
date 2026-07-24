"""Incident API tests: list, resolve, notes, pagination."""

from __future__ import annotations

import pytest

from tests.conftest import sample_alertmanager_payload


async def _create(client, **kwargs) -> str:
    r = await client.post(
        "/webhooks/alertmanager",
        json=sample_alertmanager_payload(**kwargs),
    )
    return r.json()["results"][0]["incident_id"]


@pytest.mark.asyncio
async def test_list_filter_status_and_severity(client):
    await _create(client, alertname="A1", severity="critical", pod="p1")
    await _create(client, alertname="A2", severity="warning", pod="p2")

    critical = await client.get("/incidents", params={"severity": "critical"})
    assert critical.json()["total"] == 1
    assert critical.json()["items"][0]["severity"] == "critical"

    open_only = await client.get("/incidents", params={"status": "open"})
    assert open_only.json()["total"] == 2


@pytest.mark.asyncio
async def test_pagination(client):
    for i in range(5):
        await _create(client, alertname=f"Alert{i}", pod=f"pod-{i}")

    page1 = await client.get("/incidents", params={"page": 1, "page_size": 2})
    body = page1.json()
    assert body["total"] == 5
    assert body["page"] == 1
    assert body["page_size"] == 2
    assert body["pages"] == 3
    assert len(body["items"]) == 2

    page3 = await client.get("/incidents", params={"page": 3, "page_size": 2})
    assert len(page3.json()["items"]) == 1


@pytest.mark.asyncio
async def test_resolve_via_api(client):
    incident_id = await _create(client)
    r = await client.post(
        f"/incidents/{incident_id}/resolve",
        json={"message": "Fixed by SRE"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "resolved"
    assert r.json()["resolved_at"] is not None

    timeline = await client.get(f"/incidents/{incident_id}/timeline")
    types = [e["event_type"] for e in timeline.json()]
    assert "incident_resolved" in types

    # Second resolve -> 409
    again = await client.post(f"/incidents/{incident_id}/resolve", json={})
    assert again.status_code == 409


@pytest.mark.asyncio
async def test_add_note(client):
    incident_id = await _create(client)
    r = await client.post(
        f"/incidents/{incident_id}/notes",
        json={"message": "Investigating elevated error rate"},
    )
    assert r.status_code == 201
    assert r.json()["event_type"] == "note_added"
    assert "Investigating" in r.json()["message"]


@pytest.mark.asyncio
async def test_get_unknown_incident(client):
    r = await client.get("/incidents/00000000-0000-0000-0000-000000000099")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_new_incident_after_resolve(client):
    """After resolve, same fingerprint may open a new incident."""
    payload = sample_alertmanager_payload()
    first = await client.post("/webhooks/alertmanager", json=payload)
    incident_id = first.json()["results"][0]["incident_id"]
    await client.post(f"/incidents/{incident_id}/resolve", json={})

    second = await client.post("/webhooks/alertmanager", json=payload)
    assert second.json()["results"][0]["action"] == "created"
    assert second.json()["results"][0]["incident_id"] != incident_id
