"""Prometheus metrics for the sample application."""

from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram, Info

SERVICE_INFO = Info("sample_app", "Sample application build metadata")

HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status_code"],
)

HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "endpoint"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

HTTP_REQUESTS_IN_PROGRESS = Gauge(
    "http_requests_in_progress",
    "In-flight HTTP requests",
    ["method", "endpoint"],
)

FAULT_ACTIVE = Gauge(
    "sample_app_fault_active",
    "Whether a named fault injection is currently active (1=yes, 0=no)",
    ["fault_type"],
)

FAULT_INJECTIONS_TOTAL = Counter(
    "sample_app_fault_injections_total",
    "Count of fault injection activations",
    ["fault_type", "action"],
)

BUSINESS_ORDERS_TOTAL = Counter(
    "sample_app_orders_total",
    "Simulated business orders processed",
    ["status"],
)

DEPENDENCY_CALLS_TOTAL = Counter(
    "sample_app_dependency_calls_total",
    "Outbound dependency call attempts",
    ["dependency", "status"],
)

DEPENDENCY_LATENCY_SECONDS = Histogram(
    "sample_app_dependency_latency_seconds",
    "Outbound dependency call latency",
    ["dependency"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0),
)

PROCESS_CPU_SIMULATED = Gauge(
    "sample_app_cpu_burn_active",
    "CPU burn fault is actively consuming CPU (1=yes)",
)

PROCESS_MEMORY_SIMULATED_BYTES = Gauge(
    "sample_app_memory_ballast_bytes",
    "Bytes held by memory ballast fault",
)


def init_metrics(version: str, environment: str) -> None:
    SERVICE_INFO.info({"version": version, "environment": environment})
    for fault in (
        "error_storm",
        "latency",
        "cpu_spike",
        "memory_leak",
        "dependency_timeout",
        "crash",
    ):
        FAULT_ACTIVE.labels(fault_type=fault).set(0)
