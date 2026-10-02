"""
app/api/deps.py
────────────────
FastAPI dependency-injection providers shared across all route handlers.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header

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
    _x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
    _settings: Settings = Depends(settings_dep),
) -> None:
    """
    Placeholder auth guard. In production, compare against a stored secret.
    Currently a no-op so all requests are allowed.
    """
    pass


AuthDep = Annotated[None, Depends(verify_api_key)]
