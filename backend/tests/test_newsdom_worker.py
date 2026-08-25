"""Unit tests for the NewsDOM recognition worker's per-item processing.

Fully mocked: in-memory models, an injected async config resolver, and a canned
sidecar ``request_fn`` — no database, no network. Covers the fail-closed
outcomes (unconfigured -> pending, bad payload -> failed, empty response ->
failed) that keep a pending PDF from ever masquerading as parsed.
"""

import asyncio
import base64
import logging
from types import SimpleNamespace

import pytest

from db.models import Attachment, Document, Email
from services.content_graph import ContentSegment, ParseResult
from services.newsdom_client import NewsdomConfigurationError, NewsdomPayloadTooLargeError
from services.newsdom_pdf_recognition import (
    PDF_DOM_RECOGNITION_FAILED_STATUS,
    PDF_DOM_RECOGNITION_PENDING_STATUS,
    NewsdomRuntimeConfig,
    PdfDomRecognitionRecords,
)
import services.newsdom_worker as newsdom_worker_module

NewsdomRecognitionWorker = newsdom_worker_module.NewsdomRecognitionWorker
RESULT_FAILED = newsdom_worker_module.RESULT_FAILED
RESULT_PENDING = newsdom_worker_module.RESULT_PENDING
RESULT_RECOGNIZED = newsdom_worker_module.RESULT_RECOGNIZED
process_pending_attachment = newsdom_worker_module.process_pending_attachment
process_pending_document = newsdom_worker_module.process_pending_document


def _config() -> NewsdomRuntimeConfig:
    return NewsdomRuntimeConfig(
        base_url="https://newsdom.example.com",
        api_token=None,
        request_language="auto",
        recognition_mode="auto",
        provider_name="primary",
    )


def _canned_response() -> dict:
    return {
        "pages": [
            {
                "page_number": 1,
                "articles": [{"headline": "Headline", "body_blocks": ["Body one."]}],
            }
        ]
    }


async def _resolver_with(config):
    async def resolve(_session, _org):
        return config

    return resolve


def _pending_attachment(
    payload: bytes = b"%PDF-1.7 fake",
    *,
    attachment_id: int | None = None,
    organization_id: str = "org-1",
) -> Attachment:
    email = Email()
    email.organization_id = organization_id
    attachment = Attachment(
        id=attachment_id,
        filename="news.pdf",
        content=base64.b64encode(payload).decode("ascii"),
        parse_status=PDF_DOM_RECOGNITION_PENDING_STATUS,
    )
    email.attachments.append(attachment)
    return attachment


def _pending_document(document_id: str, *, organization_id: str = "org-1") -> Document:
    return Document(
        document_id=document_id,
        workspace_id="ws-1",
        organization_id=organization_id,
        document_name="news.pdf",
        document_type="pdf",
        document_content=base64.b64encode(b"%PDF-1.7 fake").decode("ascii"),
        document_status=PDF_DOM_RECOGNITION_PENDING_STATUS,
    )


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
async def test_attachment_recognized_when_configured():
    attachment = _pending_attachment()

    async def request_fn(**_kwargs):
        return _canned_response()

    result = await process_pending_attachment(
        session=object(),
        attachment=attachment,
        config_resolver=await _resolver_with(_config()),
        request_fn=request_fn,
    )
    assert result == RESULT_RECOGNIZED
    assert attachment.parse_status == "parsed"
    assert "Headline" in attachment.content
    assert attachment.content_segments


@pytest.mark.asyncio
async def test_attachment_left_pending_when_no_provider():
    attachment = _pending_attachment()

    async def request_fn(**_kwargs):  # pragma: no cover - must not be called
        raise AssertionError("sidecar must not be called when unconfigured")

    result = await process_pending_attachment(
        session=object(),
        attachment=attachment,
        config_resolver=await _resolver_with(None),
        request_fn=request_fn,
    )
    assert result == RESULT_PENDING
    assert attachment.parse_status == PDF_DOM_RECOGNITION_PENDING_STATUS


