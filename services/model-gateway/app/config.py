"""Model Gateway configuration."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    service_name: str = "model-gateway"
    environment: str = "local"
    log_level: str = "INFO"
    version: str = "0.4.1"
    host: str = "0.0.0.0"
    port: int = 8040

    # Provider selection — switch via config only
    llm_provider: str = "ollama"  # ollama | openai_compatible | anthropic_compatible
    default_model: str = "llama3.2"

    # Ollama
    ollama_base_url: str = "http://ollama:11434"
    # CPU-only local inference for the rca_synthesizer's full-evidence prompt has
    # been measured at 15-40s in isolation, but as the 3rd+ sequential LLM call in
    # one investigation (after ~50s of prior enrichment calls) it was observed to
    # exceed 120s under real load/contention. 180s gives real headroom; 60s made
    # nearly every investigation time out and silently fall back to the rule engine.
    ollama_timeout_seconds: float = 180.0

    # OpenAI-compatible stub
    openai_base_url: str = "https://api.openai.com/v1"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    # Anthropic-compatible stub
    anthropic_base_url: str = "https://api.anthropic.com"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-3-5-sonnet-latest"

    # Resilience
    retries: int = 2
    backoff_base_seconds: float = 0.5
    backoff_max_seconds: float = 8.0
    circuit_failure_threshold: int = 5
    circuit_recovery_seconds: float = 30.0
    request_timeout_seconds: float = 180.0

    # Redis (request/response optional cache for identical prompts)
    redis_url: str = "redis://redis:6379/0"
    cache_enabled: bool = True
    cache_ttl_seconds: int = 120


@lru_cache
def get_settings() -> Settings:
    return Settings()
