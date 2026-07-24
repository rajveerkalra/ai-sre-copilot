"""Shared resilience tests."""

from __future__ import annotations

import pytest

from libs.common.resilience import CircuitBreaker, CircuitOpenError, with_retry


@pytest.mark.asyncio
async def test_retry_succeeds_second_attempt():
    calls = {"n": 0}

    async def flaky():
        calls["n"] += 1
        if calls["n"] < 2:
            raise RuntimeError("boom")
        return "ok"

    result = await with_retry(flaky, retries=3, backoff_base=0.01, operation="t")
    assert result == "ok"
    assert calls["n"] == 2


@pytest.mark.asyncio
async def test_circuit_opens():
    cb = CircuitBreaker(name="t", failure_threshold=2, recovery_timeout_seconds=60)

    async def always_fail():
        raise RuntimeError("x")

    with pytest.raises(Exception):
        await with_retry(always_fail, retries=1, circuit=cb, backoff_base=0.01, operation="t")
    with pytest.raises(Exception):
        await with_retry(always_fail, retries=1, circuit=cb, backoff_base=0.01, operation="t")
    with pytest.raises(CircuitOpenError):
        await cb.before_call()
