"""Red-green contracts for compensation-failure orphan reconciliation."""

from __future__ import annotations

import hashlib

import httpx
import pytest

from services.s3_object_storage import (
    AwsCredentials,
    S3ClientConfiguration,
    S3ObjectIntegrityError,
    S3ObjectStorageBackend,
    S3ObjectStorageRequestError,
)


PAYLOAD = b"%PDF-1.7 orphan recovery"
OBJECT_KEY = "workspace-documents/opaque/document/source.pdf"


def _configuration() -> S3ClientConfiguration:
    return S3ClientConfiguration(
        region_name="us-east-1",
        endpoint_url="https://bucket-name.s3.amazonaws.com",
        bucket_name="bucket-name",
        addressing_style="virtual",
        credentials=AwsCredentials("access-key", "secret-key"),
        server_side_encryption="AES256",
        request_timeout_seconds=5.0,
    )


@pytest.mark.asyncio
async def test_immutable_put_adopts_exact_existing_object_after_precondition_failure() -> None:
    """Retry a failed metadata saga by verifying and adopting its exact orphan."""
    methods: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        methods.append(request.method)
        if request.method == "PUT":
            return httpx.Response(412)
        if request.method == "GET":
            return httpx.Response(200, content=PAYLOAD)
        raise AssertionError(f"unexpected method {request.method}")

    backend = S3ObjectStorageBackend(
        _configuration(),
        httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    try:
        stored = await backend.put_object(
            object_key=OBJECT_KEY,
            payload=PAYLOAD,
            content_type="application/pdf",
        )
    finally:
        await backend.aclose()

    assert methods == ["PUT", "GET"]
    assert stored.object_key == OBJECT_KEY
    assert stored.content_length == len(PAYLOAD)
    assert stored.checksum_sha256 == hashlib.sha256(PAYLOAD).hexdigest()


@pytest.mark.asyncio
async def test_immutable_put_refuses_existing_object_with_different_bytes() -> None:
    """Never adopt an occupied key whose bytes differ from the intended source."""

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "PUT":
            return httpx.Response(412)
        if request.method == "GET":
            return httpx.Response(200, content=b"%PDF-1.7 different bytes")
        raise AssertionError(f"unexpected method {request.method}")

    backend = S3ObjectStorageBackend(
        _configuration(),
        httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    try:
        with pytest.raises(S3ObjectIntegrityError):
            await backend.put_object(
                object_key=OBJECT_KEY,
                payload=PAYLOAD,
                content_type="application/pdf",
            )
    finally:
        await backend.aclose()


@pytest.mark.asyncio
async def test_stream_producer_failure_is_redacted_as_storage_request_failure() -> None:
    """A partial producer failure must not leak implementation or customer data."""

    async def consume_request(request: httpx.Request) -> httpx.Response:
        await request.aread()
        return httpx.Response(200)

    async def broken_stream():
        yield PAYLOAD[:5]
        raise RuntimeError("customer-path=/private/report.pdf")

    backend = S3ObjectStorageBackend(
        _configuration(),
        httpx.AsyncClient(transport=httpx.MockTransport(consume_request)),
    )
    try:
        with pytest.raises(S3ObjectStorageRequestError) as error:
            await backend.put_object_stream(
                object_key=OBJECT_KEY,
                content_stream=broken_stream(),
                content_length=len(PAYLOAD),
                checksum_sha256=hashlib.sha256(PAYLOAD).hexdigest(),
                content_type="application/pdf",
            )
    finally:
        await backend.aclose()

    assert "customer-path" not in str(error.value)
