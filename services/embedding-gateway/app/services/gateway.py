"""Embedding gateway service."""

from __future__ import annotations

import asyncio
import hashlib
import time
from typing import Any

import structlog

from app.config import Settings, get_settings
from app.metrics import (
    EMBEDDING_LATENCY_SECONDS,
    EMBEDDING_REQUESTS_TOTAL,
    PROVIDER_FAILURES_TOTAL,
    observe_cache,
)
from app.providers import get_provider
from app.providers.onnx_provider import ProviderError

try:
    from libs.common.cache import RedisCache, cache_key
    from libs.common.resilience import (
        CircuitOpenError,
        ResiliencePolicy,
        RetryExhaustedError,
        with_retry,
    )
except ImportError:  # pragma: no cover
    from common.cache import RedisCache, cache_key  # type: ignore
    from common.resilience import (  # type: ignore
        CircuitOpenError,
        ResiliencePolicy,
        RetryExhaustedError,
        with_retry,
    )

logger = structlog.get_logger(__name__)


class EmbeddingGateway:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.provider = get_provider(self.settings)
        policy = ResiliencePolicy(
            retries=self.settings.retries,
            timeout_seconds=self.settings.request_timeout_seconds,
            backoff_base=self.settings.backoff_base_seconds,
            backoff_max=self.settings.backoff_max_seconds,
            circuit_failure_threshold=self.settings.circuit_failure_threshold,
            circuit_recovery_seconds=self.settings.circuit_recovery_seconds,
        )
        self.circuit = policy.breaker(f"embed:{self.provider.name}")
        self.policy = policy
        self.cache = RedisCache(
            self.settings.redis_url,
            enabled=self.settings.cache_enabled,
            default_ttl_seconds=self.settings.cache_ttl_seconds,
        )

    async def startup(self) -> None:
        await self.cache.connect()
        if self.settings.warmup_on_startup:
            try:
                await self.embed(["warmup"])
                logger.info("embedding_warmup_complete", provider=self.provider.name)
            except Exception as exc:  # noqa: BLE001
                logger.warning("embedding_warmup_failed", error=str(exc))

    async def shutdown(self) -> None:
        await self.cache.close()

    async def embed(self, texts: list[str]) -> dict[str, Any]:
        if not texts:
            return {
                "embeddings": [],
                "provider": self.provider.name,
                "model": self.settings.embedding_model,
                "dimensions": self.provider.dimension,
                "cached": 0,
            }

        # Per-text cache
        vectors: list[list[float] | None] = [None] * len(texts)
        missing_idx: list[int] = []
        missing_texts: list[str] = []
        cached = 0
        for i, text in enumerate(texts):
            digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
            key = cache_key(
                "emb",
                self.provider.name,
                self.settings.embedding_model,
                digest,
                prefix="egw",
            )
            hit = await self.cache.get_json(key)
            if hit is not None and isinstance(hit, list):
                vectors[i] = hit
                cached += 1
                observe_cache("embeddings", True)
            else:
                missing_idx.append(i)
                missing_texts.append(text)
                observe_cache("embeddings", False)

        started = time.perf_counter()
        provider = self.provider.name
        status = "ok"

        if missing_texts:

            async def _call():
                return await asyncio.to_thread(self.provider.embed, missing_texts)

            try:
                computed = await with_retry(
                    _call,
                    retries=self.policy.retries,
                    backoff_base=self.policy.backoff_base,
                    backoff_max=self.policy.backoff_max,
                    timeout_seconds=self.policy.timeout_seconds,
                    circuit=self.circuit,
                    retry_on=(ProviderError, TimeoutError, OSError),
                    operation=f"embed:{provider}",
                )
                for j, idx in enumerate(missing_idx):
                    vec = computed[j]
                    vectors[idx] = vec
                    digest = hashlib.sha256(missing_texts[j].encode("utf-8")).hexdigest()
                    key = cache_key(
                        "emb",
                        self.provider.name,
                        self.settings.embedding_model,
                        digest,
                        prefix="egw",
                    )
                    await self.cache.set_json(key, vec)
                EMBEDDING_REQUESTS_TOTAL.labels(provider=provider, status="ok").inc()
            except CircuitOpenError as exc:
                status = "circuit_open"
                PROVIDER_FAILURES_TOTAL.labels(
                    provider=provider, reason="circuit_open"
                ).inc()
                EMBEDDING_REQUESTS_TOTAL.labels(provider=provider, status="error").inc()
                raise ProviderError(str(exc)) from exc
            except RetryExhaustedError as exc:
                status = "retry_exhausted"
                reason = type(exc.last_error).__name__ if exc.last_error else "unknown"
                PROVIDER_FAILURES_TOTAL.labels(provider=provider, reason=reason).inc()
                EMBEDDING_REQUESTS_TOTAL.labels(provider=provider, status="error").inc()
                raise ProviderError(str(exc)) from exc
            except Exception:
                status = "error"
                PROVIDER_FAILURES_TOTAL.labels(
                    provider=provider, reason="exception"
                ).inc()
                EMBEDDING_REQUESTS_TOTAL.labels(provider=provider, status="error").inc()
                raise
            finally:
                EMBEDDING_LATENCY_SECONDS.labels(provider=provider, status=status).observe(
                    time.perf_counter() - started
                )
        else:
            EMBEDDING_LATENCY_SECONDS.labels(provider=provider, status="cache").observe(
                time.perf_counter() - started
            )

        logger.info(
            "embedding_request",
            provider=provider,
            count=len(texts),
            cached=cached,
            computed=len(missing_texts),
            duration_ms=round((time.perf_counter() - started) * 1000, 2),
        )
        return {
            "embeddings": vectors,
            "provider": provider,
            "model": self.settings.embedding_model,
            "dimensions": self.provider.dimension,
            "cached": cached,
        }


_gateway: EmbeddingGateway | None = None


def get_gateway() -> EmbeddingGateway:
    global _gateway
    if _gateway is None:
        _gateway = EmbeddingGateway()
    return _gateway
