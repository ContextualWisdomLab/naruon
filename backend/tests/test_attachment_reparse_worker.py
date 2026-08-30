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
    def __init__(self, row_batches):
        self._row_batches = list(row_batches)
        self.statements = []
        self.commit_count = 0
        self.rollback_count = 0

    async def execute(self, statement):
        self.statements.append(statement)
        return _RowsResult(self._row_batches.pop(0))

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


class _LeaseSession:
    def __init__(self, *, dialect_name="postgresql", scalar_result=True):
        self.bind = SimpleNamespace(
            dialect=SimpleNamespace(name=dialect_name),
        )
        self.scalar_result = scalar_result
        self.scalar_calls = []

    def get_bind(self):
        return self.bind

    async def scalar(self, statement, params):
        self.scalar_calls.append((statement, params))
        return self.scalar_result


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
async def test_sweep_cursor_wraps_and_empty_batches_are_stable():
    wrapped = _reparse_pending_attachment(
        content_type="application/pdf",
        payload=b"\x89PNG\r\n\x1a\n" + b"png",
        attachment_id=1,
    )
    session = _SequenceSession([[], [wrapped], []])
    worker = AttachmentReparseWorker(batch_limit=10)
    worker._attachment_cursor = 999

    rows = await worker._load_reparse_pending_attachments(session)
    empty_rows = await worker._load_reparse_pending_attachments(session)

    assert rows == [wrapped]
    assert empty_rows == []
    assert worker._attachment_cursor is None
    assert "email_attachments.id >" in str(session.statements[0])
    assert "email_attachments.id >" not in str(session.statements[1])


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


@pytest.mark.asyncio
async def test_postgresql_lease_helpers_and_non_postgresql_fallback():
    postgres = _LeaseSession(scalar_result=1)
    sqlite = _LeaseSession(dialect_name="sqlite")

    assert (
        await attachment_reparse_worker_module._try_acquire_sweep_lease(postgres)
        is True
    )
    assert (
        postgres.scalar_calls[0][1]
        == attachment_reparse_worker_module._SWEEP_LOCK_PARAMS
    )
    await attachment_reparse_worker_module._release_sweep_lease(postgres)
    assert len(postgres.scalar_calls) == 2
    assert (
        await attachment_reparse_worker_module._try_acquire_sweep_lease(sqlite) is None
    )

    class BrokenBindSession:
        def get_bind(self):
            raise RuntimeError("no bind")

    assert (
        attachment_reparse_worker_module._session_uses_postgresql(BrokenBindSession())
        is False
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("lease", "expected_sweeps", "expected_releases"),
    [(False, 0, 0), (None, 1, 0), (True, 1, 1)],
)
async def test_worker_sweep_honors_lease_outcome(
    monkeypatch, lease, expected_sweeps, expected_releases
):
    session = object()
    calls = []
    releases = []
    worker = AttachmentReparseWorker()

    monkeypatch.setattr(
        attachment_reparse_worker_module,
        "AsyncSessionLocal",
        lambda: _AsyncSessionContext(session),
    )

    async def acquire(actual_session):
        assert actual_session is session
        return lease

    async def release(actual_session):
        releases.append(actual_session)

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
