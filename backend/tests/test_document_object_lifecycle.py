"""Regression contracts for retriable S3 document-object lifecycle cleanup."""

from __future__ import annotations

import hashlib

import pytest

from db.document_object_record import DocumentObjectRecord
import services.document_object_storage as storage_module
from services.s3_object_storage import S3StoredObject


PDF_BYTES = b"%PDF-1.7 lifecycle"


class LifecycleSession:
    """Minimal async scalar session returning one lifecycle record."""

    def __init__(self, record: DocumentObjectRecord | None) -> None:
        self.record = record
        self.scalar_calls = 0

    async def scalar(self, _statement):
        self.scalar_calls += 1
        return self.record


class DeleteBackend:
    """Capture remote deletion without making a network request."""

    def __init__(self) -> None:
        self.deleted: list[S3StoredObject] = []
        self.closed = False

    async def delete_object(self, stored_object: S3StoredObject) -> None:
        self.deleted.append(stored_object)

    async def aclose(self) -> None:
        self.closed = True


def _record(*, state: str = "active") -> DocumentObjectRecord:
    return DocumentObjectRecord(
        document_id="doc-1",
        storage_backend="s3",
        bucket_name="naruon-documents",
        object_key="workspace-documents/abc/doc-1/source.pdf",
        content_type="application/pdf",
        content_length=len(PDF_BYTES),
        checksum_sha256=hashlib.sha256(PDF_BYTES).hexdigest(),
        storage_state=state,
    )


@pytest.mark.asyncio
async def test_mark_consumed_is_idempotent_and_records_consumption_time() -> None:
    record = _record()
    session = LifecycleSession(record)

    first = await storage_module.mark_document_payload_consumed(session, "doc-1")
    consumed_at = record.consumed_at
    second = await storage_module.mark_document_payload_consumed(session, "doc-1")

    assert first is record
    assert second is record
    assert record.storage_state == "consumed"
    assert consumed_at is not None
    assert record.consumed_at == consumed_at
    assert record.deleted_at is None
    assert session.scalar_calls == 2


@pytest.mark.asyncio
async def test_mark_consumed_has_no_object_record_for_legacy_database_payload() -> None:
    session = LifecycleSession(None)

    assert await storage_module.mark_document_payload_consumed(session, "doc-1") is None
    assert session.scalar_calls == 1


@pytest.mark.asyncio
async def test_delete_consumed_object_marks_deleted_only_after_remote_success(
    monkeypatch,
) -> None:
    record = _record(state="consumed")
    record.consumed_at = storage_module._utc_now()
    backend = DeleteBackend()

    async def build_backend():
        return backend

    monkeypatch.setattr(storage_module, "_build_s3_backend_from_settings", build_backend)

    await storage_module.delete_consumed_document_payload(record)

    assert len(backend.deleted) == 1
    assert backend.deleted[0].object_key == record.object_key
    assert backend.closed is True
    assert record.storage_state == "deleted"
    assert record.deleted_at is not None
    assert record.deleted_at >= record.consumed_at


@pytest.mark.asyncio
async def test_delete_consumed_object_fails_closed_before_remote_delete(monkeypatch) -> None:
    record = _record(state="active")

    async def fail_builder():  # pragma: no cover - lifecycle validation must fail first
        raise AssertionError("active objects must not be deleted")

    monkeypatch.setattr(storage_module, "_build_s3_backend_from_settings", fail_builder)

    with pytest.raises(storage_module.DocumentObjectStorageError, match="consumed"):
        await storage_module.delete_consumed_document_payload(record)

    assert record.storage_state == "active"
    assert record.deleted_at is None
