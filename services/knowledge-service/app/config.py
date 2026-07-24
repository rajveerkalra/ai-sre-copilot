"""Knowledge Service configuration."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    service_name: str = "knowledge-service"
    environment: str = "local"
    log_level: str = "INFO"
    version: str = "0.4.1"

    host: str = "0.0.0.0"
    port: int = 8030

    chroma_persist_dir: str = "/data/chroma"
    chroma_collection: str = "sre_runbooks"
    seed_on_startup: bool = True
    seed_dir: str = "/seed"

    # Embeddings via gateway — never ONNX/ST directly
    embedding_gateway_url: str = "http://embedding-gateway:8041"

    redis_url: str = "redis://redis:6379/0"
    cache_enabled: bool = True
    search_cache_ttl_seconds: int = 300

    http_timeout_seconds: float = 120.0
    http_retries: int = 5
    http_backoff_base: float = 1.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
