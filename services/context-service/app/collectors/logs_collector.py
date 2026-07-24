"""Loki logs collector."""

from __future__ import annotations

import re
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from app.collectors.base import BaseCollector, CollectionRequest

ERROR_PATTERNS = [
    (re.compile(r"oomkilled|out of memory", re.I), "oomkilled"),
    (re.compile(r"timeout|timed out|deadline exceeded", re.I), "timeout"),
    (re.compile(r"traceback|stack trace|exception", re.I), "exception"),
    (re.compile(r"connection (refused|reset|error)|connect.*fail", re.I), "connection_failure"),
    (re.compile(r"database|postgres|sqlalchemy|operationalerror", re.I), "database_error"),
    (re.compile(r"unauthorized|forbidden|authentication|authn|authz", re.I), "auth_failure"),
    (re.compile(r"\berror\b|\"level\"\s*:\s*\"error\"", re.I), "error"),
    (re.compile(r"\bwarn(ing)?\b|\"level\"\s*:\s*\"warn", re.I), "warning"),
]


class LogsCollector(BaseCollector):
    name = "logs"

    async def collect(self, request: CollectionRequest) -> dict[str, Any]:
        service = request.service or self.settings.default_service
        limit = self.settings.logs_limit
        lookback = self.settings.logs_lookback_minutes
        end = datetime.now(timezone.utc)
        start = end - timedelta(minutes=lookback)

        async with httpx.AsyncClient(
            base_url=self.settings.loki_url.rstrip("/"),
            timeout=self.settings.collector_timeout_seconds,
        ) as client:
            ready = await client.get("/ready")
            ready.raise_for_status()

            lines = await self._query_range(
                client,
                query=f'{{service="{service}"}}',
                start=start,
                end=end,
                limit=limit,
            )
            # Also pull explicit error streams if JSON labels exist
            error_lines = await self._query_range(
                client,
                query=f'{{service="{service}"}} |= "error"',
                start=start,
                end=end,
                limit=min(200, limit),
            )

        classified = self._classify(lines)
        top_errors = self._top_messages(
            [ln for ln in lines if classified["categories"].get(ln["id"], "") in {"error", "exception", "timeout", "oomkilled", "database_error", "connection_failure", "auth_failure"}]
            or error_lines
        )
        timeline = self._timeline(lines)

        return {
            "available": True,
            "source": "loki",
            "service": service,
            "lookback_minutes": lookback,
            "collected_at": end.isoformat(),
            "total_lines": len(lines),
            "lines": lines[-limit:],
            "error_lines": error_lines[:200],
            "categories": classified["counts"],
            "top_error_messages": top_errors,
            "timeline": timeline,
            "summary": {
                "error_count": classified["counts"].get("error", 0)
                + classified["counts"].get("exception", 0),
                "warning_count": classified["counts"].get("warning", 0),
                "timeout_count": classified["counts"].get("timeout", 0),
                "oomkilled_count": classified["counts"].get("oomkilled", 0),
                "has_stack_traces": classified["counts"].get("exception", 0) > 0,
            },
        }

    async def _query_range(
        self,
        client: httpx.AsyncClient,
        *,
        query: str,
        start: datetime,
        end: datetime,
        limit: int,
    ) -> list[dict[str, Any]]:
        resp = await client.get(
            "/loki/api/v1/query_range",
            params={
                "query": query,
                "start": _to_ns(start),
                "end": _to_ns(end),
                "limit": str(limit),
                "direction": "backward",
            },
        )
        resp.raise_for_status()
        payload = resp.json()
        results = payload.get("data", {}).get("result", [])
        lines: list[dict[str, Any]] = []
        idx = 0
        for stream in results:
            labels = stream.get("stream", {})
            for ts, line in stream.get("values", []):
                lines.append(
                    {
                        "id": f"log-{idx}",
                        "timestamp": _ns_to_iso(ts),
                        "line": line,
                        "labels": labels,
                    }
                )
                idx += 1
        # chronological
        lines.sort(key=lambda x: x["timestamp"])
        return lines[-limit:]

    def _classify(self, lines: list[dict[str, Any]]) -> dict[str, Any]:
        counts: Counter[str] = Counter()
        categories: dict[str, str] = {}
        for ln in lines:
            text = ln.get("line", "")
            matched = "info"
            for pattern, name in ERROR_PATTERNS:
                if pattern.search(text):
                    matched = name
                    break
            categories[ln["id"]] = matched
            counts[matched] += 1
        return {"counts": dict(counts), "categories": categories}

    def _top_messages(self, lines: list[dict[str, Any]], n: int = 10) -> list[dict[str, Any]]:
        counter: Counter[str] = Counter()
        for ln in lines:
            msg = (ln.get("line") or "")[:240]
            counter[msg] += 1
        return [
            {"message": msg, "count": count}
            for msg, count in counter.most_common(n)
        ]

    def _timeline(self, lines: list[dict[str, Any]], buckets: int = 12) -> list[dict[str, Any]]:
        if not lines:
            return []
        # Minute buckets of error-ish lines
        counter: Counter[str] = Counter()
        for ln in lines:
            ts = ln.get("timestamp", "")[:16]  # YYYY-MM-DDTHH:MM
            text = ln.get("line", "").lower()
            if any(k in text for k in ("error", "exception", "timeout", "fail", "oom")):
                counter[ts] += 1
        return [{"minute": k, "error_like_count": v} for k, v in sorted(counter.items())][-buckets:]


def _to_ns(dt: datetime) -> str:
    return str(int(dt.timestamp() * 1_000_000_000))


def _ns_to_iso(ts: str) -> str:
    try:
        seconds = int(ts) / 1_000_000_000
        return datetime.fromtimestamp(seconds, tz=timezone.utc).isoformat()
    except (TypeError, ValueError):
        return str(ts)
