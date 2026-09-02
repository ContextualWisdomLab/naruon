"""Unit tests for the attachment reparse worker's per-item processing.

Fully mocked: in-memory ``Attachment`` instances and a fake async session --
no database, no network. Covers the fail-closed outcome (invalid retained
payload -> a dedicated terminal status) alongside the two "successful
re-evaluation" outcomes: a previously-quarantined attachment whose
disagreement is now recognized as legitimate (escapes quarantine), and one
whose disagreement is still genuine (stays quarantined).
"""

import asyncio
import base64
from types import SimpleNamespace

import pytest

from db.models import Attachment
import services.attachment_reparse_worker as attachment_reparse_worker_module

AttachmentReparseWorker = attachment_reparse_worker_module.AttachmentReparseWorker
ATTACHMENT_REPARSE_PENDING_STATUS = (
    attachment_reparse_worker_module.ATTACHMENT_REPARSE_PENDING_STATUS
)
ATTACHMENT_REPARSE_PAYLOAD_INVALID_STATUS = (
    attachment_reparse_worker_module.ATTACHMENT_REPARSE_PAYLOAD_INVALID_STATUS
)
RESULT_DECODE_FAILED = attachment_reparse_worker_module.RESULT_DECODE_FAILED
process_reparse_pending_attachment = (
    attachment_reparse_worker_module.process_reparse_pending_attachment
)

_QUARANTINED_STATUS = "content_type_mismatch_quarantined"


def _reparse_pending_attachment(
    *,
    content_type: str,
    payload: bytes,
    filename: str = "attachment.bin",
    attachment_id: int | None = None,
) -> Attachment:
    return Attachment(
        id=attachment_id,
        filename=filename,
        content_type=content_type,
        content=base64.b64encode(payload).decode("ascii"),
        parse_content_type="application/zip",
        parser_key="unsupported_binary",
        parse_status=ATTACHMENT_REPARSE_PENDING_STATUS,
        parse_error_code=None,
    )


