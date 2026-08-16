"""Regression tests for retryable cleanup of consumed NewsDOM source objects.

Recognition commits parsed text and the ``consumed`` lifecycle marker before any
remote delete. These tests require a later cleanup sweep to delete consumed
objects and to keep failed deletes retryable without starving subsequent rows.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from db.document_object_record import DocumentObjectRecord
import services.document_object_cleanup as cleanup_module


class _ScalarRows:
    """Return a deterministic scalar list from a fake SQLAlchemy result."""

    def __init__(self, values):
        self._values = values

    def scalars(self):
        return self

    def all(self):
        return list(self._values)


class _CleanupSession:
    """Minimal session that survives per-object rollback boundaries."""

    def __init__(self, records: list[DocumentObjectRecord]) -> None:
        self.records = {record.document_object_record_id: record for record in records}
        self.commits = 0
        self.rollbacks = 0
        self.execute_calls = 0
        self.get_calls: list[int] = []

    async def execute(self, _statement):
        self.execute_calls += 1
        return _ScalarRows(sorted(self.records))

    async def get(self, _model, record_id: int):
        self.get_calls.append(record_id)
        return self.records.get(record_id)

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1


def _now_utc() -> datetime:
    """Return an aware timestamp for fake persisted lifecycle records."""
    return datetime.now(timezone.utc)


def _consumed_record(record_id: int) -> DocumentObjectRecord:
    """Build one persisted-looking consumed object record."""
    record = DocumentObjectRecord(
        document_object_record_id=record_id,
        document_id=f"document-{record_id}",
        storage_backend="s3",
        bucket_name="naruon-documents",
        object_key=f"workspace-documents/scope/document-{record_id}/source.pdf",
        content_type="application/pdf",
        content_length=16,
        checksum_sha256="0" * 64,
        storage_state="consumed",
    )
    record.consumed_at = _now_utc()
    return record


@pytest.mark.asyncio
async def test_consumed_object_cleanup_commits_each_remote_delete(monkeypatch):
    """Persist each successful delete so a later crash cannot replay it."""
    first = _consumed_record(1)
    second = _consumed_record(2)
    session = _CleanupSession([first, second])
    deleted_ids: list[int] = []

    async def delete_consumed(record: DocumentObjectRecord) -> None:
        deleted_ids.append(record.document_object_record_id)
        record.storage_state = "deleted"
        record.deleted_at = _now_utc()

    monkeypatch.setattr(
        cleanup_module,
        "delete_consumed_document_payload",
        delete_consumed,
    )

    result = await cleanup_module.sweep_consumed_document_objects(
        session,
        batch_limit=5,
    )

    assert result == cleanup_module.DocumentObjectCleanupResult(
        selected_count=2,
        deleted_count=2,
        failed_count=0,
    )
    assert deleted_ids == [1, 2]
    assert session.get_calls == [1, 2]
    assert session.commits == 2
    assert session.rollbacks == 0
    assert first.storage_state == "deleted"
    assert second.storage_state == "deleted"


@pytest.mark.asyncio
async def test_consumed_object_cleanup_failure_remains_retryable_and_does_not_starve(
    monkeypatch,
):
    """Rollback a failed delete and continue to later consumed object records."""
    first = _consumed_record(1)
    second = _consumed_record(2)
    session = _CleanupSession([first, second])
    attempts: list[int] = []

    async def delete_consumed(record: DocumentObjectRecord) -> None:
        attempts.append(record.document_object_record_id)
        if record.document_object_record_id == 1:
            raise cleanup_module.DocumentObjectStorageError(
                "temporary object-store outage"
            )
        record.storage_state = "deleted"
        record.deleted_at = _now_utc()

    monkeypatch.setattr(
        cleanup_module,
        "delete_consumed_document_payload",
        delete_consumed,
    )

    result = await cleanup_module.sweep_consumed_document_objects(
        session,
        batch_limit=5,
    )

    assert result == cleanup_module.DocumentObjectCleanupResult(
        selected_count=2,
        deleted_count=1,
        failed_count=1,
    )
    assert attempts == [1, 2]
    assert session.rollbacks == 1
    assert session.commits == 1
    assert first.storage_state == "consumed"
    assert first.deleted_at is None
    assert second.storage_state == "deleted"


@pytest.mark.asyncio
async def test_consumed_object_cleanup_rechecks_state_after_selection(monkeypatch):
    """Skip a row that another safe actor completed after ID selection."""
    record = _consumed_record(1)
    session = _CleanupSession([record])
    record.storage_state = "deleted"
    record.deleted_at = _now_utc()
    calls = 0

    async def forbidden_delete(_record: DocumentObjectRecord) -> None:
        nonlocal calls
        calls += 1

    monkeypatch.setattr(
        cleanup_module,
        "delete_consumed_document_payload",
        forbidden_delete,
    )

    result = await cleanup_module.sweep_consumed_document_objects(session, batch_limit=5)

    assert result == cleanup_module.DocumentObjectCleanupResult(
        selected_count=1,
        deleted_count=0,
        failed_count=0,
    )
    assert calls == 0
    assert session.commits == 0
    assert session.rollbacks == 0
