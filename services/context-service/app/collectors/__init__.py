"""Collector package exports."""

from app.collectors.base import BaseCollector, CollectionRequest, CollectorResult
from app.collectors.deployment_collector import DeploymentCollector
from app.collectors.kubernetes_collector import KubernetesCollector
from app.collectors.logs_collector import LogsCollector
from app.collectors.metrics_collector import MetricsCollector
from app.collectors.system_collector import SystemCollector

ALL_COLLECTORS = [
    MetricsCollector,
    LogsCollector,
    KubernetesCollector,
    DeploymentCollector,
    SystemCollector,
]

__all__ = [
    "ALL_COLLECTORS",
    "BaseCollector",
    "CollectionRequest",
    "CollectorResult",
    "DeploymentCollector",
    "KubernetesCollector",
    "LogsCollector",
    "MetricsCollector",
    "SystemCollector",
]
