"""
app/main.py
────────────
FastAPI application factory.

Startup sequence (lifespan):
  1. Configure structured logging
  2. Connect Redis
  3. Initialise ChromaDB + embedding model

Includes:
  - CORS middleware
  - /health liveness probe
  - /api/v1 router
  - Global exception handler
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.core.redis import close_redis, init_redis
from app.services.ingestion import init_chroma
from app.services.reranker import warm_up_reranker


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # ── Startup ───────────────────────────────────────────────────────────────
    configure_logging()
    logger = get_logger("app.lifespan")

    logger.info("app.starting")
    await init_redis()
    init_chroma()
    await run_in_threadpool(warm_up_reranker)  # pre-load cross-encoder off the event loop
    logger.info("app.ready")

    yield

    # ── Shutdown ──────────────────────────────────────────────────────────────
    logger.info("app.shutting_down")
    await close_redis()
    logger.info("app.shutdown_complete")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="LocalHost RAG",
        description="Production-grade Retrieval-Augmented Generation API",
        version="1.0.0",
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
        lifespan=lifespan,
    )

    # ── CORS ──────────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Routes ────────────────────────────────────────────────────────────────
    app.include_router(api_router)

    # ── Health check ──────────────────────────────────────────────────────────
    @app.get("/health", tags=["ops"], summary="Liveness probe")
    async def health() -> dict:
        return {"status": "ok", "env": settings.app_env}

    # ── Global exception handler ──────────────────────────────────────────────
    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger = get_logger("app.exception_handler")
        logger.error(
            "unhandled_exception",
            path=request.url.path,
            method=request.method,
            error=str(exc),
            exc_info=True,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "An internal server error occurred."},
        )

    return app


app = create_app()
