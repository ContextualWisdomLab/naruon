"""Tests for document payload persistence across database and S3 backends."""

from __future__ import annotations

import base64
import hashlib

import pytest

from db.document_object_record import DocumentObjectRecord
from db.models import Document
from db.object_storage_provider import ObjectStorageProvider
import services.document_object_storage as storage_module
from services.s3_object_storage import S3StoredObject


PDF_BYTES = b"%PDF-1.7 naruon document"


class FakeS3Backend:
    """In-memory S3 backend implementing the production backend seam."""

    def __init__(self, *, returned_payload: bytes = PDF_BYTES) -> None:
        self.returned_payload = returned_payload
        self.put_calls: list[tuple[str, bytes, str]] = []
        self.get_calls: list[S3StoredObject] = []
        self.delete_calls: list[S3StoredObject] = []
        self.closed = False

    async def put_object(
        self,
        *,
        object_key: str,
        payload: bytes,
        content_type: str,
    ) -> S3StoredObject:
        self.put_calls.append((object_key, payload, content_type))
        return S3StoredObject(
            bucket_name="naruon-documents",
            object_key=object_key,
            content_type=content_type,
            content_length=len(payload),
            checksum_sha256=hashlib.sha256(payload).hexdigest(),
        )

    async def get_object(self, stored_object: S3StoredObject) -> bytes:
        self.get_calls.append(stored_object)
        return self.returned_payload

    async def delete_object(self, stored_object: S3StoredObject) -> None:
        self.delete_calls.append(stored_object)

    async def aclose(self) -> None:
        self.closed = True


class ScalarSession:
    """Minimal async session returning a preselected object record."""

    def __init__(
        self,
        record: DocumentObjectRecord | None,
        provider: ObjectStorageProvider | None = None,
    ) -> None:
        self.record = record
        self.provider = provider
        self.scalar_calls = 0

    async def scalar(self, _statement):
        self.scalar_calls += 1
        return self.record if self.scalar_calls == 1 else self.provider


def _s3_object() -> S3StoredObject:
    return S3StoredObject(
        bucket_name="naruon-documents",
        object_key="workspace-documents/abc/doc-1/source.pdf",
        content_type="application/pdf",
        content_length=len(PDF_BYTES),
        checksum_sha256=hashlib.sha256(PDF_BYTES).hexdigest(),
    )


def _s3_record() -> DocumentObjectRecord:
    stored = _s3_object()
    return DocumentObjectRecord(
        document_id="doc-1",
        object_storage_provider_id=7,
        storage_backend="s3",
        bucket_name=stored.bucket_name,
        object_key=stored.object_key,
        content_type=stored.content_type,
        content_length=stored.content_length,
        checksum_sha256=stored.checksum_sha256,
        storage_state="active",
    )


def _s3_provider() -> ObjectStorageProvider:
    return ObjectStorageProvider(
        object_storage_provider_id=7,
        user_id="user-1",
        organization_id="organization-1",
        provider_name="primary-s3",
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
        is_active=True,
    )


def _document(*, content: str | None = None) -> Document:
    return Document(
        document_id="doc-1",
        workspace_id="workspace-1",
        organization_id="organization-1",
        document_name="source.pdf",
        document_type="pdf",
        document_content=content,
        document_status="pdf_dom_recognition_pending",
    )


def test_database_payload_preserves_legacy_inline_contract_without_object_record() -> None:
    stored = storage_module.StoredDocumentPayload.for_database(PDF_BYTES)

    assert stored.storage_backend == "database"
    assert base64.b64decode(stored.document_content or "") == PDF_BYTES
    assert stored.s3_object is None
    assert stored.to_object_record("doc-1") is None


def test_s3_payload_creates_normalized_object_record_without_inline_bytes() -> None:
    stored = storage_module.StoredDocumentPayload.for_s3(_s3_object())
    record = stored.to_object_record("doc-1")

    assert stored.document_content is None
    assert isinstance(record, DocumentObjectRecord)
    assert record.document_id == "doc-1"
    assert record.storage_backend == "s3"
    assert record.bucket_name == "naruon-documents"
    assert record.inline_payload is None
    assert record.checksum_sha256 == hashlib.sha256(PDF_BYTES).hexdigest()


@pytest.mark.parametrize(
    "encoded, expected_message",
    [
        ("not@@base64", "base64"),
        (base64.b64encode(b"not-a-pdf").decode("ascii"), "PDF"),
        (
            base64.b64encode(
                b"%PDF-" + b"x" * storage_module.MAX_PDF_DOCUMENT_BYTES
            ).decode("ascii"),
            "size limit",
        ),
    ],
)
def test_legacy_decoder_fails_closed(encoded: str, expected_message: str) -> None:
    with pytest.raises(ValueError, match=expected_message):
        storage_module.decode_legacy_pdf_payload(encoded)


def test_legacy_decoder_accepts_valid_pdf() -> None:
    assert (
        storage_module.decode_legacy_pdf_payload(
            base64.b64encode(PDF_BYTES).decode("ascii")
        )
        == PDF_BYTES
    )


