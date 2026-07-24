from __future__ import annotations

from prometheus_client import Counter, Histogram

LOGIN_TOTAL = Counter(
    "auth_login_total",
    "Login attempts",
    ["result"],
)
TOKEN_ISSUED_TOTAL = Counter(
    "auth_tokens_issued_total",
    "Access tokens issued",
)
HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "http_request_duration_seconds",
    "HTTP latency",
    ["method", "endpoint", "status_code"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5),
)


def init_metrics(version: str, environment: str) -> None:
    from prometheus_client import Info

    info = Info("auth_service", "Auth service build info")
    info.info({"version": version, "environment": environment})
