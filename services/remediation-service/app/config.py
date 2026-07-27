"""Remediation Service configuration."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    service_name: str = "remediation-service"
    environment: str = "local"
    log_level: str = "INFO"
    version: str = "0.5.0"

    host: str = "0.0.0.0"
    port: int = 8032

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

    investigation_service_url: str = "http://investigation-service:8031"
    incident_service_url: str = "http://incident-service:8000"
    sample_app_url: str = "http://sample-app:8080"

    # Safety — never auto-execute; mutations gated
    execution_enabled: bool = True
    allow_mutations: bool = False
    allow_compose_restart: bool = False

    # Real Docker restart execution (see services/docker_executor.py). Only
    # logical service names in this comma-separated allowlist may ever be
    # restarted -- this is a hard safelist enforced in code, independent of
    # whatever the LLM/rule engine proposes, so a bad or hallucinated
    # proposal can never reach postgres/redis/etc. `docker_container_prefix`
    # maps a logical name ("sample-app") to its real container name
    # ("ai-sre-sample-app") the way this project's docker-compose.yml names
    # containers.
    restart_allowed_services: str = "sample-app"
    docker_container_prefix: str = "ai-sre-"

    http_timeout_seconds: float = 30.0
    http_retries: int = 3

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
