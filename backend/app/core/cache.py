"""
app/core/cache.py
──────────────────
Phase 3 — Corpus-version-aware Redis smart caching.

Cache key schema:
    cache:{session_id}:v{corpus_version}:{sha256(rewritten_query)[:16]}

Why corpus_version in the key?
    When the user uploads a new document, increment_corpus_version() bumps
    the version stored in Redis. All subsequent cache lookups will hit a NEW
    key, making old (now stale) answers invisible — zero explicit eviction
    needed. Old keys expire naturally via their 1-hour TTL.

Public surface:
    get_cached_response(session_id, corpus_version, rewritten_query) -> str | None
    set_cached_response(session_id, corpus_version, rewritten_query, answer, sources)
    increment_corpus_version(session_id) -> int
    get_corpus_version(session_id) -> int
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List, Optional

from redis.exceptions import RedisError

from app.core.logging import get_logger
from app.core.redis import get_redis_client

logger = get_logger(__name__)

# ── Key constants ─────────────────────────────────────────────────────────────
_CACHE_TTL_SECONDS: int = 3600          # 1 hour
_VERSION_TTL_SECONDS: int = 86_400 * 7  # keep version key alive for 7 days
_VERSION_KEY_PREFIX: str = "rag:corpus_version"
_CACHE_KEY_PREFIX: str = "rag:cache"


# ── Key builders ──────────────────────────────────────────────────────────────

def _version_key(session_id: str) -> str:
    return f"{_VERSION_KEY_PREFIX}:{session_id}"


def _query_fingerprint(rewritten_query: str) -> str:
    """16-hex-char SHA-256 prefix of the lowercased, stripped query."""
    normalised = rewritten_query.strip().lower()
    return hashlib.sha256(normalised.encode()).hexdigest()[:16]


def _cache_key(session_id: str, corpus_version: int, rewritten_query: str) -> str:
    """
    Canonical cache key:
        rag:cache:{session_id}:v{corpus_version}:{sha256(query)[:16]}
    """
    fingerprint = _query_fingerprint(rewritten_query)
    return f"{_CACHE_KEY_PREFIX}:{session_id}:v{corpus_version}:{fingerprint}"


# ── Corpus version management ─────────────────────────────────────────────────

async def get_corpus_version(session_id: str) -> int:
    """
    Return the current corpus version for *session_id*.
    Returns 0 if no documents have been ingested yet.
    """
    client = get_redis_client()
    try:
        raw = await client.get(_version_key(session_id))
        return int(raw) if raw is not None else 0
    except (RedisError, ValueError) as exc:
        logger.warning("cache.version_get_error", session_id=session_id, error=str(exc))
        return 0


async def increment_corpus_version(session_id: str) -> int:
    """
    Atomically increment the corpus version for *session_id*.

    Called by the ingestion layer every time a new document is successfully
    ingested. The increment makes all previously cached answers for this
    session invisible (their keys now reference an old version), achieving
    automatic cache invalidation without explicit key scanning.

    Returns the new version number.
    """
    client = get_redis_client()
    key = _version_key(session_id)
    try:
        new_version: int = await client.incr(key)
        # Refresh TTL so active sessions never lose their version counter
        await client.expire(key, _VERSION_TTL_SECONDS)
        logger.info(
            "cache.corpus_version_incremented",
            session_id=session_id,
            new_version=new_version,
        )
        return new_version
    except RedisError as exc:
        logger.warning(
            "cache.version_increment_error",
            session_id=session_id,
            error=str(exc),
        )
        return 0


# ── Response caching ──────────────────────────────────────────────────────────

async def get_cached_response(
    session_id: str,
    corpus_version: int,
    rewritten_query: str,
) -> Optional[Dict[str, Any]]:
    """
    Look up a cached RAG response.

    Returns a dict {"answer": str, "sources": list} on a hit, or None on
    a miss. Redis errors are silently swallowed — the pipeline continues
    without caching rather than failing the request.
    """
    client = get_redis_client()
    key = _cache_key(session_id, corpus_version, rewritten_query)
    try:
        raw = await client.get(key)
        if raw is None:
            logger.debug("cache.miss", key=key)
            return None
        logger.info(
            "cache.hit",
            session_id=session_id,
            corpus_version=corpus_version,
            key=key,
        )
        return json.loads(raw)
    except (RedisError, json.JSONDecodeError) as exc:
        logger.warning("cache.get_error", key=key, error=str(exc))
        return None


async def set_cached_response(
    session_id: str,
    corpus_version: int,
    rewritten_query: str,
    answer: str,
    sources: List[Dict],
    ttl: int = _CACHE_TTL_SECONDS,
) -> None:
    """
    Store a completed RAG answer in Redis with a 1-hour TTL.

    The payload stored is {"answer": str, "sources": list[dict]}.
    Redis errors are silently swallowed.
    """
    client = get_redis_client()
    key = _cache_key(session_id, corpus_version, rewritten_query)
    payload = json.dumps({"answer": answer, "sources": sources}, ensure_ascii=False)
    try:
        await client.set(key, payload, ex=ttl)
        logger.debug(
            "cache.set",
            session_id=session_id,
            corpus_version=corpus_version,
            key=key,
            ttl=ttl,
        )
    except RedisError as exc:
        logger.warning("cache.set_error", key=key, error=str(exc))
