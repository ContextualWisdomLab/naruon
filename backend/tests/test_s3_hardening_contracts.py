"""Security and integrity regressions for the S3-compatible storage boundary."""

from __future__ import annotations

import hashlib
import re

import httpx
import pytest

from services.s3_object_storage import (
    AwsCredentials,
    S3ClientConfiguration,
    S3ObjectIntegrityError,
    S3ObjectStorageBackend,
    build_document_object_key,
)


def _backend(handler) -> S3ObjectStorageBackend:
    """Build a network-free backend whose request body is consumed by ``handler``."""
    configuration = S3ClientConfiguration(
        region_name="us-east-1",
        endpoint_url="https://storage.example.com",
        bucket_name="naruon-documents",
        addressing_style="path",
        credentials=AwsCredentials("access-key", "secret-key"),
        server_side_encryption="AES256",
        request_timeout_seconds=5.0,
    )
    return S3ObjectStorageBackend(
        configuration,
        httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )


def test_document_object_key_hides_all_domain_identifiers() -> None:
    """Keep organization, workspace, and document identifiers out of object paths."""
    organization_id = "organization_customer_secret"
    workspace_id = "workspace_customer_secret"
    document_id = "doc_0123456789abcdef"

    object_key = build_document_object_key(
        organization_id=organization_id,
        workspace_id=workspace_id,
        document_id=document_id,
        extension="pdf",
    )

    assert organization_id not in object_key
    assert workspace_id not in object_key
    assert document_id not in object_key
    prefix, scope_digest, document_digest, filename = object_key.split("/")
    assert prefix == "workspace-documents"
    assert re.fullmatch(r"[0-9a-f]{32}", scope_digest)
    assert re.fullmatch(r"[0-9a-f]{32}", document_digest)
    assert filename == "source.pdf"


@pytest.mark.asyncio
async def test_streamed_put_rejects_short_body_before_success() -> None:
    """Do not trust declared length when the async body ends early."""

    async def handler(request: httpx.Request) -> httpx.Response:
        await request.aread()
        return httpx.Response(200)

    async def content_stream():
        yield b"abc"

    backend = _backend(handler)
    try:
        with pytest.raises(S3ObjectIntegrityError, match="length"):
            await backend.put_object_stream(
                object_key="workspace-documents/a/b/source.pdf",
                content_stream=content_stream(),
                content_length=4,
                checksum_sha256=hashlib.sha256(b"abc").hexdigest(),
                content_type="application/pdf",
            )
    finally:
        await backend.aclose()


@pytest.mark.asyncio
async def test_streamed_put_rejects_body_overrun_before_success() -> None:
    """Abort a request as soon as streamed bytes exceed the signed length."""

    async def handler(request: httpx.Request) -> httpx.Response:
        await request.aread()
        return httpx.Response(200)

    async def content_stream():
        yield b"abcd"

    backend = _backend(handler)
    try:
        with pytest.raises(S3ObjectIntegrityError, match="length"):
            await backend.put_object_stream(
                object_key="workspace-documents/a/b/source.pdf",
                content_stream=content_stream(),
                content_length=3,
                checksum_sha256=hashlib.sha256(b"abc").hexdigest(),
                content_type="application/pdf",
            )
    finally:
        await backend.aclose()


@pytest.mark.asyncio
async def test_streamed_put_rejects_checksum_drift_before_success() -> None:
    """Verify the second-pass stream against the exact digest used for SigV4."""

    async def handler(request: httpx.Request) -> httpx.Response:
        await request.aread()
        return httpx.Response(200)

    async def content_stream():
        yield b"abd"

    backend = _backend(handler)
    try:
        with pytest.raises(S3ObjectIntegrityError, match="checksum"):
            await backend.put_object_stream(
                object_key="workspace-documents/a/b/source.pdf",
                content_stream=content_stream(),
                content_length=3,
                checksum_sha256=hashlib.sha256(b"abc").hexdigest(),
                content_type="application/pdf",
            )
    finally:
        await backend.aclose()


@pytest.mark.asyncio
async def test_streamed_put_rejects_non_bytes_chunks() -> None:
    """Fail closed when an adapter yields an invalid request-body chunk type."""

    async def handler(request: httpx.Request) -> httpx.Response:
        await request.aread()
        return httpx.Response(200)

    async def content_stream():
        yield "not-bytes"

    backend = _backend(handler)
    try:
        with pytest.raises(S3ObjectIntegrityError, match="bytes"):
            await backend.put_object_stream(
                object_key="workspace-documents/a/b/source.pdf",
                content_stream=content_stream(),  # type: ignore[arg-type]
                content_length=9,
                checksum_sha256=hashlib.sha256(b"not-bytes").hexdigest(),
                content_type="application/pdf",
            )
    finally:
        await backend.aclose()
