"""
app/api/v1/endpoints/session.py
─────────────────────────────────
Session management endpoints for multi-turn chat history.
History is stored in Redis as a JSON list keyed by session_id.
"""
from __future__ import annotations

import json
import uuid
from typing import List

from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel

from app.api.deps import AuthDep, RedisDep
from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/sessions", tags=["sessions"])

_SESSION_NS = "session"
_MAX_HISTORY_TURNS = 50


def _session_key(session_id: str) -> str:
    return f"rag:session:{session_id}"


# ── Schemas ───────────────────────────────────────────────────────────────────

class SessionCreateResponse(BaseModel):
    session_id: str


class TurnMessage(BaseModel):
    role: str  # "user" | "assistant"
    content: str


class SessionHistoryResponse(BaseModel):
    session_id: str
    messages: List[TurnMessage]


# ── Helpers ───────────────────────────────────────────────────────────────────

async def get_session_history(redis, session_id: str) -> List[dict]:
    raw = await redis.get(_session_key(session_id))
    if raw is None:
        return []
    return json.loads(raw)


async def append_turn(redis, session_id: str, role: str, content: str) -> None:
    settings = get_settings()
    history = await get_session_history(redis, session_id)
    history.append({"role": role, "content": content})
    # Keep only the most recent N turns
    history = history[-(_MAX_HISTORY_TURNS * 2):]
    await redis.set(
        _session_key(session_id),
        json.dumps(history),
        ex=settings.cache_ttl_seconds,
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post(
    "",
    response_model=SessionCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new chat session",
)
async def create_session(_: AuthDep, redis: RedisDep) -> SessionCreateResponse:
    session_id = str(uuid.uuid4())
    settings = get_settings()
    await redis.set(_session_key(session_id), json.dumps([]), ex=settings.cache_ttl_seconds)
    logger.info("session.created", session_id=session_id)
    return SessionCreateResponse(session_id=session_id)


@router.get(
    "/{session_id}",
    response_model=SessionHistoryResponse,
    summary="Retrieve the message history of a session",
)
async def get_session(_: AuthDep, redis: RedisDep, session_id: str) -> SessionHistoryResponse:
    history = await get_session_history(redis, session_id)
    if not history and not await redis.exists(_session_key(session_id)):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found.",
        )
    return SessionHistoryResponse(
        session_id=session_id,
        messages=[TurnMessage(**m) for m in history],
    )


@router.delete(
    "/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Delete a session and its history",
)
async def delete_session(_: AuthDep, redis: RedisDep, session_id: str) -> Response:
    deleted = await redis.delete(_session_key(session_id))
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found.",
        )
    logger.info("session.deleted", session_id=session_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
