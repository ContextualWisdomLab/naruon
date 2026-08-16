"""API-layer tests for durable PDF object-storage persistence."""

from __future__ import annotations

import base64
from io import BytesIO
from types import SimpleNamespace

from fastapi import APIRouter, HTTPException, UploadFile
import pytest

import api.document_storage as data_module
from db.document_object_record import DocumentObjectRecord
from db.models import Document
from services.document_object_storage import (
    DocumentObjectStorageError,
    StoredDocumentPayload,
)
from services.s3_object_storage import S3StoredObject


PDF_BYTES = b"%PDF-1.7 api upload"


class RecordingSession:
    """Small AsyncSession substitute for persistence and compensation tests."""

    def __init__(self, *, commit_error: Exception | None = None) -> None:
        self.added: list[object] = []
        self.commit_error = commit_error
        self.commit_count = 0
        self.rollback_count = 0
        self.refresh_count = 0

    def add(self, value: object) -> None:
        self.added.append(value)

    async def commit(self) -> None:
        self.commit_count += 1
        if self.commit_error is not None:
            raise self.commit_error

    async def rollback(self) -> None:
        self.rollback_count += 1

    async def refresh(self, _value: object) -> None:
        self.refresh_count += 1


class _ScalarOneResult:
    """Return one scoped ORM row from a fake SQLAlchemy result."""

    def __init__(self, value: object | None) -> None:
        self.value = value

    def scalar_one_or_none(self) -> object | None:
        return self.value


class DeletionSession:
    """Track the database half of one customer document-deletion saga."""

    def __init__(
        self,
        *,
        document: Document | None,
        object_record: DocumentObjectRecord | None,
        commit_error: Exception | None = None,
    ) -> None:
        self.document = document
        self.object_record = object_record
        self.commit_error = commit_error
        self.deleted: list[object] = []
        self.commit_count = 0
        self.rollback_count = 0
        self.execute_statements: list[object] = []
        self.scalar_statements: list[object] = []

    async def execute(self, statement):
        self.execute_statements.append(statement)
        return _ScalarOneResult(self.document)

    async def scalar(self, statement):
        self.scalar_statements.append(statement)
        return self.object_record

    async def delete(self, value: object) -> None:
        self.deleted.append(value)

    async def commit(self) -> None:
        self.commit_count += 1
        if self.commit_error is not None:
            raise self.commit_error

    async def rollback(self) -> None:
        self.rollback_count += 1


def _auth_context() -> SimpleNamespace:
    return SimpleNamespace(
        user_id="user-1",
        organization_id="organization-1",
        workspace_id="workspace-1",
    )


def _upload() -> UploadFile:
    return UploadFile(filename="customer-report.pdf", file=BytesIO(PDF_BYTES))


def _s3_payload() -> StoredDocumentPayload:
    return StoredDocumentPayload.for_s3(
        S3StoredObject(
            bucket_name="naruon-documents",
            object_key="workspace-documents/abc/doc/source.pdf",
            content_type="application/pdf",
            content_length=len(PDF_BYTES),
            checksum_sha256=(
                "b321c014fccbc2ee5cf1e362ef06e657878115ef12cce0ef35aac5023ac30b15"
            ),
        )
    )


def _stored_document() -> Document:
    """Build one S3-backed workspace document for deletion tests."""
    return Document(
        document_id="doc_delete_me",
        workspace_id="workspace-1",
        organization_id="organization-1",
        document_name="customer-report.pdf",
        document_type="pdf",
        document_content=None,
        document_status="pdf_dom_recognition_pending",
    )


def _object_record(document: Document) -> DocumentObjectRecord:
    """Build the normalized raw-object locator owned by a test document."""
    return DocumentObjectRecord(
        document_id=document.document_id,
        storage_backend="s3",
        bucket_name="naruon-documents",
        object_key="workspace-documents/opaque/doc_delete_me/source.pdf",
        inline_payload=None,
        content_type="application/pdf",
        content_length=len(PDF_BYTES),
        checksum_sha256="a" * 64,
        storage_state="active",
    )


