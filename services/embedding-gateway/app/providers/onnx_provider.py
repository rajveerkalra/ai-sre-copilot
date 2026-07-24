"""ONNX Runtime MiniLM embeddings (via Chroma ONNX helper)."""

from __future__ import annotations

from functools import lru_cache

from app.config import Settings


class ProviderError(Exception):
    pass


@lru_cache(maxsize=1)
def _onnx_ef():
    from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2

    return ONNXMiniLM_L6_V2()


class OnnxEmbeddingProvider:
    name = "onnx"
    dimension = 384

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.dimension = settings.embedding_dim or 384

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        try:
            vectors = _onnx_ef()(texts)
            return [list(map(float, v)) for v in vectors]
        except Exception as exc:  # noqa: BLE001
            raise ProviderError(f"ONNX embed failed: {exc}") from exc