@pytest.mark.asyncio
async def test_attachment_failed_on_invalid_payload():
    attachment = _pending_attachment()
    attachment.content = "not@@base64!!"

    async def request_fn(**_kwargs):  # pragma: no cover
        raise AssertionError("must not reach sidecar with a bad payload")

    result = await process_pending_attachment(
        session=object(),
        attachment=attachment,
        config_resolver=await _resolver_with(_config()),
        request_fn=request_fn,
    )
    assert result == RESULT_FAILED
    assert attachment.parse_status == PDF_DOM_RECOGNITION_FAILED_STATUS
    assert attachment.parse_error_code == "invalid_pending_payload"


@pytest.mark.asyncio
async def test_attachment_failed_on_empty_sidecar_response():
    attachment = _pending_attachment()

    async def request_fn(**_kwargs):
        return {"pages": []}

    result = await process_pending_attachment(
        session=object(),
        attachment=attachment,
        config_resolver=await _resolver_with(_config()),
        request_fn=request_fn,
    )
    assert result == RESULT_FAILED
    assert attachment.parse_status == PDF_DOM_RECOGNITION_FAILED_STATUS
    assert attachment.parse_error_code == "recognition_failed"
    # Never landed as parsed with empty content.
    assert attachment.parse_status != "parsed"


@pytest.mark.asyncio
async def test_attachment_above_provider_limit_fails_instead_of_remaining_pending(caplog):
    attachment = _pending_attachment()

    async def oversized_request(**_kwargs):
        raise NewsdomPayloadTooLargeError("provider limit")

    with caplog.at_level(logging.INFO, logger="services.newsdom_worker"):
        result = await process_pending_attachment(
            session=object(),
            attachment=attachment,
            config_resolver=await _resolver_with(_config()),
            request_fn=oversized_request,
        )

    assert result == RESULT_FAILED
    assert attachment.parse_status == PDF_DOM_RECOGNITION_FAILED_STATUS
    assert attachment.parse_error_code == "provider_payload_size_exceeded"
    records = [record for record in caplog.records if "exceeds the provider payload contract" in record.message]
    assert records and all(record.levelno == logging.INFO for record in records)


@pytest.mark.asyncio
async def test_attachment_orphan_and_rejected_configuration_stay_visible():
    orphan = Attachment(
        filename="orphan.pdf",
        content=base64.b64encode(b"%PDF-1.7 fake").decode("ascii"),
        parse_status=PDF_DOM_RECOGNITION_PENDING_STATUS,
    )
    orphan_result = await process_pending_attachment(
        session=object(),
        attachment=orphan,
        config_resolver=await _resolver_with(_config()),
    )
    assert orphan_result == RESULT_FAILED
    assert orphan.parse_error_code == "orphan_attachment"

    attachment = _pending_attachment()

    async def rejected_request(**_kwargs):
        raise NewsdomConfigurationError("host rejected")

    rejected_result = await process_pending_attachment(
        session=object(),
        attachment=attachment,
        config_resolver=await _resolver_with(_config()),
        request_fn=rejected_request,
    )
    assert rejected_result == RESULT_PENDING
    assert attachment.parse_status == PDF_DOM_RECOGNITION_PENDING_STATUS


@pytest.mark.asyncio
async def test_document_recognized_when_configured():
    document = Document(
        document_id="doc-1",
        workspace_id="ws-1",
        organization_id="org-1",
        document_name="news.pdf",
        document_type="pdf",
        document_content=base64.b64encode(b"%PDF-1.7 fake").decode("ascii"),
        document_status=PDF_DOM_RECOGNITION_PENDING_STATUS,
    )

    async def request_fn(**_kwargs):
        return _canned_response()

    result = await process_pending_document(
        session=object(),
        document=document,
        config_resolver=await _resolver_with(_config()),
        request_fn=request_fn,
    )
    assert result == RESULT_RECOGNIZED
    assert document.document_status == "parsed"
    assert "Headline" in document.document_content


