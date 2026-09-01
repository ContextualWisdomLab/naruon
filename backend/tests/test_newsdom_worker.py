"""Unit tests for the NewsDOM recognition worker's per-item processing.

Fully mocked: in-memory models, an injected async config resolver, and a canned
sidecar ``request_fn`` — no database, no network. Covers the fail-closed
outcomes (unconfigured -> pending, bad payload -> failed, empty response ->
failed) that keep a pending PDF from ever masquerading as parsed.
"""

import asyncio
import base64
from types import SimpleNamespace

import pytest

from db.models import Attachment, Document, Email
from services.content_graph import ContentSegment, ParseResult
from services.newsdom_client import NewsdomConfigurationError
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


def _row_key(row):
    """Return the id a bulk-loaded row is keyed by for ``session.get``.

    Duck-typed (not ``isinstance``) so the expired-instance test doubles
    (``_ExpiredAttachment``/``_ExpiredDocument``, which only expose one of
    ``id``/``document_id`` and raise ``AttributeError`` on any other read)
    register under the right key without triggering that raise.
    """
    document_id = getattr(row, "document_id", None)
    return row.id if document_id is None else document_id


class _SequenceSession:
    """A fake session whose ``get`` always returns a fresh, healthy instance.

    Mirrors the real sweep contract: the bulk-loaded rows only supply ids
    and the cursor; every actual processing target is re-fetched via ``get``
    by id, exactly like a real ``AsyncSession`` would after an earlier
    item's rollback expired the bulk-loaded instances. ``by_id`` lets a
    test register a *different* object than the bulk-loaded one to prove
    that re-fetch is what the sweep actually uses.
    """

    def __init__(self, row_batches, *, by_id=None):
        self._row_batches = list(row_batches)
        self._by_id = dict(by_id or {})
        for batch in self._row_batches:
            for row in batch:
                self._by_id.setdefault(_row_key(row), row)
        self.statements = []
        self.commit_count = 0
        self.rollback_count = 0

    async def execute(self, statement):
        self.statements.append(statement)
        return _RowsResult(self._row_batches.pop(0))

    async def get(self, _model, row_id, options=None):
        return self._by_id.get(row_id)

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


class _LeaseConnectionContext:
    def __init__(self, connection):
        self.connection = connection

    async def __aenter__(self):
        return self.connection

    async def __aexit__(self, *_args):
        return False


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
async def test_attachment_sweep_caps_the_cursor_at_the_first_failure_not_the_last_row(
    monkeypatch,
):
    # Reproduces the same starvation class already fixed on
    # AttachmentReparseWorker: if the cursor advanced to rows[-1].id
    # unconditionally, a mid-batch failure would be skipped by every future
    # sweep (its id falls below the cursor) until the whole forward queue
    # happened to drain to empty.
    first = _pending_attachment(attachment_id=1)
    second = _pending_attachment(attachment_id=2)
    third = _pending_attachment(attachment_id=3)
    session = _SequenceSession([[first, second, third]])

    async def config_resolver(_session, _organization_id):
        return _config()

    async def fail_only_the_middle_item(*, session, attachment, config_resolver, request_fn):
        if attachment.id == 2:
            raise RuntimeError("recognition blew up")
        return await process_pending_attachment(
            session=session,
            attachment=attachment,
            config_resolver=config_resolver,
            request_fn=request_fn,
        )

    monkeypatch.setattr(
        newsdom_worker_module, "process_pending_attachment", fail_only_the_middle_item
    )
    async def request_fn(**_kwargs):
        return _canned_response()

    worker = NewsdomRecognitionWorker(
        config_resolver=config_resolver,
        request_fn=request_fn,
    )
    await worker._sweep_attachments(session)

    # The cursor stops just before the failed row (id 2), not at the batch's
    # last row (id 3), so the next sweep's "id > cursor" filter still
    # reselects the still-pending row 2.
    assert worker._attachment_cursor == 1
    assert first.parse_status == "parsed"
    assert third.parse_status == "parsed"
    assert session.commit_count == 2
    assert session.rollback_count == 1


@pytest.mark.asyncio
async def test_attachment_sweep_caps_the_cursor_at_the_first_pending_result_too():
    # RESULT_PENDING (no active provider yet) leaves parse_status untouched,
    # exactly like a raised exception -- the row must still be selectable by
    # the next sweep's "id > cursor" filter, not skipped forever just
    # because later rows in the same batch resolved successfully.
    first = _pending_attachment(attachment_id=1, organization_id="org-unconfigured")
    second = _pending_attachment(attachment_id=2, organization_id="org-ready")
    third = _pending_attachment(attachment_id=3, organization_id="org-ready")
    session = _SequenceSession([[first, second, third]])

    async def config_resolver(_session, organization_id):
        return _config() if organization_id == "org-ready" else None

    async def request_fn(**_kwargs):
        return _canned_response()

    worker = NewsdomRecognitionWorker(
        config_resolver=config_resolver,
        request_fn=request_fn,
    )
    await worker._sweep_attachments(session)

    # The cursor stops just before the still-pending row (id 1), not at the
    # batch's last row (id 3), so a later sweep -- once org-unconfigured
    # gains a provider -- still reselects it.
    assert worker._attachment_cursor == 0
    assert first.parse_status == PDF_DOM_RECOGNITION_PENDING_STATUS
    assert second.parse_status == "parsed"
    assert third.parse_status == "parsed"
    assert session.rollback_count == 0


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


