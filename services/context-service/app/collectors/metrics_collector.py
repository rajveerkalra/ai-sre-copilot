"""Prometheus metrics collector."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx

from app.collectors.base import BaseCollector, CollectionRequest


class MetricsCollector(BaseCollector):
    name = "metrics"

    async def collect(self, request: CollectionRequest) -> dict[str, Any]:
        service = request.service or self.settings.default_service
        async with httpx.AsyncClient(
            base_url=self.settings.prometheus_url.rstrip("/"),
            timeout=self.settings.collector_timeout_seconds,
        ) as client:
            # Ensure Prometheus is reachable
            health = await client.get("/-/ready")
            health.raise_for_status()

            series: dict[str, Any] = {}
            for key, expr in self._queries(service).items():
                series[key] = await self._metric_with_baselines(client, expr)

            targets = await self._scrape_targets(client)

        return {
            "available": True,
            "source": "prometheus",
            "service": service,
            "collected_at": datetime.now(timezone.utc).isoformat(),
            "series": series,
            "targets": targets,
            "summary": self._summarize(series),
        }

    def _queries(self, service: str) -> dict[str, str]:
        # Prefer sample-app / recording rules; fall back to process metrics.
        job = service
        return {
            "request_rate": f'sum(rate(http_requests_total{{job="{job}"}}[5m])) or vector(0)',
            "error_rate": (
                f'job:http_request_error_rate:ratio_rate5m{{service="{service}"}} '
                f'or (sum(rate(http_requests_total{{job="{job}",status_code=~"5.."}}[5m])) '
                f'/ clamp_min(sum(rate(http_requests_total{{job="{job}"}}[5m])), 1e-9)) '
                f"or vector(0)"
            ),
            "latency_p95": (
                f'histogram_quantile(0.95, sum by (le) '
                f'(rate(http_request_duration_seconds_bucket{{job="{job}"}}[5m]))) or vector(0)'
            ),
            "latency_p99": (
                f"job:http_request_latency_p99:seconds or "
                f'histogram_quantile(0.99, sum by (le) '
                f'(rate(http_request_duration_seconds_bucket{{job="{job}"}}[5m]))) or vector(0)'
            ),
            "cpu_usage": (
                f'max(sample_app_cpu_burn_active) or '
                f'avg(rate(process_cpu_seconds_total{{job="{job}"}}[5m])) or vector(0)'
            ),
            "memory_usage_bytes": (
                f"max(sample_app_memory_ballast_bytes) or "
                f'max(process_resident_memory_bytes{{job="{job}"}}) or vector(0)'
            ),
            "container_restarts": (
                f'sum(changes(process_start_time_seconds{{job="{job}"}}[1h])) or vector(0)'
            ),
            "network_receive_bytes": (
                f'sum(rate(container_network_receive_bytes_total{{name=~".*{job}.*"}}[5m])) '
                f"or vector(0)"
            ),
            "disk_usage_bytes": (
                f'max(container_fs_usage_bytes{{name=~".*{job}.*"}}) or vector(0)'
            ),
            "node_pressure": (
                'max(kube_node_status_condition{condition="MemoryPressure",status="true"}) '
                "or vector(0)"
            ),
            "fault_active": f'max(sample_app_fault_active) or vector(0)',
        }

    async def _instant(self, client: httpx.AsyncClient, query: str) -> float | None:
        resp = await client.get("/api/v1/query", params={"query": query})
        resp.raise_for_status()
        payload = resp.json()
        result = payload.get("data", {}).get("result", [])
        if not result:
            return None
        try:
            return float(result[0]["value"][1])
        except (KeyError, IndexError, TypeError, ValueError):
            return None

    async def _range_avg(
        self, client: httpx.AsyncClient, query: str, start: float, end: float
    ) -> float | None:
        # avg_over_time of instant vector via subquery
        wrapped = f"avg_over_time(({query})[{int(end - start)}s:])"
        # Fallback: sample range API and average
        try:
            value = await self._instant(client, wrapped)
            if value is not None:
                return value
        except Exception:  # noqa: BLE001
            pass

        resp = await client.get(
            "/api/v1/query_range",
            params={"query": query, "start": start, "end": end, "step": "60"},
        )
        resp.raise_for_status()
        payload = resp.json()
        result = payload.get("data", {}).get("result", [])
        if not result:
            return None
        values = []
        for pair in result[0].get("values", []):
            try:
                values.append(float(pair[1]))
            except (TypeError, ValueError, IndexError):
                continue
        if not values:
            return None
        return sum(values) / len(values)

    async def _metric_with_baselines(
        self, client: httpx.AsyncClient, query: str
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc).timestamp()
        current = await self._instant(client, query)
        hour_avg = await self._range_avg(client, query, now - 3600, now)
        day_avg = await self._range_avg(client, query, now - 86400, now)
        trend = self._trend(current, hour_avg)
        return {
            "query": query,
            "current": current,
            "previous_hour_avg": hour_avg,
            "previous_day_avg": day_avg,
            "trend": trend,
        }

    def _trend(self, current: float | None, baseline: float | None) -> str:
        if current is None or baseline is None:
            return "unknown"
        if baseline == 0:
            return "up" if current > 0 else "stable"
        delta = (current - baseline) / abs(baseline)
        if delta > 0.15:
            return "up"
        if delta < -0.15:
            return "down"
        return "stable"

    def _summarize(self, series: dict[str, Any]) -> dict[str, Any]:
        anomalies = []
        for name, metric in series.items():
            if metric.get("trend") == "up" and name in {
                "error_rate",
                "latency_p95",
                "latency_p99",
                "cpu_usage",
                "memory_usage_bytes",
            }:
                anomalies.append(name)
        return {
            "anomaly_metrics": anomalies,
            "metric_count": len(series),
        }

    async def _scrape_targets(self, client: httpx.AsyncClient) -> list[dict[str, Any]]:
        resp = await client.get("/api/v1/targets")
        resp.raise_for_status()
        active = resp.json().get("data", {}).get("activeTargets", [])
        return [
            {
                "job": t.get("labels", {}).get("job"),
                "instance": t.get("labels", {}).get("instance"),
                "health": t.get("health"),
            }
            for t in active
        ]
