"""Redis-backed cache with hit/miss accounting hooks."""

from __future__ import annotations

import hashlib
import json
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


def cache_key(*parts: str, prefix: str = "sre") -> str:
    raw = ":".join(parts)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]
    return f"{prefix}:{digest}:{parts[0] if parts else 'k'}"


class RedisCache:
    """Thin async Redis JSON cache. Soft-fails when Redis is unavailable."""

    def __init__(
        self,
        redis_url: str,
        *,
        enabled: bool = True,
        default_ttl_seconds: int = 300,
        on_hit: Any | None = None,
        on_miss: Any | None = None,
    ) -> None:
        self.redis_url = redis_url
        self.enabled = enabled
        self.default_ttl_seconds = default_ttl_seconds
        self._on_hit = on_hit
        self._on_miss = on_miss
        self._client = None

    async def connect(self) -> None:
        if not self.enabled:
            return
        try:
            from redis import asyncio as aioredis

            self._client = aioredis.from_url(
                self.redis_url, encoding="utf-8", decode_responses=True
            )
            await self._client.ping()
            logger.info("redis_connected", url=self.redis_url)
        except Exception as exc:  # noqa: BLE001
            logger.warning("redis_unavailable", error=str(exc))
            self._client = None

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    @property
    def available(self) -> bool:
        return self.enabled and self._client is not None

    async def get_json(self, key: str) -> Any | None:
        if not self.available:
            if self._on_miss:
                self._on_miss("unavailable")
            return None
        try:
            raw = await self._client.get(key)
            if raw is None:
                if self._on_miss:
                    self._on_miss("miss")
                return None
            if self._on_hit:
                self._on_hit()
            return json.loads(raw)
        except Exception as exc:  # noqa: BLE001
            logger.warning("cache_get_failed", key=key, error=str(exc))
            if self._on_miss:
                self._on_miss("error")
            return None

    async def set_json(self, key: str, value: Any, *, ttl_seconds: int | None = None) -> bool:
        if not self.available:
            return False
        ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl_seconds
        try:
            await self._client.set(key, json.dumps(value), ex=ttl)
            return True
        except Exception as exc:  # noqa: BLE001
            logger.warning("cache_set_failed", key=key, error=str(exc))
            return False

    async def delete(self, key: str) -> None:
        if not self.available:
            return
        try:
            await self._client.delete(key)
        except Exception:  # noqa: BLE001
            pass