def test_reparse_escapes_a_now_recognized_false_positive():
    # A .docx declared with its real OOXML content type but sniffed as a
    # plain ZIP -- exactly the false-positive family the OOXML/ODF/EPUB/JAR
    # carve-out fixed. Reparsing no longer flags it as a mismatch; it lands
    # on the ordinary "unsupported_content_type" classification (this parser
    # has no dedicated OOXML parser), never back in quarantine.
    docx_content_type = (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    attachment = _reparse_pending_attachment(
        content_type=docx_content_type,
        payload=b"PK\x03\x04" + b"real docx zip bytes",
        filename="report.docx",
    )

    result = process_reparse_pending_attachment(attachment=attachment)

    assert result == "unsupported_content_type"
    assert attachment.parse_status == "unsupported_content_type"
    assert attachment.parse_error_code == "unsupported_content_type"
    assert attachment.parse_status != _QUARANTINED_STATUS


def test_reparse_to_unsupported_content_type_preserves_retained_bytes():
    # Same false-positive escape as above, but this asserts the one thing
    # that test doesn't: parse_email_attachment returns content="" for
    # unsupported_content_type (nothing to display), and apply_reparsed_result
    # must not let that empty result overwrite the only retained copy of the
    # original quarantined bytes -- there would be no way to ever recover or
    # re-attempt parsing on this attachment again.
    docx_content_type = (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    payload = b"PK\x03\x04" + b"real docx zip bytes"
    attachment = _reparse_pending_attachment(
        content_type=docx_content_type,
        payload=payload,
        filename="report.docx",
    )
    retained_content = attachment.content

    result = process_reparse_pending_attachment(attachment=attachment)

    assert result == "unsupported_content_type"
    assert attachment.content == retained_content
    assert base64.b64decode(attachment.content) == payload


def test_reparse_of_a_genuine_mismatch_returns_to_quarantine():
    # PNG bytes declared as a PDF -- a real disguise, unrelated to any parser
    # bug. Reparsing must reconfirm the same quarantine, not silently parse.
    attachment = _reparse_pending_attachment(
        content_type="application/pdf",
        payload=b"\x89PNG\r\n\x1a\n" + b"real png bytes",
        filename="invoice.pdf",
    )

    result = process_reparse_pending_attachment(attachment=attachment)

    assert result == _QUARANTINED_STATUS
    assert attachment.parse_status == _QUARANTINED_STATUS
    assert attachment.parse_error_code == _QUARANTINED_STATUS
    assert attachment.parse_content_type == "image/png"


def test_reparse_rejects_an_invalid_retained_payload():
    attachment = _reparse_pending_attachment(
        content_type="application/pdf", payload=b"irrelevant"
    )
    attachment.content = "not@@base64!!"

    result = process_reparse_pending_attachment(attachment=attachment)

    assert result == RESULT_DECODE_FAILED
    assert attachment.parse_status == ATTACHMENT_REPARSE_PAYLOAD_INVALID_STATUS
    assert attachment.parse_error_code == ATTACHMENT_REPARSE_PAYLOAD_INVALID_STATUS


def test_reparse_preserves_filename_and_declared_content_type():
    attachment = _reparse_pending_attachment(
        content_type="application/pdf",
        payload=b"\x89PNG\r\n\x1a\n" + b"real png bytes",
        filename="invoice.pdf",
    )

    process_reparse_pending_attachment(attachment=attachment)

    assert attachment.filename == "invoice.pdf"
    assert attachment.content_type == "application/pdf"


class _RowsResult:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return self

    def all(self):
        return self._rows


class _SequenceSession:
    """A fake session whose ``get`` always returns a fresh, healthy instance.

    Mirrors the real ``AttachmentReparseWorker._sweep_attachments`` contract:
    the bulk-loaded rows only supply ids and the cursor; every actual
    processing target is re-fetched via ``get`` by id, exactly like a real
    ``AsyncSession`` would after an earlier item's rollback expired the
    bulk-loaded instances. ``by_id`` lets a test register a *different*
    object than the bulk-loaded one to prove that re-fetch is what the sweep
    actually uses.
    """

    def __init__(self, row_batches, *, by_id=None):
        self._row_batches = list(row_batches)
        self._by_id = dict(by_id or {})
        for batch in self._row_batches:
            for attachment in batch:
                self._by_id.setdefault(attachment.id, attachment)
        self.statements = []
        self.commit_count = 0
        self.rollback_count = 0

    async def execute(self, statement):
        self.statements.append(statement)
        return _RowsResult(self._row_batches.pop(0))

    async def get(self, _model, attachment_id):
        return self._by_id.get(attachment_id)

    async def commit(self):
        self.commit_count += 1

    async def rollback(self):
        self.rollback_count += 1


class _AsyncSessionContext:
    def __init__(self, session):
        self.session = session

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, *_args):
        return False


class _LeaseConnection:
    def __init__(self, *, scalar_result=True):
        self.scalar_result = scalar_result
        self.scalar_calls = []
        self.execution_options_calls = []
        # Ordered log spanning both call types, so a test can prove
        # AUTOCOMMIT was set BEFORE the advisory-lock query ran, not just
        # that both happened at some point.
        self.ordered_calls = []

    async def execution_options(self, **options):
        self.execution_options_calls.append(options)
        self.ordered_calls.append(("execution_options", options))
        return self

    async def scalar(self, statement, params):
        self.scalar_calls.append((statement, params))
        self.ordered_calls.append(("scalar", params))
        return self.scalar_result


class _FakeEngine:
    def __init__(self, *, dialect_name="postgresql", connection=None):
        self.dialect = SimpleNamespace(name=dialect_name)
        self._connection = connection

    def connect(self):
        return _LeaseConnectionContext(self._connection)


@pytest.mark.asyncio
async def test_sweep_advances_the_cursor_and_retries_the_failed_row(
    monkeypatch,
):
    # An earlier version (CodeRabbit-flagged) capped the cursor at the first
    # failure instead of advancing it, to keep that one failing row
    # selectable later. That pinned the whole batch window behind it once
    # more than batch_limit rows failed at once -- nothing past them was
    # ever reached (same class of bug fixed in
    # services.newsdom_worker.NewsdomRecognitionWorker._sweep_attachments;
    # see its docstring). The cursor now always advances to the batch's
    # last row; the failed row is retried instead via the independent
    # _attachment_retry_ids set.
    first = _reparse_pending_attachment(
        content_type="application/pdf",
        payload=b"\x89PNG\r\n\x1a\n" + b"png",
        attachment_id=1,
    )
    second = _reparse_pending_attachment(
        content_type="application/pdf",
        payload=b"\x89PNG\r\n\x1a\n" + b"png",
        attachment_id=2,
    )
    third = _reparse_pending_attachment(
        content_type="application/pdf",
        payload=b"\x89PNG\r\n\x1a\n" + b"png",
        attachment_id=3,
    )
    session = _SequenceSession([[first, second, third], [second]])

    real_process = attachment_reparse_worker_module.process_reparse_pending_attachment
    failed_once = set()

    def fail_the_middle_item_once(*, attachment):
        if attachment.id == 2 and attachment.id not in failed_once:
            failed_once.add(attachment.id)
            raise RuntimeError("classification blew up")
        return real_process(attachment=attachment)

    monkeypatch.setattr(
        attachment_reparse_worker_module,
        "process_reparse_pending_attachment",
        fail_the_middle_item_once,
    )
    worker = AttachmentReparseWorker()
    await worker._sweep_attachments(session)

    assert worker._attachment_cursor == 3
    assert worker._attachment_retry_ids == {2}
    assert first.parse_status == _QUARANTINED_STATUS
    assert second.parse_status == ATTACHMENT_REPARSE_PENDING_STATUS
    assert third.parse_status == _QUARANTINED_STATUS
    assert session.commit_count == 2
    assert session.rollback_count == 1

    # The next sweep reselects row 2 via the retry set, not the cursor
    # (which stays at 3, well past it).
    await worker._sweep_attachments(session)

    assert worker._attachment_cursor == 3
    assert worker._attachment_retry_ids == set()
    assert second.parse_status == _QUARANTINED_STATUS
    assert session.commit_count == 3


@pytest.mark.asyncio
async def test_sweep_advances_the_cursor_across_batches():
    first = _reparse_pending_attachment(
        content_type="application/pdf",
        payload=b"\x89PNG\r\n\x1a\n" + b"png",
        attachment_id=1,
    )
    second = _reparse_pending_attachment(
        content_type="application/pdf",
        payload=b"\x89PNG\r\n\x1a\n" + b"png",
        attachment_id=2,
    )
    session = _SequenceSession([[first], [second]])
    worker = AttachmentReparseWorker(batch_limit=1)

    await worker._sweep_attachments(session)
    await worker._sweep_attachments(session)

    second_query = session.statements[1].compile()
    assert "email_attachments.id >" in str(second_query)
    assert 1 in second_query.params.values()
    assert worker._attachment_cursor == 2
    assert first.parse_status == _QUARANTINED_STATUS
    assert second.parse_status == _QUARANTINED_STATUS
    assert session.commit_count == 2
    assert session.rollback_count == 0


@pytest.mark.asyncio
async def test_load_reparse_pending_attachments_queries_forward_cursor_and_retry_ids():
    # No more wraparound: a persistently-failing row is retried via an
    # explicit "id IN retry_ids" filter, independent of the forward cursor,
    # instead of relying on the query going empty to trigger a rescan (which
    # never happens once new reparse-intent rows keep landing past the
    # cursor).
    row = _reparse_pending_attachment(
        content_type="application/pdf",
        payload=b"\x89PNG\r\n\x1a\n" + b"png",
        attachment_id=5,
    )
    session = _SequenceSession([[row]])
    worker = AttachmentReparseWorker(batch_limit=10)
    worker._attachment_cursor = 3
    worker._attachment_retry_ids = {1}

    rows = await worker._load_reparse_pending_attachments(session)

    assert rows == [row]
    compiled = str(session.statements[0].compile())
    assert "email_attachments.id >" in compiled
    assert "IN" in compiled.upper()


@pytest.mark.asyncio
async def test_empty_sweep_leaves_cursor_unset():
    session = _SequenceSession([[]])
    worker = AttachmentReparseWorker()

    await worker._sweep_attachments(session)

    assert worker._attachment_cursor is None
    assert session.commit_count == 0


@pytest.mark.asyncio
async def test_sweep_rolls_back_one_item_failure_and_continues_isolation(monkeypatch):
    attachment = _reparse_pending_attachment(
        content_type="application/pdf",
        payload=b"\x89PNG\r\n\x1a\n" + b"png",
        attachment_id=1,
    )
    session = _SequenceSession([[attachment]])

    def broken_processor(*, attachment):
        raise RuntimeError("classification blew up")

    monkeypatch.setattr(
        attachment_reparse_worker_module,
        "process_reparse_pending_attachment",
        broken_processor,
    )
    worker = AttachmentReparseWorker()
    await worker._sweep_attachments(session)

    assert session.commit_count == 0
    assert session.rollback_count == 1


class _ExpiredAttachment:
    """Stands in for an ORM instance ``AsyncSession.rollback()`` expired.

    Any attribute read raises, exactly like touching an expired async-mapped
    instance outside an active await/greenlet context would in real
    SQLAlchemy -- proving the sweep never touches this bulk-loaded object
    for its *own* processing once it has already failed and been rolled
    back once.
    """

    id = 1

    def __getattr__(self, _name):
        raise AttributeError(
            "must not read attributes off the stale bulk-loaded instance"
        )


@pytest.mark.asyncio
async def test_sweep_never_processes_the_bulk_loaded_instance_directly():
    poisoned_first = _ExpiredAttachment()
    fresh_first = _reparse_pending_attachment(
        content_type="application/pdf",
        payload=b"\x89PNG\r\n\x1a\n" + b"png",
        attachment_id=1,
    )
    second = _reparse_pending_attachment(
        content_type="application/pdf",
        payload=b"\x89PNG\r\n\x1a\n" + b"png",
        attachment_id=2,
    )
    # The bulk query "sees" the poisoned stand-in for id 1 (as a real
    # AsyncSession would after some earlier rollback expired it), but `get`
    # returns the real, healthy row -- proving the sweep re-fetches instead
    # of processing the bulk-loaded object directly.
    session = _SequenceSession(
        [[poisoned_first, second]], by_id={1: fresh_first, 2: second}
    )

    worker = AttachmentReparseWorker()
    await worker._sweep_attachments(session)

    assert fresh_first.parse_status == _QUARANTINED_STATUS
    assert second.parse_status == _QUARANTINED_STATUS
    assert session.commit_count == 2
    assert session.rollback_count == 0


class _LiveReparsePendingSession:
    """Mirrors ``AttachmentReparseWorker._reparse_pending_statement`` for
    real, across many sweeps -- see
    ``tests.test_newsdom_worker._LivePendingAttachmentSession`` (identical
    fake, same reason: proving a multi-sweep scheduling claim needs a fake
    that reflects the worker's own (cursor, retry_ids) state, not a
    pre-scripted batch sequence).
    """

    def __init__(self, worker, attachments):
        self._worker = worker
        self._table = {attachment.id: attachment for attachment in attachments}
        self.commit_count = 0
        self.rollback_count = 0

    async def execute(self, _statement):
        cursor = self._worker._attachment_cursor
        retry_ids = self._worker._attachment_retry_ids
        pending = [
            row
            for row in self._table.values()
            if row.parse_status == ATTACHMENT_REPARSE_PENDING_STATUS
            and (cursor is None or row.id > cursor or row.id in retry_ids)
        ]
        pending.sort(key=lambda row: (0 if (cursor is None or row.id > cursor) else 1, row.id))
        return _RowsResult(pending[: self._worker.batch_limit])

    async def get(self, _model, attachment_id):
        return self._table.get(attachment_id)

    async def commit(self):
        self.commit_count += 1

    async def rollback(self):
        self.rollback_count += 1


@pytest.mark.asyncio
async def test_sweep_does_not_starve_rows_behind_many_failing_rows(monkeypatch):
    # Same starvation class fixed on the NewsDOM worker (see
    # test_newsdom_worker.test_attachment_sweep_does_not_starve_rows_behind_many_stuck_rows):
    # a systematic classification bug affecting a burst of simultaneous
    # reparse-intent requests could put more than batch_limit consecutive
    # rows into a permanent-failure state at once.
    failing = [
        _reparse_pending_attachment(
            content_type="application/pdf",
            payload=b"\x89PNG\r\n\x1a\n" + b"png",
            attachment_id=index,
        )
        for index in range(1, 61)
    ]
    healthy = [
        _reparse_pending_attachment(
            content_type="application/pdf",
            payload=b"\x89PNG\r\n\x1a\n" + b"png",
            attachment_id=index,
        )
        for index in range(61, 121)
    ]
    all_attachments = failing + healthy
    failing_ids = {attachment.id for attachment in failing}

    real_process = attachment_reparse_worker_module.process_reparse_pending_attachment

    def fail_the_first_burst(*, attachment):
        if attachment.id in failing_ids:
            raise RuntimeError("classification blew up")
        return real_process(attachment=attachment)

    monkeypatch.setattr(
        attachment_reparse_worker_module,
        "process_reparse_pending_attachment",
        fail_the_first_burst,
    )
    worker = AttachmentReparseWorker(batch_limit=50)
    session = _LiveReparsePendingSession(worker, all_attachments)

    for _ in range(10):
        await worker._sweep_attachments(session)
        if all(a.parse_status == _QUARANTINED_STATUS for a in healthy):
            break

    assert all(a.parse_status == _QUARANTINED_STATUS for a in healthy)
    assert all(
        a.parse_status == ATTACHMENT_REPARSE_PENDING_STATUS for a in failing
    )
    assert worker._attachment_retry_ids == failing_ids


@pytest.mark.asyncio
async def test_sweep_isolates_one_items_failure_from_the_next_items_refetch(
    monkeypatch,
):
    first = _reparse_pending_attachment(
        content_type="application/pdf",
        payload=b"\x89PNG\r\n\x1a\n" + b"png",
        attachment_id=1,
    )
    second = _reparse_pending_attachment(
        content_type="application/pdf",
        payload=b"\x89PNG\r\n\x1a\n" + b"png",
        attachment_id=2,
    )
    session = _SequenceSession([[first, second]])

    real_process = attachment_reparse_worker_module.process_reparse_pending_attachment

    def process_and_fail_only_the_first(*, attachment):
        if attachment.id == 1:
            raise RuntimeError("classification blew up")
        return real_process(attachment=attachment)

    monkeypatch.setattr(
        attachment_reparse_worker_module,
        "process_reparse_pending_attachment",
        process_and_fail_only_the_first,
    )
    worker = AttachmentReparseWorker()
    await worker._sweep_attachments(session)

    assert second.parse_status == _QUARANTINED_STATUS
    assert session.commit_count == 1
    assert session.rollback_count == 1


@pytest.mark.asyncio
async def test_postgresql_lease_helpers_and_non_postgresql_fallback(monkeypatch):
    postgres_connection = _LeaseConnection(scalar_result=1)

    assert (
        await attachment_reparse_worker_module._try_acquire_sweep_lease(
            postgres_connection
        )
        is True
    )
    # AUTOCOMMIT before the lock-acquire statement: a plain (non-autocommit)
    # connection would otherwise leave this connection's implicit
    # transaction open and idle for the whole sweep -- a PostgreSQL
    # idle_in_transaction_session_timeout could then kill this connection
    # mid-sweep, silently dropping the lease.
    assert postgres_connection.execution_options_calls == [
        {"isolation_level": "AUTOCOMMIT"}
    ]
    assert (
        postgres_connection.scalar_calls[0][1]
        == attachment_reparse_worker_module._SWEEP_LOCK_PARAMS
    )
    # Ordering, not just occurrence: AUTOCOMMIT must be set before the
    # advisory-lock query runs, or the query could still open an implicit
    # transaction under the connection's prior isolation level.
    assert postgres_connection.ordered_calls[0][0] == "execution_options"
    assert postgres_connection.ordered_calls[1][0] == "scalar"
    await attachment_reparse_worker_module._release_sweep_lease(postgres_connection)
    assert len(postgres_connection.scalar_calls) == 2

    monkeypatch.setattr(
        attachment_reparse_worker_module, "engine", _FakeEngine(dialect_name="sqlite")
    )
    assert attachment_reparse_worker_module._engine_uses_postgresql() is False

    monkeypatch.setattr(
        attachment_reparse_worker_module,
        "engine",
        _FakeEngine(dialect_name="postgresql"),
    )
    assert attachment_reparse_worker_module._engine_uses_postgresql() is True


class _LeaseConnectionContext:
    def __init__(self, connection):
        self.connection = connection

    async def __aenter__(self):
        return self.connection

    async def __aexit__(self, *_args):
        return False


@pytest.mark.asyncio
async def test_worker_sweep_skips_locking_when_engine_is_not_postgresql(monkeypatch):
    session = object()
    calls = []
    worker = AttachmentReparseWorker()

    monkeypatch.setattr(
        attachment_reparse_worker_module, "engine", _FakeEngine(dialect_name="sqlite")
    )
    monkeypatch.setattr(
        attachment_reparse_worker_module,
        "AsyncSessionLocal",
        lambda: _AsyncSessionContext(session),
    )

    async def sweep_attachments(actual_session):
        calls.append(actual_session)

    monkeypatch.setattr(worker, "_sweep_attachments", sweep_attachments)

    await worker._sweep()

    assert calls == [session]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("lease", "expected_sweeps", "expected_releases"),
    [(False, 0, 0), (True, 1, 1)],
)
async def test_worker_sweep_honors_lease_outcome(
    monkeypatch, lease, expected_sweeps, expected_releases
):
    session = object()
    lock_connection = object()
    calls = []
    releases = []
    worker = AttachmentReparseWorker()

    monkeypatch.setattr(
        attachment_reparse_worker_module,
        "engine",
        _FakeEngine(dialect_name="postgresql", connection=lock_connection),
    )
    monkeypatch.setattr(
        attachment_reparse_worker_module,
        "AsyncSessionLocal",
        lambda: _AsyncSessionContext(session),
    )

    async def acquire(actual_connection):
        assert actual_connection is lock_connection
        return lease

    async def release(actual_connection):
        releases.append(actual_connection)

    async def sweep_attachments(actual_session):
        calls.append(("attachments", actual_session))

    monkeypatch.setattr(
        attachment_reparse_worker_module, "_try_acquire_sweep_lease", acquire
    )
    monkeypatch.setattr(
        attachment_reparse_worker_module, "_release_sweep_lease", release
    )
    monkeypatch.setattr(worker, "_sweep_attachments", sweep_attachments)

    await worker._sweep()

    assert len(calls) == expected_sweeps
    assert len(releases) == expected_releases


