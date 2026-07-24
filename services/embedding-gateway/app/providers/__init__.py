"""Embedding providers."""

from __future__ import annotations

from typing import Protocol

from app.config import Settings
from app.providers.onnx_provider import OnnxEmbeddingProvider
from app.providers.openai_stub import OpenAIEmbeddingProvider
from app.providers.sentence_transformers_provider import SentenceTransformersProvider


class EmbeddingProvider(Protocol):
    name: str
    dimension: int

    def embed(self, texts: list[str]) -> list[list[float]]: ...


def get_provider(settings: Settings) -> EmbeddingProvider:
    key = (settings.embedding_provider or "onnx").strip().lower()
    if key in {"onnx", "onnxruntime", "onnx_runtime"}:
        return OnnxEmbeddingProvider(settings)
    if key in {"sentence_transformers", "sentence-transformers", "st"}:
        return SentenceTransformersProvider(settings)
    if key in {"openai", "openai_compatible"}:
        return OpenAIEmbeddingProvider(settings)
    raise ValueError(f"Unknown embedding provider: {settings.embedding_provider}")
