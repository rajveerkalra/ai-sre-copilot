"""Fault injection engine for demo incident scenarios."""

from __future__ import annotations

import asyncio
import os
import random
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from app.metrics import (
    FAULT_ACTIVE,
    FAULT_INJECTIONS_TOTAL,
    PROCESS_CPU_SIMULATED,
    PROCESS_MEMORY_SIMULATED_BYTES,
)


class FaultType(str, Enum):
    ERROR_STORM = "error_storm"
    LATENCY = "latency"
    CPU_SPIKE = "cpu_spike"
    MEMORY_LEAK = "memory_leak"
    DEPENDENCY_TIMEOUT = "dependency_timeout"
    CRASH = "crash"


@dataclass
class FaultState:
    active: bool = False
    params: dict[str, Any] = field(default_factory=dict)
    activated_at: float | None = None
    expires_at: float | None = None


class FaultInjector:
    """In-process fault injection used by demo scenarios and alert validation."""

    def __init__(self) -> None:
        self._states: dict[FaultType, FaultState] = {
            ft: FaultState() for ft in FaultType
        }
        self._lock = threading.RLock()
        self._cpu_thread: threading.Thread | None = None
        self._cpu_stop = threading.Event()
        self._memory_ballast: list[bytearray] = []

    def status(self) -> dict[str, Any]:
        with self._lock:
            now = time.time()
            result: dict[str, Any] = {}
            for ft, state in self._states.items():
                active = state.active
                if active and state.expires_at and now >= state.expires_at:
                    self._deactivate_unlocked(ft)
                    active = False
                result[ft.value] = {
                    "active": active,
                    "params": dict(state.params),
                    "activated_at": state.activated_at,
                    "expires_at": state.expires_at,
                }
            return result

    def activate(
        self,
        fault_type: FaultType,
        *,
        duration_seconds: float | None = None,
        **params: Any,
    ) -> dict[str, Any]:
        with self._lock:
            if fault_type == FaultType.CRASH:
                FAULT_INJECTIONS_TOTAL.labels(
                    fault_type=fault_type.value, action="activate"
                ).inc()
                # Soft crash: raise so the request fails; hard crash via os._exit
                if params.get("hard", False):
                    os._exit(1)
                raise RuntimeError("Injected crash fault")

            now = time.time()
            state = self._states[fault_type]
            state.active = True
            state.params = params
            state.activated_at = now
            state.expires_at = (
                now + duration_seconds if duration_seconds else None
            )

            FAULT_ACTIVE.labels(fault_type=fault_type.value).set(1)
            FAULT_INJECTIONS_TOTAL.labels(
                fault_type=fault_type.value, action="activate"
            ).inc()

            if fault_type == FaultType.CPU_SPIKE:
                self._start_cpu_burn(params.get("workers", 2))
            elif fault_type == FaultType.MEMORY_LEAK:
                self._grow_memory(int(params.get("megabytes", 128)))

            return self.status()[fault_type.value]

    def deactivate(self, fault_type: FaultType) -> dict[str, Any]:
        with self._lock:
            self._deactivate_unlocked(fault_type)
            return self.status()[fault_type.value]

    def deactivate_all(self) -> dict[str, Any]:
        with self._lock:
            for ft in FaultType:
                if ft != FaultType.CRASH:
                    self._deactivate_unlocked(ft)
            return self.status()

    def _deactivate_unlocked(self, fault_type: FaultType) -> None:
        state = self._states[fault_type]
        was_active = state.active
        state.active = False
        state.params = {}
        state.activated_at = None
        state.expires_at = None
        FAULT_ACTIVE.labels(fault_type=fault_type.value).set(0)
        if was_active:
            FAULT_INJECTIONS_TOTAL.labels(
                fault_type=fault_type.value, action="deactivate"
            ).inc()

        if fault_type == FaultType.CPU_SPIKE:
            self._stop_cpu_burn()
        elif fault_type == FaultType.MEMORY_LEAK:
            self._clear_memory()

    def is_active(self, fault_type: FaultType) -> bool:
        with self._lock:
            state = self._states[fault_type]
            if state.active and state.expires_at and time.time() >= state.expires_at:
                self._deactivate_unlocked(fault_type)
                return False
            return state.active

    def get_params(self, fault_type: FaultType) -> dict[str, Any]:
        with self._lock:
            return dict(self._states[fault_type].params)

    async def maybe_inject_latency(self) -> None:
        if not self.is_active(FaultType.LATENCY):
            return
        params = self.get_params(FaultType.LATENCY)
        min_ms = float(params.get("min_ms", 500))
        max_ms = float(params.get("max_ms", 2000))
        delay = random.uniform(min_ms, max_ms) / 1000.0
        await asyncio.sleep(delay)

    def should_error(self) -> bool:
        if not self.is_active(FaultType.ERROR_STORM):
            return False
        rate = float(self.get_params(FaultType.ERROR_STORM).get("error_rate", 0.8))
        return random.random() < rate

    def should_dependency_timeout(self) -> bool:
        return self.is_active(FaultType.DEPENDENCY_TIMEOUT)

    def _start_cpu_burn(self, workers: int) -> None:
        self._stop_cpu_burn()
        self._cpu_stop.clear()
        PROCESS_CPU_SIMULATED.set(1)

        def burn() -> None:
            while not self._cpu_stop.is_set():
                _ = sum(i * i for i in range(10_000))

        threads = []
        for _ in range(max(1, workers)):
            t = threading.Thread(target=burn, name="cpu-burn", daemon=True)
            t.start()
            threads.append(t)
        self._cpu_thread = threads[0] if threads else None
        self._cpu_threads = threads  # type: ignore[attr-defined]

    def _stop_cpu_burn(self) -> None:
        self._cpu_stop.set()
        PROCESS_CPU_SIMULATED.set(0)
        threads = getattr(self, "_cpu_threads", [])
        for t in threads:
            t.join(timeout=0.5)
        self._cpu_threads = []  # type: ignore[attr-defined]

    def _grow_memory(self, megabytes: int) -> None:
        chunk = bytearray(max(1, megabytes) * 1024 * 1024)
        self._memory_ballast.append(chunk)
        total = sum(len(b) for b in self._memory_ballast)
        PROCESS_MEMORY_SIMULATED_BYTES.set(total)

    def _clear_memory(self) -> None:
        self._memory_ballast.clear()
        PROCESS_MEMORY_SIMULATED_BYTES.set(0)


fault_injector = FaultInjector()