class _ExpiredDocument:
    """Document counterpart of ``_ExpiredAttachment``."""

    document_id = "doc-001"

    def __getattr__(self, _name):
        raise AttributeError(
            "must not read attributes off the stale bulk-loaded instance"
        )


@pytest.mark.asyncio
async def test_attachment_sweep_never_processes_the_bulk_loaded_instance_directly():
    poisoned_first = _ExpiredAttachment()
    fresh_first = _pending_attachment(attachment_id=1, organization_id="org-ready")
    second = _pending_attachment(attachment_id=2, organization_id="org-ready")
    # The bulk query "sees" the poisoned stand-in for id 1 (as a real
    # AsyncSession would after some earlier rollback expired it), but `get`
    # returns the real, healthy row -- proving the sweep re-fetches instead
    # of processing the bulk-loaded object directly.
    session = _SequenceSession(
        [[poisoned_first, second]], by_id={1: fresh_first, 2: second}
    )

    async def config_resolver(_session, _organization_id):
        return _config()

    async def request_fn(**_kwargs):
        return _canned_response()

    worker = NewsdomRecognitionWorker(
        config_resolver=config_resolver, request_fn=request_fn
    )
    await worker._sweep_attachments(session)

    assert fresh_first.parse_status == "parsed"
    assert second.parse_status == "parsed"
    assert session.commit_count == 2
    assert session.rollback_count == 0


@pytest.mark.asyncio
async def test_document_sweep_advances_and_wraps_without_starvation():
    # A batch that fully resolves lets the cursor legitimately advance to
    # its tail. The next sweep then finds nothing above that cursor and
    # wraps (resets to None, re-queries from the start) -- which is how a
    # late-arriving row behind the old cursor position gets picked up. A
    # row that comes back via the wrap but is still blocked (no provider
    # configured for its org) must not itself advance the cursor -- that is
    # the same no-starvation fix as `_sweep_attachments`, just reached via
    # the wrap path instead of directly.
    resolved_batch = [
        _pending_document(f"doc-{index:03d}", organization_id="org-ready")
        for index in range(1, 11)
    ]
    late_arrival = _pending_document("doc-011", organization_id="org-blocked")
    # The re-sweep re-fetches "doc-011" by id -- exactly like a real
    # database would return the current state of that single row, not a
    # separate instance -- so simulate "it became configured" by mutating
    # the same object rather than registering a second, distinct Document
    # under the same id.
    session = _SequenceSession(
        [resolved_batch, [], [late_arrival], [late_arrival]]
    )

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
    assert worker._document_cursor == "doc-010"
    for document in resolved_batch:
        assert document.document_status == "parsed"

    await worker._sweep_documents(session)
    # Nothing above "doc-010" existed, so the wrap fired; the still-blocked
    # late arrival keeps the cursor at None rather than skipping past it.
    assert worker._document_cursor is None
    assert late_arrival.document_status == PDF_DOM_RECOGNITION_PENDING_STATUS

    late_arrival.organization_id = "org-ready"
    await worker._sweep_documents(session)
    assert worker._document_cursor == "doc-011"
    assert late_arrival.document_status == "parsed"

    empty_query = session.statements[1].compile()
    wrapped_query = session.statements[2].compile()
    assert "workspace_documents.document_id >" in str(empty_query)
    assert "doc-010" in empty_query.params.values()
    assert "workspace_documents.document_id >" not in str(wrapped_query)
    assert session.commit_count == 12
    assert session.rollback_count == 0


@pytest.mark.asyncio
async def test_document_sweep_caps_the_cursor_at_the_first_failure_not_the_last_row(
    monkeypatch,
):
    # Same starvation class as the attachment sweep, adapted for the
    # string-keyed document cursor: there is no "id - 1" to fall back on, so
    # the fix tracks the last row actually confirmed resolved before the
    # failure instead.
    first = _pending_document("doc-001")
    second = _pending_document("doc-002")
    third = _pending_document("doc-003")
    session = _SequenceSession([[first, second, third]])

    async def config_resolver(_session, _organization_id):
        return _config()

    async def fail_only_the_middle_item(*, session, document, config_resolver, request_fn):
        if document.document_id == "doc-002":
            raise RuntimeError("recognition blew up")
        return await process_pending_document(
            session=session,
            document=document,
            config_resolver=config_resolver,
            request_fn=request_fn,
        )

    monkeypatch.setattr(
        newsdom_worker_module, "process_pending_document", fail_only_the_middle_item
    )
    async def request_fn(**_kwargs):
        return _canned_response()

    worker = NewsdomRecognitionWorker(
        config_resolver=config_resolver,
        request_fn=request_fn,
    )
    await worker._sweep_documents(session)

    assert worker._document_cursor == "doc-001"
    assert first.document_status == "parsed"
    assert third.document_status == "parsed"
    assert session.commit_count == 2
    assert session.rollback_count == 1