@pytest.mark.asyncio
async def test_store_configured_database_payload_uses_no_s3_client(monkeypatch) -> None:
    monkeypatch.setattr(storage_module.settings, "OBJECT_STORAGE_BACKEND", "database")

    async def fail_builder():  # pragma: no cover - must not run
        raise AssertionError("database backend must not construct an S3 client")

    monkeypatch.setattr(storage_module, "_build_s3_backend_from_settings", fail_builder)
    stored = await storage_module.store_configured_pdf_document(
        payload=PDF_BYTES,
        document_id="doc-1",
        organization_id="organization-1",
        workspace_id="workspace-1",
    )

    assert stored.storage_backend == "database"
    assert storage_module.decode_legacy_pdf_payload(stored.document_content) == PDF_BYTES


@pytest.mark.asyncio
async def test_store_and_delete_configured_s3_payload(monkeypatch) -> None:
    backend = FakeS3Backend()
    monkeypatch.setattr(storage_module.settings, "OBJECT_STORAGE_BACKEND", "s3")

    async def build_backend():
        return backend

    monkeypatch.setattr(storage_module, "_build_s3_backend_from_settings", build_backend)
    stored = await storage_module.store_configured_pdf_document(
        payload=PDF_BYTES,
        document_id="doc-1",
        organization_id="organization-1",
        workspace_id="workspace-1",
    )

    assert stored.storage_backend == "s3"
    assert backend.put_calls[0][1] == PDF_BYTES
    assert "organization-1" not in backend.put_calls[0][0]
    assert "workspace-1" not in backend.put_calls[0][0]
    assert backend.closed is True

    delete_backend = FakeS3Backend()

    async def build_delete_backend():
        return delete_backend

    monkeypatch.setattr(
        storage_module,
        "_build_s3_backend_from_settings",
        build_delete_backend,
    )
    await storage_module.delete_configured_document_payload(stored)
    assert delete_backend.delete_calls == [stored.s3_object]
    assert delete_backend.closed is True


@pytest.mark.asyncio
async def test_delete_database_payload_is_a_noop(monkeypatch) -> None:
    async def fail_builder():  # pragma: no cover - must not run
        raise AssertionError("database cleanup must not construct an S3 client")

    monkeypatch.setattr(storage_module, "_build_s3_backend_from_settings", fail_builder)
    await storage_module.delete_configured_document_payload(
        storage_module.StoredDocumentPayload.for_database(PDF_BYTES)
    )


@pytest.mark.asyncio
async def test_loader_prefers_legacy_inline_payload_without_querying_object_record() -> None:
    session = ScalarSession(_s3_record())
    document = _document(content=base64.b64encode(PDF_BYTES).decode("ascii"))

    loaded = await storage_module.load_pending_pdf_document_bytes(session, document)

    assert loaded == PDF_BYTES
    assert session.scalar_calls == 0


@pytest.mark.asyncio
async def test_loader_reads_s3_record_and_closes_backend(monkeypatch) -> None:
    backend = FakeS3Backend()
    session = ScalarSession(_s3_record(), _s3_provider())

    async def build_backend(_runtime_config):
        return backend

    monkeypatch.setattr(storage_module, "_build_s3_backend", build_backend)
    loaded = await storage_module.load_pending_pdf_document_bytes(
        session,
        _document(content=None),
    )

    assert loaded == PDF_BYTES
    assert backend.get_calls[0].object_key.endswith("source.pdf")
    assert backend.closed is True
    assert session.scalar_calls == 2


@pytest.mark.asyncio
async def test_loader_rejects_missing_or_inactive_object_record() -> None:
    with pytest.raises(storage_module.DocumentObjectStorageError, match="not available"):
        await storage_module.load_pending_pdf_document_bytes(
            ScalarSession(None),
            _document(content=None),
        )

    inactive = _s3_record()
    inactive.storage_state = "deleted"
    with pytest.raises(storage_module.DocumentObjectStorageError, match="not active"):
        await storage_module.load_pending_pdf_document_bytes(
            ScalarSession(inactive),
            _document(content=None),
        )


@pytest.mark.asyncio
async def test_loader_rejects_wrong_document_and_corrupt_download(monkeypatch) -> None:
    record = _s3_record()
    record.document_id = "other-document"
    with pytest.raises(storage_module.DocumentObjectStorageError, match="does not match"):
        await storage_module.load_pending_pdf_document_bytes(
            ScalarSession(record),
            _document(content=None),
        )

    backend = FakeS3Backend(returned_payload=b"not-a-pdf")

    async def build_backend(_runtime_config):
        return backend

    monkeypatch.setattr(storage_module, "_build_s3_backend", build_backend)
    with pytest.raises(storage_module.DocumentObjectStorageError, match="PDF"):
        await storage_module.load_pending_pdf_document_bytes(
            ScalarSession(_s3_record(), _s3_provider()),
            _document(content=None),
        )
    assert backend.closed is True
