"""Event-bus consumer: ack/retry semantics for the durable dispatch path.

Only orchestrator.collect_for_incident is mocked here -- its own internals
are already covered by test_api.py. This tests the consumer's control flow:
a successful collection is acked, a permanent failure (incident not found
upstream) is acked so it isn't retried forever, and a transient failure is
left unacked so it gets redelivered.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.services.eventbus_consumer import _process_one
from app.services.orchestrator import IncidentLookupError


@pytest.mark.asyncio
async def test_malformed_entry_is_acked_without_touching_db(db_engine):
    assert await _process_one("1-0", {}) is True  # missing incident_id
    assert await _process_one("2-0", {"incident_id": "not-a-uuid"}) is True


@pytest.mark.asyncio
async def test_successful_collection_is_acked(db_engine):
    incident_id = uuid.uuid4()
    fake_ctx = type("Ctx", (), {"id": uuid.uuid4()})()

    with patch(
        "app.services.orchestrator.collect_for_incident",
        new=AsyncMock(return_value=fake_ctx),
    ) as mocked:
        ok = await _process_one("3-0", {"incident_id": str(incident_id)})

    assert ok is True
    mocked.assert_called_once()
    called_incident_id = mocked.call_args.args[1]
    assert called_incident_id == incident_id


@pytest.mark.asyncio
async def test_incident_lookup_error_is_acked_not_retried(db_engine):
    incident_id = uuid.uuid4()
    with patch(
        "app.services.orchestrator.collect_for_incident",
        new=AsyncMock(side_effect=IncidentLookupError("incident-service 404")),
    ):
        ok = await _process_one("4-0", {"incident_id": str(incident_id)})

    assert ok is True  # permanent failure -- acked so it's not redelivered forever


@pytest.mark.asyncio
async def test_transient_error_is_left_unacked_for_retry(db_engine):
    incident_id = uuid.uuid4()
    with patch(
        "app.services.orchestrator.collect_for_incident",
        new=AsyncMock(side_effect=RuntimeError("prometheus unreachable")),
    ):
        ok = await _process_one("5-0", {"incident_id": str(incident_id)})

    assert ok is False  # transient -- must NOT be acked, so it gets redelivered