@pytest.mark.asyncio
async def test_document_failed_on_empty_response():
    document = Document(
        document_id="doc-2",
        workspace_id="ws-1",
        organization_id="org-1",
        document_name="news.pdf",
        document_type="pdf",
        document_content=base64.b64encode(b"%PDF-1.7 fake").decode("ascii"),
        document_status=PDF_DOM_RECOGNITION_PENDING_STATUS,
    )

    async def request_fn(**_kwargs):
        return {"pages": []}

    result = await process_pending_document(
        session=object(),
        document=document,
        config_resolver=await _resolver_with(_config()),
        request_fn=request_fn,
    )
    assert result == RESULT_FAILED
    assert document.document_status == PDF_DOM_RECOGNITION_FAILED_STATUS


@pytest.mark.asyncio
async def test_document_invalid_payload_and_rejected_configuration_are_visible():
    invalid = _pending_document("doc-invalid")
    invalid.document_content = "not@@base64"
    invalid_result = await process_pending_document(
        session=object(),
        document=invalid,
        config_resolver=await _resolver_with(_config()),
    )
    assert invalid_result == RESULT_FAILED
    assert invalid.document_status == PDF_DOM_RECOGNITION_FAILED_STATUS

    document = _pending_document("doc-rejected")

    async def rejected_request(**_kwargs):
        raise NewsdomConfigurationError("host rejected")

    rejected_result = await process_pending_document(
        session=object(),
        document=document,
        config_resolver=await _resolver_with(_config()),
        request_fn=rejected_request,
    )
    assert rejected_result == RESULT_PENDING
    assert document.document_status == PDF_DOM_RECOGNITION_PENDING_STATUS


def test_attachment_mapping_keeps_unmatched_segments_without_false_parent():
    email = Email()
    attachment = Attachment(filename="news.pdf", content="pending")
    email.attachments.append(attachment)
    segment = ContentSegment(
        content_segment_uid="segment-1",
        source_kind="attachment",
        source_record_uid="attachment-1",
        content_node_uid="missing-node",
        segment_kind="paragraph",
        segment_path="/paragraph/1",
        ordinal_index=0,
        heading_path=None,
        safe_text_content="Recognized text",
        content_hash="hash",
        word_count=2,
    )
    records = PdfDomRecognitionRecords(
        parse_text="Recognized text",
        source_content_hash="source-hash",
        parse_result=ParseResult(
            source_kind="attachment",
            source_record_uid="attachment-1",
            display_name="news.pdf",
            content_type="application/pdf",
            source_content_hash="source-hash",
            nodes=(),
            segments=(segment,),
        ),
    )

    newsdom_worker_module.apply_recognition_to_attachment(
        email=email,
        attachment=attachment,
        records=records,
    )

    assert attachment.content_segments[0].content_node is None
    assert email.content_segments[0] is attachment.content_segments[0]


@pytest.mark.asyncio
async def test_attachment_sweep_advances_past_unconfigured_batch():
    blocked = [
        _pending_attachment(attachment_id=index, organization_id="org-blocked")
        for index in range(1, 11)
    ]
    ready = _pending_attachment(attachment_id=11, organization_id="org-ready")
    session = _SequenceSession([blocked, [ready]])

    async def config_resolver(_session, organization_id):
        return _config() if organization_id == "org-ready" else None

    request_count = 0

    async def request_fn(**_kwargs):
        nonlocal request_count
        request_count += 1
        return _canned_response()

    worker = NewsdomRecognitionWorker(
        batch_limit=10,
        config_resolver=config_resolver,
        request_fn=request_fn,
    )
    await worker._sweep_attachments(session)
    await worker._sweep_attachments(session)

    second_query = session.statements[1].compile()
    assert "email_attachments.id >" in str(second_query)
    assert 10 in second_query.params.values()
    assert worker._attachment_cursor == 11
    assert ready.parse_status == "parsed"
    assert request_count == 1
    assert session.commit_count == 11
    assert session.rollback_count == 0


