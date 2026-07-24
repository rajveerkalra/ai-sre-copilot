"""Embedding Gateway configuration."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    service_name: str = "embedding-gateway"
    environment: str = "local"
    log_level: str = "INFO"
    version: str = "0.4.1"
    host: str = "0.0.0.0"
    port: int = 8041

    # onnx | sentence_transformers | openai
    embedding_provider: str = "onnx"
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_dim: int = 384

    # OpenAI stub
    openai_base_url: str = "https://api.openai.com/v1"
    openai_api_key: str = ""
    openai_embedding_model: str = "text-embedding-3-small"

    retries: int = 3
    backoff_base_seconds: float = 0.25
    backoff_max_seconds: float = 4.0
    circuit_failure_threshold: int = 8
    circuit_recovery_seconds: float = 45.0
    request_timeout_seconds: float = 120.0

    redis_url: str = "redis://redis:6379/0"
    cache_enabled: bool = True
    cache_ttl_seconds: int = 86400
    warmup_on_startup: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()
