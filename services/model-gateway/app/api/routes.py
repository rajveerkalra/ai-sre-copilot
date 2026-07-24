"""Model Gateway REST API."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.config import get_settings
from app.providers.ollama import ProviderError
from app.services.gateway import get_gateway

router = APIRouter(tags=["model-gateway"])


class ChatRequest(BaseModel):
    messages: list[dict[str, str]] = Field(..., min_length=1)
    model: str | None = None
    temperature: float = 0.1
    response_format: str | None = None
    agent: str | None = None
    use_cache: bool = False


class GenerateJsonRequest(BaseModel):
    system: str
    prompt: str
    model: str | None = None
    agent: str | None = None


@router.post("/v1/chat")
async def chat(body: ChatRequest) -> dict:
    gw = get_gateway()
    try:
        return await gw.chat(
            model=body.model,
            messages=body.messages,
            temperature=body.temperature,
            response_format=body.response_format,
            agent=body.agent,
            use_cache=body.use_cache,
        )
    except ProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/v1/generate-json")
async def generate_json(body: GenerateJsonRequest) -> dict:
    gw = get_gateway()
    try:
        return await gw.generate_json(
            model=body.model,
            system=body.system,
            prompt=body.prompt,
            agent=body.agent,
        )
    except ProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/v1/providers")
async def providers() -> dict:
    settings = get_settings()
    gw = get_gateway()
    return {
        "active": settings.llm_provider,
        "default_model": settings.default_model,
        "available": await gw.available(),
        "supported": ["ollama", "openai_compatible", "anthropic_compatible"],
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
async def ready() -> dict:
    gw = get_gateway()
    s = get_settings()
    return {
        "status": "healthy",
        "service": s.service_name,
        "provider": s.llm_provider,
        "provider_available": await gw.available(),
        "redis": gw.cache.available,
        "circuit": gw.circuit.state.value,
    }
