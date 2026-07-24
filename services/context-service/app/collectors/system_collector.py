"""System / host / Docker container collector for local Compose environments."""

from __future__ import annotations

import os
import socket
from datetime import datetime, timezone
from typing import Any

import httpx

from app.collectors.base import BaseCollector, CollectionRequest


class SystemCollector(BaseCollector):
    name = "system"

    async def collect(self, request: CollectionRequest) -> dict[str, Any]:
        collected_at = datetime.now(timezone.utc).isoformat()
        host = self._host_stats()
        docker_info = await self._docker_status()
        prom_process = await self._prometheus_process_hints(request.service)

        return {
            "available": True,
            "collected_at": collected_at,
            "host": host,
            "docker": docker_info,
            "process_hints": prom_process,
            "open_ports_sample": self._local_ports_sample(),
            "summary": {
                "containers_running": docker_info.get("running_count", 0),
                "containers_unhealthy": docker_info.get("unhealthy_count", 0),
                "hostname": host.get("hostname"),
            },
        }

    def _host_stats(self) -> dict[str, Any]:
        hostname = socket.gethostname()
        loadavg = None
        try:
            loadavg = list(os.getloadavg())
        except OSError:
            loadavg = None

        mem = {}
        try:
            # Linux /proc; on macOS Docker VM this still works inside container
            if os.path.exists("/proc/meminfo"):
                with open("/proc/meminfo", encoding="utf-8") as f:
                    data = f.read()
                kv = {}
                for line in data.splitlines():
                    if ":" in line:
                        k, v = line.split(":", 1)
                        kv[k.strip()] = v.strip()
                mem = {
                    "mem_total": kv.get("MemTotal"),
                    "mem_available": kv.get("MemAvailable"),
                    "mem_free": kv.get("MemFree"),
                }
        except OSError:
            mem = {}

        disk = {}
        try:
            st = os.statvfs("/")
            disk = {
                "total_bytes": st.f_frsize * st.f_blocks,
                "free_bytes": st.f_frsize * st.f_bavail,
                "used_bytes": st.f_frsize * (st.f_blocks - st.f_bavail),
            }
        except OSError:
            disk = {}

        cpu_count = os.cpu_count()
        return {
            "hostname": hostname,
            "cpu_count": cpu_count,
            "loadavg": loadavg,
            "memory": mem,
            "disk": disk,
            "pid": os.getpid(),
        }

    async def _docker_status(self) -> dict[str, Any]:
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
        items = []
        unhealthy = 0
        running = 0
        for c in containers:
            labels = c.labels or {}
            if labels.get("com.docker.compose.project") not in {None, project}:
                if labels.get("com.docker.compose.project") != project:
                    continue
            health = None
            state = c.attrs.get("State", {})
            if "Health" in state:
                health = state["Health"].get("Status")
                if health and health != "healthy":
                    unhealthy += 1
            if c.status == "running":
                running += 1
            restart_count = state.get("RestartCount", 0)
            items.append(
                {
                    "name": c.name,
                    "service": labels.get("com.docker.compose.service"),
                    "status": c.status,
                    "health": health,
                    "restart_count": restart_count,
                    "image": c.image.tags[0] if c.image.tags else None,
                    "started_at": state.get("StartedAt"),
                }
            )
        return {
            "available": True,
            "running_count": running,
            "unhealthy_count": unhealthy,
            "containers": items,
        }

    async def _prometheus_process_hints(self, service: str | None) -> dict[str, Any]:
        service = service or self.settings.default_service
        try:
            async with httpx.AsyncClient(
                base_url=self.settings.prometheus_url.rstrip("/"),
                timeout=min(10.0, self.settings.collector_timeout_seconds),
            ) as client:
                queries = {
                    "process_resident_memory_bytes": f'process_resident_memory_bytes{{job="{service}"}}',
                    "process_cpu_seconds_total": f'rate(process_cpu_seconds_total{{job="{service}"}}[5m])',
                    "open_fds": f'process_open_fds{{job="{service}"}}',
                }
                out: dict[str, Any] = {}
                for name, q in queries.items():
                    resp = await client.get("/api/v1/query", params={"query": q})
                    if resp.status_code != 200:
                        continue
                    result = resp.json().get("data", {}).get("result", [])
                    if result:
                        out[name] = float(result[0]["value"][1])
                return out
        except Exception as exc:  # noqa: BLE001
            return {"error": str(exc)}

    def _local_ports_sample(self) -> list[int]:
        # Best-effort: known platform ports (not a full scan)
        return [3000, 3100, 5432, 8000, 8020, 8080, 9090, 9093]
