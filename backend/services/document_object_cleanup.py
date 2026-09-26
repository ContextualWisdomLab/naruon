"""Retryable cleanup for retained workspace-document source objects.

NewsDOM recognition commits parsed document content together with an S3 object
lifecycle transition from ``active`` to ``consumed``. Consumed source objects
remain available for the configured reprocessing-retention window before this
module performs the separate, retryable remote-delete phase through the provider
retained by each object record. Each object is committed independently so one
unavailable provider cannot starve later cleanup work.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import logging

from sqlalchemy import select

from core.object_storage_config import object_storage_settings
from db.document_object_record import DocumentObjectRecord
from db.models import Document
from db.session import AsyncSessionLocal
import services.document_object_storage as document_storage

DocumentObjectStorageError = document_storage.DocumentObjectStorageError
delete_consumed_document_payload = document_storage.delete_consumed_document_payload

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
    retention_seconds: int,
) -> DocumentObjectCleanupResult:
    """Delete retained consumed objects only after their reprocessing window.

    Candidate identifiers older than the retention cutoff are selected first,
    then each object and its owning document are reloaded before provider
    resolution. A remote-delete or database-commit failure is rolled back for
    that object and the sweep continues with later candidates; the row therefore
    remains retryable.
    """
    if batch_limit <= 0:
        raise ValueError("Document object cleanup batch_limit must be positive")
    if retention_seconds < 0:
        raise ValueError(
            "Document object cleanup retention_seconds must not be negative"
        )

    retention_cutoff = datetime.now(timezone.utc) - timedelta(
        seconds=retention_seconds
    )
    result = await session.execute(
        select(DocumentObjectRecord.document_object_record_id)
        .where(
            DocumentObjectRecord.storage_state == "consumed",
            DocumentObjectRecord.consumed_at <= retention_cutoff,
        )
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
            document = await session.get(Document, record.document_id)
            if document is None:
                raise DocumentObjectStorageError(
                    "Consumed document object has no owning document"
                )
            runtime_config = (
                await document_storage.resolve_document_object_runtime_config(
                    session,
                    document,
                    record,
                )
            )
            await delete_consumed_document_payload(
                record,
                runtime_config=runtime_config,
            )
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


class DocumentObjectCleanupWorker:
    """Continuously drain expired consumed document objects in bounded batches.

    The worker owns no business state: PostgreSQL lifecycle rows remain the
    durable retry queue. A fresh database session is opened for each sweep so a
    failed remote delete or stale connection cannot poison later iterations.
    """

    def __init__(
        self,
        *,
        interval_seconds: float = 60.0,
        batch_limit: int = 25,
        retention_seconds: int = (
            object_storage_settings.OBJECT_STORAGE_CONSUMED_RETENTION_SECONDS
        ),
        session_factory=AsyncSessionLocal,
    ) -> None:
        """Create a worker with finite polling, query, and retention bounds."""
        if interval_seconds <= 0:
            raise ValueError("Document object cleanup interval_seconds must be positive")
        if batch_limit <= 0:
            raise ValueError("Document object cleanup batch_limit must be positive")
        if retention_seconds < 0:
            raise ValueError(
                "Document object cleanup retention_seconds must not be negative"
            )
        self.interval_seconds = interval_seconds
        self.batch_limit = batch_limit
        self.retention_seconds = retention_seconds
        self.session_factory = session_factory
        self._task: asyncio.Task | None = None
        self._is_running = False

    async def start(self) -> None:
        """Start exactly one cleanup loop for this worker instance."""
        if self._is_running:
            logger.warning("DocumentObjectCleanupWorker is already running.")
            return
        self._is_running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info("DocumentObjectCleanupWorker started.")

    async def stop(self) -> None:
        """Cancel the cleanup loop and tolerate normal task cancellation."""
        if not self._is_running:
            return
        self._is_running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                logger.debug(
                    "DocumentObjectCleanupWorker cancellation acknowledged during shutdown."
                )
        logger.info("DocumentObjectCleanupWorker stopped.")

    async def _run_loop(self) -> None:
        """Keep later sweeps alive after one transient database/storage failure."""
        while self._is_running:
            try:
                await self._sync()
            except asyncio.CancelledError:
                break
            except Exception:
                logger.error("Error in DocumentObjectCleanupWorker loop", exc_info=True)

            if self._is_running:
                try:
                    await asyncio.sleep(self.interval_seconds)
                except asyncio.CancelledError:
                    break

    async def _sync(self) -> DocumentObjectCleanupResult:
        """Run one bounded sweep through an independently scoped database session."""
        async with self.session_factory() as session:
            return await sweep_consumed_document_objects(
                session,
                batch_limit=self.batch_limit,
                retention_seconds=self.retention_seconds,
            )