def test_runtime_route_replacement_removes_only_legacy_pdf_upload() -> None:
    candidate_router = APIRouter(prefix="/api/data")

    @candidate_router.post("/documents/pdf-dom-recognition")
    async def legacy_pdf_upload() -> dict[str, bool]:
        return {"legacy": True}

    @candidate_router.get("/health")
    async def health() -> dict[str, bool]:
        return {"ok": True}

    assert data_module.remove_legacy_pdf_upload_route(candidate_router) is True
    assert data_module.remove_legacy_pdf_upload_route(candidate_router) is False
    assert [route.path for route in candidate_router.routes] == ["/api/data/health"]


@pytest.mark.asyncio
async def test_s3_upload_persists_document_and_normalized_object_record(monkeypatch) -> None:
    session = RecordingSession()
    stored = _s3_payload()

    async def store(**_kwargs):
        return stored

    monkeypatch.setattr(data_module, "store_configured_pdf_upload", store)
    response = await data_module.upload_document_for_pdf_dom_recognition(
        file=_upload(),
        document_name="Quarterly evidence",
        auth_context=_auth_context(),
        db=session,
    )

    document = next(item for item in session.added if isinstance(item, Document))
    object_record = next(
        item for item in session.added if isinstance(item, DocumentObjectRecord)
    )
    assert document.document_id == object_record.document_id
    assert document.document_content is None
    assert document.document_status == "pdf_dom_recognition_pending"
    assert object_record.storage_backend == "s3"
    assert object_record.bucket_name == "naruon-documents"
    assert object_record.object_key.endswith("source.pdf")
    assert response.document_id == document.document_id
    assert session.commit_count == 1
    assert session.refresh_count == 1


@pytest.mark.asyncio
async def test_database_upload_preserves_existing_inline_behavior(monkeypatch) -> None:
    session = RecordingSession()

    async def store(**_kwargs):
        return StoredDocumentPayload.for_database(PDF_BYTES)

    monkeypatch.setattr(data_module, "store_configured_pdf_upload", store)
    await data_module.upload_document_for_pdf_dom_recognition(
        file=_upload(),
        document_name=None,
        auth_context=_auth_context(),
        db=session,
    )

    assert len(session.added) == 1
    document = session.added[0]
    assert isinstance(document, Document)
    assert base64.b64decode(document.document_content or "") == PDF_BYTES


@pytest.mark.asyncio
async def test_database_failure_compensates_s3_upload(monkeypatch) -> None:
    session = RecordingSession(commit_error=RuntimeError("database unavailable"))
    stored = _s3_payload()
    deleted: list[StoredDocumentPayload] = []

    async def store(**_kwargs):
        return stored

    async def delete(value: StoredDocumentPayload):
        deleted.append(value)

    monkeypatch.setattr(data_module, "store_configured_pdf_upload", store)
    monkeypatch.setattr(data_module, "delete_configured_document_payload", delete)

    with pytest.raises(RuntimeError, match="database unavailable"):
        await data_module.upload_document_for_pdf_dom_recognition(
            file=_upload(),
            document_name=None,
            auth_context=_auth_context(),
            db=session,
        )

    assert session.rollback_count == 1
    assert deleted == [stored]


@pytest.mark.asyncio
async def test_storage_failure_returns_safe_service_unavailable(monkeypatch) -> None:
    session = RecordingSession()

    async def store(**_kwargs):
        raise DocumentObjectStorageError("bucket=secret-bucket key=private/source.pdf")

    monkeypatch.setattr(data_module, "store_configured_pdf_upload", store)

    with pytest.raises(HTTPException) as error:
        await data_module.upload_document_for_pdf_dom_recognition(
            file=_upload(),
            document_name=None,
            auth_context=_auth_context(),
            db=session,
        )

    assert error.value.status_code == 503
    assert error.value.detail == "Configured document storage is unavailable."
    assert "secret-bucket" not in str(error.value.detail)
    assert session.added == []


@pytest.mark.asyncio
async def test_rejects_non_pdf_before_touching_storage(monkeypatch) -> None:
    session = RecordingSession()

    async def store(**_kwargs):  # pragma: no cover - must not run
        raise AssertionError("invalid content must not reach storage")

    monkeypatch.setattr(data_module, "store_configured_pdf_upload", store)

    with pytest.raises(HTTPException) as error:
        await data_module.upload_document_for_pdf_dom_recognition(
            file=UploadFile(filename="not.pdf", file=BytesIO(b"not a PDF")),
            document_name=None,
            auth_context=_auth_context(),
            db=session,
        )

    assert error.value.status_code == 415
    assert session.added == []


