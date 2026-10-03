"""
app/api/v1/endpoints/chat.py
──────────────────────────────
Phase 3 — Streaming RAG endpoint with query rewriting and smart caching.

Single endpoint: POST /api/v1/chat/stream

Full pipeline (in order):
  1. Check Redis cache (session_id + corpus_version + rewritten_query key)
     → If HIT: replay stored answer as SSE stream and exit early.
  2. Load session history from Redis.
  3. Rewrite query via LLM (llama-3.1-8b-instant) to resolve anaphora.
  4. Hybrid search (asyncio.gather: dense ChromaDB + sparse BM25 + RRF).
  5. Cross-encoder rerank in threadpool (non-blocking).
  6. Stream LLM generation (llama-3.3-70b-versatile) token-by-token as SSE.
  7. On stream complete: persist turn to session history + write cache.

SSE event shapes:
  data: {"type": "rewritten_query", "content": "<str>"}
  data: {"type": "token",           "content": "<delta>"}
  data: {"type": "done",            "sources": [...]}
  data: {"type": "error",           "detail":  "<str>"}
  data: {"type": "cached",          "answer":  "<str>", "sources": [...]}
"""
from __future__ import annotations

import json
from typing import AsyncIterator, List, Optional

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.api.deps import AuthDep, RedisDep
from app.api.v1.endpoints.session import append_turn, get_session_history
from app.core.cache import (
    get_cached_response,
    get_corpus_version,
    set_cached_response,
)
from app.core.logging import get_logger
from app.services.llm import generate_rag_stream, rewrite_query_and_hyde
from app.services.reranker import rerank
from app.services.retriever import Document, expand_to_parents, hybrid_search

logger = get_logger(__name__)
router = APIRouter(prefix="/chat", tags=["chat"])


# ── Request / Response schemas ────────────────────────────────────────────────

class ChatRequest(BaseModel):
    session_id: str = Field(..., description="Session UUID from POST /api/v1/sessions")
    query: str = Field(..., min_length=1, max_length=4096, description="User's raw message")
    model: Optional[str] = Field(
        None, description="Override default generation model (must be in allowlist)"
    )
    top_k: int = Field(20, ge=1, le=100, description="Candidates per retrieval path")
    top_n: int = Field(5, ge=1, le=20, description="Chunks kept after reranking")
    temperature: float = Field(0.2, ge=0.0, le=2.0)
    max_tokens: int = Field(1024, ge=64, le=8192)
    use_cache: bool = Field(True, description="Serve cached answer if available")


# ── SSE helpers ───────────────────────────────────────────────────────────────

def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


# ── Pipeline ──────────────────────────────────────────────────────────────────