@pytest.mark.asyncio
async def test_document_sweep_caps_the_cursor_at_the_first_pending_result_too():
    # Same fix as the attachment sweep: RESULT_PENDING must cap the cursor
    # just like a raised exception, not advance past the still-pending row.
    first = _pending_document("doc-001", organization_id="org-unconfigured")
    second = _pending_document("doc-002", organization_id="org-ready")
    third = _pending_document("doc-003", organization_id="org-ready")
    session = _SequenceSession([[first, second, third]])

    async def config_resolver(_session, organization_id):
        return _config() if organization_id == "org-ready" else None

    async def request_fn(**_kwargs):
        return _canned_response()

    worker = NewsdomRecognitionWorker(
        config_resolver=config_resolver,
        request_fn=request_fn,
    )
    await worker._sweep_documents(session)

    assert worker._document_cursor is None
    assert first.document_status == PDF_DOM_RECOGNITION_PENDING_STATUS
    assert second.document_status == "parsed"
    assert third.document_status == "parsed"
    assert session.rollback_count == 0


@pytest.mark.asyncio
async def test_document_sweep_never_processes_the_bulk_loaded_instance_directly():
    poisoned_first = _ExpiredDocument()
    fresh_first = _pending_document("doc-001", organization_id="org-ready")
    second = _pending_document("doc-002", organization_id="org-ready")
    session = _SequenceSession(
        [[poisoned_first, second]],
        by_id={"doc-001": fresh_first, "doc-002": second},
    )

    async def config_resolver(_session, _organization_id):
        return _config()

    async def request_fn(**_kwargs):
        return _canned_response()

    worker = NewsdomRecognitionWorker(
        config_resolver=config_resolver, request_fn=request_fn
    )
    await worker._sweep_documents(session)

    assert fresh_first.document_status == "parsed"
    assert second.document_status == "parsed"
    assert session.commit_count == 2
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
async def test_postgresql_lease_helpers_and_non_postgresql_fallback(monkeypatch):
    postgres_connection = _LeaseConnection(scalar_result=1)

    assert (
        await newsdom_worker_module._try_acquire_sweep_lease(postgres_connection)
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
        == newsdom_worker_module._SWEEP_LOCK_PARAMS
    )
    # Ordering, not just occurrence: AUTOCOMMIT must be set before the
    # advisory-lock query runs, or the query could still open an implicit
    # transaction under the connection's prior isolation level.
    assert postgres_connection.ordered_calls[0][0] == "execution_options"
    assert postgres_connection.ordered_calls[1][0] == "scalar"
    await newsdom_worker_module._release_sweep_lease(postgres_connection)
    assert len(postgres_connection.scalar_calls) == 2

    monkeypatch.setattr(
        newsdom_worker_module, "engine", _FakeEngine(dialect_name="sqlite")
    )
    assert newsdom_worker_module._engine_uses_postgresql() is False

    monkeypatch.setattr(
        newsdom_worker_module, "engine", _FakeEngine(dialect_name="postgresql")
    )
    assert newsdom_worker_module._engine_uses_postgresql() is True


@pytest.mark.asyncio
async def test_worker_sweep_skips_locking_when_engine_is_not_postgresql(monkeypatch):
    session = object()
    calls = []
    worker = NewsdomRecognitionWorker()

    monkeypatch.setattr(
        newsdom_worker_module, "engine", _FakeEngine(dialect_name="sqlite")
    )
    monkeypatch.setattr(
        newsdom_worker_module,
        "AsyncSessionLocal",
        lambda: _AsyncSessionContext(session),
    )

    async def sweep_attachments(actual_session):
        calls.append(("attachments", actual_session))

    async def sweep_documents(actual_session):
        calls.append(("documents", actual_session))

    monkeypatch.setattr(worker, "_sweep_attachments", sweep_attachments)
    monkeypatch.setattr(worker, "_sweep_documents", sweep_documents)

    await worker._sweep()

    assert calls == [("attachments", session), ("documents", session)]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("lease", "expected_sweeps", "expected_releases"),
    [(False, 0, 0), (True, 2, 1)],
)
async def test_worker_sweep_honors_lease_outcome(
    monkeypatch, lease, expected_sweeps, expected_releases
):
    session = object()
    lock_connection = object()
    calls = []
    releases = []
    worker = NewsdomRecognitionWorker()

    monkeypatch.setattr(
        newsdom_worker_module,
        "engine",
        _FakeEngine(dialect_name="postgresql", connection=lock_connection),
    )
    monkeypatch.setattr(
        newsdom_worker_module,
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
