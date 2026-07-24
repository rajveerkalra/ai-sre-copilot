"""Knowledge Service REST API."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.store import get_store

router = APIRouter(tags=["knowledge"])


class DocumentCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=256)
    content: str = Field(..., min_length=1)
    tags: list[str] = Field(default_factory=list)
    id: str | None = None


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    top_k: int = Field(5, ge=1, le=20)


@router.post("/documents")
async def create_document(body: DocumentCreate) -> dict:
    store = get_store()
    try:
        return await store.upsert_document(
            title=body.title,
            content=body.content,
            tags=body.tags,
            doc_id=body.id,
            source="api",
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/documents")
async def list_documents() -> dict:
    store = get_store()
    docs = store.list_documents()
    return {"count": len(docs), "documents": docs}


@router.delete("/documents/{doc_id}")
async def delete_document(doc_id: str) -> dict:
    store = get_store()
    ok = store.delete_document(doc_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Document not found or delete failed")
    return {"deleted": True, "id": doc_id}


@router.post("/search")
async def search(body: SearchRequest) -> dict:
    store = get_store()
    try:
        hits = await store.search(body.query, top_k=body.top_k)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"query": body.query, "count": len(hits), "results": hits}


@router.get("/health")
@router.get("/healthz")
async def health() -> dict:
    from app import __version__
    from app.config import get_settings

    settings = get_settings()
    return {
        "status": "healthy",
        "service": settings.service_name,
        "version": __version__,
        "documents": get_store().count(),
    }


@router.get("/live")
@router.get("/livez")
async def live() -> dict:
    from app.config import get_settings

    return {"status": "healthy", "service": get_settings().service_name}


@router.get("/ready")
@router.get("/readyz")
async def ready() -> dict:
    store = get_store()
    await store.ensure_cache()
    return {
        "status": "healthy",
        "service": "knowledge-service",
        "chroma": "ok",
        "documents": store.count(),
        "redis": store.cache.available,
    }
