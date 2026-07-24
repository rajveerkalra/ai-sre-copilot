"""HTTP observability middleware."""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.metrics import (
    HTTP_ERRORS_TOTAL,
    HTTP_REQUEST_DURATION_SECONDS,
    HTTP_REQUESTS_IN_PROGRESS,
    HTTP_REQUESTS_TOTAL,
)

logger = structlog.get_logger(__name__)


def _endpoint_label(path: str) -> str:
    if path.startswith("/incidents/") and path.endswith("/timeline"):
        return "/incidents/{id}/timeline"
    if path.startswith("/incidents/") and path.endswith("/resolve"):
        return "/incidents/{id}/resolve"
    if path.startswith("/incidents/") and path.endswith("/notes"):
        return "/incidents/{id}/notes"
    if path.startswith("/incidents/") and path.count("/") == 2:
        return "/incidents/{id}"
    if path.startswith("/webhooks/"):
        return path
    return path


class ObservabilityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
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
        else:
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
