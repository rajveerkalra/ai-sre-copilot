"""Resilience primitives: retry, timeout, circuit breaker."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, TypeVar

T = TypeVar("T")


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitOpenError(Exception):
    """Raised when the circuit breaker is open."""


class RetryExhaustedError(Exception):
    """Raised when all retry attempts fail."""

    def __init__(self, message: str, *, last_error: BaseException | None = None) -> None:
        super().__init__(message)
        self.last_error = last_error


@dataclass
class CircuitBreaker:
    """Simple consecutive-failure circuit breaker."""

    name: str
    failure_threshold: int = 5
    recovery_timeout_seconds: float = 30.0
    half_open_max_calls: int = 1
    _state: CircuitState = CircuitState.CLOSED
    _failures: int = 0
    _opened_at: float | None = None
    _half_open_calls: int = 0
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    @property
    def state(self) -> CircuitState:
        if self._state == CircuitState.OPEN and self._opened_at is not None:
            if time.monotonic() - self._opened_at >= self.recovery_timeout_seconds:
                return CircuitState.HALF_OPEN
        return self._state

    async def before_call(self) -> None:
        async with self._lock:
            state = self.state
            if state == CircuitState.OPEN:
                raise CircuitOpenError(f"Circuit '{self.name}' is open")
            if state == CircuitState.HALF_OPEN:
                if self._half_open_calls >= self.half_open_max_calls:
                    raise CircuitOpenError(f"Circuit '{self.name}' half-open saturated")
                self._state = CircuitState.HALF_OPEN
                self._half_open_calls += 1

    async def record_success(self) -> None:
        async with self._lock:
            self._failures = 0
            self._half_open_calls = 0
            self._opened_at = None
            self._state = CircuitState.CLOSED

    async def record_failure(self) -> None:
        async with self._lock:
            self._failures += 1
            if self._state == CircuitState.HALF_OPEN or self._failures >= self.failure_threshold:
                self._state = CircuitState.OPEN
                self._opened_at = time.monotonic()
                self._half_open_calls = 0


async def with_retry(
    fn: Callable[[], Awaitable[T]],
    *,
    retries: int = 3,
    backoff_base: float = 0.5,
    backoff_max: float = 8.0,
    timeout_seconds: float | None = None,
    circuit: CircuitBreaker | None = None,
    retry_on: tuple[type[BaseException], ...] = (Exception,),
    operation: str = "operation",
) -> T:
    """Execute async fn with timeout, exponential backoff, and optional circuit breaker."""
    last_error: BaseException | None = None
    attempts = max(1, retries)

    for attempt in range(1, attempts + 1):
        if circuit is not None:
            await circuit.before_call()
        try:
            if timeout_seconds is not None:
                result = await asyncio.wait_for(fn(), timeout=timeout_seconds)
            else:
                result = await fn()
            if circuit is not None:
                await circuit.record_success()
            return result
        except asyncio.TimeoutError as exc:
            last_error = exc
            if circuit is not None:
                await circuit.record_failure()
            if attempt >= attempts:
                break
            delay = min(backoff_max, backoff_base * (2 ** (attempt - 1)))
            await asyncio.sleep(delay)
        except CircuitOpenError:
            raise
        except retry_on as exc:  # type: ignore[misc]
            last_error = exc
            if circuit is not None:
                await circuit.record_failure()
            if attempt >= attempts:
                break
            delay = min(backoff_max, backoff_base * (2 ** (attempt - 1)))
            await asyncio.sleep(delay)

    raise RetryExhaustedError(
        f"{operation} failed after {attempts} attempts", last_error=last_error
    ) from last_error


@dataclass
class ResiliencePolicy:
    retries: int = 3
    timeout_seconds: float = 30.0
    backoff_base: float = 0.5
    backoff_max: float = 8.0
    circuit_failure_threshold: int = 5
    circuit_recovery_seconds: float = 30.0

    def breaker(self, name: str) -> CircuitBreaker:
        return CircuitBreaker(
            name=name,
            failure_threshold=self.circuit_failure_threshold,
            recovery_timeout_seconds=self.circuit_recovery_seconds,
        )
