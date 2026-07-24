"""Model Gateway client — Investigation Service must never call Ollama directly."""

from __future__ import annotations

from typing import Any

import httpx
import structlog

from app.config import Settings, get_settings
from app.metrics import LLM_FAILURES_TOTAL, LLM_REQUESTS_TOTAL

try:
    from libs.common.resilience import CircuitBreaker, CircuitOpenError, with_retry
except ImportError:  # pragma: no cover
    from common.resilience import CircuitBreaker, CircuitOpenError, with_retry  # type: ignore

logger = structlog.get_logger(__name__)

_breaker = CircuitBreaker(name="model-gateway", failure_threshold=5, recovery_timeout_seconds=30.0)


class ModelGatewayError(Exception):
    pass


class ModelGatewayClient:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    @property
    def model(self) -> str:
        return self.settings.llm_model

    async def available(self) -> bool:
        if not self.settings.llm_enabled:
            return False
        try:
            async with httpx.AsyncClient(
                base_url=self.settings.model_gateway_url.rstrip("/"),
                timeout=5.0,
            ) as client:
                resp = await client.get("/v1/providers")
                if resp.status_code != 200:
                    return False
                return bool(resp.json().get("available"))
        except Exception:
            return False

    async def generate_json(
        self,
        *,
        agent: str,
        system: str,
        prompt: str,
    ) -> dict[str, Any]:
        if not self.settings.llm_enabled:
            LLM_FAILURES_TOTAL.labels(agent=agent, reason="disabled").inc()
            raise ModelGatewayError("LLM disabled")

        url = f"{self.settings.model_gateway_url.rstrip('/')}/v1/generate-json"
        payload = {
            "system": system,
            "prompt": prompt,
            "model": self.model,
            "agent": agent,
        }

        async def _call():
            async with httpx.AsyncClient(
                timeout=self.settings.llm_timeout_seconds
            ) as client:
                resp = await client.post(url, json=payload)
                if resp.status_code >= 400:
                    raise ModelGatewayError(
                        f"Model gateway HTTP {resp.status_code}: {resp.text[:300]}"
                    )
                body = resp.json()
                parsed = body.get("json")
                if not isinstance(parsed, dict):
                    raise ModelGatewayError("Invalid JSON payload from model gateway")
                return parsed

        try:
            parsed = await with_retry(
                _call,
                retries=self.settings.http_retries,
                backoff_base=self.settings.http_backoff_base,
                timeout_seconds=self.settings.llm_timeout_seconds,
                circuit=_breaker,
                retry_on=(ModelGatewayError, httpx.TimeoutException, OSError),
                operation="model-gateway.generate_json",
            )
            LLM_REQUESTS_TOTAL.labels(agent=agent, status="ok").inc()
            return parsed
        except CircuitOpenError as exc:
            LLM_FAILURES_TOTAL.labels(agent=agent, reason="circuit_open").inc()
            LLM_REQUESTS_TOTAL.labels(agent=agent, status="error").inc()
            raise ModelGatewayError(str(exc)) from exc
        except Exception as exc:
            LLM_FAILURES_TOTAL.labels(agent=agent, reason=type(exc).__name__).inc()
            LLM_REQUESTS_TOTAL.labels(agent=agent, status="error").inc()
            if isinstance(exc, ModelGatewayError):
                raise
            raise ModelGatewayError(str(exc)) from exc
