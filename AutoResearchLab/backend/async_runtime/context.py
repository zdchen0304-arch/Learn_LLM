"""Redis-backed, TTL-bounded research context snapshots and idempotency keys."""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any

from .types import ContextReference


class RuntimeUnavailableError(RuntimeError):
    """Raised instead of silently accepting work without configured infrastructure."""


class InMemoryContextStore:
    """Deterministic local/test store implementing the Redis contract."""

    backend_name = "memory"

    def __init__(self) -> None:
        self._values: dict[str, tuple[float, dict[str, Any]]] = {}
        self._idempotency: dict[str, float] = {}
        self._lock = asyncio.Lock()

    async def put(self, ref: ContextReference, value: dict[str, Any], ttl_seconds: int) -> str:
        async with self._lock:
            self._values[ref.key] = (time.monotonic() + ttl_seconds, value)
        return ref.key

    async def get(self, ref: str) -> dict[str, Any] | None:
        async with self._lock:
            item = self._values.get(ref)
            if not item or item[0] <= time.monotonic():
                self._values.pop(ref, None)
                return None
            return item[1]

    async def delete(self, ref: str) -> None:
        async with self._lock:
            self._values.pop(ref, None)

    async def claim_idempotency(self, key: str, ttl_seconds: int) -> bool:
        async with self._lock:
            now = time.monotonic()
            expiry = self._idempotency.get(key, 0)
            if expiry > now:
                return False
            self._idempotency[key] = now + ttl_seconds
            return True

    async def release_idempotency(self, key: str) -> None:
        async with self._lock:
            self._idempotency.pop(key, None)

    async def health(self) -> dict[str, Any]:
        return {"backend": self.backend_name, "ready": True}

    async def close(self) -> None:
        return None


class RedisContextStore:
    """Lazy Redis client.  Importing the API does not require a live Redis server."""

    backend_name = "redis"

    def __init__(self, url: str, *, key_prefix: str = "maars") -> None:
        self._url = url
        self._key_prefix = key_prefix.strip(":")
        self._client = None

    def _key(self, value: str) -> str:
        return f"{self._key_prefix}:{value}"

    async def _get_client(self):
        if self._client is None:
            try:
                import redis.asyncio as redis
            except ImportError as exc:
                raise RuntimeUnavailableError("redis package is not installed; run pip install -r requirements.txt") from exc
            self._client = redis.from_url(self._url, decode_responses=True)
        return self._client

    async def put(self, ref: ContextReference, value: dict[str, Any], ttl_seconds: int) -> str:
        client = await self._get_client()
        await client.set(self._key(ref.key), json.dumps(value, ensure_ascii=False), ex=ttl_seconds)
        return ref.key

    async def get(self, ref: str) -> dict[str, Any] | None:
        client = await self._get_client()
        value = await client.get(self._key(ref))
        return json.loads(value) if value else None

    async def delete(self, ref: str) -> None:
        client = await self._get_client()
        await client.delete(self._key(ref))

    async def claim_idempotency(self, key: str, ttl_seconds: int) -> bool:
        client = await self._get_client()
        return bool(await client.set(self._key(f"idempotency:{key}"), "1", ex=ttl_seconds, nx=True))

    async def release_idempotency(self, key: str) -> None:
        client = await self._get_client()
        await client.delete(self._key(f"idempotency:{key}"))

    async def health(self) -> dict[str, Any]:
        try:
            client = await self._get_client()
            await client.ping()
            return {"backend": self.backend_name, "ready": True}
        except Exception as exc:
            return {"backend": self.backend_name, "ready": False, "error": str(exc)}

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None
