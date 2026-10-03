"""
app/services/file_store.py
---------------------------
On-disk store for original uploaded PDFs, used by the citation page preview.

Layout: {upload_dir}/{sha256(session_id)}/{sha256(doc_id)}.pdf

Both path segments are hashes, so user-controlled values (filenames,
session ids, doc ids) never reach the filesystem path directly, and a file
can only be resolved through the session that uploaded it.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Optional

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _pdf_path(session_id: str, doc_id: str) -> Path:
    root = Path(get_settings().upload_dir)
    return root / _digest(session_id) / f"{_digest(doc_id)}.pdf"


def save_pdf(session_id: str, doc_id: str, data: bytes) -> None:
    """Persist the original PDF bytes (no-op if already stored)."""
    path = _pdf_path(session_id, doc_id)
    if path.exists():
        return
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_bytes(data)
        tmp.replace(path)
    except OSError as exc:
        logger.warning("file_store.save_failed", doc_id=doc_id, error=str(exc))


def get_pdf_path(session_id: str, doc_id: str) -> Optional[Path]:
    """Return the stored PDF for this session's document, or None."""
    path = _pdf_path(session_id, doc_id)
    return path if path.is_file() else None


def delete_pdf(session_id: str, doc_id: str) -> None:
    try:
        _pdf_path(session_id, doc_id).unlink(missing_ok=True)
    except OSError as exc:
        logger.warning("file_store.delete_failed", doc_id=doc_id, error=str(exc))
