"""Knowledge Service Prometheus metrics."""

from __future__ import annotations

from prometheus_client import Counter, Gauge

CACHE_HITS_TOTAL = Counter("cache_hits_total", "Cache hits", ["cache"])
CACHE_MISSES_TOTAL = Counter("cache_misses_total", "Cache misses", ["cache"])
CACHE_HIT_RATIO = Gauge("cache_hit_ratio", "Cache hit ratio", ["cache"])
PROVIDER_FAILURES_TOTAL = Counter(
    "provider_failures_total", "Upstream failures", ["provider", "reason"]
)


def observe_cache(cache: str, hit: bool) -> None:
    if hit:
        CACHE_HITS_TOTAL.labels(cache=cache).inc()
    else:
        CACHE_MISSES_TOTAL.labels(cache=cache).inc()
    hits = CACHE_HITS_TOTAL.labels(cache=cache)._value.get()  # type: ignore[attr-defined]
    misses = CACHE_MISSES_TOTAL.labels(cache=cache)._value.get()  # type: ignore[attr-defined]
    total = hits + misses
    CACHE_HIT_RATIO.labels(cache=cache).set((hits / total) if total else 0.0)
