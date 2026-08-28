"""Priority scoring and per-task worker logic for the auto-dispatch path."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine

from app.db.base import Base
from app.db.session import reset_engine
from app.services.dispatch import _process_investigation_task, priority_score


@pytest_asyncio.fixture
async def db_engine(tmp_path, monkeypatch):
    db_path = tmp_path / "dispatch.db"
    url = f"sqlite+aiosqlite:///{db_path}"
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("DATABASE_URL_SYNC", f"sqlite:///{db_path}")
    monkeypatch.setenv("RUN_MIGRATIONS_ON_STARTUP", "false")
    monkeypatch.setenv("LLM_ENABLED", "false")
    monkeypatch.setenv("CACHE_ENABLED", "false")
    monkeypatch.setenv("EVENT_BUS_ENABLED", "false")
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


def test_priority_score_ranks_critical_before_warning_before_info():
    critical = priority_score("critical")
    warning = priority_score("warning")
    info = priority_score("info")
    unknown = priority_score("something-never-seen")

    assert critical < warning < info < unknown


def test_priority_score_is_case_insensitive():
    assert priority_score("CRITICAL") < priority_score("Warning")


def test_priority_score_same_severity_is_roughly_fifo():
    import time

    first = priority_score("critical")
    time.sleep(0.01)
    second = priority_score("critical")
    assert first < second  # earlier enqueue drains first among equal severity


@pytest.mark.asyncio
async def test_malformed_task_is_dropped_without_touching_db(db_engine):
    assert await _process_investigation_task("not json", worker_id=0) is False
    assert await _process_investigation_task('{"severity": "critical"}', worker_id=0) is False  # missing incident_id
    assert await _process_investigation_task('{"incident_id": "not-a-uuid"}', worker_id=0) is False


@pytest.mark.asyncio
async def test_successful_task_calls_run_investigation_with_correct_incident(db_engine):
    incident_id = uuid.uuid4()
    fake_run = type("Run", (), {"id": uuid.uuid4(), "status": "completed", "used_fallback": False})()

    with patch(
        "app.services.orchestrator.run_investigation",
        new=AsyncMock(return_value=fake_run),
    ) as mocked:
        raw = f'{{"incident_id": "{incident_id}", "severity": "critical"}}'
        ok = await _process_investigation_task(raw, worker_id=0)

    assert ok is True
    mocked.assert_called_once()
    called_incident_id = mocked.call_args.args[1]
    assert called_incident_id == incident_id


@pytest.mark.asyncio
async def test_investigation_failure_is_caught_and_still_marked_handled(db_engine):
    incident_id = uuid.uuid4()
    with patch(
        "app.services.orchestrator.run_investigation",
        new=AsyncMock(side_effect=RuntimeError("model-gateway unreachable")),
    ):
        raw = f'{{"incident_id": "{incident_id}", "severity": "warning"}}'
        ok = await _process_investigation_task(raw, worker_id=0)

    # The item is already off the priority queue (ZPOPMIN is destructive) --
    # there's nothing to "retry" from here, so this is correctly handled=True
    # even though the investigation itself failed. The failure is logged;
    # an operator can re-trigger via POST /investigate if needed.
    assert ok is True
