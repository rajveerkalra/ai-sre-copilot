"""Model gateway service layer."""

from __future__ import annotations

import time
from typing import Any

import structlog

from app.config import Settings, get_settings
from app.metrics import (
    CIRCUIT_STATE,
    LLM_LATENCY_SECONDS,
    LLM_REQUESTS_TOTAL,
    PROVIDER_FAILURES_TOTAL,
    TOKEN_USAGE_TOTAL,
    observe_cache,
)
from app.providers import get_provider
from app.providers.ollama import ProviderError, extract_json

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


class ModelGateway:
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
        self.circuit = policy.breaker(f"llm:{self.provider.name}")
        self.policy = policy
        self.cache = RedisCache(
            self.settings.redis_url,
            enabled=self.settings.cache_enabled,
            default_ttl_seconds=self.settings.cache_ttl_seconds,
        )

    async def startup(self) -> None:
        await self.cache.connect()

    async def shutdown(self) -> None:
        await self.cache.close()

    def _sync_circuit_metric(self) -> None:
        mapping = {"closed": 0, "half_open": 1, "open": 2}
        CIRCUIT_STATE.labels(name=self.circuit.name).set(
            mapping.get(self.circuit.state.value, 0)
        )

    async def available(self) -> bool:
        try:
            return await self.provider.available()
        except Exception:
            return False

    async def chat(
        self,
        *,
        model: str | None,
        messages: list[dict[str, str]],
        temperature: float = 0.1,
        response_format: str | None = None,
        agent: str | None = None,
        use_cache: bool = False,
    ) -> dict[str, Any]:
        model_name = model or self.settings.default_model
        cache_k = None
        if use_cache:
            cache_k = cache_key(
                "llm",
                self.provider.name,
                model_name,
                response_format or "",
                str(messages),
                prefix="mgw",
            )
            cached = await self.cache.get_json(cache_k)
            if cached is not None:
                observe_cache("llm", True)
                return cached
            observe_cache("llm", False)

        started = time.perf_counter()
        provider = self.provider.name
        status = "ok"

        async def _call():
            return await self.provider.chat(
                model=model_name,
                messages=messages,
                temperature=temperature,
                response_format=response_format,
            )

        try:
            result = await with_retry(
                _call,
                retries=self.policy.retries,
                backoff_base=self.policy.backoff_base,
                backoff_max=self.policy.backoff_max,
                timeout_seconds=self.policy.timeout_seconds,
                circuit=self.circuit,
                retry_on=(ProviderError, TimeoutError, OSError),
                operation=f"llm.chat:{provider}",
            )
            usage = result.get("usage") or {}
            for token_type in ("prompt_tokens", "completion_tokens", "total_tokens"):
                TOKEN_USAGE_TOTAL.labels(
                    provider=provider, model=model_name, token_type=token_type
                ).inc(float(usage.get(token_type) or 0))
            LLM_REQUESTS_TOTAL.labels(provider=provider, status="ok").inc()
            logger.info(
                "llm_request",
                provider=provider,
                model=model_name,
                agent=agent,
                prompt_tokens=usage.get("prompt_tokens"),
                completion_tokens=usage.get("completion_tokens"),
                duration_ms=round((time.perf_counter() - started) * 1000, 2),
            )
            if cache_k:
                await self.cache.set_json(cache_k, result)
            return result
        except CircuitOpenError as exc:
            status = "circuit_open"
            PROVIDER_FAILURES_TOTAL.labels(provider=provider, reason="circuit_open").inc()
            LLM_REQUESTS_TOTAL.labels(provider=provider, status="error").inc()
            raise ProviderError(str(exc)) from exc
        except RetryExhaustedError as exc:
            status = "retry_exhausted"
            reason = type(exc.last_error).__name__ if exc.last_error else "unknown"
            PROVIDER_FAILURES_TOTAL.labels(provider=provider, reason=reason).inc()
            LLM_REQUESTS_TOTAL.labels(provider=provider, status="error").inc()
            raise ProviderError(str(exc)) from exc
        except Exception as exc:
            status = "error"
            PROVIDER_FAILURES_TOTAL.labels(provider=provider, reason=type(exc).__name__).inc()
            LLM_REQUESTS_TOTAL.labels(provider=provider, status="error").inc()
            raise
        finally:
            LLM_LATENCY_SECONDS.labels(
                provider=provider, model=model_name, status=status
            ).observe(time.perf_counter() - started)
            self._sync_circuit_metric()

    async def generate_json(
        self,
        *,
        model: str | None,
        system: str,
        prompt: str,
        agent: str | None = None,
    ) -> dict[str, Any]:
        result = await self.chat(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
            response_format="json",
            agent=agent,
            use_cache=False,
        )
        parsed = extract_json(result.get("content") or "")
        if parsed is None:
            PROVIDER_FAILURES_TOTAL.labels(
                provider=self.provider.name, reason="invalid_json"
            ).inc()
            raise ProviderError("Invalid JSON from model")
        return {
            "json": parsed,
            "provider": result.get("provider"),
            "model": result.get("model"),
            "usage": result.get("usage"),
        }


_gateway: ModelGateway | None = None


def get_gateway() -> ModelGateway:
    global _gateway
    if _gateway is None:
        _gateway = ModelGateway()
    return _gateway
