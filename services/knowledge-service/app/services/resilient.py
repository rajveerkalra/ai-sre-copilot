"""Resilient HTTP helper for knowledge-service."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TypeVar

try:
    from libs.common.resilience import CircuitBreaker, with_retry
except ImportError:  # pragma: no cover
    from common.resilience import CircuitBreaker, with_retry  # type: ignore

T = TypeVar("T")

_breakers: dict[str, CircuitBreaker] = {}


def _breaker(name: str) -> CircuitBreaker:
    if name not in _breakers:
        _breakers[name] = CircuitBreaker(name=name, failure_threshold=5, recovery_timeout_seconds=20.0)
    return _breakers[name]


async def call_with_resilience(
    fn: Callable[[], Awaitable[T]],
    *,
    name: str,
    retries: int = 3,
    timeout_seconds: float = 30.0,
    backoff_base: float = 0.5,
) -> T:
    return await with_retry(
        fn,
        retries=retries,
        backoff_base=backoff_base,
        timeout_seconds=timeout_seconds,
        circuit=_breaker(name),
        operation=name,
    )
