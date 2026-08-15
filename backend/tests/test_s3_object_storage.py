"""Contract tests for the S3-compatible object-storage backend."""

from __future__ import annotations

import base64
from datetime import datetime, timezone
import hashlib

import httpx
import pytest

from services.s3_object_storage import (
    AwsCredentials,
    S3ClientConfiguration,
    S3ObjectIntegrityError,
    S3ObjectStorageBackend,
    S3ObjectStorageRequestError,
    S3StoredObject,
    build_document_object_key,
    sign_s3_request,
)


AWS_EXAMPLE_CREDENTIALS = AwsCredentials(
    access_key_id="AKIAIOSFODNN7EXAMPLE",
    secret_access_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
)


def _configuration(
    *,
    addressing_style: str = "virtual",
    endpoint_url: str = "https://examplebucket.s3.amazonaws.com",
    encryption: str = "AES256",
    kms_key_id: str | None = None,
    session_token: str | None = None,
    expected_bucket_owner: str | None = None,
) -> S3ClientConfiguration:
    return S3ClientConfiguration(
        region_name="us-east-1",
        endpoint_url=endpoint_url,
        bucket_name="examplebucket",
        addressing_style=addressing_style,
        credentials=AwsCredentials(
            access_key_id=AWS_EXAMPLE_CREDENTIALS.access_key_id,
            secret_access_key=AWS_EXAMPLE_CREDENTIALS.secret_access_key,
            session_token=session_token,
        ),
        server_side_encryption=encryption,
        kms_key_id=kms_key_id,
        expected_bucket_owner=expected_bucket_owner,
        request_timeout_seconds=5.0,
    )


def _stored(payload: bytes, *, key: str = "workspace-documents/a/doc/source.pdf") -> S3StoredObject:
    return S3StoredObject(
        bucket_name="examplebucket",
        object_key=key,
        content_type="application/pdf",
        content_length=len(payload),
        checksum_sha256=hashlib.sha256(payload).hexdigest(),
    )


def test_signature_matches_aws_s3_published_get_object_vector() -> None:
    signed = sign_s3_request(
        method="GET",
        url="https://examplebucket.s3.amazonaws.com/test.txt",
        headers={"Range": "bytes=0-9"},
        payload=b"",
        credentials=AWS_EXAMPLE_CREDENTIALS,
        region_name="us-east-1",
        request_time=datetime(2013, 5, 24, tzinfo=timezone.utc),
    )

    assert signed["authorization"] == (
        "AWS4-HMAC-SHA256 "
        "Credential=AKIAIOSFODNN7EXAMPLE/20130524/us-east-1/s3/aws4_request,"
        "SignedHeaders=host;range;x-amz-content-sha256;x-amz-date,"
        "Signature=f0e8bdb87c964420e857bd35b5d6ed310bd44f0170aba48dd91039c6036bdb41"
    )
    assert signed["x-amz-content-sha256"] == hashlib.sha256(b"").hexdigest()
    assert signed["x-amz-date"] == "20130524T000000Z"


def test_document_object_key_is_opaque_and_deterministic() -> None:
    key = build_document_object_key(
        organization_id="customer-secret-org",
        workspace_id="customer-secret-workspace",
        document_id="doc_0123456789abcdef",
        extension="pdf",
    )
    repeated = build_document_object_key(
        organization_id="customer-secret-org",
        workspace_id="customer-secret-workspace",
        document_id="doc_0123456789abcdef",
        extension="pdf",
    )

    assert key == repeated
    assert key.startswith("workspace-documents/")
    assert key.endswith("/doc_0123456789abcdef/source.pdf")
    assert "customer-secret-org" not in key
    assert "customer-secret-workspace" not in key


@pytest.mark.parametrize(
    "object_key",
    ["", "/absolute.pdf", "../escape.pdf", "safe/../escape.pdf", "control\n.pdf"],
)
def test_backend_rejects_unsafe_object_keys(object_key: str) -> None:
    backend = S3ObjectStorageBackend(
        _configuration(),
        httpx.AsyncClient(transport=httpx.MockTransport(lambda _request: httpx.Response(500))),
    )
    with pytest.raises(ValueError, match="object key"):
        backend.object_url(object_key)


