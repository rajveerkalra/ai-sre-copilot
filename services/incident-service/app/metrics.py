"""Prometheus metrics for the incident service."""

from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram, Info

SERVICE_INFO = Info("incident_service", "Incident service build metadata")

HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status_code"],
)

HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "endpoint"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)

HTTP_REQUESTS_IN_PROGRESS = Gauge(
    "http_requests_in_progress",
    "In-flight HTTP requests",
    ["method", "endpoint"],
)

HTTP_ERRORS_TOTAL = Counter(
    "http_errors_total",
    "HTTP 5xx responses",
    ["method", "endpoint"],
)

WEBHOOKS_RECEIVED_TOTAL = Counter(
    "incident_webhooks_received_total",
    "Alertmanager webhook payloads received",
    ["status"],
)

ALERTS_PROCESSED_TOTAL = Counter(
    "incident_alerts_processed_total",
    "Individual alerts processed from webhooks",
    ["action", "severity"],
)

INCIDENTS_OPEN = Gauge(
    "incident_open_count",
    "Currently open incidents",
)

INCIDENTS_CREATED_TOTAL = Counter(
    "incident_created_total",
    "Incidents created",
    ["severity"],
)

INCIDENTS_RESOLVED_TOTAL = Counter(
    "incident_resolved_total",
    "Incidents resolved",
    ["source"],
)


def init_metrics(version: str, environment: str) -> None:
    SERVICE_INFO.info({"version": version, "environment": environment})
