"""Incident Service configuration."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    service_name: str = "incident-service"
    environment: str = "local"
    log_level: str = "INFO"
    version: str = "0.2.0"

    host: str = "0.0.0.0"
    port: int = 8000

    # async SQLAlchemy URL (asyncpg)
    database_url: str = (
        "postgresql+asyncpg://sre:sre@postgres:5432/sre_incidents"
    )
    # sync URL for Alembic
    database_url_sync: str = (
        "postgresql+psycopg2://sre:sre@postgres:5432/sre_incidents"
    )

    db_pool_size: int = 5
    db_max_overflow: int = 10
    db_echo: bool = False

    # Auto-run migrations on startup (Compose / K8s)
    run_migrations_on_startup: bool = True

    # Phase 3 — trigger context collection after incident create
    context_service_url: str = "http://context-service:8020"
    context_service_enabled: bool = True
    context_service_timeout_seconds: float = 120.0

    # Phase 7
    auth_enabled: bool = False
    jwt_secret: str = "change-me-phase7-local-secret-min-32-chars!!"
    jwt_algorithm: str = "HS256"
    jwt_issuer: str = "ai-sre-copilot"
    internal_service_token: str = "local-internal-service-token"
    otel_traces_exporter: str = "none"
    otel_exporter_otlp_endpoint: str = "http://otel-collector:4317"


@lru_cache
def get_settings() -> Settings:
    return Settings()
