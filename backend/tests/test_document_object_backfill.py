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
        )
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
    monkeypatch.setattr(
        backfill_module,
        "decode_legacy_pdf_payload",
        lambda payload: b"%PDF-1.7 real" if payload else b"",
    )

    async def store_payload(**kwargs):
        stored_ids.append(kwargs["document_id"])
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
    monkeypatch.setattr(
        backfill_module,
        "decode_legacy_pdf_payload",
        lambda _payload: b"%PDF-1.7 real",
    )
    monkeypatch.setattr(
        backfill_module,
        "store_configured_pdf_document",
        lambda **_kwargs: None,
    )

    async def store_payload(**kwargs):
        return _stored_payload(kwargs["document_id"])

    async def compensate(stored):
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
