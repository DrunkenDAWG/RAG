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
from pydantic import BaseModel, Field
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.config import get_settings
from app.core.logging import get_logger
from app.services.retriever import Document, to_sources

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

_TUTOR_INSTRUCTION: str = (
    "You are a Socratic tutor. Use the retrieved context to explain the concept clearly. "
    "Do NOT just give away the final answer immediately if they are solving a problem. "
    "Always end your response with a thought-provoking follow-up question to test their understanding of the context."
)

_QUIZ_SYSTEM_PROMPT: str = (
    "You are an expert educator and exam designer specializing in active recall.\n"
    "Based strictly on the provided study notes, generate exactly 5 rigorous, high-quality "
    "multiple-choice questions to test deep student comprehension.\n\n"
    "Rules:\n"
    "1. Base all questions and answers EXCLUSIVELY on the provided context passages. Do NOT extrapolate or use outside facts.\n"
    "2. Each question must provide exactly 4 distinct options.\n"
    "3. The 'correct_answer' field MUST match one of the 4 options verbatim.\n"
    "4. The 'explanation' must explain clearly why the answer is correct with reference to the notes.\n"
    "5. Output must be a valid JSON object matching this schema:\n"
    "{\n"
    '  "questions": [\n'
    "    {\n"
    '      "question": "string",\n'
    '      "options": ["string", "string", "string", "string"],\n'
    '      "correct_answer": "string",\n'
    '      "explanation": "string"\n'
    "    }\n"
    "  ]\n"
    "}"
)


# -- Active Recall / Quiz Models ----------------------------------------------

class Question(BaseModel):
    question: str = Field(..., description="The multiple-choice question text")
    options: List[str] = Field(
        ...,
        min_length=4,
        max_length=4,
        description="List of exactly 4 choices/options",
    )
    correct_answer: str = Field(
        ...,
        description="The correct answer matching one of the 4 options verbatim",
    )
    explanation: str = Field(
        ...,
        description="Detailed explanation of why the correct answer is right based on notes",
    )


class Quiz(BaseModel):
    questions: List[Question] = Field(
        ...,
        min_length=1,
        description="List of 5 active recall multiple-choice questions",
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
    # Chunk ids / scores are kept out of the prompt so the model can't echo
    # retrieval internals into the user-facing answer.
    blocks = []
    for i, doc in enumerate(docs, start=1):
        page = ""
        if doc.page is not None:
            page = (f" | pages {doc.page}-{doc.page_end}"
                    if doc.page_end and doc.page_end != doc.page
                    else f" | page {doc.page}")
        blocks.append(f"[{i}] Source: {doc.filename}{page}\n{doc.text}")
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
    tutor_mode: bool = False,
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

    system_prompt = (
        f"{_TUTOR_INSTRUCTION}\n\n{_RAG_SYSTEM_PROMPT}"
        if tutor_mode
        else _RAG_SYSTEM_PROMPT
    )

    messages: List[dict] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]

    logger.info(
        "llm.stream_start",
        model=resolved_model,
        doc_count=len(context_docs),
        query_preview=query[:60],
        tutor_mode=tutor_mode,
    )

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

    sources = to_sources(context_docs)
    yield _sse({"type": "done", "sources": sources})
    logger.info("llm.stream_complete", model=resolved_model, source_count=len(sources))


# -- SSE serialiser -----------------------------------------------------------

def _sse(payload: dict) -> str:
    """Serialise a dict to a well-formed SSE data line."""
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _build_quiz_context_block(docs: List[Document], max_chars: int = 6000) -> str:
    """Build a context block capped at max_chars to stay safely within Groq ITPM limits."""
    blocks = []
    current_chars = 0
    for i, doc in enumerate(docs, start=1):
        clean_text = doc.text.strip()
        block = f"[{i}] Source: {doc.filename}\n{clean_text}"
        if current_chars + len(block) > max_chars:
            remaining = max_chars - current_chars
            if remaining > 250:
                blocks.append(f"[{i}] Source: {doc.filename}\n{clean_text[:remaining]}...")
            break
        blocks.append(block)
        current_chars += len(block)
    return "\n\n---\n\n".join(blocks)


# -- Active Recall / Quiz Generation ------------------------------------------

async def generate_quiz_json(
    context_docs: List[Document],
    model: Optional[str] = None,
) -> Quiz:
    """
    Generate 5 rigorous active recall multiple-choice questions from retrieved context
    using Groq's JSON output mode.

    Args:
        context_docs: Retrieved chunks/documents containing study notes.
        model: Optional model override (must be in allowlist).

    Returns:
        Validated Quiz Pydantic model with 5 questions.
    """
    if not context_docs:
        raise ValueError("Cannot generate quiz from empty context documents.")

    resolved_model = _resolve_model(model)
    context_block = _build_quiz_context_block(context_docs)
    user_prompt = (
        f"Study notes:\n\n{context_block}\n\n---\n\n"
        "Generate exactly 5 rigorous active recall multiple-choice questions in JSON based strictly on the study notes above."
    )

    messages: List[dict] = [
        {"role": "system", "content": _QUIZ_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    logger.info(
        "llm.generate_quiz_start",
        model=resolved_model,
        doc_count=len(context_docs),
        prompt_chars=len(user_prompt),
    )

    response = None
    async for attempt in _retry_policy():
        with attempt:
            response = await _client().chat.completions.create(
                model=resolved_model,
                messages=messages,
                temperature=0.3,
                max_tokens=2048,
                response_format={"type": "json_object"},
            )

    raw_content = (response.choices[0].message.content or "{}").strip()
    if raw_content.startswith("```"):
        raw_content = raw_content.split("```")[1]
        if raw_content.startswith("json"):
            raw_content = raw_content[4:]
        raw_content = raw_content.strip()

    data = json.loads(raw_content)
    if "questions" not in data and "quiz" in data:
        data = {"questions": data["quiz"]}

    quiz = Quiz.model_validate(data)
    logger.info(
        "llm.generate_quiz_complete",
        model=resolved_model,
        question_count=len(quiz.questions),
    )
    return quiz
