"""S3-aware workspace PDF persistence and deletion routes.

The broader data router remains responsible for data-quality and document
workflow surfaces. This module owns only the raw-PDF persistence boundary so
object-storage policy can evolve independently without duplicating tenant or
workflow authority.
"""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api import data as data_api
from api.auth import AuthContext, get_auth_context
from api.data import DataDocumentActionResponse, _document_response, _safe_display_text
from db.document_object_record import DocumentObjectRecord
from db.models import Document
from db.session import get_db
from services.document_object_storage import (
    DocumentObjectStorageError,
    StoredDocumentPayload,
    delete_configured_document_payload,
    delete_document_object_record,
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

    The replacement route deliberately reads the legacy data-router limit at
    request time so existing deployments and tests that tighten that boundary
    continue to exercise the same fail-closed size policy after runtime routing.
    """
    upload_limit_bytes = data_api._MAX_PDF_DOM_UPLOAD_BYTES
    raw = await file.read(upload_limit_bytes + 1)
    if len(raw) > upload_limit_bytes:
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


@router.delete(
    "/documents/{document_id}",
    response_model=DataDocumentActionResponse,
)
async def delete_workspace_document(
    document_id: str,
    auth_context: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
) -> DataDocumentActionResponse:
    """Delete one workspace-scoped document and its raw S3 source when present.

    Authorization is established from the signed workspace before object metadata
    is read. For S3-backed documents, remote deletion happens first; the owning
    relational row is deleted only after that succeeds. If the database commit
    later fails, the surviving locator makes the idempotent S3 DELETE retryable.
    Inline-database documents have no object row and are removed relationally.
    """
    document = await data_api._get_workspace_document(
        db,
        auth_context,
        document_id,
    )
    object_record = await db.scalar(
        select(DocumentObjectRecord).where(
            DocumentObjectRecord.document_id == document.document_id
        )
    )

    if object_record is not None:
        try:
            await delete_document_object_record(object_record)
        except DocumentObjectStorageError as exc:
            await db.rollback()
            raise HTTPException(
                status_code=503,
                detail="Configured document storage is unavailable.",
            ) from exc

    response = DataDocumentActionResponse(
        document_id=document.document_id,
        workspace_id=document.workspace_id,
        document_name=document.document_name,
        document_type=document.document_type,
        document_status="deleted",
        content_chars=0,
        provider_write_executed=False,
        provenance="server-authoritative",
        audit_event="data.document.deleted",
        message=(
            "Document deleted from this workspace. Upload a new copy if you need "
            "to process it again."
        ),
    )
    try:
        await db.delete(document)
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    return response
