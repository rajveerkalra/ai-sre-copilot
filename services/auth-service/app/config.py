from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    service_name: str = "auth-service"
    environment: str = "local"
    log_level: str = "INFO"
    version: str = "0.7.0"

    jwt_secret: str = "change-me-phase7-local-secret-min-32-chars!!"
    jwt_algorithm: str = "HS256"
    jwt_issuer: str = "ai-sre-copilot"
    access_token_ttl_minutes: int = 60

    # Demo users: username:password:role1|role2 (comma-separated users)
    # Prefer AUTH_USERS env; defaults are for local demo only.
    auth_users: str = (
        "admin:admin123:admin,"
        "operator:operator123:operator,"
        "viewer:viewer123:viewer"
    )

    rate_limit_login_per_minute: int = 20
    otel_traces_exporter: str = "otlp"
    otel_exporter_otlp_endpoint: str = "http://otel-collector:4317"


@lru_cache
def get_settings() -> Settings:
    return Settings()