@pytest.mark.asyncio
async def test_worker_start_stop_are_idempotent(monkeypatch):
    worker = AttachmentReparseWorker()
    entered = asyncio.Event()
    blocker = asyncio.Event()

    async def blocked_loop():
        entered.set()
        await blocker.wait()

    monkeypatch.setattr(worker, "_run_loop", blocked_loop)
    await worker.start()
    await entered.wait()
    task = worker._task
    await worker.start()
    await worker.stop()
    await worker.stop()

    assert task is not None
    assert task.cancelled()

    worker._is_running = True
    worker._task = None
    await worker.stop()


@pytest.mark.asyncio
async def test_worker_loop_reports_errors_and_honors_cancellation(monkeypatch):
    worker = AttachmentReparseWorker(interval_seconds=1)
    worker._is_running = True
    sleep_calls = 0

    async def sleep_then_cancel(_seconds):
        nonlocal sleep_calls
        sleep_calls += 1
        if sleep_calls > 1:
            raise asyncio.CancelledError

    async def failing_sweep():
        raise RuntimeError("sweep failed")

    monkeypatch.setattr(attachment_reparse_worker_module.asyncio, "sleep", sleep_then_cancel)
    monkeypatch.setattr(worker, "_sweep", failing_sweep)
    await worker._run_loop()
    assert sleep_calls == 2

    async def cancel_immediately(_seconds):
        raise asyncio.CancelledError

    monkeypatch.setattr(attachment_reparse_worker_module.asyncio, "sleep", cancel_immediately)
    await worker._run_loop()