async def _stream_pipeline(
    req: ChatRequest,
    redis,
) -> AsyncIterator[str]:
    """
    Core generator that drives the full RAG pipeline and yields SSE lines.
    Consumed by the StreamingResponse.
    """
    session_id = req.session_id

    # ── Step 1: corpus version + cache check ──────────────────────────────────
    corpus_version = await get_corpus_version(session_id)

    if req.use_cache:
        # We need the rewritten query to build the cache key, but for a cache
        # hit we want to avoid the rewrite round-trip. Attempt a cache lookup
        # with the raw query first (fast path for exact repeat questions).
        cached = await get_cached_response(session_id, corpus_version, req.query)
        if cached:
            logger.info(
                "chat.cache_hit",
                session_id=session_id,
                corpus_version=corpus_version,
            )
            yield _sse(
                {
                    "type": "cached",
                    "answer": cached["answer"],
                    "sources": cached.get("sources", []),
                }
            )
            return

    # ── Step 2: load session history ──────────────────────────────────────────
    history = await get_session_history(redis, session_id)

    # ── Step 3: merged query rewrite + HyDE (single LLM call) ────────────────
    search_query, hyde_passage = await rewrite_query_and_hyde(
        chat_history=history,
        latest_query=req.query,
    )
    yield _sse({"type": "rewritten_query", "content": search_query})

    # Second cache check with rewritten query (catches paraphrases)
    if req.use_cache and search_query != req.query:
        cached = await get_cached_response(session_id, corpus_version, search_query)
        if cached:
            logger.info(
                "chat.cache_hit_rewritten",
                session_id=session_id,
                corpus_version=corpus_version,
            )
            yield _sse(
                {
                    "type": "cached",
                    "answer": cached["answer"],
                    "sources": cached.get("sources", []),
                }
            )
            return

    # ── Step 4: hybrid search (BM25 on search_query, dense on hyde_passage) ───
    candidates: List[Document] = await hybrid_search(
        session_id=session_id,
        top_k=req.top_k,
        search_query=search_query,
        hyde_passage=hyde_passage,
    )
    if not candidates:
        yield _sse(
            {
                "type": "error",
                "detail": (
                    "No relevant context found for this session. "
                    "Upload documents first via POST /api/v1/documents/upload."
                ),
            }
        )
        return

    # ── Step 5: cross-encoder rerank on child chunks (within 512-token limit) ─
    top_children: List[Document] = await rerank(
        query=search_query, docs=candidates, top_n=req.top_n
    )

    # ── Step 5b: parent expansion — swap children for full 800-token parents ──
    top_docs: List[Document] = await expand_to_parents(top_children)

    # ── Step 6: stream LLM generation ────────────────────────────────────────
    full_answer_parts: List[str] = []

    async for sse_line in generate_rag_stream(
        query=search_query,
        context_docs=top_docs,
        model=req.model,
        temperature=req.temperature,
        max_tokens=req.max_tokens,
    ):
        # Accumulate tokens for persistence; forward every SSE line verbatim
        try:
            payload = json.loads(sse_line.removeprefix("data: ").strip())
            if payload.get("type") == "token":
                full_answer_parts.append(payload["content"])
        except (json.JSONDecodeError, AttributeError):
            pass
        yield sse_line

    # ── Step 7: persist turn + write cache ───────────────────────────────────
    full_answer = "".join(full_answer_parts)
    if full_answer:
        await append_turn(redis, session_id, "user", req.query)
        await append_turn(redis, session_id, "assistant", full_answer)

        if req.use_cache:
            sources = [
                {
                    "doc_id": doc.doc_id,
                    "filename": doc.filename,
                    "chunk_index": doc.chunk_index,
                    "score": round(doc.score, 4),
                }
                for doc in top_docs
            ]
            await set_cached_response(
                session_id=session_id,
                corpus_version=corpus_version,
                rewritten_query=search_query,
                answer=full_answer,
                sources=sources,
            )
            logger.info(
                "chat.response_cached",
                session_id=session_id,
                corpus_version=corpus_version,
            )


# ── Endpoint ──────────────────────────────────────────────────────────────────

@router.post(
    "/stream",
    summary="Stream a RAG-grounded response via Server-Sent Events",
    response_class=StreamingResponse,
    responses={
        200: {
            "description": "SSE stream of tokens. Content-Type: text/event-stream.",
            "content": {"text/event-stream": {}},
        }
    },
)
async def chat_stream(
    _: AuthDep,
    redis: RedisDep,
    req: ChatRequest,
) -> StreamingResponse:
    """
    Full RAG pipeline delivered as a Server-Sent Event stream.

    **Pipeline order**:
    1. Redis cache lookup (corpus-version-scoped)
    2. Session history load
    3. Contextual query rewriting (llama-3.1-8b-instant)
    4. Hybrid search — concurrent dense (ChromaDB) + sparse (BM25) + RRF
    5. Cross-encoder rerank (threadpool)
    6. Streaming generation (llama-3.3-70b-versatile)
    7. Session history persistence + cache write

    **SSE event types**: `rewritten_query` | `token` | `done` | `error` | `cached`
    """
    return StreamingResponse(
        _stream_pipeline(req, redis),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",   # disable Nginx buffering
        },
    )
