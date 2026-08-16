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

from sqlalchemy import or_, select

from db.document_object_record import DocumentObjectRecord
from db.object_storage_cleanup_record import ObjectStorageCleanupRecord
from db.session import AsyncSessionLocal
import services.document_object_storage as document_storage
from services.s3_object_storage import S3StoredObject

logger = logging.getLogger(__name__)
_MAX_RETRY_DELAY_SECONDS = 60 * 60


@dataclass(frozen=True)
class ObjectStorageOrphanCleanupResult:
    """Summarize one bounded orphan cleanup sweep."""

    selected_count: int
    deleted_count: int
    failed_count: int


def _utc_now() -> datetime.datetime:
    """Return an aware UTC time for durable retry and terminal-state metadata."""
    return datetime.datetime.now(datetime.timezone.utc)


def _retry_delay(attempt_count: int) -> datetime.timedelta:
    """Return bounded exponential backoff without introducing random scheduler state."""
    exponent = min(max(attempt_count, 1), 12)
    seconds = min(2**exponent, _MAX_RETRY_DELAY_SECONDS)
    return datetime.timedelta(seconds=seconds)


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
        raise document_storage.DocumentObjectStorageError(
            "Object-storage orphan metadata failed validation"
        ) from exc
    return document_storage.StoredDocumentPayload.for_s3(
        stored_object,
        object_storage_provider_id=record.object_storage_provider_id,
    )


async def resolve_explicit_s3_provider_runtime_config(
    session,
    organization_id: str,
    *,
    object_storage_provider_id: int,
):
    """Resolve exactly the retained provider revision used by an orphan locator."""
    return await document_storage._resolve_s3_provider_runtime_config(
        session,
        organization_id,
        object_storage_provider_id=object_storage_provider_id,
    )


async def cancel_matching_object_storage_cleanup(
    session,
    *,
    object_storage_provider_id: int,
    stored_object: S3StoredObject,
) -> ObjectStorageCleanupRecord | None:
    """Cancel a stale orphan row when its exact object becomes live metadata again."""
    result = await session.execute(
        select(ObjectStorageCleanupRecord.object_storage_cleanup_record_id)
        .where(
            ObjectStorageCleanupRecord.object_storage_provider_id
            == object_storage_provider_id,
            ObjectStorageCleanupRecord.bucket_name == stored_object.bucket_name,
            ObjectStorageCleanupRecord.object_key == stored_object.object_key,
            ObjectStorageCleanupRecord.cleanup_status == "pending",
        )
        .limit(1)
        .with_for_update()
    )
    record_ids = list(result.scalars().all())
    if not record_ids:
        return None
    record = await session.get(ObjectStorageCleanupRecord, record_ids[0])
    if record is None or record.cleanup_status != "pending":
        return None
    record.cleanup_status = "cancelled"
    record.completed_at = _utc_now()
    record.next_attempt_at = None
    return record


async def _live_document_reference(
    session,
    record: ObjectStorageCleanupRecord,
) -> DocumentObjectRecord | None:
    """Return a live SQL locator that makes destructive orphan cleanup unsafe."""
    candidate = await session.scalar(
        select(DocumentObjectRecord)
        .where(
            DocumentObjectRecord.object_storage_provider_id
            == record.object_storage_provider_id,
            DocumentObjectRecord.bucket_name == record.bucket_name,
            DocumentObjectRecord.object_key == record.object_key,
        )
        .limit(1)
    )
    return candidate if isinstance(candidate, DocumentObjectRecord) else None


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
    """Retry a bounded set of due provider-bound orphan deletions safely."""
    if batch_limit <= 0:
        raise ValueError("Object storage orphan cleanup batch_limit must be positive")

    now = _utc_now()
    result = await session.execute(
        select(ObjectStorageCleanupRecord.object_storage_cleanup_record_id)
        .where(
            ObjectStorageCleanupRecord.cleanup_status == "pending",
            or_(
                ObjectStorageCleanupRecord.next_attempt_at.is_(None),
                ObjectStorageCleanupRecord.next_attempt_at <= now,
            ),
        )
        .order_by(
            ObjectStorageCleanupRecord.next_attempt_at,
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

        live_reference = await _live_document_reference(session, record)
        if live_reference is not None:
            record.cleanup_status = "cancelled"
            record.completed_at = _utc_now()
            record.next_attempt_at = None
            await session.commit()
            continue

        attempt_started_at = _utc_now()
        attempt_count = (record.attempt_count or 0) + 1
        try:
            runtime_config = await resolve_explicit_s3_provider_runtime_config(
                session,
                record.organization_id,
                object_storage_provider_id=record.object_storage_provider_id,
            )
            record.attempt_count = attempt_count
            record.last_attempt_at = attempt_started_at
            await delete_orphan_cleanup_record(record, runtime_config=runtime_config)
            record.cleanup_status = "completed"
            record.completed_at = _utc_now()
            record.next_attempt_at = None
            await session.commit()
        except Exception:
            failed_count += 1
            await session.rollback()
            retry_record = await session.get(
                ObjectStorageCleanupRecord,
                cleanup_record_id,
            )
            if retry_record is not None and retry_record.cleanup_status == "pending":
                retry_record.attempt_count = attempt_count
                retry_record.last_attempt_at = attempt_started_at
                retry_record.next_attempt_at = attempt_started_at + _retry_delay(
                    attempt_count
                )
                await session.commit()
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
