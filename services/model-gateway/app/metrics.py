"""Prometheus metrics for model-gateway."""

from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram, Info

SERVICE_INFO = Info("model_gateway", "Model gateway metadata")

LLM_LATENCY_SECONDS = Histogram(
    "llm_latency_seconds",
    "LLM request latency",
    ["provider", "model", "status"],
    buckets=(0.1, 0.25, 0.5, 1, 2, 5, 10, 30, 60, 120),
)
PROVIDER_FAILURES_TOTAL = Counter(
    "provider_failures_total",
    "Provider failures",
    ["provider", "reason"],
)
LLM_REQUESTS_TOTAL = Counter(
    "llm_requests_total",
    "LLM requests",
    ["provider", "status"],
)
TOKEN_USAGE_TOTAL = Counter(
    "llm_tokens_total",
    "Token accounting",
    ["provider", "model", "token_type"],
)
CACHE_HITS_TOTAL = Counter("cache_hits_total", "Cache hits", ["cache"])
CACHE_MISSES_TOTAL = Counter("cache_misses_total", "Cache misses", ["cache"])
CACHE_HIT_RATIO = Gauge("cache_hit_ratio", "Cache hit ratio", ["cache"])
CIRCUIT_STATE = Gauge(
    "circuit_breaker_state",
    "Circuit breaker state (0=closed,1=half_open,2=open)",
    ["name"],
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
