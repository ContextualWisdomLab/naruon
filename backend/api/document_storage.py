"""S3-aware workspace PDF upload route.

The broader data router remains responsible for data-quality and document
workflow surfaces. This module owns only the raw-PDF persistence boundary so
object-storage policy can evolve independently without duplicating tenant or
workflow authority.
"""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import AuthContext, get_auth_context
from api.data import DataDocumentActionResponse, _document_response, _safe_display_text
from db.document_object_record import DocumentObjectRecord
from db.models import Document
from db.session import get_db
from services.document_object_storage import (
    MAX_PDF_DOCUMENT_BYTES,
    DocumentObjectStorageError,
    StoredDocumentPayload,
    delete_configured_document_payload,
    store_configured_pdf_document,
)
from services.newsdom_pdf_recognition import PDF_DOM_RECOGNITION_PENDING_STATUS

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/data", tags=["data"])
PDF_UPLOAD_ROUTE_PATH = "/api/data/documents/pdf-dom-recognition"


def remove_legacy_pdf_upload_route(data_router: APIRouter) -> bool:
    """Remove the legacy inline-PDF route from a data router exactly once.

    ``api.data`` still carries the backward-compatible implementation for direct
    callers and old unit tests. Runtime composition removes that route before
    registering this S3-aware replacement, preventing duplicate FastAPI routes
    while keeping the rest of the large data surface unchanged.
    """
    matching_routes = [
        route
        for route in data_router.routes
        if getattr(route, "path", None) == PDF_UPLOAD_ROUTE_PATH
        and "POST" in (getattr(route, "methods", set()) or set())
    ]
    if len(matching_routes) > 1:
        raise RuntimeError("Multiple legacy PDF upload routes are registered")
    if not matching_routes:
        return False
    data_router.routes.remove(matching_routes[0])
    return True


async def _compensate_failed_metadata_commit(stored: StoredDocumentPayload) -> None:
    """Best-effort delete a just-written object after relational commit failure."""
    try:
        await delete_configured_document_payload(stored)
    except DocumentObjectStorageError:
        logger.error(
            "Document object compensation failed after metadata commit failure",
            exc_info=True,
        )


@router.post(
    "/documents/pdf-dom-recognition",
    response_model=DataDocumentActionResponse,
)
async def upload_document_for_pdf_dom_recognition(
    file: UploadFile = File(...),
    document_name: str | None = Form(None),
    auth_context: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
) -> DataDocumentActionResponse:
    """Persist a bounded PDF and queue NewsDOM recognition safely.

    The database backend preserves the existing base64 contract for deployments
    that have not opted into object storage. The S3 backend writes raw bytes once
    and stores only normalized locator/integrity metadata in PostgreSQL.
    """
    raw = await file.read(MAX_PDF_DOCUMENT_BYTES + 1)
    if len(raw) > MAX_PDF_DOCUMENT_BYTES:
        raise HTTPException(status_code=413, detail="PDF upload is too large.")
    if not raw.startswith(b"%PDF-"):
        raise HTTPException(
            status_code=415,
            detail="Only application/pdf uploads are supported for DOM recognition.",
        )

    document_id = f"doc_{uuid.uuid4().hex}"
    try:
        stored_payload = await store_configured_pdf_document(
            payload=raw,
            document_id=document_id,
            organization_id=auth_context.organization_id,
            workspace_id=auth_context.workspace_id,
        )
    except DocumentObjectStorageError as exc:
        raise HTTPException(
            status_code=503,
            detail="Configured document storage is unavailable.",
        ) from exc

    document = Document(
        document_id=document_id,
        workspace_id=auth_context.workspace_id,
        organization_id=auth_context.organization_id,
        document_name=_safe_display_text(
            document_name or file.filename,
            "workspace document",
        ),
        document_type="pdf",
        document_content=stored_payload.document_content,
        document_status=PDF_DOM_RECOGNITION_PENDING_STATUS,
    )
    object_record: DocumentObjectRecord | None = stored_payload.to_object_record(
        document_id
    )

    try:
        db.add(document)
        if object_record is not None:
            db.add(object_record)
        await db.commit()
        await db.refresh(document)
    except Exception:
        await db.rollback()
        await _compensate_failed_metadata_commit(stored_payload)
        raise

    return _document_response(
        document,
        audit_event="data.document.pdf_dom_recognition_upload",
        message=(
            "PDF stored in the configured document backend pending NewsDOM DOM "
            "recognition; no provider write executed."
        ),
    )
