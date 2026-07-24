"""Knowledge service tests with mocked store (no ONNX / Chroma)."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app


class FakeStore:
    def __init__(self) -> None:
        self._docs: dict[str, dict[str, Any]] = {}
        self.cache = type("C", (), {"available": False})()

    async def ensure_cache(self) -> None:
        return None

    async def close(self) -> None:
        return None

    async def upsert_document(self, *, title, content, tags=None, doc_id=None, source=None):
        doc_id = doc_id or "doc-1"
        self._docs[doc_id] = {
            "id": doc_id,
            "title": title,
            "content": content,
            "tags": tags or [],
            "source": source or "api",
            "evidence_id": f"runbook-{doc_id[:8]}",
        }
        return self._docs[doc_id]

    async def search(self, query: str, *, top_k: int = 5):
        return list(self._docs.values())[:top_k]

    def list_documents(self):
        return [
            {
                "id": d["id"],
                "title": d["title"],
                "tags": d["tags"],
                "source": d["source"],
                "content_preview": d["content"][:240],
                "evidence_id": d["evidence_id"],
            }
            for d in self._docs.values()
        ]

    def delete_document(self, doc_id: str) -> bool:
        return self._docs.pop(doc_id, None) is not None

    def count(self) -> int:
        return len(self._docs)

    async def seed_from_directory(self, directory):
        return 0


@pytest.fixture
def client(monkeypatch):
    store = FakeStore()
    monkeypatch.setenv("SEED_ON_STARTUP", "false")
    from app.config import get_settings

    get_settings.cache_clear()

    with patch("app.services.store.get_store", return_value=store):
        with patch("app.api.routes.get_store", return_value=store):
            app = create_app()
            transport = ASGITransport(app=app)
            yield app, store, transport
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_documents_crud(client):
    app, store, transport = client
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        h = await ac.get("/health")
        assert h.status_code == 200

        created = await ac.post(
            "/documents",
            json={
                "title": "High CPU",
                "content": "Check CPU saturation and scale pods.",
                "tags": ["cpu"],
                "id": "cpu-runbook",
            },
        )
        assert created.status_code == 200
        assert created.json()["id"] == "cpu-runbook"

        listed = await ac.get("/documents")
        assert listed.status_code == 200
        assert listed.json()["count"] == 1

        search = await ac.post("/search", json={"query": "cpu saturation", "top_k": 3})
        assert search.status_code == 200
        assert search.json()["count"] == 1
        assert search.json()["results"][0]["evidence_id"].startswith("runbook-")

        deleted = await ac.delete("/documents/cpu-runbook")
        assert deleted.status_code == 200
        assert store.count() == 0
