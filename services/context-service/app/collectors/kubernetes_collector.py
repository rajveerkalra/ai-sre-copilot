"""Kubernetes collector — Kind / kubeconfig; degrades gracefully when unavailable."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.collectors.base import BaseCollector, CollectionRequest


class KubernetesCollector(BaseCollector):
    name = "kubernetes"

    async def collect(self, request: CollectionRequest) -> dict[str, Any]:
        if not self.settings.enable_kubernetes_collector:
            return {
                "available": False,
                "reason": "disabled",
                "collected_at": datetime.now(timezone.utc).isoformat(),
            }

        try:
            from kubernetes import client, config
        except ImportError as exc:
            raise RuntimeError("kubernetes package not installed") from exc

        loaded = self._load_config(config)
        if not loaded:
            return {
                "available": False,
                "reason": "no_kubeconfig",
                "hint": "Mount a kubeconfig or run against Kind; collector is Kind/EKS-ready.",
                "collected_at": datetime.now(timezone.utc).isoformat(),
                "pods": [],
                "deployments": [],
                "events": [],
                "nodes": [],
                "issues": [],
            }

        namespace = request.namespace or self.settings.kubernetes_namespace
        v1 = client.CoreV1Api()
        apps = client.AppsV1Api()

        pods = self._list_pods(v1, namespace)
        deployments = self._list_deployments(apps, namespace)
        replica_sets = self._list_replica_sets(apps, namespace)
        events = self._list_events(v1, namespace)
        nodes = self._list_nodes(v1)
        namespaces = self._list_namespaces(v1)
        issues = self._detect_issues(pods, events)

        return {
            "available": True,
            "source": "kubernetes",
            "namespace": namespace,
            "collected_at": datetime.now(timezone.utc).isoformat(),
            "pods": pods,
            "deployments": deployments,
            "replica_sets": replica_sets,
            "events": events[:100],
            "nodes": nodes,
            "namespaces": namespaces,
            "issues": issues,
            "summary": {
                "pod_count": len(pods),
                "deployment_count": len(deployments),
                "issue_count": len(issues),
                "crashloop_count": sum(
                    1 for i in issues if i.get("type") == "CrashLoopBackOff"
                ),
                "oomkilled_count": sum(
                    1 for i in issues if i.get("type") == "OOMKilled"
                ),
            },
        }

    def _load_config(self, config_mod: Any) -> bool:
        path = self.settings.kubeconfig_path
        try:
            if path:
                config_mod.load_kube_config(config_file=path)
                return True
            config_mod.load_incluster_config()
            return True
        except Exception:
            try:
                config_mod.load_kube_config()
                return True
            except Exception:
                return False

    def _list_pods(self, v1: Any, namespace: str) -> list[dict[str, Any]]:
        items = v1.list_namespaced_pod(namespace).items
        result = []
        for pod in items:
            containers = []
            for cs in pod.status.container_statuses or []:
                state = "unknown"
                reason = None
                if cs.state.running:
                    state = "running"
                elif cs.state.waiting:
                    state = "waiting"
                    reason = cs.state.waiting.reason
                elif cs.state.terminated:
                    state = "terminated"
                    reason = cs.state.terminated.reason
                containers.append(
                    {
                        "name": cs.name,
                        "ready": cs.ready,
                        "restart_count": cs.restart_count,
                        "state": state,
                        "reason": reason,
                        "image": cs.image,
                    }
                )
            result.append(
                {
                    "name": pod.metadata.name,
                    "namespace": pod.metadata.namespace,
                    "phase": pod.status.phase,
                    "node": pod.spec.node_name,
                    "labels": pod.metadata.labels or {},
                    "containers": containers,
                    "restarts": sum(c["restart_count"] for c in containers),
                }
            )
        return result

    def _list_deployments(self, apps: Any, namespace: str) -> list[dict[str, Any]]:
        items = apps.list_namespaced_deployment(namespace).items
        return [
            {
                "name": d.metadata.name,
                "replicas": d.spec.replicas,
                "ready_replicas": d.status.ready_replicas or 0,
                "updated_replicas": d.status.updated_replicas or 0,
                "unavailable_replicas": d.status.unavailable_replicas or 0,
                "images": [
                    c.image for c in (d.spec.template.spec.containers or [])
                ],
                "generation": d.metadata.generation,
                "observed_generation": d.status.observed_generation,
            }
            for d in items
        ]

    def _list_replica_sets(self, apps: Any, namespace: str) -> list[dict[str, Any]]:
        items = apps.list_namespaced_replica_set(namespace).items
        return [
            {
                "name": rs.metadata.name,
                "replicas": rs.status.replicas or 0,
                "ready_replicas": rs.status.ready_replicas or 0,
                "owner": [
                    {"kind": o.kind, "name": o.name}
                    for o in (rs.metadata.owner_references or [])
                ],
            }
            for rs in items
        ]

    def _list_events(self, v1: Any, namespace: str) -> list[dict[str, Any]]:
        items = v1.list_namespaced_event(namespace).items
        events = []
        for ev in items:
            events.append(
                {
                    "type": ev.type,
                    "reason": ev.reason,
                    "message": ev.message,
                    "involved_object": {
                        "kind": ev.involved_object.kind,
                        "name": ev.involved_object.name,
                    },
                    "count": ev.count,
                    "last_timestamp": (
                        ev.last_timestamp.isoformat() if ev.last_timestamp else None
                    ),
                }
            )
        events.sort(key=lambda e: e.get("last_timestamp") or "", reverse=True)
        return events

    def _list_nodes(self, v1: Any) -> list[dict[str, Any]]:
        items = v1.list_node().items
        nodes = []
        for node in items:
            conditions = {
                c.type: c.status for c in (node.status.conditions or [])
            }
            nodes.append(
                {
                    "name": node.metadata.name,
                    "ready": conditions.get("Ready"),
                    "memory_pressure": conditions.get("MemoryPressure"),
                    "disk_pressure": conditions.get("DiskPressure"),
                    "pid_pressure": conditions.get("PIDPressure"),
                    "unschedulable": bool(node.spec.unschedulable),
                }
            )
        return nodes

    def _list_namespaces(self, v1: Any) -> list[str]:
        return [ns.metadata.name for ns in v1.list_namespace().items]

    def _detect_issues(
        self, pods: list[dict[str, Any]], events: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        issues: list[dict[str, Any]] = []
        for pod in pods:
            if pod.get("phase") == "Pending":
                issues.append(
                    {
                        "type": "Pending",
                        "pod": pod["name"],
                        "detail": "Pod is pending",
                    }
                )
            for c in pod.get("containers", []):
                reason = c.get("reason") or ""
                if reason == "CrashLoopBackOff":
                    issues.append(
                        {
                            "type": "CrashLoopBackOff",
                            "pod": pod["name"],
                            "container": c["name"],
                            "restarts": c["restart_count"],
                        }
                    )
                if reason == "OOMKilled":
                    issues.append(
                        {
                            "type": "OOMKilled",
                            "pod": pod["name"],
                            "container": c["name"],
                        }
                    )
                if reason == "ImagePullBackOff" or reason == "ErrImagePull":
                    issues.append(
                        {
                            "type": "ImagePullBackOff",
                            "pod": pod["name"],
                            "container": c["name"],
                        }
                    )
                if c.get("restart_count", 0) >= 3:
                    issues.append(
                        {
                            "type": "HighRestarts",
                            "pod": pod["name"],
                            "container": c["name"],
                            "restarts": c["restart_count"],
                        }
                    )
        for ev in events:
            if ev.get("reason") in {"FailedScheduling", "FailedMount", "Unhealthy"}:
                issues.append(
                    {
                        "type": ev.get("reason"),
                        "message": ev.get("message"),
                        "object": ev.get("involved_object"),
                    }
                )
        return issues
