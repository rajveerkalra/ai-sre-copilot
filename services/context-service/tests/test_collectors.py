"""Collector unit tests with httpx AsyncClient stubs."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from app.collectors.base import CollectionRequest
from app.collectors.kubernetes_collector import KubernetesCollector
from app.collectors.logs_collector import LogsCollector
from app.collectors.metrics_collector import MetricsCollector
from app.config import get_settings


def _req() -> CollectionRequest:
    return CollectionRequest(
        incident_id="00000000-0000-0000-0000-000000000001",
        correlation_id="corr-1",
        service="sample-app",
        namespace="default",
        alertname="SampleAppHighErrorRate",
    )


def _resp(status_code: int = 200, *, text: str = "", json_data: Any = None):
    def raise_for_status():
        if status_code >= 400:
            raise RuntimeError(f"HTTP {status_code}")

    return SimpleNamespace(
        status_code=status_code,
        text=text,
        json=lambda: json_data if json_data is not None else {},
        raise_for_status=raise_for_status,
    )


class _FakeAsyncClient:
    def __init__(self, *args: Any, handler=None, **kwargs: Any) -> None:
        self._handler = handler

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def get(self, path: str, params: dict | None = None):
        assert self._handler is not None
        return self._handler(path, params or {})


@pytest.mark.asyncio
async def test_metrics_collector_success(monkeypatch):
    settings = get_settings()

    def handler(path: str, params: dict):
        if path.endswith("/-/ready") or path == "/-/ready":
            return _resp(200, text="ready")
        if "query_range" in path:
            return _resp(
                200,
                json_data={
                    "status": "success",
                    "data": {
                        "resultType": "matrix",
                        "result": [{"values": [[1, "0.4"], [2, "0.5"]]}],
                    },
                },
            )
        if path.endswith("/api/v1/query") or path == "/api/v1/query":
            return _resp(
                200,
                json_data={
                    "status": "success",
                    "data": {
                        "resultType": "vector",
                        "result": [{"value": [1, "0.42"]}],
                    },
                },
            )
        if "targets" in path:
            return _resp(
                200,
                json_data={
                    "status": "success",
                    "data": {
                        "activeTargets": [
                            {
                                "labels": {"job": "sample-app", "instance": "x"},
                                "health": "up",
                            }
                        ]
                    },
                },
            )
        return _resp(404, text=f"unexpected {path}")

    monkeypatch.setattr(
        "app.collectors.metrics_collector.httpx.AsyncClient",
        lambda *a, **k: _FakeAsyncClient(handler=handler),
    )
    result = await MetricsCollector(settings).run(_req())
    assert result.status == "success"
    assert result.data["available"] is True
    assert "request_rate" in result.data["series"]


@pytest.mark.asyncio
async def test_logs_collector_success(monkeypatch):
    settings = get_settings()

    def handler(path: str, params: dict):
        if path.endswith("/ready") or path == "/ready":
            return _resp(200, text="ready")
        if "query_range" in path:
            return _resp(
                200,
                json_data={
                    "status": "success",
                    "data": {
                        "resultType": "streams",
                        "result": [
                            {
                                "stream": {"service": "sample-app"},
                                "values": [
                                    [
                                        "1700000000000000000",
                                        '{"level":"error","event":"boom"}',
                                    ],
                                    ["1700000001000000000", "INFO ok"],
                                    [
                                        "1700000002000000000",
                                        "Exception: traceback here",
                                    ],
                                ],
                            }
                        ],
                    },
                },
            )
        return _resp(404, text=path)

    monkeypatch.setattr(
        "app.collectors.logs_collector.httpx.AsyncClient",
        lambda *a, **k: _FakeAsyncClient(handler=handler),
    )
    result = await LogsCollector(settings).run(_req())
    assert result.status == "success"
    assert result.data["total_lines"] >= 1
    assert "summary" in result.data


@pytest.mark.asyncio
async def test_kubernetes_collector_unavailable_without_cluster():
    settings = get_settings()
    result = await KubernetesCollector(settings).run(_req())
    assert result.status == "success"
    assert result.data["available"] is False


@pytest.mark.asyncio
async def test_metrics_collector_retries_then_fails(monkeypatch):
    settings = get_settings()

    def handler(path: str, params: dict):
        return _resp(503, text="unavailable")

    monkeypatch.setattr(
        "app.collectors.metrics_collector.httpx.AsyncClient",
        lambda *a, **k: _FakeAsyncClient(handler=handler),
    )
    result = await MetricsCollector(settings).run(_req())
    assert result.status == "failed"
    assert result.attempt_count >= 2
    assert result.error
