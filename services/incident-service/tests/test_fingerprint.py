"""Fingerprint helper unit tests."""

from __future__ import annotations

from app.services.fingerprint import compute_fingerprint


def test_fingerprint_stable():
    a = compute_fingerprint(
        alertname="HighCPU",
        namespace="prod",
        pod="api-1",
        service="api",
        instance="1.2.3.4:8080",
    )
    b = compute_fingerprint(
        alertname="HighCPU",
        namespace="prod",
        pod="api-1",
        service="api",
        instance="1.2.3.4:8080",
    )
    assert a == b
    assert len(a) == 64


def test_fingerprint_case_insensitive():
    a = compute_fingerprint(alertname="HighCPU", service="API")
    b = compute_fingerprint(alertname="highcpu", service="api")
    assert a == b


def test_fingerprint_differs_on_pod():
    a = compute_fingerprint(alertname="X", pod="a")
    b = compute_fingerprint(alertname="X", pod="b")
    assert a != b
