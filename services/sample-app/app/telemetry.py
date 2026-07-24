"""OpenTelemetry tracing bootstrap (no-op exporter by default in Phase 1)."""

from __future__ import annotations

from app.config import Settings


def setup_telemetry(settings: Settings) -> None:
    """Initialize OTel if an exporter is configured; otherwise stay silent.

    Phase 7 wires a full OTLP collector. Phase 1 keeps the hook so the app
    is already instrumented without requiring external collectors.
    """
    if settings.otel_traces_exporter in ("none", "", "False", "false"):
        return

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
            OTLPSpanExporter,
        )
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError:
        return

    resource = Resource.create(
        {
            "service.name": settings.otel_service_name,
            "deployment.environment": settings.environment,
            "service.version": settings.version,
        }
    )
    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(endpoint=settings.otel_exporter_otlp_endpoint)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    # FastAPIInstrumentor is applied in main after app creation when enabled
    _ = FastAPIInstrumentor