@pytest.mark.asyncio
async def test_customer_delete_removes_s3_payload_before_relational_document(monkeypatch):
    """Delete the raw customer object before committing its scoped metadata removal."""
    document = _stored_document()
    object_record = _object_record(document)
    session = DeletionSession(document=document, object_record=object_record)
    remote_deleted: list[DocumentObjectRecord] = []

    async def delete_remote(record: DocumentObjectRecord) -> None:
        remote_deleted.append(record)

    monkeypatch.setattr(data_module, "delete_document_object_record", delete_remote)

    response = await data_module.delete_workspace_document(
        document_id=document.document_id,
        auth_context=_auth_context(),
        db=session,
    )

    assert remote_deleted == [object_record]
    assert session.deleted == [document]
    assert session.commit_count == 1
    assert session.rollback_count == 0
    assert response.document_id == document.document_id
    assert response.document_status == "deleted"
    assert response.content_chars == 0
    assert response.audit_event == "data.document.deleted"
    assert "deleted" in response.message.lower()


@pytest.mark.asyncio
async def test_customer_delete_db_commit_failure_preserves_retryable_locator(monkeypatch):
    """Rollback relational deletion so idempotent S3 DELETE can be retried later."""
    document = _stored_document()
    object_record = _object_record(document)
    session = DeletionSession(
        document=document,
        object_record=object_record,
        commit_error=RuntimeError("database unavailable"),
    )
    remote_deleted: list[DocumentObjectRecord] = []

    async def delete_remote(record: DocumentObjectRecord) -> None:
        remote_deleted.append(record)

    monkeypatch.setattr(data_module, "delete_document_object_record", delete_remote)

    with pytest.raises(RuntimeError, match="database unavailable"):
        await data_module.delete_workspace_document(
            document_id=document.document_id,
            auth_context=_auth_context(),
            db=session,
        )

    assert remote_deleted == [object_record]
    assert session.deleted == [document]
    assert session.commit_count == 1
    assert session.rollback_count == 1
    assert session.object_record is object_record
    assert object_record.object_key.endswith("source.pdf")


@pytest.mark.asyncio
async def test_customer_delete_storage_failure_is_safe_and_retryable(monkeypatch):
    """Keep database metadata when the external raw object cannot be deleted."""
    document = _stored_document()
    object_record = _object_record(document)
    session = DeletionSession(document=document, object_record=object_record)

    async def delete_remote(_record: DocumentObjectRecord) -> None:
        raise DocumentObjectStorageError("bucket=secret-bucket key=private/source.pdf")

    monkeypatch.setattr(data_module, "delete_document_object_record", delete_remote)

    with pytest.raises(HTTPException) as error:
        await data_module.delete_workspace_document(
            document_id=document.document_id,
            auth_context=_auth_context(),
            db=session,
        )

    assert error.value.status_code == 503
    assert error.value.detail == "Configured document storage is unavailable."
    assert "secret-bucket" not in str(error.value.detail)
    assert session.deleted == []
    assert session.commit_count == 0
    assert session.rollback_count == 1


@pytest.mark.asyncio
async def test_customer_delete_is_workspace_scoped_before_storage_access(monkeypatch):
    """A missing or cross-workspace document must not expose or delete object metadata."""
    session = DeletionSession(document=None, object_record=None)
    remote_calls = 0

    async def forbidden_delete(_record: DocumentObjectRecord) -> None:
        nonlocal remote_calls
        remote_calls += 1

    monkeypatch.setattr(data_module, "delete_document_object_record", forbidden_delete)

    with pytest.raises(HTTPException) as error:
        await data_module.delete_workspace_document(
            document_id="doc_other_workspace",
            auth_context=_auth_context(),
            db=session,
        )

    assert error.value.status_code == 404
    assert remote_calls == 0
    assert session.scalar_statements == []
    assert session.deleted == []
    assert session.commit_count == 0
    assert session.rollback_count == 0
    assert "workspace_documents.workspace_id" in str(session.execute_statements[0])
