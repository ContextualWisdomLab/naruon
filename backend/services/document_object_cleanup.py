"""Retryable cleanup for consumed workspace-document source objects.

NewsDOM recognition commits parsed document content together with an S3 object
lifecycle transition from ``active`` to ``consumed``. This module performs the
separate, retryable remote-delete phase. Each object is committed independently
so one unavailable object store request cannot starve later cleanup work, and a
failed database commit remains safe to retry because S3 DELETE is idempotent.
"""

from __future__ import annotations

from dataclasses import dataclass
import logging

from sqlalchemy import select

from db.document_object_record import DocumentObjectRecord
import services.document_object_storage as document_storage

# Public compatibility alias used by the cleanup contract and its tests.
DocumentObjectStorageError = document_storage.DocumentObjectStorageError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DocumentObjectCleanupResult:
    """Summarize one bounded consumed-object cleanup sweep."""

    selected_count: int
    deleted_count: int
    failed_count: int


async def sweep_consumed_document_objects(
    session,
    *,
    batch_limit: int,
) -> DocumentObjectCleanupResult:
    """Delete a bounded batch of consumed S3 source objects without starvation.

    Candidate identifiers are selected first, then each row is reloaded before
    deletion. Reloading prevents stale selection state from deleting a row that
    another safe actor already completed. A remote-delete or database-commit
    failure is rolled back for that object and the sweep continues with later
    candidates; the row therefore remains retryable on a future sweep.
    """
    result = await session.execute(
        select(DocumentObjectRecord.document_object_record_id)
        .where(DocumentObjectRecord.storage_state == "consumed")
        .order_by(DocumentObjectRecord.document_object_record_id)
        .limit(batch_limit)
    )
    selected_ids = list(result.scalars().all())
    deleted_count = 0
    failed_count = 0

    for record_id in selected_ids:
        record = await session.get(DocumentObjectRecord, record_id)
        if record is None or record.storage_state != "consumed":
            continue
        try:
            await document_storage.delete_consumed_document_payload(record)
            await session.commit()
        except Exception:
            failed_count += 1
            await session.rollback()
            logger.warning(
                "Consumed document object cleanup failed for record %s; "
                "leaving it retryable.",
                record_id,
                exc_info=True,
            )
            continue
        deleted_count += 1

    return DocumentObjectCleanupResult(
        selected_count=len(selected_ids),
        deleted_count=deleted_count,
        failed_count=failed_count,
    )
