"""Resilient HTTP helpers for investigation-service external calls."""

from __future__ import annotations

from typing import Any

import httpx

from app.config import get_settings

try:
    from libs.common.resilience import CircuitBreaker, with_retry
except ImportError:  # pragma: no cover
    from common.resilience import CircuitBreaker, with_retry  # type: ignore

_breakers: dict[str, CircuitBreaker] = {}


def _breaker(name: str) -> CircuitBreaker:
    if name not in _breakers:
        _breakers[name] = CircuitBreaker(
            name=name, failure_threshold=5, recovery_timeout_seconds=30.0
        )
    return _breakers[name]


async def get_json(
    url: str,
    *,
    name: str,
    timeout: float | None = None,
) -> dict[str, Any]:
    settings = get_settings()
    timeout = timeout if timeout is not None else settings.http_timeout_seconds

    async def _call():
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.json()

    return await with_retry(
        _call,
        retries=settings.http_retries,
        backoff_base=settings.http_backoff_base,
        timeout_seconds=timeout,
        circuit=_breaker(name),
        retry_on=(httpx.HTTPError, OSError),
        operation=name,
    )


async def get_json_post(
    url: str,
    *,
    json_body: dict[str, Any],
    name: str,
    timeout: float | None = None,
) -> dict[str, Any]:
    settings = get_settings()
    timeout = timeout if timeout is not None else settings.http_timeout_seconds

    async def _call():
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(url, json=json_body)
            resp.raise_for_status()
            return resp.json()

    return await with_retry(
        _call,
        retries=settings.http_retries,
        backoff_base=settings.http_backoff_base,
        timeout_seconds=timeout,
        circuit=_breaker(name),
        retry_on=(httpx.HTTPError, OSError),
        operation=name,
    )
