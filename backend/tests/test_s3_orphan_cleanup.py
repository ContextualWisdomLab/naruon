"""Contracts for durable cleanup after failed S3 compensation."""

from __future__ import annotations

import asyncio
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


class _SessionContext:
    """Expose one fake session through an asynchronous context manager."""

    def __init__(self, session: _Session) -> None:
        self.session = session

    async def __aenter__(self) -> _Session:
        return self.session

    async def __aexit__(self, _exc_type, _exc, _tb) -> None:
        return None


class _SessionFactory:
    """Count bounded worker session creation."""

    def __init__(self, session: _Session) -> None:
        self.session = session
        self.calls = 0

    def __call__(self) -> _SessionContext:
        self.calls += 1
        return _SessionContext(self.session)


class _CancelledTask:
    """Awaitable task substitute that acknowledges cancellation."""

    def __init__(self) -> None:
        self.cancelled = False

    def cancel(self) -> None:
        self.cancelled = True

    def __await__(self):
        async def cancelled_wait():
            raise asyncio.CancelledError

        return cancelled_wait().__await__()


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
async def test_orphan_cleanup_skips_completed_or_missing_rows(monkeypatch) -> None:
    completed = _record(1)
    completed.cleanup_status = "completed"
    session = _Session([completed])
    calls = 0

    async def forbidden_delete(*_args, **_kwargs):
        nonlocal calls
        calls += 1

    monkeypatch.setattr(cleanup_module, "delete_orphan_cleanup_record", forbidden_delete)
    result = await cleanup_module.sweep_object_storage_orphans(session, batch_limit=5)

    assert result == cleanup_module.ObjectStorageOrphanCleanupResult(1, 0, 0)
    assert calls == 0
    assert session.commits == 0


@pytest.mark.asyncio
async def test_orphan_cleanup_rejects_unbounded_batch() -> None:
    session = _Session([])
    with pytest.raises(ValueError, match="batch_limit must be positive"):
        await cleanup_module.sweep_object_storage_orphans(session, batch_limit=0)
    assert session.statements == []


@pytest.mark.parametrize(
    ("interval_seconds", "batch_limit", "message"),
    [
        (0.0, 25, "interval_seconds must be positive"),
        (60.0, 0, "batch_limit must be positive"),
    ],
)
def test_orphan_cleanup_worker_rejects_unbounded_configuration(
    interval_seconds,
    batch_limit,
    message,
) -> None:
    factory = _SessionFactory(_Session([]))
    with pytest.raises(ValueError, match=message):
        cleanup_module.ObjectStorageOrphanCleanupWorker(
            interval_seconds=interval_seconds,
            batch_limit=batch_limit,
            session_factory=factory,
        )


@pytest.mark.asyncio
async def test_orphan_cleanup_worker_sync_uses_bounded_session(monkeypatch) -> None:
    session = _Session([])
    factory = _SessionFactory(session)
    expected = cleanup_module.ObjectStorageOrphanCleanupResult(0, 0, 0)
    observed: list[tuple[object, int]] = []

    async def sweep(candidate_session, *, batch_limit):
        observed.append((candidate_session, batch_limit))
        return expected

    monkeypatch.setattr(cleanup_module, "sweep_object_storage_orphans", sweep)
    worker = cleanup_module.ObjectStorageOrphanCleanupWorker(
        interval_seconds=60,
        batch_limit=7,
        session_factory=factory,
    )

    assert await worker._sync() == expected
    assert observed == [(session, 7)]
    assert factory.calls == 1


@pytest.mark.asyncio
async def test_orphan_cleanup_worker_start_stop_is_idempotent(monkeypatch) -> None:
    worker = cleanup_module.ObjectStorageOrphanCleanupWorker(
        interval_seconds=60,
        batch_limit=5,
        session_factory=_SessionFactory(_Session([])),
    )
    entered = asyncio.Event()
    release = asyncio.Event()

    async def blocking_sync():
        entered.set()
        await release.wait()
        return cleanup_module.ObjectStorageOrphanCleanupResult(0, 0, 0)

    monkeypatch.setattr(worker, "_sync", blocking_sync)
    await worker.start()
    first_task = worker._task
    await asyncio.wait_for(entered.wait(), timeout=1)
    await worker.start()
    assert worker._task is first_task

    release.set()
    await asyncio.sleep(0)
    await worker.stop()
    await worker.stop()
    assert worker._is_running is False


@pytest.mark.asyncio
async def test_orphan_cleanup_worker_recovers_after_one_sync_failure(monkeypatch) -> None:
    worker = cleanup_module.ObjectStorageOrphanCleanupWorker(
        interval_seconds=60,
        batch_limit=5,
        session_factory=_SessionFactory(_Session([])),
    )
    calls = 0

    async def flaky_sync():
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("temporary database outage")
        worker._is_running = False
        return cleanup_module.ObjectStorageOrphanCleanupResult(0, 0, 0)

    async def immediate_sleep(_seconds):
        return None

    monkeypatch.setattr(worker, "_sync", flaky_sync)
    monkeypatch.setattr(cleanup_module.asyncio, "sleep", immediate_sleep)
    worker._is_running = True
    await worker._run_loop()
    assert calls == 2


@pytest.mark.asyncio
async def test_orphan_cleanup_worker_stop_handles_cancelled_task() -> None:
    worker = cleanup_module.ObjectStorageOrphanCleanupWorker(
        interval_seconds=60,
        batch_limit=5,
        session_factory=_SessionFactory(_Session([])),
    )
    task = _CancelledTask()
    worker._is_running = True
    worker._task = task
    await worker.stop()
    assert task.cancelled is True
    assert worker._is_running is False
