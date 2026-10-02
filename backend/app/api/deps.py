"""
app/api/deps.py
────────────────
FastAPI dependency-injection providers shared across all route handlers.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header, HTTPException, status

from app.core.config import Settings, get_settings
from app.core.redis import get_redis_client
from redis.asyncio import Redis


# ── Settings ──────────────────────────────────────────────────────────────────

def settings_dep() -> Settings:
    return get_settings()


SettingsDep = Annotated[Settings, Depends(settings_dep)]


# ── Redis ─────────────────────────────────────────────────────────────────────

def redis_dep() -> Redis:
    return get_redis_client()


RedisDep = Annotated[Redis, Depends(redis_dep)]


# ── Optional API-key guard (for future auth layer) ────────────────────────────

async def verify_api_key(
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
    settings: Settings = Depends(settings_dep),
) -> None:
    """
    Placeholder auth guard. In production, compare against a stored secret.
    Currently a no-op so all requests are allowed.
    """
    # TODO: replace with real secret comparison when auth is enabled
    pass


AuthDep = Annotated[None, Depends(verify_api_key)]