@pytest.mark.asyncio
async def test_document_sweep_advances_and_wraps_without_starvation():
    blocked = [
        _pending_document(f"doc-{index:03d}", organization_id="org-blocked")
        for index in range(1, 11)
    ]
    ready_after_batch = _pending_document("doc-011", organization_id="org-ready")
    ready_after_wrap = _pending_document("doc-001", organization_id="org-ready")
    session = _SequenceSession([blocked, [ready_after_batch], [], [ready_after_wrap]])

    async def config_resolver(_session, organization_id):
        return _config() if organization_id == "org-ready" else None

    async def request_fn(**_kwargs):
        return _canned_response()

    worker = NewsdomRecognitionWorker(
        batch_limit=10,
        config_resolver=config_resolver,
        request_fn=request_fn,
    )
    await worker._sweep_documents(session)
    await worker._sweep_documents(session)
    worker._document_cursor = "doc-999"
    await worker._sweep_documents(session)

    second_query = session.statements[1].compile()
    wrapped_query = session.statements[3].compile()
    assert "workspace_documents.document_id >" in str(second_query)
    assert "doc-010" in second_query.params.values()
    assert "workspace_documents.document_id >" not in str(wrapped_query)
    assert worker._document_cursor == "doc-001"
    assert ready_after_batch.document_status == "parsed"
    assert ready_after_wrap.document_status == "parsed"
    assert session.commit_count == 12
    assert session.rollback_count == 0


@pytest.mark.asyncio
async def test_attachment_cursor_wraps_and_empty_batches_are_stable():
    wrapped = _pending_attachment(attachment_id=1)
    session = _SequenceSession([[], [wrapped], []])
    worker = NewsdomRecognitionWorker(batch_limit=10)
    worker._attachment_cursor = 999

    rows = await worker._load_pending_attachments(session)
    empty_rows = await worker._load_pending_attachments(session)

    assert rows == [wrapped]
    assert empty_rows == []
    assert worker._attachment_cursor is None
    assert "email_attachments.id >" in str(session.statements[0])
    assert "email_attachments.id >" not in str(session.statements[1])


@pytest.mark.asyncio
async def test_empty_sweeps_leave_both_cursors_unset():
    attachment_session = _SequenceSession([[]])
    document_session = _SequenceSession([[]])
    worker = NewsdomRecognitionWorker()

    await worker._sweep_attachments(attachment_session)
    await worker._sweep_documents(document_session)

    assert worker._attachment_cursor is None
    assert worker._document_cursor is None
    assert attachment_session.commit_count == 0
    assert document_session.commit_count == 0


@pytest.mark.asyncio
async def test_sweeps_rollback_one_item_failure_and_continue_isolation():
    attachment = _pending_attachment(attachment_id=1)
    document = _pending_document("doc-1")
    attachment_session = _SequenceSession([[attachment]])
    document_session = _SequenceSession([[document]])

    async def broken_resolver(_session, _organization_id):
        raise RuntimeError("provider lookup failed")

    worker = NewsdomRecognitionWorker(config_resolver=broken_resolver)
    await worker._sweep_attachments(attachment_session)
    await worker._sweep_documents(document_session)

    assert attachment_session.commit_count == 0
    assert attachment_session.rollback_count == 1
    assert document_session.commit_count == 0
    assert document_session.rollback_count == 1


