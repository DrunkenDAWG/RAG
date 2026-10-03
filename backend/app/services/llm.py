"""
app/services/llm.py
--------------------
Phase 3 — Merged HyDE + Query Rewrite + grounded streaming generation.

Public API:
  rewrite_query_and_hyde(chat_history, latest_query) -> (search_query, hyde_passage)
    Single LLM call returning structured JSON:
      {"search_query": "...", "hyde_passage": "..."}
    search_query  — disambiguated, standalone keyword query for BM25.
    hyde_passage  — hypothetical answer passage for dense (BGE) embedding.
    Falls back to (latest_query, latest_query) on any error.

  generate_rag_stream(query, context_docs, ...) -> AsyncIterator[str]
    Streams SSE-formatted grounded answer tokens.

Design notes:
  - A single AsyncGroq client per call; SDK manages connection pooling.
  - Retry applied to the non-streaming rewrite call only.
  - Streaming retries the *initial* create() invocation, not mid-stream tokens.
"""
from __future__ import annotations

import json
from typing import AsyncIterator, List, Optional, Tuple

from groq import AsyncGroq, APIStatusError, RateLimitError
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.config import get_settings
from app.core.logging import get_logger
from app.services.retriever import Document

logger = get_logger(__name__)

# -- Model constants ----------------------------------------------------------
_FAST_MODEL: str = "qwen/qwen3.8-27b"    # query rewrite + HyDE
_STRONG_MODEL: str = "qwen/qwen3.8-27b"  # RAG generation

# -- System prompts -----------------------------------------------------------

_REWRITE_HYDE_SYSTEM_PROMPT: str = (
    "You are a dual-purpose search assistant. Given the conversation history "
    "and the user's latest message, return a single JSON object with exactly "
    "two keys:\n"
    '  "search_query"  — a concise, standalone keyword query optimised for '
    "BM25 lexical search. Resolve pronouns and elliptical references. "
    "Preserve domain-specific terminology exactly.\n"
    '  "hyde_passage"  — a short hypothetical document passage (2-4 sentences) '
    "that directly answers the question, as if it were extracted from a relevant "
    "document. This is used for dense semantic embedding, so write it in the "
    "style of a factual document excerpt.\n"
    "Output ONLY valid JSON — no markdown fences, no preamble, no explanation."
)

_RAG_SYSTEM_PROMPT: str = (
    "You are a precise, citation-driven AI assistant.\n\n"
    "Answer the user's question EXCLUSIVELY from the numbered context passages "
    "provided below. Do not use any external knowledge.\n\n"
    "Strict rules:\n"
    "1. Cite every claim with [N] referencing the passage number.\n"
    '2. If the answer is not present in the context, respond with exactly: '
    '"I cannot answer this from the provided documents."\n'
    "3. Do not speculate, extrapolate, or hallucinate.\n"
    "4. Be concise — prefer bullet points for multi-part answers."
)

# -- Groq client --------------------------------------------------------------

def _client() -> AsyncGroq:
    return AsyncGroq(api_key=get_settings().groq_api_key)


def _resolve_model(model: Optional[str]) -> str:
    settings = get_settings()
    if model is None:
        return settings.default_model_name
    if model not in settings.model_names:
        raise ValueError(
            f"Model '{model}' is not allowed. Allowed: {settings.model_names}"
        )
    return model


# -- Retry policy -------------------------------------------------------------

def _retry_policy() -> AsyncRetrying:
    """Retry on Groq 429 (rate-limit) and 503 (overloaded) with back-off."""
    return AsyncRetrying(
        retry=retry_if_exception_type((RateLimitError, APIStatusError)),
        stop=stop_after_attempt(4),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        reraise=True,
    )


# -- Prompt builders ----------------------------------------------------------

def _build_context_block(docs: List[Document]) -> str:
    blocks = []
    for i, doc in enumerate(docs, start=1):
        blocks.append(
            f"[{i}] Source: {doc.filename} | chunk {doc.chunk_index} "
            f"| score {doc.score:.4f}\n{doc.text}"
        )
    return "\n\n---\n\n".join(blocks)


def _build_rag_user_message(query: str, docs: List[Document]) -> str:
    context = _build_context_block(docs)
    return f"Context passages:\n\n{context}\n\n---\n\nQuestion: {query}"


