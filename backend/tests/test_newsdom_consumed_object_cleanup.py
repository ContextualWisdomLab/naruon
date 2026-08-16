"""Regression tests for retryable cleanup of consumed NewsDOM source objects.

Recognition commits parsed text and the ``consumed`` lifecycle marker before any
remote delete. These tests require a later cleanup sweep to delete consumed
objects and to keep failed deletes retryable without starving subsequent rows.
"""

from __future__ import annotations

import asyncio
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


class _CleanupSessionContext:
    """Expose one fake session through an async context-manager boundary."""

    def __init__(self, session: _CleanupSession) -> None:
        self.session = session

    async def __aenter__(self) -> _CleanupSession:
        return self.session

    async def __aexit__(self, _exc_type, _exc, _tb) -> None:
        return None


class _CleanupSessionFactory:
    """Record worker session-factory use without a live database."""

    def __init__(self, session: _CleanupSession) -> None:
        self.session = session
        self.calls = 0

    def __call__(self) -> _CleanupSessionContext:
        self.calls += 1
        return _CleanupSessionContext(self.session)


class _CancelledTask:
    """Task substitute whose await path raises cancellation after cancel()."""

    def __init__(self) -> None:
        self.cancelled = False

    def cancel(self) -> None:
        self.cancelled = True

    def __await__(self):
        async def cancelled_wait():
            raise asyncio.CancelledError

        return cancelled_wait().__await__()


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


@pytest.mark.asyncio
@pytest.mark.parametrize("batch_limit", [0, -1])
async def test_consumed_object_cleanup_rejects_nonpositive_batch_limit(batch_limit):
    """Reject values that could turn a bounded cleanup sweep into an unbounded query."""
    session = _CleanupSession([])

    with pytest.raises(ValueError, match="batch_limit must be positive"):
        await cleanup_module.sweep_consumed_document_objects(
            session,
            batch_limit=batch_limit,
        )

    assert session.execute_calls == 0


@pytest.mark.parametrize(
    ("interval_seconds", "batch_limit", "message"),
    [
        (0.0, 25, "interval_seconds must be positive"),
        (60.0, 0, "batch_limit must be positive"),
    ],
)
def test_consumed_object_cleanup_worker_rejects_unbounded_runtime_configuration(
    interval_seconds,
    batch_limit,
    message,
):
    """Refuse worker settings that can spin or issue an unbounded cleanup query."""
    session_factory = _CleanupSessionFactory(_CleanupSession([]))

    with pytest.raises(ValueError, match=message):
        cleanup_module.DocumentObjectCleanupWorker(
            interval_seconds=interval_seconds,
            batch_limit=batch_limit,
            session_factory=session_factory,
        )


@pytest.mark.asyncio
async def test_consumed_object_cleanup_worker_sync_uses_bounded_session_factory(
    monkeypatch,
):
    """Run one cleanup sweep through a fresh database session with the configured cap."""
    session = _CleanupSession([])
    session_factory = _CleanupSessionFactory(session)
    observed: list[tuple[object, int]] = []
    expected = cleanup_module.DocumentObjectCleanupResult(0, 0, 0)

    async def sweep(candidate_session, *, batch_limit):
        observed.append((candidate_session, batch_limit))
        return expected

    monkeypatch.setattr(cleanup_module, "sweep_consumed_document_objects", sweep)
    worker = cleanup_module.DocumentObjectCleanupWorker(
        interval_seconds=60,
        batch_limit=7,
        session_factory=session_factory,
    )

    result = await worker._sync()

    assert result == expected
    assert observed == [(session, 7)]
    assert session_factory.calls == 1


@pytest.mark.asyncio
async def test_consumed_object_cleanup_worker_start_stop_is_idempotent(monkeypatch):
    """Start one background loop and shut it down without spawning duplicates."""
    worker = cleanup_module.DocumentObjectCleanupWorker(
        interval_seconds=60,
        batch_limit=5,
        session_factory=_CleanupSessionFactory(_CleanupSession([])),
    )
    entered = asyncio.Event()
    release = asyncio.Event()

    async def blocking_sync():
        entered.set()
        await release.wait()
        return cleanup_module.DocumentObjectCleanupResult(0, 0, 0)

    monkeypatch.setattr(worker, "_sync", blocking_sync)

    await worker.start()
    first_task = worker._task
    await asyncio.wait_for(entered.wait(), timeout=1)
    await worker.start()

    assert worker._task is first_task
    assert worker._is_running is True

    release.set()
    await asyncio.sleep(0)
    await worker.stop()
    await worker.stop()

    assert worker._is_running is False


@pytest.mark.asyncio
async def test_consumed_object_cleanup_worker_recovers_after_one_sync_failure(
    monkeypatch,
):
    """Log one transient sweep failure and continue to the next scheduled sweep."""
    worker = cleanup_module.DocumentObjectCleanupWorker(
        interval_seconds=60,
        batch_limit=5,
        session_factory=_CleanupSessionFactory(_CleanupSession([])),
    )
    calls = 0

    async def flaky_sync():
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("temporary database outage")
        worker._is_running = False
        return cleanup_module.DocumentObjectCleanupResult(0, 0, 0)

    async def immediate_sleep(_seconds):
        return None

    monkeypatch.setattr(worker, "_sync", flaky_sync)
    monkeypatch.setattr(cleanup_module.asyncio, "sleep", immediate_sleep)
    worker._is_running = True

    await worker._run_loop()

    assert calls == 2


@pytest.mark.asyncio
async def test_consumed_object_cleanup_worker_stop_handles_cancelled_task() -> None:
    """Treat task cancellation during shutdown as the expected control path."""
    worker = cleanup_module.DocumentObjectCleanupWorker(
        interval_seconds=60,
        batch_limit=5,
        session_factory=_CleanupSessionFactory(_CleanupSession([])),
    )
    task = _CancelledTask()
    worker._is_running = True
    worker._task = task

    await worker.stop()

    assert task.cancelled is True
    assert worker._is_running is False
