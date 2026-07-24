"""LLM provider protocol and registry."""

from __future__ import annotations

from typing import Any, Protocol

from app.config import Settings
from app.providers.anthropic_stub import AnthropicCompatibleProvider
from app.providers.ollama import OllamaProvider
from app.providers.openai_stub import OpenAICompatibleProvider


class LLMProvider(Protocol):
    name: str

    async def available(self) -> bool: ...

    async def chat(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        temperature: float = 0.1,
        response_format: str | None = None,
    ) -> dict[str, Any]: ...


def get_provider(settings: Settings) -> LLMProvider:
    key = (settings.llm_provider or "ollama").strip().lower()
    if key in {"ollama"}:
        return OllamaProvider(settings)
    if key in {"openai", "openai_compatible", "openai-compatible"}:
        return OpenAICompatibleProvider(settings)
    if key in {"anthropic", "anthropic_compatible", "anthropic-compatible"}:
        return AnthropicCompatibleProvider(settings)
    raise ValueError(f"Unknown LLM provider: {settings.llm_provider}")
