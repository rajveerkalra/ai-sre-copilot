"""Ollama LLM provider."""

from __future__ import annotations

import json
import re
from typing import Any

import httpx
import structlog

from app.config import Settings

logger = structlog.get_logger(__name__)


class ProviderError(Exception):
    pass


class OllamaProvider:
    name = "ollama"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def available(self) -> bool:
        try:
            async with httpx.AsyncClient(
                base_url=self.settings.ollama_base_url.rstrip("/"),
                timeout=5.0,
            ) as client:
                resp = await client.get("/api/tags")
                return resp.status_code == 200
        except Exception:
            return False

    async def chat(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        temperature: float = 0.1,
        response_format: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": model,
            "stream": False,
            "messages": messages,
            "options": {"temperature": temperature},
        }
        if response_format == "json":
            payload["format"] = "json"

        async with httpx.AsyncClient(
            base_url=self.settings.ollama_base_url.rstrip("/"),
            timeout=self.settings.ollama_timeout_seconds,
        ) as client:
            resp = await client.post("/api/chat", json=payload)
            if resp.status_code >= 400:
                raise ProviderError(f"Ollama HTTP {resp.status_code}: {resp.text[:300]}")
            body = resp.json()
            content = (body.get("message") or {}).get("content") or body.get("response") or ""
            prompt_tokens = int((body.get("prompt_eval_count") or 0))
            completion_tokens = int((body.get("eval_count") or 0))
            return {
                "content": content,
                "provider": self.name,
                "model": model,
                "usage": {
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": prompt_tokens + completion_tokens,
                },
                "raw": {
                    "done": body.get("done"),
                    "total_duration": body.get("total_duration"),
                },
            }


def extract_json(text: str) -> dict[str, Any] | None:
    text = (text or "").strip()
    if not text:
        return None
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", text)
        if not match:
            return None
        try:
            data = json.loads(match.group(0))
            return data if isinstance(data, dict) else None
        except json.JSONDecodeError:
            return None
