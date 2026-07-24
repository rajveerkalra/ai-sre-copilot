"""OpenAI embeddings stub — enabled when API key is configured."""

from __future__ import annotations

import httpx

from app.config import Settings
from app.providers.onnx_provider import ProviderError


class OpenAIEmbeddingProvider:
    name = "openai"
    dimension = 1536

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.dimension = settings.embedding_dim or 1536

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not self.settings.openai_api_key:
            raise ProviderError(
                "OpenAI embeddings stub: set OPENAI_API_KEY to enable (future)"
            )
        if not texts:
            return []
        headers = {
            "Authorization": f"Bearer {self.settings.openai_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.settings.openai_embedding_model,
            "input": texts,
        }
        with httpx.Client(
            base_url=self.settings.openai_base_url.rstrip("/"),
            timeout=self.settings.request_timeout_seconds,
            headers=headers,
        ) as client:
            resp = client.post("/embeddings", json=payload)
            if resp.status_code >= 400:
                raise ProviderError(f"OpenAI embed HTTP {resp.status_code}: {resp.text[:300]}")
            data = resp.json().get("data") or []
            data = sorted(data, key=lambda x: x.get("index", 0))
            return [list(map(float, row.get("embedding") or [])) for row in data]
