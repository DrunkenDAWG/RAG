"""
app/services/vision.py
-----------------------
Image → text conversion for ingestion, powered by Gemini's multimodal API.

Used for:
  - Figures, diagrams, charts and scanned tables embedded in PDFs.
  - Standalone image uploads (.png / .jpg / .jpeg / .webp).

Each image is turned into plain text (verbatim transcription of visible
text + a factual description of any diagram/chart) so it flows through
the normal chunk → embed → BM25 pipeline unchanged.

Degrades gracefully: with no GEMINI_API_KEY or on API failure, callers get
None and ingestion continues with the text layer only.
"""
from __future__ import annotations

import asyncio
import base64
import io
from typing import List, Optional

import httpx
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Primary model, then a lighter fallback used when the primary is overloaded
GEMINI_VISION_MODELS: tuple = ("gemini-flash-latest", "gemini-flash-lite-latest")
_GEMINI_URL: str = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
)

_MAX_SIDE_PX: int = 2048        # downscale larger images before upload
_MAX_CONCURRENCY: int = 4       # parallel Gemini calls per process
_DECORATIVE_SENTINEL: str = "NONE"

_semaphore: Optional[asyncio.Semaphore] = None

_VISION_PROMPT: str = (
    "You are converting an image from a study document into plain text for a "
    "search index.\n"
    "1. Transcribe ALL legible text exactly as written: labels, captions, "
    "headings, equations, code, and table cells (keep table rows on one line, "
    "cells separated by ' | ').\n"
    "2. If the image is a diagram, flowchart, chart, graph, table, or figure, "
    "describe its structure and meaning: the components, how they connect "
    "(arrows, layers, sequence), axes and units, trends, and what concept it "
    "illustrates.\n"
    "Be factual and concise. Do not speculate beyond what is visible. Output "
    "plain text only, no markdown headings.\n"
    f"If the image has no informational content (logo, icon, decorative "
    f"border, blank), reply with exactly: {_DECORATIVE_SENTINEL}"
)


class _RetryableVisionError(Exception):
    """Gemini rate-limit / transient server error."""


def vision_available() -> bool:
    settings = get_settings()
    return settings.vision_enabled and bool(settings.gemini_api_key)


def prepare_image(data: bytes) -> Optional[bytes]:
    """
    Normalise any Pillow-readable image to an RGB JPEG no larger than
    _MAX_SIDE_PX on its longest side. Returns None if undecodable or too
    small to carry information. CPU-bound — call via run_in_threadpool.
    """
    from PIL import Image

    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except Exception as exc:
        logger.debug("vision.image_decode_failed", error=str(exc))
        return None

    min_px = get_settings().vision_min_image_px
    if min(img.size) < min_px:
        return None

    if img.mode in ("RGBA", "LA", "P"):
        # Flatten transparency onto white so diagrams stay legible
        img = img.convert("RGBA")
        background = Image.new("RGB", img.size, (255, 255, 255))
        background.paste(img, mask=img.split()[-1])
        img = background
    elif img.mode != "RGB":
        img = img.convert("RGB")

    img.thumbnail((_MAX_SIDE_PX, _MAX_SIDE_PX))
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=90)
    return out.getvalue()


def _get_semaphore() -> asyncio.Semaphore:
    global _semaphore
    if _semaphore is None:
        _semaphore = asyncio.Semaphore(_MAX_CONCURRENCY)
    return _semaphore


async def _call_gemini(model: str, jpeg: bytes) -> str:
    settings = get_settings()
    payload = {
        "contents": [{
            "role": "user",
            "parts": [
                {"text": _VISION_PROMPT},
                {"inline_data": {
                    "mime_type": "image/jpeg",
                    "data": base64.b64encode(jpeg).decode("ascii"),
                }},
            ],
        }],
        "generationConfig": {
            "temperature": 0.0,
            "maxOutputTokens": 1024,
            # Transcription doesn't benefit from reasoning; ~2x faster without it
            "thinkingConfig": {"thinkingBudget": 0},
        },
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            _GEMINI_URL.format(model=model),
            json=payload,
            headers={"x-goog-api-key": settings.gemini_api_key},
        )

    if response.status_code == 429 or response.status_code >= 500:
        raise _RetryableVisionError(f"HTTP {response.status_code}")
    if response.status_code != 200:
        raise RuntimeError(f"HTTP {response.status_code}: {response.text[:200]}")

    parts = response.json()["candidates"][0]["content"]["parts"]
    return "".join(p.get("text", "") for p in parts).strip()


async def describe_image(jpeg: bytes) -> Optional[str]:
    """
    Convert one prepared image (see prepare_image) to text.
    Returns None for decorative images, when vision is unavailable, or on error.
    """
    if not vision_available():
        return None

    text = ""
    async with _get_semaphore():
        for model in GEMINI_VISION_MODELS:
            try:
                async for attempt in AsyncRetrying(
                    retry=retry_if_exception_type(
                        (_RetryableVisionError, httpx.TransportError)
                    ),
                    stop=stop_after_attempt(3),
                    wait=wait_exponential(multiplier=2, min=2, max=10),
                    reraise=True,
                ):
                    with attempt:
                        text = await _call_gemini(model, jpeg)
                break
            except Exception as exc:
                logger.warning("vision.describe_failed", model=model, error=str(exc)[:200])
        else:
            return None

    if not text or text.strip().upper().rstrip(".") == _DECORATIVE_SENTINEL:
        return None
    return text


async def describe_images(images: List[bytes]) -> List[Optional[str]]:
    """Describe many prepared images concurrently (bounded by a semaphore)."""
    if not images:
        return []
    results = await asyncio.gather(*(describe_image(img) for img in images))
    logger.info("vision.batch_done", images=len(images),
                described=sum(r is not None for r in results))
    return list(results)
