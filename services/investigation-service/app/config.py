"""Investigation Service configuration."""

from __future__ import annotations

from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    service_name: str = "investigation-service"
    environment: str = "local"
    log_level: str = "INFO"
    version: str = "0.4.1"
    prompt_version: str = "rca-v1"

    host: str = "0.0.0.0"
    port: int = 8031

    database_url: str = (
        "postgresql+asyncpg://sre:sre@postgres:5432/sre_incidents"
    )
    database_url_sync: str = (
        "postgresql+psycopg2://sre:sre@postgres:5432/sre_incidents"
    )
    db_pool_size: int = 5
    db_max_overflow: int = 10
    db_echo: bool = False
    run_migrations_on_startup: bool = True

    context_service_url: str = "http://context-service:8020"
    knowledge_service_url: str = "http://knowledge-service:8030"
    incident_service_url: str = "http://incident-service:8000"
    model_gateway_url: str = "http://model-gateway:8040"

    llm_model: str = "llama3.2"
    # CPU-only local inference for the rca_synthesizer's full-evidence prompt has
    # been measured at 15-40s in isolation, but as the 3rd+ sequential LLM call in
    # one investigation it was observed to exceed 120s under real load/contention.
    # 180s gives real headroom; 60s made nearly every investigation silently fall
    # back to the rule engine.
    llm_timeout_seconds: float = 180.0
    llm_enabled: bool = True
    # Kept separate from http_retries (below): LLM calls are slow enough that
    # 3 retries at 180s each risks ~9 minutes of worst-case latency per agent.
    llm_retries: int = 2

    redis_url: str = "redis://redis:6379/0"
    cache_enabled: bool = True
    context_cache_ttl_seconds: int = 120

    http_retries: int = 3
    http_backoff_base: float = 0.5
    http_timeout_seconds: float = 30.0

    auto_collect_context_if_missing: bool = True
    citation_required: bool = True

    # Auth/RBAC. Defaults to disabled so tests and bare `uvicorn app.main:app`
    # keep working without a token; docker-compose.yml turns this on for the
    # running stack via AUTH_ENABLED=true, matching remediation-service's
    # pattern. Previously this service had NO auth config at all -- every
    # route (including feedback, which writes into the knowledge base) was
    # reachable by anyone who could hit the port, despite the dashboard's
    # nginx already forwarding a real Authorization header that was simply
    # never checked here.
    auth_enabled: bool = False
    jwt_secret: str = "change-me-phase7-local-secret-min-32-chars!!"
    jwt_algorithm: str = "HS256"
    jwt_issuer: str = "ai-sre-copilot"
    internal_service_token: str = "local-internal-service-token"

    # Deprecated aliases — prefer LLM_* / MODEL_GATEWAY_URL
    ollama_model: str | None = None
    ollama_enabled: bool | None = None
    ollama_timeout_seconds: float | None = None

    @model_validator(mode="after")
    def _apply_legacy_aliases(self) -> Settings:
        if self.ollama_model:
            self.llm_model = self.ollama_model
        if self.ollama_enabled is not None:
            self.llm_enabled = self.ollama_enabled
        if self.ollama_timeout_seconds is not None:
            self.llm_timeout_seconds = self.ollama_timeout_seconds
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
