"""Application configuration via environment variables."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    service_name: str = "sample-app"
    environment: str = "local"
    log_level: str = "INFO"
    version: str = "0.1.0"

    # HTTP
    host: str = "0.0.0.0"
    port: int = 8080

    # Simulated dependency (e.g. downstream API / DB)
    dependency_url: str = "http://127.0.0.1:9"  # blackhole by default when fault enabled
    dependency_timeout_seconds: float = 2.0

    # OpenTelemetry
    otel_service_name: str = "sample-app"
    otel_exporter_otlp_endpoint: str = "http://otel-collector:4317"
    otel_traces_exporter: str = "none"


@lru_cache
def get_settings() -> Settings:
    return Settings()
