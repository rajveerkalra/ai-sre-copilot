"""Sample app unit / API tests (Phase 1)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.faults import FaultType, fault_injector
from app.main import create_app


@pytest.fixture()
def client():
    fault_injector.deactivate_all()
    app = create_app()
    with TestClient(app) as c:
        yield c
    fault_injector.deactivate_all()


def test_healthz(client: TestClient):
    r = client.get("/healthz")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "healthy"
    assert body["service"] == "sample-app"


def test_livez_readyz(client: TestClient):
    assert client.get("/livez").status_code == 200
    assert client.get("/readyz").status_code == 200


def test_metrics_endpoint(client: TestClient):
    client.get("/api/products")
    r = client.get("/metrics")
    assert r.status_code == 200
    assert "http_requests_total" in r.text
    assert "sample_app_orders_total" in r.text or "http_request_duration_seconds" in r.text


def test_create_order(client: TestClient):
    r = client.post("/api/orders", json={"sku": "SKU-100", "quantity": 2})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "accepted"
    assert body["sku"] == "SKU-100"


def test_error_storm_fault(client: TestClient):
    act = client.post(
        "/faults/error_storm/activate",
        json={"error_rate": 1.0, "duration_seconds": 60},
    )
    assert act.status_code == 200
    assert act.json()["state"]["active"] is True

    # With error_rate=1.0 every request should fail
    failures = 0
    for _ in range(5):
        r = client.get("/api/products")
        if r.status_code == 500:
            failures += 1
    assert failures == 5

    deact = client.post("/faults/error_storm/deactivate")
    assert deact.status_code == 200
    assert deact.json()["state"]["active"] is False


def test_latency_fault_increases_duration(client: TestClient):
    client.post(
        "/faults/latency/activate",
        json={"min_ms": 100, "max_ms": 150, "duration_seconds": 60},
    )
    import time

    started = time.perf_counter()
    r = client.get("/api/products")
    elapsed = time.perf_counter() - started
    assert r.status_code == 200
    assert elapsed >= 0.09
    client.post("/faults/latency/deactivate")


def test_list_faults(client: TestClient):
    r = client.get("/faults")
    assert r.status_code == 200
    body = r.json()
    assert "error_storm" in body["available"]
    assert "scenarios" in body


def test_deactivate_all(client: TestClient):
    client.post("/faults/cpu_spike/activate", json={"workers": 1, "duration_seconds": 30})
    assert fault_injector.is_active(FaultType.CPU_SPIKE)
    r = client.post("/faults/deactivate-all")
    assert r.status_code == 200
    assert not fault_injector.is_active(FaultType.CPU_SPIKE)


def test_request_id_header(client: TestClient):
    r = client.get("/api/info")
    assert r.status_code == 200
    assert "x-request-id" in r.headers
