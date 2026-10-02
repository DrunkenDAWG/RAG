"""
app/api/v1/router.py
─────────────────────
Aggregates all v1 endpoint routers under the /api/v1 prefix.
"""
from fastapi import APIRouter

from app.api.v1.endpoints import chat, documents, session

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(chat.router)
api_router.include_router(documents.router)
api_router.include_router(session.router)
