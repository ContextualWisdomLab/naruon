"""Durable retry worker for S3 objects left after failed compensation.

A metadata transaction may fail after immutable object creation, and the
best-effort compensating DELETE can fail independently. In that case Naruon
records the provider-bound locator and integrity metadata in
``object_storage_cleanup_records``. This worker retries only those explicit
locators; it never requires or performs bucket enumeration.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import datetime
import logging

from sqlalchemy import select

from db.object_storage_cleanup_record import ObjectStorageCleanupRecord
from db.session import AsyncSessionLocal
import services.document_object_storage as document_storage
from services.document_object_storage import DocumentObjectStorageError
from services.s3_object_storage import S3StoredObject

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ObjectStorageOrphanCleanupResult:
    """Summarize one bounded orphan cleanup sweep."""

    selected_count: int
    deleted_count: int
    failed_count: int


def _stored_payload(record: ObjectStorageCleanupRecord):
    """Build a validated provider-bound payload handle from one cleanup row."""
    try:
        stored_object = S3StoredObject(
            bucket_name=record.bucket_name,
            object_key=record.object_key,
            content_type=record.content_type,
            content_length=record.content_length,
            checksum_sha256=record.checksum_sha256,
        )
    except ValueError as exc:
        raise DocumentObjectStorageError(
            "Object-storage orphan metadata failed validation"
        ) from exc
    return document_storage.StoredDocumentPayload.for_s3(
        stored_object,
        object_storage_provider_id=record.object_storage_provider_id,
    )


async def delete_orphan_cleanup_record(
    record: ObjectStorageCleanupRecord,
    *,
    runtime_config: document_storage.DocumentStorageRuntimeConfig,
) -> None:
    """Delete one orphan through the exact provider authority retained by its row."""
    await document_storage.delete_configured_document_payload(
        _stored_payload(record),
        runtime_config=runtime_config,
    )


async def sweep_object_storage_orphans(
    session,
    *,
    batch_limit: int,
) -> ObjectStorageOrphanCleanupResult:
    """Retry a bounded set of pending provider-bound orphan deletions."""
    if batch_limit <= 0:
        raise ValueError("Object storage orphan cleanup batch_limit must be positive")

    result = await session.execute(
        select(ObjectStorageCleanupRecord.object_storage_cleanup_record_id)
        .where(ObjectStorageCleanupRecord.cleanup_status == "pending")
        .order_by(
            ObjectStorageCleanupRecord.created_at,
            ObjectStorageCleanupRecord.object_storage_cleanup_record_id,
        )
        .limit(batch_limit)
    )
    selected_ids = list(result.scalars().all())
    deleted_count = 0
    failed_count = 0

    for cleanup_record_id in selected_ids:
        record = await session.get(ObjectStorageCleanupRecord, cleanup_record_id)
        if record is None or record.cleanup_status != "pending":
            continue
        try:
            runtime_config = await document_storage._resolve_s3_provider_runtime_config(
                session,
                record.organization_id,
                object_storage_provider_id=record.object_storage_provider_id,
            )
            record.attempt_count += 1
            record.last_attempt_at = datetime.datetime.now(datetime.timezone.utc)
            await delete_orphan_cleanup_record(record, runtime_config=runtime_config)
            record.cleanup_status = "completed"
            record.completed_at = datetime.datetime.now(datetime.timezone.utc)
            await session.commit()
        except Exception:
            failed_count += 1
            await session.rollback()
            logger.warning(
                "Object-storage orphan cleanup failed; leaving the locator retryable.",
                exc_info=True,
            )
            continue
        deleted_count += 1

    return ObjectStorageOrphanCleanupResult(
        selected_count=len(selected_ids),
        deleted_count=deleted_count,
        failed_count=failed_count,
    )


class ObjectStorageOrphanCleanupWorker:
    """Continuously retry explicit orphan locators in bounded database sessions."""

    def __init__(
        self,
        *,
        interval_seconds: float = 60.0,
        batch_limit: int = 25,
        session_factory=AsyncSessionLocal,
    ) -> None:
        """Create a worker with finite polling and query bounds."""
        if interval_seconds <= 0:
            raise ValueError("Object storage orphan cleanup interval_seconds must be positive")
        if batch_limit <= 0:
            raise ValueError("Object storage orphan cleanup batch_limit must be positive")
        self.interval_seconds = interval_seconds
        self.batch_limit = batch_limit
        self.session_factory = session_factory
        self._task: asyncio.Task | None = None
        self._is_running = False

    async def start(self) -> None:
        """Start exactly one orphan cleanup loop for this worker instance."""
        if self._is_running:
            logger.warning("ObjectStorageOrphanCleanupWorker is already running.")
            return
        self._is_running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info("ObjectStorageOrphanCleanupWorker started.")

    async def stop(self) -> None:
        """Cancel the orphan cleanup loop and tolerate normal task cancellation."""
        if not self._is_running:
            return
        self._is_running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                logger.debug(
                    "ObjectStorageOrphanCleanupWorker cancellation acknowledged."
                )
        logger.info("ObjectStorageOrphanCleanupWorker stopped.")

    async def _run_loop(self) -> None:
        """Keep future sweeps alive after transient database or provider failures."""
        while self._is_running:
            try:
                await self._sync()
            except asyncio.CancelledError:
                break
            except Exception:
                logger.error("Error in ObjectStorageOrphanCleanupWorker loop", exc_info=True)
            if self._is_running:
                try:
                    await asyncio.sleep(self.interval_seconds)
                except asyncio.CancelledError:
                    break

    async def _sync(self) -> ObjectStorageOrphanCleanupResult:
        """Run one bounded sweep in a fresh database session."""
        async with self.session_factory() as session:
            return await sweep_object_storage_orphans(
                session,
                batch_limit=self.batch_limit,
            )
