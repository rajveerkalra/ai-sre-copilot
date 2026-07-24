"""Context Service configuration."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    service_name: str = "context-service"
    environment: str = "local"
    log_level: str = "INFO"
    version: str = "0.3.0"

    host: str = "0.0.0.0"
    port: int = 8020

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

    # Upstream observability
    prometheus_url: str = "http://prometheus:9090"
    loki_url: str = "http://loki:3100"
    incident_service_url: str = "http://incident-service:8000"

    # Collector tuning
    collector_timeout_seconds: float = 30.0
    collector_retries: int = 3
    collector_backoff_base_seconds: float = 0.5
    metrics_lookback_minutes: int = 60
    logs_limit: int = 500
    logs_lookback_minutes: int = 30

    # Kubernetes (Kind / kubeconfig). Empty = auto-detect or degrade gracefully.
    kubeconfig_path: str = ""
    kubernetes_namespace: str = "default"
    docker_socket: str = "unix:///var/run/docker.sock"
    enable_docker_collector: bool = True
    enable_kubernetes_collector: bool = True

    # Default service label when incident metadata lacks service
    default_service: str = "sample-app"


@lru_cache
def get_settings() -> Settings:
    return Settings()
