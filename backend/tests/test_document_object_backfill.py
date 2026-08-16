"""Regression tests for migrating legacy inline pending PDFs into S3."""

from types import SimpleNamespace

import pytest

from db.document_object_record import DocumentObjectRecord
from db.models import Document
import services.document_object_backfill as backfill_module
from services.document_object_storage import (
    DocumentObjectStorageError,
    StoredDocumentPayload,
)
from services.s3_object_storage import S3StoredObject


class _RowsResult:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return self

    def all(self):
        return self._rows


class _BackfillSession:
    def __init__(self, documents, *, existing_records=None, fail_commit_for=None):
        self.documents = {document.document_id: document for document in documents}
        self.existing_records = existing_records or {}
        self.fail_commit_for = set(fail_commit_for or ())
        self.added = []
        self.commit_count = 0
        self.rollback_count = 0
        self._current_document_id = None

    async def execute(self, _statement):
        return _RowsResult(list(self.documents))

    async def get(self, model, record_id):
        assert model is Document
        self._current_document_id = record_id
        return self.documents.get(record_id)

    async def scalar(self, _statement):
        return self.existing_records.get(self._current_document_id)

    def add(self, value):
        self.added.append(value)

    async def commit(self):
        if self._current_document_id in self.fail_commit_for:
            self.fail_commit_for.remove(self._current_document_id)
            raise RuntimeError("database commit unavailable")
        self.commit_count += 1

    async def rollback(self):
        self.rollback_count += 1


class _BackfillSessionContext:
    """Expose one operator backfill session through an async context manager."""

    def __init__(self, session: object) -> None:
        self.session = session

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, _exc_type, _exc, _tb) -> None:
        return None


class _BackfillSessionFactory:
    """Return fresh sentinel sessions and record each bounded batch."""

    def __init__(self) -> None:
        self.sessions: list[object] = []

    def __call__(self) -> _BackfillSessionContext:
        session = object()
        self.sessions.append(session)
        return _BackfillSessionContext(session)


def _pending_document(document_id: str) -> Document:
    return Document(
        document_id=document_id,
        workspace_id="workspace-one",
        organization_id="organization-one",
        document_name=f"{document_id}.pdf",
        document_type="pdf",
        document_content="JVBERi0xLjcgcmVhbA==",
        document_status="pdf_dom_recognition_pending",
    )


def _stored_payload(document_id: str) -> StoredDocumentPayload:
    return StoredDocumentPayload.for_s3(
        S3StoredObject(
            bucket_name="naruon-documents",
            object_key=f"opaque/{document_id}.pdf",
            content_type="application/pdf",
            content_length=13,
            checksum_sha256="a" * 64,
        ),
        object_storage_provider_id=77,
    )


def _install_runtime(monkeypatch) -> None:
    """Resolve a stable organization provider without coupling tests to DNS."""

    async def resolve(_session, organization_id):
        assert organization_id == "organization-one"
        return SimpleNamespace(
            storage_backend="s3",
            object_storage_provider_id=77,
        )

    monkeypatch.setattr(
        backfill_module,
        "resolve_document_storage_runtime_config",
        resolve,
    )


@pytest.mark.asyncio
async def test_backfill_migrates_each_legacy_pending_pdf_atomically(monkeypatch):
    first = _pending_document("doc-one")
    second = _pending_document("doc-two")
    session = _BackfillSession([first, second])
    stored_ids = []

    monkeypatch.setattr(
        backfill_module,
        "settings",
        SimpleNamespace(OBJECT_STORAGE_BACKEND="s3"),
    )
    _install_runtime(monkeypatch)
    monkeypatch.setattr(
        backfill_module,
        "decode_legacy_pdf_payload",
        lambda payload: b"%PDF-1.7 real" if payload else b"",
    )

    async def store_payload(**kwargs):
        stored_ids.append(kwargs["document_id"])
        assert kwargs["runtime_config"].object_storage_provider_id == 77
        return _stored_payload(kwargs["document_id"])

    monkeypatch.setattr(backfill_module, "store_configured_pdf_document", store_payload)

    result = await backfill_module.backfill_legacy_document_payloads(
        session,
        batch_limit=10,
    )

    assert result.selected_count == 2
    assert result.migrated_count == 2
    assert result.failed_count == 0
    assert stored_ids == ["doc-one", "doc-two"]
    assert first.document_content is None
    assert second.document_content is None
    assert session.commit_count == 2
    assert session.rollback_count == 0
    records = [value for value in session.added if isinstance(value, DocumentObjectRecord)]
    assert [record.document_id for record in records] == ["doc-one", "doc-two"]
    assert all(record.object_storage_provider_id == 77 for record in records)


@pytest.mark.asyncio
async def test_backfill_failure_is_retryable_and_does_not_starve(monkeypatch):
    first = _pending_document("doc-one")
    second = _pending_document("doc-two")
    session = _BackfillSession([first, second])

    monkeypatch.setattr(
        backfill_module,
        "settings",
        SimpleNamespace(OBJECT_STORAGE_BACKEND="s3"),
    )
    _install_runtime(monkeypatch)
    monkeypatch.setattr(
        backfill_module,
        "decode_legacy_pdf_payload",
        lambda _payload: b"%PDF-1.7 real",
    )

    async def store_payload(**kwargs):
        if kwargs["document_id"] == "doc-one":
            raise DocumentObjectStorageError("temporary S3 outage")
        return _stored_payload(kwargs["document_id"])

    monkeypatch.setattr(backfill_module, "store_configured_pdf_document", store_payload)

    result = await backfill_module.backfill_legacy_document_payloads(
        session,
        batch_limit=10,
    )

    assert result.migrated_count == 1
    assert result.failed_count == 1
    assert first.document_content is not None
    assert second.document_content is None
    assert session.commit_count == 1
    assert session.rollback_count == 1


