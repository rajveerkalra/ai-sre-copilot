"""ChromaDB vector store — embeddings come from Embedding Gateway (never ONNX directly)."""

from __future__ import annotations

import hashlib
import uuid
from functools import lru_cache
from pathlib import Path
from typing import Any

import chromadb
import httpx
import structlog

from app.config import Settings, get_settings
from app.metrics import observe_cache
from app.services.resilient import call_with_resilience

try:
    from libs.common.cache import RedisCache, cache_key
except ImportError:  # pragma: no cover
    from common.cache import RedisCache, cache_key  # type: ignore

logger = structlog.get_logger(__name__)


class KnowledgeStore:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        Path(self.settings.chroma_persist_dir).mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(path=self.settings.chroma_persist_dir)
        # No embedding function — vectors supplied by embedding-gateway
        self._collection = self._client.get_or_create_collection(
            name=self.settings.chroma_collection,
            metadata={
                "hnsw:space": "cosine",
                "embedding_source": "embedding-gateway",
            },
        )
        self.cache = RedisCache(
            self.settings.redis_url,
            enabled=self.settings.cache_enabled,
            default_ttl_seconds=self.settings.search_cache_ttl_seconds,
        )
        self._cache_started = False

    async def ensure_cache(self) -> None:
        if not self._cache_started:
            await self.cache.connect()
            self._cache_started = True

    async def close(self) -> None:
        await self.cache.close()

    async def _embed(self, texts: list[str]) -> list[list[float]]:
        url = f"{self.settings.embedding_gateway_url.rstrip('/')}/v1/embed"

        async def _post():
            async with httpx.AsyncClient(timeout=self.settings.http_timeout_seconds) as client:
                resp = await client.post(url, json={"texts": texts})
                if resp.status_code >= 400:
                    raise RuntimeError(f"embed gateway {resp.status_code}: {resp.text[:200]}")
                data = resp.json()
                return data.get("embeddings") or []

        return await call_with_resilience(
            _post,
            name="embedding-gateway",
            retries=self.settings.http_retries,
            timeout_seconds=self.settings.http_timeout_seconds,
            backoff_base=self.settings.http_backoff_base,
        )

    async def upsert_document(
        self,
        *,
        title: str,
        content: str,
        tags: list[str] | None = None,
        doc_id: str | None = None,
        source: str | None = None,
    ) -> dict[str, Any]:
        await self.ensure_cache()
        doc_id = doc_id or str(uuid.uuid4())
        tags = tags or []
        metadata = {
            "title": title,
            "tags": ",".join(tags),
            "source": source or "api",
            "content_hash": hashlib.sha256(content.encode()).hexdigest()[:16],
        }
        embeddings = await self._embed([content])
        if not embeddings or not embeddings[0]:
            raise RuntimeError("Embedding gateway returned empty vector")
        self._collection.upsert(
            ids=[doc_id],
            documents=[content],
            embeddings=[embeddings[0]],
            metadatas=[metadata],
        )
        # Invalidate search cache broadly by bumping collection epoch key
        await self.cache.delete(cache_key("search_epoch", self.settings.chroma_collection, prefix="ks"))
        logger.info("document_upserted", doc_id=doc_id, title=title)
        return {"id": doc_id, "title": title, "tags": tags, "source": metadata["source"]}

    async def search(self, query: str, *, top_k: int = 5) -> list[dict[str, Any]]:
        await self.ensure_cache()
        if self._collection.count() == 0:
            return []

        skey = cache_key("search", self.settings.chroma_collection, query, str(top_k), prefix="ks")
        cached = await self.cache.get_json(skey)
        if cached is not None:
            observe_cache("runbook_search", True)
            return cached
        observe_cache("runbook_search", False)

        q_emb = await self._embed([query])
        if not q_emb or not q_emb[0]:
            return []
        result = self._collection.query(
            query_embeddings=[q_emb[0]],
            n_results=min(top_k, max(1, self._collection.count())),
        )
        hits: list[dict[str, Any]] = []
        ids = (result.get("ids") or [[]])[0]
        docs = (result.get("documents") or [[]])[0]
        metas = (result.get("metadatas") or [[]])[0]
        dists = (result.get("distances") or [[]])[0]
        for i, doc_id in enumerate(ids):
            dist = dists[i] if i < len(dists) else None
            score = round(1.0 - float(dist), 4) if dist is not None else None
            meta = metas[i] if i < len(metas) else {}
            hits.append(
                {
                    "id": doc_id,
                    "title": meta.get("title", ""),
                    "content": docs[i] if i < len(docs) else "",
                    "tags": [t for t in (meta.get("tags") or "").split(",") if t],
                    "source": meta.get("source"),
                    "score": score,
                    "evidence_id": f"runbook-{doc_id[:8]}",
                }
            )
        await self.cache.set_json(skey, hits)
        return hits

    def list_documents(self) -> list[dict[str, Any]]:
        if self._collection.count() == 0:
            return []
        data = self._collection.get(include=["metadatas", "documents"])
        out = []
        for i, doc_id in enumerate(data.get("ids") or []):
            meta = (data.get("metadatas") or [])[i] or {}
            content = (data.get("documents") or [])[i] or ""
            out.append(
                {
                    "id": doc_id,
                    "title": meta.get("title", ""),
                    "tags": [t for t in (meta.get("tags") or "").split(",") if t],
                    "source": meta.get("source"),
                    "content_preview": content[:240],
                    "evidence_id": f"runbook-{doc_id[:8]}",
                }
            )
        return out

    def delete_document(self, doc_id: str) -> bool:
        try:
            self._collection.delete(ids=[doc_id])
            logger.info("document_deleted", doc_id=doc_id)
            return True
        except Exception:
            return False

    def count(self) -> int:
        return self._collection.count()

    async def seed_from_directory(self, directory: str | Path) -> int:
        path = Path(directory)
        if not path.exists():
            logger.warning("seed_dir_missing", path=str(path))
            return 0
        count = 0
        for md in sorted(path.glob("**/*.md")):
            content = md.read_text(encoding="utf-8")
            title = md.stem.replace("-", " ").replace("_", " ").title()
            tags = [md.stem]
            doc_id = hashlib.sha256(md.name.encode()).hexdigest()[:32]
            await self.upsert_document(
                title=title,
                content=content,
                tags=tags,
                doc_id=doc_id,
                source=f"seed:{md.name}",
            )
            count += 1
        logger.info("seed_complete", count=count, path=str(path))
        return count


_store: KnowledgeStore | None = None


def get_store() -> KnowledgeStore:
    global _store
    if _store is None:
        _store = KnowledgeStore()
    return _store