# -- Public API ---------------------------------------------------------------

async def rewrite_query_and_hyde(
    chat_history: List[dict],
    latest_query: str,
) -> Tuple[str, str]:
    """
    Single LLM call that returns both a BM25 keyword query and a HyDE passage.

    Args:
        chat_history:  Recent turns [{role, content}], capped to last 6.
        latest_query:  The user's raw message.

    Returns:
        (search_query, hyde_passage)
        Falls back to (latest_query, latest_query) on any error.
    """
    recent_history = chat_history[-6:] if chat_history else []

    messages: List[dict] = [
        {"role": "system", "content": _REWRITE_HYDE_SYSTEM_PROMPT},
        *recent_history,
        {
            "role": "user",
            "content": (
                f"Conversation context above.\n"
                f"Latest user message: {latest_query}\n\n"
                f"Return JSON with search_query and hyde_passage."
            ),
        },
    ]

    try:
        async for attempt in _retry_policy():
            with attempt:
                response = await _client().chat.completions.create(
                    model=_FAST_MODEL,
                    messages=messages,
                    temperature=0.0,
                    max_tokens=512,
                )
        raw = (response.choices[0].message.content or "{}").strip()
        # Strip optional markdown code fences if model adds them
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        parsed = json.loads(raw)
        search_query = parsed.get("search_query", latest_query).strip() or latest_query
        hyde_passage = parsed.get("hyde_passage", latest_query).strip() or latest_query
        logger.info(
            "llm.rewrite_hyde_done",
            original=latest_query[:80],
            search_query=search_query[:80],
            hyde_preview=hyde_passage[:80],
        )
        return search_query, hyde_passage
    except Exception as exc:
        logger.warning(
            "llm.rewrite_hyde_failed",
            error=str(exc),
            fallback=latest_query[:80],
        )
        return latest_query, latest_query


# Backward-compatible alias used by chat.py (single return value)
async def rewrite_query(
    chat_history: List[dict],
    latest_query: str,
) -> str:
    """Legacy alias — returns only the search_query string."""
    search_query, _ = await rewrite_query_and_hyde(chat_history, latest_query)
    return search_query


async def generate_rag_stream(
    query: str,
    context_docs: List[Document],
    model: Optional[str] = None,
    temperature: float = 0.2,
    max_tokens: int = 1024,
) -> AsyncIterator[str]:
    """
    Stream a strictly-grounded RAG answer as SSE-formatted lines.

    Each yielded string is a complete SSE line ready to be written to the
    response body. Tenacity retries the stream *creation* only.

    SSE line formats:
        data: {"type": "token", "content": "<delta>"}\n\n
        data: {"type": "done",  "sources": [...]}\n\n
        data: {"type": "error", "detail": "<message>"}\n\n
    """
    resolved_model = _resolve_model(model)
    user_message = _build_rag_user_message(query, context_docs)

    messages: List[dict] = [
        {"role": "system", "content": _RAG_SYSTEM_PROMPT},
        {"role": "user", "content": user_message},
    ]

    logger.info("llm.stream_start", model=resolved_model,
                doc_count=len(context_docs), query_preview=query[:60])

    stream = None
    try:
        async for attempt in _retry_policy():
            with attempt:
                stream = await _client().chat.completions.create(
                    model=resolved_model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    stream=True,
                )
    except (RateLimitError, APIStatusError) as exc:
        logger.error("llm.stream_create_failed", error=str(exc))
        yield _sse({"type": "error", "detail": f"LLM unavailable: {exc}"})
        return

    try:
        async for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield _sse({"type": "token", "content": delta})
    except Exception as exc:
        logger.error("llm.stream_interrupted", error=str(exc))
        yield _sse({"type": "error", "detail": "Stream interrupted."})
        return

    sources = [
        {
            "doc_id": doc.doc_id,
            "filename": doc.filename,
            "chunk_index": doc.chunk_index,
            "score": round(doc.score, 4),
        }
        for doc in context_docs
    ]
    yield _sse({"type": "done", "sources": sources})
    logger.info("llm.stream_complete", model=resolved_model, source_count=len(sources))


# -- SSE serialiser -----------------------------------------------------------

def _sse(payload: dict) -> str:
    """Serialise a dict to a well-formed SSE data line."""
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
