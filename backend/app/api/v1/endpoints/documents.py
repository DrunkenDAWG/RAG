"""
app/api/v1/endpoints/documents.py
───────────────────────────────────
Document management endpoints:
  POST   /documents/upload   – ingest one or more files
  GET    /documents           – list all ingested documents
  DELETE /documents/{doc_id} – remove a document and its chunks
  GET    /documents/{doc_id}/file – stream the original PDF (session-scoped)
"""
from __future__ import annotations

from pathlib import Path
from typing import Annotated, List, Optional

from fastapi import APIRouter, File, Form, Header, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from app.api.deps import AuthDep
from app.core.logging import get_logger
from app.services.file_store import delete_pdf, get_pdf_path, save_pdf
from app.services.ingestion import (
    delete_document,
    get_session_collection,
    ingest_document,
)

logger = get_logger(__name__)
router = APIRouter(prefix="/documents", tags=["documents"])

MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB


# ── Schemas ───────────────────────────────────────────────────────────────────

class IngestResult(BaseModel):
    filename: str
    document_id: str
    chunk_count: int
    status: str
    warning: Optional[str] = None


class DocumentMeta(BaseModel):
    document_id: str
    filename: str
    chunk_count: int


class DeleteResult(BaseModel):
    document_id: str
    chunks_removed: int


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post(
    "/upload",
    response_model=List[IngestResult],
    status_code=status.HTTP_201_CREATED,
    summary="Upload and ingest one or more documents",
)
async def upload_documents(
    _: AuthDep,
    files: List[UploadFile] = File(..., description="PDF, DOCX, plain-text, or image (PNG/JPG/WEBP) files"),
    x_session_id: Annotated[Optional[str], Header(alias="X-Session-Id")] = None,
    session_id: Optional[str] = Form(None),
) -> List[IngestResult]:
    active_session_id = x_session_id or session_id or "default"
    results: List[IngestResult] = []
    for upload in files:
        data = await upload.read()

        if len(data) > MAX_FILE_SIZE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File '{upload.filename}' exceeds the 50 MB limit.",
            )

        try:
            summary = await ingest_document(
                filename=upload.filename or "unknown",
                data=data,
                session_id=active_session_id,
                extra_metadata={"content_type": upload.content_type or "application/octet-stream"},
            )
        except Exception as exc:
            logger.error("ingestion.failed", filename=upload.filename, error=str(exc))
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Failed to ingest '{upload.filename}': {exc}",
            )

        # Keep the original PDF so citations can preview the cited page
        if Path(upload.filename or "").suffix.lower() == ".pdf":
            await run_in_threadpool(save_pdf, active_session_id, summary["doc_id"], data)

        warning = None
        if summary.get("figures_failed"):
            warning = (
                f"{summary['figures_failed']} image(s) couldn't be converted to text "
                "(vision model unavailable). Delete and re-upload to retry."
            )
        results.append(
            IngestResult(
                filename=upload.filename or "unknown",
                document_id=summary["doc_id"],
                chunk_count=summary["chunk_count"],
                status=summary["status"],
                warning=warning,
            )
        )
    return results


@router.get(
    "",
    response_model=List[DocumentMeta],
    summary="List all ingested documents",
)
async def list_documents(
    _: AuthDep,
    x_session_id: Annotated[Optional[str], Header(alias="X-Session-Id")] = None,
) -> List[DocumentMeta]:
    active_session_id = x_session_id or "default"
    collection = get_session_collection(active_session_id)
    # Fetch all metadata (no embedding needed)
    result = collection.get(include=["metadatas"])
    if not result["metadatas"]:
        return []

    # Aggregate chunks per document_id
    doc_map: dict = {}
    for meta in result["metadatas"]:
        doc_id = meta.get("doc_id", "")
        filename = meta.get("filename", "")
        if doc_id not in doc_map:
            doc_map[doc_id] = {"filename": filename, "chunk_count": 0}
        doc_map[doc_id]["chunk_count"] += 1

    return [
        DocumentMeta(document_id=doc_id, filename=v["filename"], chunk_count=v["chunk_count"])
        for doc_id, v in doc_map.items()
    ]


@router.delete(
    "/{document_id}",
    response_model=DeleteResult,
    summary="Delete a document and all its chunks",
)
async def remove_document(
    _: AuthDep,
    document_id: str,
    x_session_id: Annotated[Optional[str], Header(alias="X-Session-Id")] = None,
) -> DeleteResult:
    active_session_id = x_session_id or "default"
    removed = await delete_document(session_id=active_session_id, doc_id=document_id)
    if removed == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document '{document_id}' not found.",
        )
    delete_pdf(active_session_id, document_id)
    return DeleteResult(document_id=document_id, chunks_removed=removed)


@router.get(
    "/{document_id}/file",
    response_class=FileResponse,
    summary="Stream an uploaded PDF belonging to the caller's session",
)
async def get_document_file(
    _: AuthDep,
    document_id: str,
    x_session_id: Annotated[str, Header(alias="X-Session-Id")],
) -> FileResponse:
    # Ownership: the doc must be indexed in this session's own collection,
    # and the file is resolved under this session's own storage directory.
    collection = get_session_collection(x_session_id)
    owned = collection.get(where={"doc_id": document_id}, limit=1, include=["metadatas"])
    path = get_pdf_path(x_session_id, document_id) if owned["ids"] else None
    if path is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document file not found.",
        )

    filename = (owned["metadatas"] or [{}])[0].get("filename") or "document.pdf"
    return FileResponse(
        path,
        media_type="application/pdf",
        content_disposition_type="inline",
        filename=filename,
        headers={
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )

