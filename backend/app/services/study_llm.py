"""
app/services/study_llm.py
─────────────────────────
Dedicated Active Recall LLM service powered by Google Gemini API
(gemini-flash-latest) for generating Quizzes and Flashcards with structured JSON.
"""
from __future__ import annotations

import json
from typing import List, Optional

import httpx
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.core.logging import get_logger
from app.services.retriever import Document

logger = get_logger(__name__)

GEMINI_MODEL: str = "gemini-flash-latest"
GEMINI_API_URL: str = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"


# ── Pydantic Schemas ──────────────────────────────────────────────────────────

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


class Flashcard(BaseModel):
    front: str = Field(..., description="Question, prompt, or concept on the front of the flashcard")
    back: str = Field(..., description="Clear, concise explanation, formula, or definition on the back")
    key_term: str = Field(..., description="Short key term or concept category")


class FlashcardDeck(BaseModel):
    cards: List[Flashcard] = Field(
        ...,
        min_length=1,
        description="List of active recall study flashcards",
    )


# ── Context builder ───────────────────────────────────────────────────────────

def _format_context(docs: List[Document]) -> str:
    blocks = []
    for i, doc in enumerate(docs, start=1):
        blocks.append(f"[{i}] Source: {doc.filename}\n{doc.text.strip()}")
    return "\n\n---\n\n".join(blocks)


# ── Gemini API Client ─────────────────────────────────────────────────────────

async def _call_gemini_json(prompt: str, system_instruction: str) -> dict:
    """Call Google Gemini REST API with forced JSON response formatting."""
    settings = get_settings()
    api_key = settings.gemini_api_key

    if not api_key:
        raise ValueError("GEMINI_API_KEY is not configured in backend/.env")

    url = f"{GEMINI_API_URL}?key={api_key}"

    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": f"{system_instruction}\n\n{prompt}"}],
            }
        ],
        "generationConfig": {
            "response_mime_type": "application/json",
            "temperature": 0.2,
        },
    }

    async with httpx.AsyncClient(timeout=45.0) as client:
        response = await client.post(url, json=payload)

    if response.status_code != 200:
        logger.error(
            "gemini.api_error",
            status_code=response.status_code,
            body=response.text[:300],
        )
        raise RuntimeError(
            f"Gemini API returned HTTP {response.status_code}: {response.text[:200]}"
        )

    res_json = response.json()
    try:
        raw_text = res_json["candidates"][0]["content"]["parts"][0]["text"].strip()
        # Clean any accidental code fences
        if raw_text.startswith("```"):
            raw_text = raw_text.split("```")[1]
            if raw_text.startswith("json"):
                raw_text = raw_text[4:]
            raw_text = raw_text.strip()
        return json.loads(raw_text)
    except (KeyError, IndexError, json.JSONDecodeError) as exc:
        logger.error("gemini.parse_failed", error=str(exc), response=res_json)
        raise ValueError(f"Failed to parse structured JSON from Gemini: {exc}")


# ── Public Study Functions ────────────────────────────────────────────────────

_QUIZ_SYSTEM_PROMPT = (
    "You are an expert educator specializing in active recall and conceptual assessment.\n"
    "Based STRICTLY on the provided study notes, generate exactly 5 rigorous, high-yield "
    "multiple-choice questions.\n\n"
    "Rules:\n"
    "1. Base all questions strictly on the text. Do not invent or use outside information.\n"
    "2. Each question must provide exactly 4 distinct, plausible options.\n"
    "3. 'correct_answer' must be one of the 4 options verbatim.\n"
    "4. 'explanation' must explain why the answer is correct with reference to the notes.\n"
    "5. Return a JSON object with a single key 'questions' containing the list of 5 question objects."
)

_FLASHCARD_SYSTEM_PROMPT = (
    "You are a master study coach creating active recall flashcards for students.\n"
    "Based STRICTLY on the provided study notes, generate 6 to 8 high-impact flashcards.\n\n"
    "Rules:\n"
    "1. 'front': A clear, testable question, prompt, or term.\n"
    "2. 'back': A concise, high-yield explanation, key takeaway, or definition.\n"
    "3. 'key_term': The core subject or concept tag.\n"
    "4. Return a JSON object with a single key 'cards' containing the list of flashcard objects."
)


async def generate_quiz_gemini(context_docs: List[Document]) -> Quiz:
    """Generate 5 multiple-choice questions from study notes using Google Gemini."""
    if not context_docs:
        raise ValueError("Cannot generate quiz with empty context documents.")

    context_str = _format_context(context_docs)
    user_prompt = f"Study Notes Context:\n\n{context_str}\n\nTask: Generate 5 multiple-choice questions based on these notes."

    logger.info("gemini.generate_quiz_start", doc_count=len(context_docs))
    data = await _call_gemini_json(user_prompt, _QUIZ_SYSTEM_PROMPT)

    if "questions" not in data and "quiz" in data:
        data = {"questions": data["quiz"]}

    quiz = Quiz.model_validate(data)
    logger.info("gemini.generate_quiz_success", question_count=len(quiz.questions))
    return quiz


async def generate_flashcards_gemini(context_docs: List[Document]) -> FlashcardDeck:
    """Generate 6-8 active recall flashcards from study notes using Google Gemini."""
    if not context_docs:
        raise ValueError("Cannot generate flashcards with empty context documents.")

    context_str = _format_context(context_docs)
    user_prompt = f"Study Notes Context:\n\n{context_str}\n\nTask: Generate 6 to 8 active recall flashcards based on these notes."

    logger.info("gemini.generate_flashcards_start", doc_count=len(context_docs))
    data = await _call_gemini_json(user_prompt, _FLASHCARD_SYSTEM_PROMPT)

    if "cards" not in data and "flashcards" in data:
        data = {"cards": data["flashcards"]}

    deck = FlashcardDeck.model_validate(data)
    logger.info("gemini.generate_flashcards_success", card_count=len(deck.cards))
    return deck
