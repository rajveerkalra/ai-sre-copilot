"""Sentence Transformers embedding provider (optional dependency)."""

from __future__ import annotations

from functools import lru_cache

from app.config import Settings
from app.providers.onnx_provider import ProviderError


@lru_cache(maxsize=2)
def _load_model(model_name: str):
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:  # pragma: no cover
        raise ProviderError(
            "sentence-transformers not installed; set EMBEDDING_PROVIDER=onnx "
            "or install sentence-transformers"
        ) from exc
    return SentenceTransformer(model_name)


class SentenceTransformersProvider:
    name = "sentence_transformers"
    dimension = 384

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.model_name = settings.embedding_model
        self.dimension = settings.embedding_dim or 384

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        try:
            model = _load_model(self.model_name)
            vectors = model.encode(texts, normalize_embeddings=True)
            return [list(map(float, v)) for v in vectors]
        except ProviderError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise ProviderError(f"SentenceTransformers embed failed: {exc}") from exc
