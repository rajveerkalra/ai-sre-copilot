"""Deployment history collector — K8s ReplicaSets / Compose image metadata."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.collectors.base import BaseCollector, CollectionRequest


class DeploymentCollector(BaseCollector):
    name = "deployment"

    async def collect(self, request: CollectionRequest) -> dict[str, Any]:
        collected_at = datetime.now(timezone.utc).isoformat()
        k8s = await self._from_kubernetes(request)
        compose = await self._from_docker_compose(request)

        history = k8s.get("rollout_history") or compose.get("containers") or []
        deployment_before_incident = self._deployment_before_incident(
            history, request.incident_created_at
        )

        available = bool(k8s.get("available") or compose.get("available"))
        return {
            "available": available,
            "collected_at": collected_at,
            "kubernetes": k8s,
            "compose": compose,
            "recent_images": self._recent_images(k8s, compose),
            "replica_changes": k8s.get("replica_changes", []),
            "rollout_history": history[:50],
            "deployment_before_incident": deployment_before_incident,
            "summary": {
                "had_recent_deployment": deployment_before_incident is not None,
                "image_count": len(self._recent_images(k8s, compose)),
                "source": "kubernetes" if k8s.get("available") else (
                    "docker_compose" if compose.get("available") else "none"
                ),
            },
        }

    async def _from_kubernetes(self, request: CollectionRequest) -> dict[str, Any]:
        if not self.settings.enable_kubernetes_collector:
            return {"available": False, "reason": "disabled"}
        try:
            from kubernetes import client, config
        except ImportError:
            return {"available": False, "reason": "kubernetes_package_missing"}

        try:
            if self.settings.kubeconfig_path:
                config.load_kube_config(config_file=self.settings.kubeconfig_path)
            else:
                try:
                    config.load_incluster_config()
                except Exception:
                    config.load_kube_config()
        except Exception:
            return {"available": False, "reason": "no_kubeconfig"}

        namespace = request.namespace or self.settings.kubernetes_namespace
        apps = client.AppsV1Api()
        deployments = apps.list_namespaced_deployment(namespace).items
        replica_sets = apps.list_namespaced_replica_set(namespace).items

        rollout_history = []
        replica_changes = []
        for rs in replica_sets:
            created = rs.metadata.creation_timestamp
            images = [c.image for c in (rs.spec.template.spec.containers or [])]
            owners = [
                {"kind": o.kind, "name": o.name}
                for o in (rs.metadata.owner_references or [])
            ]
            entry = {
                "name": rs.metadata.name,
                "created_at": created.isoformat() if created else None,
                "replicas": rs.status.replicas or 0,
                "ready_replicas": rs.status.ready_replicas or 0,
                "images": images,
                "revision": (rs.metadata.annotations or {}).get(
                    "deployment.kubernetes.io/revision"
                ),
                "owners": owners,
            }
            rollout_history.append(entry)
            replica_changes.append(
                {
                    "name": rs.metadata.name,
                    "replicas": rs.status.replicas or 0,
                    "created_at": entry["created_at"],
                }
            )

        rollout_history.sort(key=lambda x: x.get("created_at") or "", reverse=True)

        return {
            "available": True,
            "namespace": namespace,
            "deployments": [
                {
                    "name": d.metadata.name,
                    "replicas": d.spec.replicas,
                    "images": [c.image for c in (d.spec.template.spec.containers or [])],
                    "updated_at": (
                        d.status.conditions[-1].last_update_time.isoformat()
                        if d.status.conditions
                        else None
                    ),
                }
                for d in deployments
            ],
            "rollout_history": rollout_history,
            "replica_changes": replica_changes,
            "rollback_candidates": [
                h for h in rollout_history if h.get("revision") and h.get("replicas", 0) == 0
            ][:10],
        }

    async def _from_docker_compose(self, request: CollectionRequest) -> dict[str, Any]:
        if not self.settings.enable_docker_collector:
            return {"available": False, "reason": "disabled"}
        try:
            import docker
        except ImportError:
            return {"available": False, "reason": "docker_package_missing"}

        try:
            client = docker.DockerClient(base_url=self.settings.docker_socket)
            containers = client.containers.list(all=True)
        except Exception as exc:  # noqa: BLE001
            return {"available": False, "reason": str(exc)}

        project = "ai-sre-copilot"
        entries = []
        for c in containers:
            labels = c.labels or {}
            if labels.get("com.docker.compose.project") not in {project, None}:
                # still include labeled project containers; skip unrelated
                if labels.get("com.docker.compose.project") and labels.get(
                    "com.docker.compose.project"
                ) != project:
                    continue
            created = c.attrs.get("Created")
            entries.append(
                {
                    "name": c.name,
                    "image": (
                        c.image.tags[0]
                        if c.image.tags
                        else c.attrs.get("Config", {}).get("Image")
                    ),
                    "status": c.status,
                    "created_at": created,
                    "service": labels.get("com.docker.compose.service"),
                    "labels": {
                        k: v
                        for k, v in labels.items()
                        if k.startswith("com.docker.compose")
                        or k.startswith("ai-sre-copilot")
                    },
                }
            )
        return {"available": True, "containers": entries}

    def _recent_images(
        self, k8s: dict[str, Any], compose: dict[str, Any]
    ) -> list[str]:
        images: list[str] = []
        for d in k8s.get("deployments") or []:
            images.extend(d.get("images") or [])
        for c in compose.get("containers") or []:
            if c.get("image"):
                images.append(c["image"])
        # unique preserve order
        seen: set[str] = set()
        out = []
        for img in images:
            if img not in seen:
                seen.add(img)
                out.append(img)
        return out

    def _deployment_before_incident(
        self, history: list[dict[str, Any]], incident_created_at: str | None
    ) -> dict[str, Any] | None:
        if not incident_created_at or not history:
            # Still surface most recent change
            return history[0] if history else None
        try:
            incident_ts = datetime.fromisoformat(
                incident_created_at.replace("Z", "+00:00")
            )
        except ValueError:
            return history[0] if history else None

        prior = []
        for entry in history:
            created = entry.get("created_at")
            if not created:
                continue
            try:
                ts = datetime.fromisoformat(str(created).replace("Z", "+00:00"))
            except ValueError:
                continue
            if ts <= incident_ts:
                prior.append((ts, entry))
        if not prior:
            return None
        prior.sort(key=lambda x: x[0], reverse=True)
        chosen = prior[0][1]
        return {**chosen, "preceded_incident": True}
