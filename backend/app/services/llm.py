"""
app/services/llm.py
────────────────────
Groq LLM client with:
  - Async chat completion (streaming and non-streaming)
  - Tenacity-based retry with exponential back-off
  - Per-request model override with allowlist validation
  - Context-window-aware prompt builder
"""
from __future__ import annotations

import json
from typing import AsyncIterator, List, Optional

from groq import AsyncGroq, APIError, APIStatusError, RateLimitError
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.config import get_settings
from app.core.logging import get_logger
from app.services.retriever import RetrievedChunk

logger = get_logger(__name__)

# ── Prompt templates ──────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """\
You are a precise and helpful AI assistant. Answer the user's question
exclusively based on the provided context passages. If the answer is not
contained in the context, clearly state that you don't have enough information.
Do not hallucinate or speculate beyond the provided context.
Always cite the source filename and chunk index when you use information from a passage.
"""


def _build_user_prompt(query: str, chunks: List[RetrievedChunk]) -> str:
    context_blocks = []
    for i, chunk in enumerate(chunks, start=1):
        context_blocks.append(
            f"[{i}] Source: {chunk.filename} (chunk {chunk.chunk_index})\n{chunk.text}"
        )
    context = "\n\n---\n\n".join(context_blocks)
    return f"Context:\n{context}\n\nQuestion: {query}"


# ── Retry policy ──────────────────────────────────────────────────────────────

def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, RateLimitError):
        return True
    if isinstance(exc, APIStatusError) and exc.status_code in {429, 500, 502, 503}:
        return True
    return False


def _groq_retry():
    return AsyncRetrying(
        retry=retry_if_exception_type((RateLimitError, APIStatusError)),
        stop=stop_after_attempt(4),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        reraise=True,
    )


# ── Client factory ────────────────────────────────────────────────────────────

def _get_client() -> AsyncGroq:
    settings = get_settings()
    return AsyncGroq(api_key=settings.groq_api_key)


def _validate_model(model: Optional[str]) -> str:
    settings = get_settings()
    if model is None:
        return settings.default_model_name
    if model not in settings.model_names:
        raise ValueError(
            f"Model '{model}' is not in the allowed list: {settings.model_names}"
        )
    return model


# ── Public API ────────────────────────────────────────────────────────────────

async def chat_completion(
    query: str,
    chunks: List[RetrievedChunk],
    session_history: Optional[List[dict]] = None,
    model: Optional[str] = None,
    temperature: float = 0.2,
    max_tokens: int = 1024,
) -> str:
    """
    Non-streaming chat completion over retrieved context.

    Args:
        query:           The user's current question.
        chunks:          Reranked context chunks from the retrieval pipeline.
        session_history: Prior turns as [{"role": ..., "content": ...}] dicts.
        model:           Override the default model (must be in allowed list).
        temperature:     Sampling temperature.
        max_tokens:      Maximum tokens in the response.

    Returns:
        The assistant's reply as a plain string.
    """
    model = _validate_model(model)
    client = _get_client()

    messages = [{"role": "system", "content": _SYSTEM_PROMPT}]
    if session_history:
        messages.extend(session_history[-10:])  # cap history to last 10 turns
    messages.append({"role": "user", "content": _build_user_prompt(query, chunks)})

    logger.info("llm.request", model=model, chunk_count=len(chunks))

    async for attempt in _groq_retry():
        with attempt:
            response = await client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )

    content = response.choices[0].message.content or ""
    logger.info(
        "llm.response",
        model=model,
        prompt_tokens=response.usage.prompt_tokens,
        completion_tokens=response.usage.completion_tokens,
    )
    return content


async def chat_completion_stream(
    query: str,
    chunks: List[RetrievedChunk],
    session_history: Optional[List[dict]] = None,
    model: Optional[str] = None,
    temperature: float = 0.2,
    max_tokens: int = 1024,
) -> AsyncIterator[str]:
    """
    Streaming variant — yields text deltas as they arrive from Groq.
    Suitable for Server-Sent Events (SSE) endpoints.
    """
    model = _validate_model(model)
    client = _get_client()

    messages = [{"role": "system", "content": _SYSTEM_PROMPT}]
    if session_history:
        messages.extend(session_history[-10:])
    messages.append({"role": "user", "content": _build_user_prompt(query, chunks)})

    logger.info("llm.stream_request", model=model)

    stream = await client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        stream=True,
    )

    async for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta
