"""Anthropic-compatible provider stub — enabled when API key is configured."""

from __future__ import annotations

from typing import Any

import httpx
import structlog

from app.config import Settings
from app.providers.ollama import ProviderError

logger = structlog.get_logger(__name__)


class AnthropicCompatibleProvider:
    name = "anthropic_compatible"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def available(self) -> bool:
        return bool(self.settings.anthropic_api_key)

    async def chat(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        temperature: float = 0.1,
        response_format: str | None = None,
    ) -> dict[str, Any]:
        if not self.settings.anthropic_api_key:
            raise ProviderError(
                "Anthropic-compatible provider stub: set ANTHROPIC_API_KEY to enable"
            )
        system = ""
        user_messages = []
        for m in messages:
            if m.get("role") == "system":
                system = m.get("content") or ""
            else:
                user_messages.append(
                    {"role": m.get("role") or "user", "content": m.get("content") or ""}
                )
        headers = {
            "x-api-key": self.settings.anthropic_api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        payload: dict[str, Any] = {
            "model": model or self.settings.anthropic_model,
            "max_tokens": 4096,
            "temperature": temperature,
            "messages": user_messages,
        }
        if system:
            payload["system"] = system
        if response_format == "json":
            payload["system"] = (
                (system + "\n" if system else "")
                + "Respond with valid JSON only."
            )

        async with httpx.AsyncClient(
            base_url=self.settings.anthropic_base_url.rstrip("/"),
            timeout=self.settings.request_timeout_seconds,
            headers=headers,
        ) as client:
            resp = await client.post("/v1/messages", json=payload)
            if resp.status_code >= 400:
                raise ProviderError(
                    f"Anthropic HTTP {resp.status_code}: {resp.text[:300]}"
                )
            body = resp.json()
            blocks = body.get("content") or []
            content = ""
            for b in blocks:
                if b.get("type") == "text":
                    content += b.get("text") or ""
            usage = body.get("usage") or {}
            return {
                "content": content,
                "provider": self.name,
                "model": model or self.settings.anthropic_model,
                "usage": {
                    "prompt_tokens": int(usage.get("input_tokens") or 0),
                    "completion_tokens": int(usage.get("output_tokens") or 0),
                    "total_tokens": int(usage.get("input_tokens") or 0)
                    + int(usage.get("output_tokens") or 0),
                },
                "raw": {"id": body.get("id")},
            }
