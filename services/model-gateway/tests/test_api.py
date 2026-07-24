"""Model gateway unit tests with mocked Ollama provider."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app
from app.providers.ollama import OllamaProvider


@pytest.mark.asyncio
async def test_generate_json_via_gateway(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("CACHE_ENABLED", "false")
    monkeypatch.setenv("RETRIES", "1")
    from app.config import get_settings
    from app.services import gateway as gw_mod

    get_settings.cache_clear()
    gw_mod._gateway = None

    async def fake_chat(**kwargs):
        return {
            "content": '{"ok": true, "root_cause": "test"}',
            "provider": "ollama",
            "model": "llama3.2",
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }

    with patch.object(OllamaProvider, "chat", new=AsyncMock(side_effect=fake_chat)):
        with patch.object(OllamaProvider, "available", new=AsyncMock(return_value=True)):
            app = create_app()
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                resp = await ac.post(
                    "/v1/generate-json",
                    json={
                        "system": "sys",
                        "prompt": "prompt",
                        "agent": "test",
                    },
                )
                assert resp.status_code == 200, resp.text
                body = resp.json()
                assert body["json"]["ok"] is True
                assert body["provider"] == "ollama"

                providers = await ac.get("/v1/providers")
                assert providers.status_code == 200
                assert providers.json()["active"] == "ollama"

    get_settings.cache_clear()
    gw_mod._gateway = None


@pytest.mark.asyncio
async def test_openai_stub_requires_key(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai_compatible")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("CACHE_ENABLED", "false")
    from app.config import get_settings
    from app.services import gateway as gw_mod

    get_settings.cache_clear()
    gw_mod._gateway = None

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post(
            "/v1/chat",
            json={"messages": [{"role": "user", "content": "hi"}]},
        )
        assert resp.status_code == 502

    get_settings.cache_clear()
    gw_mod._gateway = None
