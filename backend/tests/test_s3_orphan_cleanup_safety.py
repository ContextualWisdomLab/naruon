"""Safety contracts for adopting and retrying durable S3 orphan cleanup rows."""

from __future__ import annotations

import datetime
from types import SimpleNamespace

import pytest
from sqlalchemy import BigInteger

from db.document_object_record import DocumentObjectRecord
from db.object_storage_cleanup_record import ObjectStorageCleanupRecord
import services.object_storage_orphan_cleanup as cleanup_module
from services.s3_object_storage import S3StoredObject


class _Rows:
    """Expose selected cleanup identifiers through SQLAlchemy-like methods."""

    def __init__(self, values) -> None:
        self.values = list(values)

    def scalars(self):
        return self

    def all(self):
        return list(self.values)


class _SafetySession:
    """Track cancellation, defensive-reference checks, and retry commits."""

    def __init__(
        self,
        cleanup: ObjectStorageCleanupRecord,
        *,
        live_reference: DocumentObjectRecord | None = None,
    ) -> None:
        self.cleanup = cleanup
        self.live_reference = live_reference
        self.execute_count = 0
        self.get_count = 0
        self.scalar_count = 0
        self.commits = 0
        self.rollbacks = 0

    async def execute(self, _statement):
        self.execute_count += 1
        return _Rows([self.cleanup.object_storage_cleanup_record_id])

    async def get(self, model, record_id):
        assert model is ObjectStorageCleanupRecord
        assert record_id == self.cleanup.object_storage_cleanup_record_id
        self.get_count += 1
        return self.cleanup

    async def scalar(self, _statement):
        self.scalar_count += 1
        return self.live_reference

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def _cleanup() -> ObjectStorageCleanupRecord:
    return ObjectStorageCleanupRecord(
        object_storage_cleanup_record_id=11,
        object_storage_provider_id=77,
        organization_id="organization-one",
        bucket_name="naruon-documents",
        object_key="workspace-documents/scope/document/source.pdf",
        content_type="application/pdf",
        content_length=29,
        checksum_sha256="a" * 64,
        cleanup_reason="metadata_commit_compensation_failed",
        cleanup_status="pending",
        attempt_count=0,
        next_attempt_at=_now(),
        created_at=_now(),
    )


def _stored_object() -> S3StoredObject:
    return S3StoredObject(
        bucket_name="naruon-documents",
        object_key="workspace-documents/scope/document/source.pdf",
        content_type="application/pdf",
        content_length=29,
        checksum_sha256="a" * 64,
    )


def _live_object() -> DocumentObjectRecord:
    return DocumentObjectRecord(
        document_object_record_id=5,
        document_id="document-one",
        object_storage_provider_id=77,
        storage_backend="s3",
        bucket_name="naruon-documents",
        object_key="workspace-documents/scope/document/source.pdf",
        inline_payload=None,
        content_type="application/pdf",
        content_length=29,
        checksum_sha256="a" * 64,
        storage_state="active",
    )


@pytest.mark.asyncio
async def test_successful_metadata_adoption_cancels_matching_cleanup_in_same_transaction():
    """A retried upload must cancel the stale orphan row before SQL commit."""
    cleanup = _cleanup()
    session = _SafetySession(cleanup)
    cancel = getattr(cleanup_module, "cancel_matching_object_storage_cleanup", None)
    assert callable(cancel), "orphan cleanup service must expose adoption cancellation"

    cancelled = await cancel(
        session,
        object_storage_provider_id=77,
        stored_object=_stored_object(),
    )

    assert cancelled is cleanup
    assert cleanup.cleanup_status == "cancelled"
    assert cleanup.completed_at is not None
    assert cleanup.next_attempt_at is None
    assert session.commits == 0
    assert session.rollbacks == 0


@pytest.mark.asyncio
async def test_cleanup_worker_never_deletes_locator_referenced_by_live_document(monkeypatch):
    """A defensive reference check must win even when adoption cancellation raced."""
    cleanup = _cleanup()
    session = _SafetySession(cleanup, live_reference=_live_object())
    delete_calls = 0

    async def forbidden_delete(*_args, **_kwargs):
        nonlocal delete_calls
        delete_calls += 1

    monkeypatch.setattr(cleanup_module, "delete_orphan_cleanup_record", forbidden_delete)

    result = await cleanup_module.sweep_object_storage_orphans(session, batch_limit=5)

    assert result == cleanup_module.ObjectStorageOrphanCleanupResult(1, 0, 0)
    assert delete_calls == 0
    assert cleanup.cleanup_status == "cancelled"
    assert cleanup.completed_at is not None
    assert cleanup.next_attempt_at is None
    assert session.commits == 1
    assert session.rollbacks == 0


@pytest.mark.asyncio
async def test_cleanup_failure_persists_attempt_count_and_bounded_backoff(monkeypatch):
    """Rollback the failed delete, then durably commit retry timing metadata."""
    cleanup = _cleanup()
    session = _SafetySession(cleanup)

    async def runtime(*_args, **_kwargs):
        return SimpleNamespace(object_storage_provider_id=77)

    async def failing_delete(*_args, **_kwargs):
        raise cleanup_module.DocumentObjectStorageError("temporary provider outage")

    monkeypatch.setattr(
        cleanup_module,
        "resolve_explicit_s3_provider_runtime_config",
        runtime,
    )
    monkeypatch.setattr(cleanup_module, "delete_orphan_cleanup_record", failing_delete)

    result = await cleanup_module.sweep_object_storage_orphans(session, batch_limit=5)

    assert result == cleanup_module.ObjectStorageOrphanCleanupResult(1, 0, 1)
    assert session.rollbacks == 1
    assert session.commits == 1
    assert cleanup.cleanup_status == "pending"
    assert cleanup.attempt_count == 1
    assert cleanup.last_attempt_at is not None
    assert cleanup.next_attempt_at is not None
    assert cleanup.next_attempt_at > cleanup.last_attempt_at
    assert cleanup.next_attempt_at - cleanup.last_attempt_at <= datetime.timedelta(hours=1)
    assert cleanup.completed_at is None


def test_cleanup_schema_supports_large_objects_due_time_and_cancelled_terminal_state():
    """The ORM must match durable queue size, due-time, and lifecycle contracts."""
    table = ObjectStorageCleanupRecord.__table__
    assert isinstance(table.c.content_length.type, BigInteger)
    assert "next_attempt_at" in table.c
    status_constraint = next(
        constraint
        for constraint in table.constraints
        if constraint.name == "ck_object_storage_cleanup_records_status"
    )
    assert "cancelled" in str(status_constraint.sqltext)
