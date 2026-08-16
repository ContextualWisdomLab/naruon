"""Transactional migration of legacy inline pending PDFs into configured S3.

The backfill is intentionally bounded and retryable. PostgreSQL remains the
source of truth for document ownership and workflow state; raw bytes move to S3
only after the object write succeeds, and the inline payload is cleared only in
the same transaction that inserts normalized object metadata. A failed metadata
commit compensates the just-written remote object before the row is retried.
"""

from __future__ import annotations

from dataclasses import dataclass
import logging

from sqlalchemy import select

from core.object_storage_config import object_storage_settings as settings
from db.document_object_record import DocumentObjectRecord
from db.models import Document
from db.session import AsyncSessionLocal
from services.document_object_storage import (
    DocumentObjectStorageError,
    StoredDocumentPayload,
    decode_legacy_pdf_payload,
    delete_configured_document_payload,
    store_configured_pdf_document,
)
from services.newsdom_pdf_recognition import PDF_DOM_RECOGNITION_PENDING_STATUS

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DocumentObjectBackfillResult:
    """Summarize one bounded legacy-payload migration sweep."""

    selected_count: int
    migrated_count: int
    failed_count: int


@dataclass(frozen=True)
class DocumentObjectBackfillRunResult:
    """Summarize one bounded operator backfill run across fresh sessions."""

    completed: bool
    batch_count: int
    selected_count: int
    migrated_count: int
    failed_count: int


async def _compensate_backfill_object(stored: StoredDocumentPayload) -> None:
    """Best-effort delete an S3 object whose relational migration did not commit."""
    try:
        await delete_configured_document_payload(stored)
    except DocumentObjectStorageError:
        logger.error(
            "Document object backfill compensation failed; orphan reconciliation "
            "must retain this object for operator recovery.",
            exc_info=True,
        )


async def backfill_legacy_document_payloads(
    session,
    *,
    batch_limit: int,
) -> DocumentObjectBackfillResult:
    """Move a bounded batch of legacy pending PDF payloads into S3 safely.

    Only pending PDF rows with non-empty inline content are candidates. Each
    candidate is reloaded and checked for pre-existing object metadata before
    any remote write, preventing an ambiguous SQL/S3 split-brain row from being
    overwritten. Successful migrations commit independently so one corrupt row
    or transient object-store failure cannot starve later documents.
    """
    if batch_limit <= 0:
        raise ValueError("Document object backfill batch_limit must be positive")
    if settings.OBJECT_STORAGE_BACKEND != "s3":
        raise DocumentObjectStorageError(
            "Document object backfill requires the S3 backend"
        )

    result = await session.execute(
        select(Document.document_id)
        .where(
            Document.document_type == "pdf",
            Document.document_status == PDF_DOM_RECOGNITION_PENDING_STATUS,
            Document.document_content.is_not(None),
            Document.document_content != "",
        )
        .order_by(Document.document_id)
        .limit(batch_limit)
    )
    selected_ids = list(result.scalars().all())
    migrated_count = 0
    failed_count = 0

    for document_id in selected_ids:
        document = await session.get(Document, document_id)
        if (
            document is None
            or document.document_type != "pdf"
            or document.document_status != PDF_DOM_RECOGNITION_PENDING_STATUS
            or not document.document_content
        ):
            continue

        original_content = document.document_content
        stored_payload: StoredDocumentPayload | None = None
        try:
            existing_record = await session.scalar(
                select(DocumentObjectRecord).where(
                    DocumentObjectRecord.document_id == document_id
                )
            )
            if existing_record is not None:
                raise DocumentObjectStorageError(
                    "Legacy document already has object metadata; refusing split-brain backfill"
                )

            payload = decode_legacy_pdf_payload(original_content)
            stored_payload = await store_configured_pdf_document(
                payload=payload,
                document_id=document.document_id,
                organization_id=document.organization_id,
                workspace_id=document.workspace_id,
            )
            object_record = stored_payload.to_object_record(document.document_id)
            if stored_payload.storage_backend != "s3" or object_record is None:
                raise DocumentObjectStorageError(
                    "Document object backfill did not produce S3 metadata"
                )

            session.add(object_record)
            document.document_content = None
            await session.commit()
        except Exception:
            failed_count += 1
            await session.rollback()
            document.document_content = original_content
            if stored_payload is not None and stored_payload.s3_object is not None:
                await _compensate_backfill_object(stored_payload)
            logger.warning(
                "Document object backfill failed for %s; leaving the inline payload "
                "retryable.",
                document_id,
                exc_info=True,
            )
            continue
        migrated_count += 1

    return DocumentObjectBackfillResult(
        selected_count=len(selected_ids),
        migrated_count=migrated_count,
        failed_count=failed_count,
    )


async def run_document_object_backfill_batches(
    *,
    batch_limit: int,
    max_batches: int,
    session_factory=AsyncSessionLocal,
) -> DocumentObjectBackfillRunResult:
    """Run a bounded operator migration until an empty batch proves completion.

    Every batch receives a fresh database session so transaction state and
    identity-map contents cannot leak across retries. The explicit batch budget
    prevents a persistently failing legacy row from creating an unbounded
    operator process. ``completed`` is true only after a subsequent empty batch
    proves that no eligible inline payload remains at that instant.
    """
    if batch_limit <= 0:
        raise ValueError("Document object backfill batch_limit must be positive")
    if max_batches <= 0:
        raise ValueError("Document object backfill max_batches must be positive")

    selected_count = 0
    migrated_count = 0
    failed_count = 0

    for batch_count in range(1, max_batches + 1):
        async with session_factory() as session:
            batch_result = await backfill_legacy_document_payloads(
                session,
                batch_limit=batch_limit,
            )

        selected_count += batch_result.selected_count
        migrated_count += batch_result.migrated_count
        failed_count += batch_result.failed_count
        if batch_result.selected_count == 0:
            return DocumentObjectBackfillRunResult(
                completed=True,
                batch_count=batch_count,
                selected_count=selected_count,
                migrated_count=migrated_count,
                failed_count=failed_count,
            )

    return DocumentObjectBackfillRunResult(
        completed=False,
        batch_count=max_batches,
        selected_count=selected_count,
        migrated_count=migrated_count,
        failed_count=failed_count,
    )
