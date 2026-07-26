"""Embedding Gateway REST API."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, Field

from app.config import get_settings
from app.providers.onnx_provider import ProviderError
from app.services.gateway import get_gateway

router = APIRouter(tags=["embedding-gateway"])


class EmbedRequest(BaseModel):
    texts: list[str] = Field(..., min_length=1, max_length=64)


@router.post("/v1/embed")
async def embed(body: EmbedRequest) -> dict:
    gw = get_gateway()
    try:
        return await gw.embed(body.texts)
    except ProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/v1/providers")
async def providers() -> dict:
    s = get_settings()
    gw = get_gateway()
    return {
        "active": s.embedding_provider,
        "model": s.embedding_model,
        "dimensions": gw.provider.dimension,
        "supported": ["onnx", "sentence_transformers", "openai"],
        "circuit": gw.circuit.state.value,
    }


@router.get("/health")
@router.get("/healthz")
async def health() -> dict:
    from app import __version__

    s = get_settings()
    return {"status": "healthy", "service": s.service_name, "version": __version__}


@router.get("/ready")
@router.get("/readyz")
async def ready(response: Response) -> dict:
    gw = get_gateway()
    s = get_settings()
    circuit_open = gw.circuit.state.value == "open"
    if circuit_open:
        response.status_code = 503
    return {
        "status": "degraded" if circuit_open else "healthy",
        "service": s.service_name,
        "provider": s.embedding_provider,
        "redis": gw.cache.available,
        "circuit": gw.circuit.state.value,
    }