@pytest.mark.asyncio
async def test_postgresql_lease_helpers_and_non_postgresql_fallback():
    postgres = _LeaseSession(scalar_result=1)
    sqlite = _LeaseSession(dialect_name="sqlite")

    assert await newsdom_worker_module._try_acquire_sweep_lease(postgres) is True
    assert postgres.scalar_calls[0][1] == newsdom_worker_module._SWEEP_LOCK_PARAMS
    await newsdom_worker_module._release_sweep_lease(postgres)
    assert len(postgres.scalar_calls) == 2
    assert await newsdom_worker_module._try_acquire_sweep_lease(sqlite) is None

    class BrokenBindSession:
        def get_bind(self):
            raise RuntimeError("no bind")

    assert newsdom_worker_module._session_uses_postgresql(BrokenBindSession()) is False


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("lease", "expected_sweeps", "expected_releases"),
    [(False, 0, 0), (None, 2, 0), (True, 2, 1)],
)
async def test_worker_sweep_honors_lease_outcome(
    monkeypatch, lease, expected_sweeps, expected_releases
):
    session = object()
    calls = []
    releases = []
    worker = NewsdomRecognitionWorker()

    monkeypatch.setattr(
        newsdom_worker_module,
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

    async def sweep_documents(actual_session):
        calls.append(("documents", actual_session))

    monkeypatch.setattr(newsdom_worker_module, "_try_acquire_sweep_lease", acquire)
    monkeypatch.setattr(newsdom_worker_module, "_release_sweep_lease", release)
    monkeypatch.setattr(worker, "_sweep_attachments", sweep_attachments)
    monkeypatch.setattr(worker, "_sweep_documents", sweep_documents)

    await worker._sweep()

    assert len(calls) == expected_sweeps
    assert len(releases) == expected_releases


@pytest.mark.asyncio
async def test_worker_start_stop_are_idempotent(monkeypatch):
    worker = NewsdomRecognitionWorker()
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
    worker = NewsdomRecognitionWorker(interval_seconds=1)
    worker._is_running = True
    sleep_calls = 0

    async def sleep_then_cancel(_seconds):
        nonlocal sleep_calls
        sleep_calls += 1
        if sleep_calls > 1:
            raise asyncio.CancelledError

    async def failing_sweep():
        raise RuntimeError("sweep failed")

    monkeypatch.setattr(newsdom_worker_module.asyncio, "sleep", sleep_then_cancel)
    monkeypatch.setattr(worker, "_sweep", failing_sweep)
    await worker._run_loop()
    assert sleep_calls == 2

    async def cancel_immediately(_seconds):
        raise asyncio.CancelledError

    monkeypatch.setattr(newsdom_worker_module.asyncio, "sleep", cancel_immediately)
    await worker._run_loop()


@pytest.mark.asyncio
async def test_worker_loop_stops_when_sweep_is_cancelled(monkeypatch):
    worker = NewsdomRecognitionWorker(interval_seconds=1)
    worker._is_running = True

    async def no_sleep(_seconds):
        return None

    async def cancelled_sweep():
        raise asyncio.CancelledError

    monkeypatch.setattr(newsdom_worker_module.asyncio, "sleep", no_sleep)
    monkeypatch.setattr(worker, "_sweep", cancelled_sweep)
    await worker._run_loop()


@pytest.mark.asyncio
async def test_worker_loop_returns_after_a_normal_interval(monkeypatch):
    worker = NewsdomRecognitionWorker(interval_seconds=1)
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

    monkeypatch.setattr(newsdom_worker_module.asyncio, "sleep", stop_after_interval)
    monkeypatch.setattr(worker, "_sweep", successful_sweep)
    await worker._run_loop()

    assert sleep_calls == 2
    assert sweep_calls == 1


@pytest.mark.asyncio
async def test_worker_loop_skips_interval_when_sweep_stops_worker(monkeypatch):
    worker = NewsdomRecognitionWorker(interval_seconds=1)
    worker._is_running = True
    sleep_calls = 0

    async def record_sleep(_seconds):
        nonlocal sleep_calls
        sleep_calls += 1

    async def stopping_sweep():
        worker._is_running = False

    monkeypatch.setattr(newsdom_worker_module.asyncio, "sleep", record_sleep)
    monkeypatch.setattr(worker, "_sweep", stopping_sweep)
    await worker._run_loop()

    assert sleep_calls == 1
