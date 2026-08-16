"""Contracts for durable cleanup after failed S3 compensation."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from db.object_storage_cleanup_record import ObjectStorageCleanupRecord
import services.object_storage_orphan_cleanup as cleanup_module


class _Rows:
    """Expose deterministic scalar values for bounded cleanup selection."""

    def __init__(self, values) -> None:
        self.values = list(values)

    def scalars(self):
        return self

    def all(self):
        return list(self.values)


class _Session:
    """Minimal session for orphan cleanup retry and commit boundaries."""

    def __init__(self, records: list[ObjectStorageCleanupRecord]) -> None:
        self.records = {
            record.object_storage_cleanup_record_id: record for record in records
        }
        self.provider = SimpleNamespace(
            object_storage_provider_id=77,
            organization_id="organization-one",
            provider_type="s3",
            bucket_name="naruon-documents",
            region_name="us-east-1",
            endpoint_url=None,
            addressing_style="virtual",
            access_key_id="access-key",
            secret_access_key="secret-key",
            session_token=None,
            server_side_encryption="AES256",
            kms_key_id=None,
            expected_bucket_owner=None,
            is_active=False,
        )
        self.commits = 0
        self.rollbacks = 0
        self.statements = []

    async def execute(self, statement):
        self.statements.append(statement)
        return _Rows(sorted(self.records))

    async def get(self, model, record_id):
        if model is ObjectStorageCleanupRecord:
            return self.records.get(record_id)
        raise AssertionError("unexpected model")

    async def scalar(self, _statement):
        return self.provider

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1


def _record(record_id: int) -> ObjectStorageCleanupRecord:
    """Build one persisted-looking pending orphan cleanup record."""
    return ObjectStorageCleanupRecord(
        object_storage_cleanup_record_id=record_id,
        object_storage_provider_id=77,
        organization_id="organization-one",
        bucket_name="naruon-documents",
        object_key=f"workspace-documents/opaque/{record_id}/source.pdf",
        content_type="application/pdf",
        content_length=16,
        checksum_sha256="0" * 64,
        cleanup_reason="metadata_commit_compensation_failed",
        cleanup_status="pending",
        attempt_count=0,
        created_at=datetime.now(timezone.utc),
    )


@pytest.mark.asyncio
async def test_orphan_cleanup_deletes_each_pending_object_and_commits(monkeypatch) -> None:
    first = _record(1)
    second = _record(2)
    session = _Session([first, second])
    deleted: list[int] = []

    async def delete_orphan(record, *, runtime_config):
        assert runtime_config.object_storage_provider_id == 77
        deleted.append(record.object_storage_cleanup_record_id)

    monkeypatch.setattr(cleanup_module, "delete_orphan_cleanup_record", delete_orphan)

    result = await cleanup_module.sweep_object_storage_orphans(session, batch_limit=5)

    assert result == cleanup_module.ObjectStorageOrphanCleanupResult(2, 2, 0)
    assert deleted == [1, 2]
    assert session.commits == 2
    assert session.rollbacks == 0
    assert first.cleanup_status == "completed"
    assert first.completed_at is not None
    assert first.attempt_count == 1
    assert second.cleanup_status == "completed"


@pytest.mark.asyncio
async def test_orphan_cleanup_failure_is_retryable_and_does_not_starve(monkeypatch) -> None:
    first = _record(1)
    second = _record(2)
    session = _Session([first, second])

    async def delete_orphan(record, *, runtime_config):
        del runtime_config
        if record.object_storage_cleanup_record_id == 1:
            raise cleanup_module.DocumentObjectStorageError("temporary outage")

    monkeypatch.setattr(cleanup_module, "delete_orphan_cleanup_record", delete_orphan)

    result = await cleanup_module.sweep_object_storage_orphans(session, batch_limit=5)

    assert result == cleanup_module.ObjectStorageOrphanCleanupResult(2, 1, 1)
    assert session.rollbacks == 1
    assert first.cleanup_status == "pending"
    assert first.completed_at is None
    assert second.cleanup_status == "completed"
    assert second.attempt_count == 1


@pytest.mark.asyncio
async def test_orphan_cleanup_rejects_unbounded_batch() -> None:
    session = _Session([])
    with pytest.raises(ValueError, match="batch_limit must be positive"):
        await cleanup_module.sweep_object_storage_orphans(session, batch_limit=0)
    assert session.statements == []
