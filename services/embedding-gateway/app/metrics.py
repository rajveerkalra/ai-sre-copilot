"""Prometheus metrics for embedding-gateway."""

from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram, Info

SERVICE_INFO = Info("embedding_gateway", "Embedding gateway metadata")

EMBEDDING_LATENCY_SECONDS = Histogram(
    "embedding_latency_seconds",
    "Embedding request latency",
    ["provider", "status"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2, 5),
)
PROVIDER_FAILURES_TOTAL = Counter(
    "provider_failures_total",
    "Provider failures",
    ["provider", "reason"],
)
EMBEDDING_REQUESTS_TOTAL = Counter(
    "embedding_requests_total",
    "Embedding requests",
    ["provider", "status"],
)
CACHE_HITS_TOTAL = Counter("cache_hits_total", "Cache hits", ["cache"])
CACHE_MISSES_TOTAL = Counter("cache_misses_total", "Cache misses", ["cache"])
CACHE_HIT_RATIO = Gauge("cache_hit_ratio", "Cache hit ratio", ["cache"])


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
