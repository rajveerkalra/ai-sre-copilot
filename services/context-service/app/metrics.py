"""Prometheus metrics for context-service collectors."""

from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram, Info

SERVICE_INFO = Info("context_service", "Context service build metadata")

HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status_code"],
)
HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency",
    ["method", "endpoint"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 15.0, 30.0),
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

COLLECTOR_DURATION_SECONDS = Histogram(
    "collector_duration_seconds",
    "Collector wall-clock duration",
    ["collector_name", "status"],
    buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0),
)
COLLECTOR_ERRORS_TOTAL = Counter(
    "collector_errors_total",
    "Collector failures (after retries exhausted or soft-fail)",
    ["collector_name"],
)
COLLECTOR_SUCCESS_TOTAL = Counter(
    "collector_success_total",
    "Successful collector runs",
    ["collector_name"],
)
COLLECTOR_LATENCY = Histogram(
    "collector_latency",
    "Per-attempt collector latency seconds",
    ["collector_name", "attempt"],
    buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0),
)
COLLECTION_RUNS_TOTAL = Counter(
    "context_collection_runs_total",
    "Full investigation context collection runs",
    ["status"],
)


def init_metrics(version: str, environment: str) -> None:
    SERVICE_INFO.info({"version": version, "environment": environment})
