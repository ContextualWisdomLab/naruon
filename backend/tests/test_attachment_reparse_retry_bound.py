"""Resource-bound regressions for attachment reparse retry scheduling."""

from types import SimpleNamespace

import pytest

import services.attachment_reparse_worker as worker_module


class _RowsResult:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return self

    def all(self):
        return self._rows


class _FailureSession:
    def __init__(self, rows):
        self._rows = rows
        self.rollback_count = 0

    async def execute(self, _statement):
        return _RowsResult(self._rows)

    async def get(self, _model, attachment_id):
        return SimpleNamespace(id=attachment_id)

    async def refresh(self, _attachment, *, attribute_names):
        del attribute_names

    async def commit(self):
        raise AssertionError("failing attachments must not commit")

    async def rollback(self):
        self.rollback_count += 1


@pytest.mark.asyncio
async def test_retry_tracking_stays_bounded_after_large_failure_burst(monkeypatch):
    """Persistent failures must not create unbounded in-memory retry metadata."""
    retry_limit = worker_module.MAX_ATTACHMENT_REPARSE_RETRY_IDS
    rows = [SimpleNamespace(id=index) for index in range(1, retry_limit * 4 + 1)]
    worker = worker_module.AttachmentReparseWorker(batch_limit=len(rows))
    session = _FailureSession(rows)

    def always_fail(*, attachment):
        del attachment
        raise RuntimeError("classification blew up")

    monkeypatch.setattr(worker_module, "process_reparse_pending_attachment", always_fail)

    await worker._sweep_attachments(session)

    assert session.rollback_count == len(rows)
    assert len(worker._attachment_retry_ids) == retry_limit
    assert worker._attachment_retry_ids.issubset({row.id for row in rows})


def test_retry_query_never_binds_more_than_the_retry_limit():
    """The SQL ``IN`` predicate must remain bounded even if caller state is corrupt."""
    retry_limit = worker_module.MAX_ATTACHMENT_REPARSE_RETRY_IDS
    worker = worker_module.AttachmentReparseWorker()
    oversized_retry_ids = set(range(1, retry_limit * 8 + 1))

    statement = worker._reparse_pending_statement(10_000, oversized_retry_ids)
    compiled = statement.compile()
    expanding_values = [
        value
        for value in compiled.params.values()
        if isinstance(value, (list, tuple, set))
    ]

    assert expanding_values
    assert max(len(value) for value in expanding_values) <= retry_limit
