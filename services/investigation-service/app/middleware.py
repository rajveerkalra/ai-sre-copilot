"""HTTP observability middleware."""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable

import structlog
from prometheus_client import Counter, Gauge, Histogram
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = structlog.get_logger(__name__)

HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "HTTP requests",
    ["method", "endpoint", "status_code"],
)
HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency",
    ["method", "endpoint"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60, 120),
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


def _endpoint_label(path: str) -> str:
    if path.endswith("/investigate"):
        return "/incidents/{id}/investigate"
    if "/investigations/" in path and path.endswith("/evidence"):
        return "/investigations/{id}/evidence"
    if "/investigations/" in path and path.endswith("/rca"):
        return "/investigations/{id}/rca"
    if path.startswith("/investigations/"):
        return "/investigations/{id}"
    if path.endswith("/investigation"):
        return "/incidents/{id}/investigation"
    return path


class ObservabilityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            correlation_id=request.headers.get("x-correlation-id", request_id),
            method=request.method,
            path=request.url.path,
        )
        method = request.method
        endpoint = _endpoint_label(request.url.path)
        HTTP_REQUESTS_IN_PROGRESS.labels(method=method, endpoint=endpoint).inc()
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            duration = time.perf_counter() - started
            HTTP_REQUEST_DURATION_SECONDS.labels(
                method=method, endpoint=endpoint
            ).observe(duration)
            HTTP_REQUESTS_TOTAL.labels(
                method=method, endpoint=endpoint, status_code="500"
            ).inc()
            HTTP_ERRORS_TOTAL.labels(method=method, endpoint=endpoint).inc()
            HTTP_REQUESTS_IN_PROGRESS.labels(method=method, endpoint=endpoint).dec()
            logger.exception("request_failed")
            raise
        duration = time.perf_counter() - started
        status = str(response.status_code)
        HTTP_REQUEST_DURATION_SECONDS.labels(
            method=method, endpoint=endpoint
        ).observe(duration)
        HTTP_REQUESTS_TOTAL.labels(
            method=method, endpoint=endpoint, status_code=status
        ).inc()
        if response.status_code >= 500:
            HTTP_ERRORS_TOTAL.labels(method=method, endpoint=endpoint).inc()
        HTTP_REQUESTS_IN_PROGRESS.labels(method=method, endpoint=endpoint).dec()
        response.headers["X-Request-ID"] = request_id
        logger.info(
            "request_completed",
            status_code=response.status_code,
            duration_ms=round(duration * 1000, 2),
        )
        return response
