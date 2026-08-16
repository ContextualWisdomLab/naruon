"""Red-green contracts for bounded, non-buffering PDF uploads to S3."""

from __future__ import annotations

from io import BytesIO
import hashlib

from fastapi import UploadFile
import httpx
import pytest

import api.document_storage as document_storage_api
import services.document_object_storage as document_storage
from services.s3_object_storage import (
    AwsCredentials,
    S3ClientConfiguration,
    S3ObjectStorageBackend,
    S3StoredObject,
)


PDF_BYTES = b"%PDF-1.7\n" + b"streamed-content" * 8192
MAX_READ_BYTES = 64 * 1024


class GuardedUploadFile(UploadFile):
    """Reject callers that attempt to read the whole request body in one call."""

    def __init__(self, payload: bytes = PDF_BYTES) -> None:
        super().__init__(filename="streamed.pdf", file=BytesIO(payload))
        self.read_sizes: list[int] = []
        self.seek_offsets: list[int] = []

    async def read(self, size: int = -1) -> bytes:
        self.read_sizes.append(size)
        if size <= 0 or size > MAX_READ_BYTES:
            raise AssertionError("upload reads must remain positively bounded")
        return await super().read(size)

    async def seek(self, offset: int) -> None:
        self.seek_offsets.append(offset)
        await super().seek(offset)


def _configuration() -> S3ClientConfiguration:
    return S3ClientConfiguration(
        region_name="us-east-1",
        endpoint_url="https://examplebucket.s3.amazonaws.com",
        bucket_name="examplebucket",
        addressing_style="virtual",
        credentials=AwsCredentials("access-key", "secret-key"),
        server_side_encryption="AES256",
        request_timeout_seconds=5.0,
    )


def _stored_payload() -> document_storage.StoredDocumentPayload:
    return document_storage.StoredDocumentPayload.for_s3(
        S3StoredObject(
            bucket_name="examplebucket",
            object_key="workspace-documents/opaque/doc/source.pdf",
            content_type="application/pdf",
            content_length=len(PDF_BYTES),
            checksum_sha256=hashlib.sha256(PDF_BYTES).hexdigest(),
        )
    )


@pytest.mark.asyncio
async def test_pdf_inspection_reads_bounded_chunks_and_rewinds() -> None:
    inspect_upload = getattr(document_storage, "inspect_pdf_upload", None)
    assert callable(inspect_upload), "inspect_pdf_upload must implement the streaming seam"
    upload = GuardedUploadFile()

    inspected = await inspect_upload(
        upload,
        max_bytes=len(PDF_BYTES),
        chunk_size=MAX_READ_BYTES,
    )

    assert inspected.content_length == len(PDF_BYTES)
    assert inspected.checksum_sha256 == hashlib.sha256(PDF_BYTES).hexdigest()
    assert upload.read_sizes
    assert max(upload.read_sizes) <= MAX_READ_BYTES
    assert upload.seek_offsets[-1] == 0
    assert await upload.read(5) == b"%PDF"


@pytest.mark.asyncio
async def test_s3_backend_streams_prehashed_payload_without_byte_buffer() -> None:
    captured: dict[str, object] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["request"] = request
        captured["payload"] = await request.aread()
        return httpx.Response(200)

    backend = S3ObjectStorageBackend(
        _configuration(),
        httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    put_stream = getattr(backend, "put_object_stream", None)
    assert callable(put_stream), "S3 backend must expose a streaming PUT operation"
    yielded: list[bytes] = []

    async def stream():
        for offset in range(0, len(PDF_BYTES), MAX_READ_BYTES):
            chunk = PDF_BYTES[offset : offset + MAX_READ_BYTES]
            yielded.append(chunk)
            yield chunk

    stored = await put_stream(
        object_key="workspace-documents/opaque/doc/source.pdf",
        content_stream=stream(),
        content_length=len(PDF_BYTES),
        checksum_sha256=hashlib.sha256(PDF_BYTES).hexdigest(),
        content_type="application/pdf",
    )

    request = captured["request"]
    assert isinstance(request, httpx.Request)
    assert captured["payload"] == PDF_BYTES
    assert b"".join(yielded) == PDF_BYTES
    assert request.headers["content-length"] == str(len(PDF_BYTES))
    assert request.headers["x-amz-content-sha256"] == stored.checksum_sha256
    assert stored.content_length == len(PDF_BYTES)
    await backend.aclose()


@pytest.mark.asyncio
async def test_pdf_upload_route_never_requests_an_unbounded_read(monkeypatch) -> None:
    store_upload = getattr(document_storage_api, "store_configured_pdf_upload", None)
    assert callable(store_upload), "API must use the streaming document-storage seam"
    upload = GuardedUploadFile()
    stored = _stored_payload()

    async def store(**kwargs):
        assert kwargs["upload"] is upload
        assert kwargs["validated_upload"].content_length == len(PDF_BYTES)
        return stored

    monkeypatch.setattr(document_storage_api, "store_configured_pdf_upload", store)

    class Session:
        def __init__(self) -> None:
            self.added: list[object] = []

        def add(self, value: object) -> None:
            self.added.append(value)

        async def commit(self) -> None:
            return None

        async def refresh(self, _value: object) -> None:
            return None

        async def rollback(self) -> None:
            return None

    response = await document_storage_api.upload_document_for_pdf_dom_recognition(
        file=upload,
        document_name="Streaming evidence",
        auth_context=type(
            "AuthContext",
            (),
            {
                "organization_id": "organization-one",
                "workspace_id": "workspace-one",
            },
        )(),
        db=Session(),
    )

    assert response.document_status == "pdf_dom_recognition_pending"
    assert upload.read_sizes
    assert max(upload.read_sizes) <= MAX_READ_BYTES