@pytest.mark.asyncio
async def test_worker_loop_stops_when_sweep_is_cancelled(monkeypatch):
    worker = AttachmentReparseWorker(interval_seconds=1)
    worker._is_running = True

    async def no_sleep(_seconds):
        return None

    async def cancelled_sweep():
        raise asyncio.CancelledError

    monkeypatch.setattr(attachment_reparse_worker_module.asyncio, "sleep", no_sleep)
    monkeypatch.setattr(worker, "_sweep", cancelled_sweep)
    await worker._run_loop()


@pytest.mark.asyncio
async def test_worker_loop_returns_after_a_normal_interval(monkeypatch):
    worker = AttachmentReparseWorker(interval_seconds=1)
    worker._is_running = True
    sleep_calls = 0
    sweep_calls = 0

    async def stop_after_interval(_seconds):
        nonlocal sleep_calls
        sleep_calls += 1
        if sleep_calls == 2:
            worker._is_running = False

    async def successful_sweep():
        nonlocal sweep_calls
        sweep_calls += 1

    monkeypatch.setattr(attachment_reparse_worker_module.asyncio, "sleep", stop_after_interval)
    monkeypatch.setattr(worker, "_sweep", successful_sweep)
    await worker._run_loop()

    assert sleep_calls == 2
    assert sweep_calls == 1


@pytest.mark.asyncio
async def test_worker_loop_skips_interval_when_sweep_stops_worker(monkeypatch):
    worker = AttachmentReparseWorker(interval_seconds=1)
    worker._is_running = True
    sleep_calls = 0

    async def record_sleep(_seconds):
        nonlocal sleep_calls
        sleep_calls += 1

    async def stopping_sweep():
        worker._is_running = False

    monkeypatch.setattr(attachment_reparse_worker_module.asyncio, "sleep", record_sleep)
    monkeypatch.setattr(worker, "_sweep", stopping_sweep)
    await worker._run_loop()

    assert sleep_calls == 1
