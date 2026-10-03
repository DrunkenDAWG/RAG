"""
app/api/v1/endpoints/study.py
──────────────────────────────
Active recall study endpoints (quiz generation, concept checks) powered by
Groq structured JSON output and hybrid retrieval.
"""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.api.deps import AuthDep
from app.core.logging import get_logger
from app.services.reranker import rerank
from app.services.retriever import Document, expand_to_parents, hybrid_search
from app.services.study_llm import (
    FlashcardDeck,
    Quiz,
    generate_flashcards_gemini,
    generate_quiz_gemini,
)

logger = get_logger(__name__)
router = APIRouter(prefix="/study", tags=["study"])


# ── Request / Response schemas ────────────────────────────────────────────────

class GenerateQuizRequest(BaseModel):
    session_id: str = Field(..., description="Session UUID from POST /api/v1/sessions")
    topic: str = Field(..., min_length=1, max_length=1000, description="Topic or subject for quiz generation")


class GenerateFlashcardsRequest(BaseModel):
    session_id: str = Field(..., description="Session UUID from POST /api/v1/sessions")
    topic: str = Field(..., min_length=1, max_length=1000, description="Topic or subject for flashcard generation")


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post(
    "/generate-quiz",
    response_model=Quiz,
    summary="Generate an active recall multiple-choice quiz from study notes using Gemini",
    responses={
        200: {"description": "5 rigorous multiple-choice questions validated via JSON schema"},
        404: {"description": "No relevant documents found for the session and topic"},
    },
)
async def generate_quiz(
    req: GenerateQuizRequest,
    _: AuthDep,
) -> Quiz:
    """
    Active recall quiz generator powered by Google Gemini.

    1. Executes hybrid search for relevant candidate chunks matching the topic.
    2. Reranks chunks via cross-encoder to select the most relevant passages.
    3. Expands top reranked chunks to their parent document contexts.
    4. Invokes Google Gemini structured JSON mode to generate 5 high-yield multiple-choice questions.
    """
    logger.info(
        "study.generate_quiz_request",
        session_id=req.session_id,
        topic=req.topic,
    )

    # 1. Retrieve candidate chunks using hybrid search
    docs: List[Document] = await hybrid_search(
        session_id=req.session_id,
        top_k=10,
        search_query=req.topic,
        hyde_passage=req.topic,
    )

    if not docs:
        logger.warning(
            "study.generate_quiz_no_context",
            session_id=req.session_id,
            topic=req.topic,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No relevant study notes found for topic '{req.topic}'. Upload documents first via POST /api/v1/documents/upload.",
        )

    # 2. Rerank candidates to pick the top 4 most relevant chunks
    top_candidates: List[Document] = await rerank(
        query=req.topic, docs=docs, top_n=4
    )

    # 3. Expand top chunks to parent passages
    context_docs: List[Document] = await expand_to_parents(top_candidates)

    # 4. Generate structured quiz via Google Gemini JSON mode
    try:
        quiz: Quiz = await generate_quiz_gemini(context_docs)
    except Exception as exc:
        logger.error(
            "study.generate_quiz_failed",
            session_id=req.session_id,
            topic=req.topic,
            error=str(exc),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate quiz: {exc}",
        )

    return quiz


@router.post(
    "/generate-flashcards",
    response_model=FlashcardDeck,
    summary="Generate active recall flashcards from study notes using Gemini",
    responses={
        200: {"description": "Active recall flashcard deck validated via JSON schema"},
        404: {"description": "No relevant documents found for the session and topic"},
    },
)
async def generate_flashcards(
    req: GenerateFlashcardsRequest,
    _: AuthDep,
) -> FlashcardDeck:
    """
    Active recall flashcard generator powered by Google Gemini.

    1. Executes hybrid search for relevant candidate chunks matching the topic.
    2. Reranks chunks via cross-encoder to select the most relevant passages.
    3. Expands top reranked chunks to their parent document contexts.
    4. Invokes Google Gemini structured JSON mode to generate 6-8 flashcards.
    """
    logger.info(
        "study.generate_flashcards_request",
        session_id=req.session_id,
        topic=req.topic,
    )

    # 1. Retrieve candidate chunks using hybrid search
    docs: List[Document] = await hybrid_search(
        session_id=req.session_id,
        top_k=10,
        search_query=req.topic,
        hyde_passage=req.topic,
    )

    if not docs:
        logger.warning(
            "study.generate_flashcards_no_context",
            session_id=req.session_id,
            topic=req.topic,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No relevant study notes found for topic '{req.topic}'. Upload documents first via POST /api/v1/documents/upload.",
        )

    # 2. Rerank candidates to pick the top 4 most relevant chunks
    top_candidates: List[Document] = await rerank(
        query=req.topic, docs=docs, top_n=4
    )

    # 3. Expand top chunks to parent passages
    context_docs: List[Document] = await expand_to_parents(top_candidates)

    # 4. Generate structured flashcards via Google Gemini JSON mode
    try:
        deck: FlashcardDeck = await generate_flashcards_gemini(context_docs)
    except Exception as exc:
        logger.error(
            "study.generate_flashcards_failed",
            session_id=req.session_id,
            topic=req.topic,
            error=str(exc),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate flashcards: {exc}",
        )

    return deck

