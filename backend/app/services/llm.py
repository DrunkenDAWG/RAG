"""
app/services/llm.py
────────────────────
Phase 3 — Contextual query rewriting + grounded streaming generation.

Two public coroutines:

  rewrite_query(chat_history, latest_query) -> str
    Sends a condensation prompt to a fast model (llama-3.1-8b-instant) and
    returns a self-contained, context-free search query. Falls back to the
    raw query on any error so the pipeline never stalls.

  generate_rag_stream(query, context_docs) -> AsyncIterator[str]
    Yields raw SSE-formatted lines (each ending with \\n\\n).
    Uses tenacity to retry on Groq 429 / 503 with exponential back-off.
    The system prompt strictly grounds the model to the provided context.

Design notes:
  • A single AsyncGroq client is constructed per call — Groq's SDK manages
    connection pooling internally, so this is safe and avoids shared state.
  • Retry is only applied to the non-streaming rewrite call; streaming
    connections should not be retried mid-stream (data would be duplicated).
    Instead, the stream call retries the *initial* create() invocation only.
  • Both models are configurable via settings.model_names; the fast model
    is hard-coded to the first element with "8b" in the name or fallback.
"""
from __future__ import annotations

import json
from typing import AsyncIterator, List, Optional

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

# ── Model constants ───────────────────────────────────────────────────────────
_FAST_MODEL: str = "llama-3.1-8b-instant"     # query rewriting — cheap & fast
_STRONG_MODEL: str = "llama-3.3-70b-versatile" # RAG generation — high quality

# ── System prompts ────────────────────────────────────────────────────────────

_REWRITE_SYSTEM_PROMPT: str = """\
You are a search-query optimiser. Your sole job is to rewrite the user's \
latest message into a single, standalone, self-contained search query that \
can be understood without any prior conversation context.

Rules:
- Output ONLY the rewritten query — no preamble, no explanation, no quotes.
- Resolve pronouns and elliptical references using the chat history.
- Preserve domain-specific terminology exactly.
- If the latest message is already self-contained, return it unchanged.
"""

_RAG_SYSTEM_PROMPT: str = """\
You are a precise, citation-driven AI assistant.

Answer the user's question EXCLUSIVELY from the numbered context passages \
provided below. Do not use any external knowledge.

Strict rules:
1. Cite every claim with [N] referencing the passage number.
2. If the answer is not present in the context, respond with exactly:
   "I cannot answer this from the provided documents."
3. Do not speculate, extrapolate, or hallucinate.
4. Be concise — prefer bullet points for multi-part answers.
"""

# ── Groq client ───────────────────────────────────────────────────────────────

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


# ── Retry decorator ───────────────────────────────────────────────────────────

def _retry_policy() -> AsyncRetrying:
    """Retry on Groq 429 (rate-limit) and 503 (overloaded) with back-off."""
    return AsyncRetrying(
        retry=retry_if_exception_type((RateLimitError, APIStatusError)),
        stop=stop_after_attempt(4),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        reraise=True,
    )


# ── Prompt builders ───────────────────────────────────────────────────────────

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


# ── Public API ────────────────────────────────────────────────────────────────

async def rewrite_query(
    chat_history: List[dict],
    latest_query: str,
) -> str:
    """
    Disambiguate a potentially anaphoric follow-up question into a
    standalone search query using chat history as context.

    Uses llama-3.1-8b-instant for speed (rewriting is latency-sensitive).
    Falls back to *latest_query* on any error so the pipeline never stalls.

    Args:
        chat_history:  Recent turns as [{"role": "user"|"assistant", "content": str}].
                       Capped internally to the last 6 turns (3 exchanges).
        latest_query:  The user's most recent raw message.

    Returns:
        A standalone, context-free search query string.
    """
    # If no history exists there is nothing to disambiguate
    if not chat_history:
        return latest_query

    # Cap history to last 6 messages (3 user/assistant pairs) to stay within
    # context budget of the fast model
    recent_history = chat_history[-6:]

    messages: List[dict] = [
        {"role": "system", "content": _REWRITE_SYSTEM_PROMPT},
        *recent_history,
        {
            "role": "user",
            "content": (
                f"Latest message to rewrite into a standalone query:\n{latest_query}"
            ),
        },
    ]

    try:
        async for attempt in _retry_policy():
            with attempt:
                response = await _client().chat.completions.create(
                    model=_FAST_MODEL,
                    messages=messages,
                    temperature=0.0,   # deterministic rewriting
                    max_tokens=256,
                )
        rewritten = (response.choices[0].message.content or latest_query).strip()
        logger.info(
            "llm.query_rewritten",
            original=latest_query[:80],
            rewritten=rewritten[:80],
        )
        return rewritten
    except Exception as exc:
        # Non-fatal: fall back gracefully so retrieval is never blocked
        logger.warning(
            "llm.rewrite_failed",
            error=str(exc),
            fallback=latest_query[:80],
        )
        return latest_query


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
    response body. The caller should NOT add additional framing.

    SSE line formats:
        data: {"type": "token", "content": "<delta>"}\\n\\n
        data: {"type": "done",  "sources": [...]}\\n\\n
        data: {"type": "error", "detail": "<message>"}\\n\\n

    Tenacity retries the *stream creation* (not mid-stream) on 429 / 503.

    Args:
        query:        The (rewritten) search query / user question.
        context_docs: Reranked Document list from the retrieval pipeline.
        model:        Optional model override (validated against allowlist).
        temperature:  Sampling temperature.
        max_tokens:   Maximum completion tokens.

    Yields:
        SSE-formatted strings ending with \\n\\n.
    """
    resolved_model = _resolve_model(model)
    user_message = _build_rag_user_message(query, context_docs)

    messages: List[dict] = [
        {"role": "system", "content": _RAG_SYSTEM_PROMPT},
        {"role": "user", "content": user_message},
    ]

    logger.info(
        "llm.stream_start",
        model=resolved_model,
        doc_count=len(context_docs),
        query_preview=query[:60],
    )

    # ── Retry only the stream *creation* — not mid-stream tokens ─────────────
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

    # ── Stream tokens ─────────────────────────────────────────────────────────
    try:
        async for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield _sse({"type": "token", "content": delta})
    except Exception as exc:
        logger.error("llm.stream_interrupted", error=str(exc))
        yield _sse({"type": "error", "detail": "Stream interrupted."})
        return

    # ── Done event with source citations ──────────────────────────────────────
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


# ── SSE serialiser ────────────────────────────────────────────────────────────

def _sse(payload: dict) -> str:
    """Serialise a dict to a well-formed SSE data line."""
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
