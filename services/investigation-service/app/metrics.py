"""Prometheus metrics for investigation-service."""

from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram, Info

SERVICE_INFO = Info("investigation_service", "Investigation service metadata")

INVESTIGATION_DURATION_SECONDS = Histogram(
    "investigation_duration_seconds",
    "Full investigation duration",
    ["status"],
    buckets=(0.5, 1, 2, 5, 10, 30, 60, 120, 300),
)
LLM_REQUESTS_TOTAL = Counter(
    "llm_requests_total",
    "Model gateway LLM requests",
    ["agent", "status"],
)
LLM_FAILURES_TOTAL = Counter(
    "llm_failures_total",
    "Model gateway failures",
    ["agent", "reason"],
)
FALLBACK_TOTAL = Counter(
    "fallback_total",
    "Rule-based fallback activations",
    ["agent"],
)
AGENT_DURATION_SECONDS = Histogram(
    "agent_duration_seconds",
    "Per-agent duration",
    ["agent", "status"],
    buckets=(0.05, 0.1, 0.25, 0.5, 1, 2, 5, 15, 30, 60),
)
CACHE_HITS_TOTAL = Counter("cache_hits_total", "Cache hits", ["cache"])
CACHE_MISSES_TOTAL = Counter("cache_misses_total", "Cache misses", ["cache"])
CACHE_HIT_RATIO = Gauge("cache_hit_ratio", "Cache hit ratio", ["cache"])
PROVIDER_FAILURES_TOTAL = Counter(
    "provider_failures_total",
    "Upstream provider failures",
    ["provider", "reason"],
)


def init_metrics(version: str, environment: str) -> None:
    SERVICE_INFO.info({"version": version, "environment": environment})


def observe_cache(cache: str, hit: bool) -> None:
    if hit:
        CACHE_HITS_TOTAL.labels(cache=cache).inc()
    else:
        CACHE_MISSES_TOTAL.labels(cache=cache).inc()
    hits = CACHE_HITS_TOTAL.labels(cache=cache)._value.get()  # type: ignore[attr-defined]
    misses = CACHE_MISSES_TOTAL.labels(cache=cache)._value.get()  # type: ignore[attr-defined]
    total = hits + misses
    CACHE_HIT_RATIO.labels(cache=cache).set((hits / total) if total else 0.0)
