"""
app/api/v1/endpoints/chat.py
──────────────────────────────
Chat endpoints:
  POST /chat          – non-streaming RAG chat (with Redis cache)
  POST /chat/stream   – streaming RAG chat via Server-Sent Events

Full pipeline per request:
  1. Load session history from Redis
  2. Hybrid retrieval (dense + BM25 + RRF)
  3. Cross-encoder reranking
  4. Groq LLM completion
  5. Persist turns to session history
  6. Cache response keyed on (session_id, query, model)
"""
from __future__ import annotations

import json
from typing import List, Optional

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.api.deps import AuthDep, RedisDep
from app.api.v1.endpoints.session import append_turn, get_session_history
from app.core.logging import get_logger
from app.core.redis import cache_get, cache_set
from app.services.llm import chat_completion, chat_completion_stream
from app.services.reranker import rerank
from app.services.retriever import hybrid_retrieve

logger = get_logger(__name__)
router = APIRouter(prefix="/chat", tags=["chat"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    session_id: str = Field(..., description="Session UUID obtained from POST /sessions")
    query: str = Field(..., min_length=1, max_length=4096)
    model: Optional[str] = Field(None, description="Override the default Groq model")
    document_ids: Optional[List[str]] = Field(
        None, description="Restrict retrieval to specific document IDs"
    )
    temperature: float = Field(0.2, ge=0.0, le=2.0)
    max_tokens: int = Field(1024, ge=64, le=8192)
    use_cache: bool = Field(True, description="Return cached response if available")


class SourceChunk(BaseModel):
    document_id: str
    filename: str
    chunk_index: int
    score: float


class ChatResponse(BaseModel):
    session_id: str
    answer: str
    sources: List[SourceChunk]
    cached: bool = False


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _run_rag_pipeline(req: ChatRequest) -> tuple[str, list]:
    """Run retrieval → rerank → LLM. Returns (answer, reranked_chunks)."""
    # 1. Retrieve
    candidates = await hybrid_retrieve(
        query=req.query,
        document_ids=req.document_ids,
    )
    if not candidates:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No relevant context found. Please upload documents first.",
        )

    # 2. Rerank
    top_chunks = await rerank(query=req.query, candidates=candidates)

    # 3. LLM
    answer = await chat_completion(
        query=req.query,
        chunks=top_chunks,
        model=req.model,
        temperature=req.temperature,
        max_tokens=req.max_tokens,
    )

    return answer, top_chunks


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post(
    "",
    response_model=ChatResponse,
    summary="Send a message and receive a RAG-grounded response",
)
async def chat(
    _: AuthDep,
    redis: RedisDep,
    req: ChatRequest,
) -> ChatResponse:
    # Session history
    history = await get_session_history(redis, req.session_id)

    # Cache lookup
    if req.use_cache:
        cached = await cache_get("chat", req.session_id, req.query, req.model or "default")
        if cached:
            logger.info("chat.cache_hit", session_id=req.session_id)
            return ChatResponse(**cached, cached=True)

    try:
        answer, top_chunks = await _run_rag_pipeline(req)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("chat.pipeline_error", error=str(exc), session_id=req.session_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="RAG pipeline failed. Check server logs.",
        )

    # Persist turn
    await append_turn(redis, req.session_id, "user", req.query)
    await append_turn(redis, req.session_id, "assistant", answer)

    response_data = {
        "session_id": req.session_id,
        "answer": answer,
        "sources": [
            {
                "document_id": c.document_id,
                "filename": c.filename,
                "chunk_index": c.chunk_index,
                "score": c.score,
            }
            for c in top_chunks
        ],
    }

    # Cache the result
    if req.use_cache:
        await cache_set("chat", response_data, req.session_id, req.query, req.model or "default")

    return ChatResponse(**response_data)


@router.post(
    "/stream",
    summary="Stream a RAG-grounded response via Server-Sent Events",
    response_class=StreamingResponse,
)
async def chat_stream(
    _: AuthDep,
    redis: RedisDep,
    req: ChatRequest,
) -> StreamingResponse:
    """
    Streams the LLM response as SSE.  Each event has the form:
        data: <text_delta>\n\n
    The stream ends with:
        data: [DONE]\n\n
    """
    # 1. Retrieve & rerank (not streamed)
    candidates = await hybrid_retrieve(query=req.query, document_ids=req.document_ids)
    if not candidates:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No relevant context found. Please upload documents first.",
        )
    top_chunks = await rerank(query=req.query, candidates=candidates)

    # 2. Capture full answer for session persistence
    full_answer_parts: list[str] = []

    async def event_generator():
        async for delta in chat_completion_stream(
            query=req.query,
            chunks=top_chunks,
            model=req.model,
            temperature=req.temperature,
            max_tokens=req.max_tokens,
        ):
            full_answer_parts.append(delta)
            yield f"data: {json.dumps({'delta': delta})}\n\n"

        # Persist after stream completes
        full_answer = "".join(full_answer_parts)
        await append_turn(redis, req.session_id, "user", req.query)
        await append_turn(redis, req.session_id, "assistant", full_answer)
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
