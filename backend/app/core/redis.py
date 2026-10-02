"""
app/core/redis.py
──────────────────
Async Redis client lifecycle management.
Exposes a dependency-injectable client and a simple cache helper.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Optional

from redis.asyncio import Redis, from_url as redis_from_url
from redis.exceptions import RedisError

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Module-level singleton — initialised by lifespan
_redis_client: Optional[Redis] = None


async def init_redis() -> None:
    """Create the global async Redis client. Called from app lifespan."""
    global _redis_client
    settings = get_settings()
    _redis_client = redis_from_url(
        settings.redis_url,
        encoding="utf-8",
        decode_responses=True,
        socket_connect_timeout=5,
        socket_timeout=5,
        retry_on_timeout=True,
        health_check_interval=30,
    )
    # Verify connectivity on startup
    await _redis_client.ping()
    logger.info("redis.connected", url=settings.redis_url)


async def close_redis() -> None:
    """Gracefully close the Redis connection pool."""
    global _redis_client
    if _redis_client is not None:
        if hasattr(_redis_client, "aclose"):
            await _redis_client.aclose()
        elif hasattr(_redis_client, "close"):
            await _redis_client.close()
        _redis_client = None
        logger.info("redis.closed")


def get_redis_client() -> Redis:
    """Return the live Redis client (raises if not initialised)."""
    if _redis_client is None:
        raise RuntimeError("Redis client is not initialised. Call init_redis() first.")
    return _redis_client


# ── Cache helpers ─────────────────────────────────────────────────────────────

def _make_cache_key(namespace: str, *parts: str) -> str:
    payload = ":".join(parts)
    digest = hashlib.sha256(payload.encode()).hexdigest()[:16]
    return f"rag:{namespace}:{digest}"


async def cache_get(namespace: str, *key_parts: str) -> Optional[Any]:
    client = get_redis_client()
    key = _make_cache_key(namespace, *key_parts)
    try:
        raw = await client.get(key)
        if raw is not None:
            logger.debug("cache.hit", key=key)
            return json.loads(raw)
        logger.debug("cache.miss", key=key)
        return None
    except RedisError as exc:
        logger.warning("cache.get_error", key=key, error=str(exc))
        return None


async def cache_set(
    namespace: str,
    value: Any,
    *key_parts: str,
    ttl: Optional[int] = None,
) -> None:
    settings = get_settings()
    client = get_redis_client()
    key = _make_cache_key(namespace, *key_parts)
    ttl = ttl if ttl is not None else settings.cache_ttl_seconds
    try:
        await client.set(key, json.dumps(value, default=str), ex=ttl)
        logger.debug("cache.set", key=key, ttl=ttl)
    except RedisError as exc:
        logger.warning("cache.set_error", key=key, error=str(exc))


async def cache_delete(namespace: str, *key_parts: str) -> None:
    client = get_redis_client()
    key = _make_cache_key(namespace, *key_parts)
    try:
        await client.delete(key)
        logger.debug("cache.delete", key=key)
    except RedisError as exc:
        logger.warning("cache.delete_error", key=key, error=str(exc))