@pytest.mark.asyncio
async def test_put_object_signs_checksum_encryption_and_non_overwrite_contract() -> None:
    payload = b"%PDF-1.7 naruon"
    checksum_hex = hashlib.sha256(payload).hexdigest()
    checksum_b64 = base64.b64encode(hashlib.sha256(payload).digest()).decode("ascii")
    captured: dict[str, object] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["request"] = request
        captured["body"] = await request.aread()
        return httpx.Response(200, headers={"x-amz-checksum-sha256": checksum_b64})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    backend = S3ObjectStorageBackend(_configuration(), client)
    stored = await backend.put_object(
        object_key="workspace-documents/abc/doc/source.pdf",
        payload=payload,
        content_type="application/pdf",
    )

    request = captured["request"]
    assert isinstance(request, httpx.Request)
    assert request.method == "PUT"
    assert str(request.url) == (
        "https://examplebucket.s3.amazonaws.com/"
        "workspace-documents/abc/doc/source.pdf"
    )
    assert captured["body"] == payload
    assert request.headers["if-none-match"] == "*"
    assert request.headers["x-amz-content-sha256"] == checksum_hex
    assert request.headers["x-amz-checksum-sha256"] == checksum_b64
    assert request.headers["x-amz-server-side-encryption"] == "AES256"
    assert "x-amz-acl" not in request.headers
    assert request.headers["authorization"].startswith("AWS4-HMAC-SHA256 ")
    assert stored == _stored(payload, key="workspace-documents/abc/doc/source.pdf")
    await backend.aclose()


@pytest.mark.asyncio
async def test_put_object_supports_kms_temporary_credentials_and_expected_owner() -> None:
    payload = b"%PDF-1.7 encrypted"
    captured: dict[str, httpx.Request] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["request"] = request
        return httpx.Response(200)

    backend = S3ObjectStorageBackend(
        _configuration(
            encryption="aws:kms",
            kms_key_id="arn:aws:kms:us-east-1:111122223333:key/example",
            session_token="temporary-token",
            expected_bucket_owner="111122223333",
        ),
        httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    await backend.put_object(
        object_key="workspace-documents/abc/doc/source.pdf",
        payload=payload,
        content_type="application/pdf",
    )

    headers = captured["request"].headers
    assert headers["x-amz-server-side-encryption"] == "aws:kms"
    assert headers["x-amz-server-side-encryption-aws-kms-key-id"].endswith("/example")
    assert headers["x-amz-security-token"] == "temporary-token"
    assert headers["x-amz-expected-bucket-owner"] == "111122223333"
    assert "x-amz-security-token" in headers["authorization"]
    await backend.aclose()


@pytest.mark.asyncio
async def test_path_style_endpoint_preserves_operator_base_path() -> None:
    payload = b"%PDF-1.7 path-style"
    captured: dict[str, str] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        return httpx.Response(200)

    backend = S3ObjectStorageBackend(
        _configuration(
            addressing_style="path",
            endpoint_url="https://storage.example.com/s3-api",
        ),
        httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    await backend.put_object(
        object_key="workspace-documents/abc/doc/source.pdf",
        payload=payload,
        content_type="application/pdf",
    )

    assert captured["url"] == (
        "https://storage.example.com/s3-api/examplebucket/"
        "workspace-documents/abc/doc/source.pdf"
    )
    await backend.aclose()


@pytest.mark.asyncio
async def test_get_object_verifies_length_and_sha256() -> None:
    payload = b"%PDF-1.7 verified"
    stored = _stored(payload)

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.headers["x-amz-checksum-mode"] == "ENABLED"
        return httpx.Response(200, content=payload)

    backend = S3ObjectStorageBackend(
        _configuration(),
        httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    assert await backend.get_object(stored) == payload
    await backend.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize("returned", [b"short", b"%PDF-1.7 corrupted-and-longer"])
async def test_get_object_fails_closed_on_integrity_mismatch(returned: bytes) -> None:
    expected = b"%PDF-1.7 expected"

    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=returned)

    backend = S3ObjectStorageBackend(
        _configuration(),
        httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    with pytest.raises(S3ObjectIntegrityError, match="integrity"):
        await backend.get_object(_stored(expected))
    await backend.aclose()


@pytest.mark.asyncio
async def test_delete_object_accepts_no_content_response() -> None:
    payload = b"%PDF-1.7 delete"
    captured: dict[str, str] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        return httpx.Response(204)

    backend = S3ObjectStorageBackend(
        _configuration(),
        httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    await backend.delete_object(_stored(payload))
    assert captured["method"] == "DELETE"
    await backend.aclose()


@pytest.mark.asyncio
async def test_request_failure_redacts_bucket_key_and_response_body() -> None:
    payload = b"%PDF-1.7 secret"

    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, content=b"credential=do-not-leak")

    backend = S3ObjectStorageBackend(
        _configuration(),
        httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    with pytest.raises(S3ObjectStorageRequestError) as error:
        await backend.put_object(
            object_key="workspace-documents/private/doc/source.pdf",
            payload=payload,
            content_type="application/pdf",
        )

    message = str(error.value)
    assert "do-not-leak" not in message
    assert "examplebucket" not in message
    assert "private" not in message
    await backend.aclose()