@pytest.mark.asyncio
async def test_backfill_compensates_remote_object_after_commit_failure(monkeypatch):
    document = _pending_document("doc-one")
    session = _BackfillSession([document], fail_commit_for={"doc-one"})
    compensated = []

    monkeypatch.setattr(
        backfill_module,
        "settings",
        SimpleNamespace(OBJECT_STORAGE_BACKEND="s3"),
    )
    _install_runtime(monkeypatch)
    monkeypatch.setattr(
        backfill_module,
        "decode_legacy_pdf_payload",
        lambda _payload: b"%PDF-1.7 real",
    )

    async def store_payload(**kwargs):
        return _stored_payload(kwargs["document_id"])

    async def compensate(stored, **kwargs):
        assert kwargs["runtime_config"].object_storage_provider_id == 77
        compensated.append(stored)

    monkeypatch.setattr(backfill_module, "store_configured_pdf_document", store_payload)
    monkeypatch.setattr(backfill_module, "delete_configured_document_payload", compensate)

    result = await backfill_module.backfill_legacy_document_payloads(
        session,
        batch_limit=1,
    )

    assert result.migrated_count == 0
    assert result.failed_count == 1
    assert document.document_content is not None
    assert session.rollback_count == 1
    assert len(compensated) == 1


@pytest.mark.asyncio
async def test_backfill_refuses_non_s3_backend_and_split_brain_rows(monkeypatch):
    document = _pending_document("doc-one")
    session = _BackfillSession([document])
    monkeypatch.setattr(
        backfill_module,
        "settings",
        SimpleNamespace(OBJECT_STORAGE_BACKEND="database"),
    )

    with pytest.raises(DocumentObjectStorageError, match="requires the S3 backend"):
        await backfill_module.backfill_legacy_document_payloads(session, batch_limit=1)

    existing = DocumentObjectRecord(
        document_id="doc-one",
        storage_backend="s3",
        bucket_name="bucket-name",
        object_key="opaque/doc-one.pdf",
        inline_payload=None,
        content_type="application/pdf",
        content_length=13,
        checksum_sha256="b" * 64,
        storage_state="active",
    )
    session = _BackfillSession([document], existing_records={"doc-one": existing})
    monkeypatch.setattr(
        backfill_module,
        "settings",
        SimpleNamespace(OBJECT_STORAGE_BACKEND="s3"),
    )

    result = await backfill_module.backfill_legacy_document_payloads(session, batch_limit=1)
    assert result.migrated_count == 0
    assert result.failed_count == 1
    assert document.document_content is not None
    assert session.rollback_count == 1


@pytest.mark.asyncio
async def test_operator_backfill_runner_uses_fresh_sessions_and_stops_on_empty_batch(
    monkeypatch,
):
    """Bound an operator migration run while proving completion with an empty batch."""
    session_factory = _BackfillSessionFactory()
    results = iter(
        [
            backfill_module.DocumentObjectBackfillResult(2, 2, 0),
            backfill_module.DocumentObjectBackfillResult(0, 0, 0),
        ]
    )
    observed: list[tuple[object, int]] = []

    async def backfill(session, *, batch_limit):
        observed.append((session, batch_limit))
        return next(results)

    monkeypatch.setattr(backfill_module, "backfill_legacy_document_payloads", backfill)

    result = await backfill_module.run_document_object_backfill_batches(
        batch_limit=2,
        max_batches=5,
        session_factory=session_factory,
    )

    assert result.completed is True
    assert result.batch_count == 2
    assert result.selected_count == 2
    assert result.migrated_count == 2
    assert result.failed_count == 0
    assert len(session_factory.sessions) == 2
    assert [batch_limit for _, batch_limit in observed] == [2, 2]
    assert observed[0][0] is not observed[1][0]


@pytest.mark.asyncio
async def test_operator_backfill_runner_fails_closed_at_batch_budget(monkeypatch):
    """Stop at the explicit operator budget instead of retrying forever."""
    session_factory = _BackfillSessionFactory()

    async def persistently_failing(_session, *, batch_limit):
        assert batch_limit == 1
        return backfill_module.DocumentObjectBackfillResult(1, 0, 1)

    monkeypatch.setattr(
        backfill_module,
        "backfill_legacy_document_payloads",
        persistently_failing,
    )

    result = await backfill_module.run_document_object_backfill_batches(
        batch_limit=1,
        max_batches=2,
        session_factory=session_factory,
    )

    assert result.completed is False
    assert result.batch_count == 2
    assert result.selected_count == 2
    assert result.migrated_count == 0
    assert result.failed_count == 2
    assert len(session_factory.sessions) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("batch_limit", "max_batches", "message"),
    [
        (0, 1, "batch_limit must be positive"),
        (1, 0, "max_batches must be positive"),
    ],
)
async def test_operator_backfill_runner_rejects_unbounded_limits(
    batch_limit,
    max_batches,
    message,
):
    """Refuse operator arguments that remove either database or run bounds."""
    with pytest.raises(ValueError, match=message):
        await backfill_module.run_document_object_backfill_batches(
            batch_limit=batch_limit,
            max_batches=max_batches,
            session_factory=_BackfillSessionFactory(),
        )
