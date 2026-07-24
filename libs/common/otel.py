"""OpenTelemetry bootstrap for FastAPI services."""

from __future__ import annotations

import os
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


def setup_otel(
    *,
    service_name: str,
    environment: str = "local",
    endpoint: str | None = None,
    enabled: bool | None = None,
) -> bool:
    """
    Configure OTLP trace export. Soft-fails if packages or collector unavailable.

    Returns True when instrumentation is active.
    """
    if enabled is None:
        enabled = os.getenv("OTEL_TRACES_EXPORTER", "none").lower() not in {
            "",
            "none",
            "false",
            "0",
        }
    if not enabled:
        return False

    endpoint = endpoint or os.getenv(
        "OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector:4317"
    )

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
            OTLPSpanExporter,
        )
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError:
        logger.warning("otel_packages_missing")
        return False

    resource = Resource.create(
        {
            "service.name": service_name,
            "deployment.environment": environment,
        }
    )
    provider = TracerProvider(resource=resource)
    try:
        exporter = OTLPSpanExporter(endpoint=endpoint, insecure=True)
        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)
        logger.info("otel_configured", endpoint=endpoint, service=service_name)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("otel_setup_failed", error=str(exc))
        return False


def instrument_fastapi(app: Any, *, service_name: str) -> bool:
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        FastAPIInstrumentor.instrument_app(app, excluded_urls="health,ready,live,metrics")
        logger.info("otel_fastapi_instrumented", service=service_name)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("otel_fastapi_instrument_failed", error=str(exc))
        return False


def get_tracer(name: str):
    try:
        from opentelemetry import trace

        return trace.get_tracer(name)
    except Exception:  # noqa: BLE001
        return None
