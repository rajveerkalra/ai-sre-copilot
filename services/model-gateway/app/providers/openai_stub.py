"""OpenAI-compatible provider stub — enabled when API key is configured."""

from __future__ import annotations

from typing import Any

import httpx
import structlog

from app.config import Settings
from app.providers.ollama import ProviderError

logger = structlog.get_logger(__name__)


class OpenAICompatibleProvider:
    name = "openai_compatible"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def available(self) -> bool:
        return bool(self.settings.openai_api_key)

    async def chat(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        temperature: float = 0.1,
        response_format: str | None = None,
    ) -> dict[str, Any]:
        if not self.settings.openai_api_key:
            raise ProviderError(
                "OpenAI-compatible provider stub: set OPENAI_API_KEY to enable"
            )
        headers = {
            "Authorization": f"Bearer {self.settings.openai_api_key}",
            "Content-Type": "application/json",
        }
        payload: dict[str, Any] = {
            "model": model or self.settings.openai_model,
            "messages": messages,
            "temperature": temperature,
        }
        if response_format == "json":
            payload["response_format"] = {"type": "json_object"}

        async with httpx.AsyncClient(
            base_url=self.settings.openai_base_url.rstrip("/"),
            timeout=self.settings.request_timeout_seconds,
            headers=headers,
        ) as client:
            resp = await client.post("/chat/completions", json=payload)
            if resp.status_code >= 400:
                raise ProviderError(f"OpenAI HTTP {resp.status_code}: {resp.text[:300]}")
            body = resp.json()
            choice = (body.get("choices") or [{}])[0]
            content = (choice.get("message") or {}).get("content") or ""
            usage = body.get("usage") or {}
            return {
                "content": content,
                "provider": self.name,
                "model": model or self.settings.openai_model,
                "usage": {
                    "prompt_tokens": int(usage.get("prompt_tokens") or 0),
                    "completion_tokens": int(usage.get("completion_tokens") or 0),
                    "total_tokens": int(usage.get("total_tokens") or 0),
                },
                "raw": {"id": body.get("id")},
            }
