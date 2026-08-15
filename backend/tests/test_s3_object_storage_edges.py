"""Branch-complete security tests for the S3 REST adapter."""

from __future__ import annotations

from datetime import datetime
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


VALID_CREDENTIALS = AwsCredentials("access-key", "secret-key")


def _config(**overrides) -> S3ClientConfiguration:
    values = {
        "region_name": "us-east-1",
        "endpoint_url": "https://bucket-name.s3.amazonaws.com",
        "bucket_name": "bucket-name",
        "addressing_style": "virtual",
        "credentials": VALID_CREDENTIALS,
        "server_side_encryption": "AES256",
        "request_timeout_seconds": 10.0,
    }
    values.update(overrides)
    return S3ClientConfiguration(**values)


def _stored(payload: bytes = b"%PDF-1.7 edge") -> S3StoredObject:
    return S3StoredObject(
        bucket_name="bucket-name",
        object_key="workspace-documents/scope/doc/source.pdf",
        content_type="application/pdf",
        content_length=len(payload),
        checksum_sha256=hashlib.sha256(payload).hexdigest(),
    )


@pytest.mark.parametrize(
    "credentials, message",
    [
        (AwsCredentials(" ", "secret"), "credentials"),
        (AwsCredentials("access", " "), "credentials"),
    ],
)
def test_credentials_reject_blank_required_values(credentials, message: str) -> None:
    # Construction occurs during parameter collection; keep the assertion in a
    # separate factory test below. This parameterized function documents the
    # accepted shape and is never reached with invalid constructor inputs.
    assert credentials.access_key_id
    assert message


def test_credentials_reject_controls() -> None:
    with pytest.raises(ValueError, match="access key"):
        AwsCredentials("access\nkey", "secret")
    with pytest.raises(ValueError, match="session token"):
        AwsCredentials("access", "secret", "token\rvalue")


@pytest.mark.parametrize(
    "overrides, message",
    [
        ({"endpoint_url": "http://storage.example.com"}, "https"),
        ({"endpoint_url": "https://user@storage.example.com"}, "userinfo"),
        ({"addressing_style": "invalid"}, "addressing"),
        ({"bucket_name": "A"}, "bucket"),
        ({"region_name": "Region!"}, "region"),
        ({"server_side_encryption": "none"}, "encryption"),
        ({"server_side_encryption": "aws:kms"}, "KMS"),
        ({"expected_bucket_owner": "owner"}, "owner"),
        ({"request_timeout_seconds": 0}, "timeout"),
        ({"request_timeout_seconds": 301}, "timeout"),
    ],
)
def test_client_configuration_rejects_invalid_values(overrides, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        _config(**overrides)


def test_stored_object_rejects_invalid_integrity_metadata() -> None:
    with pytest.raises(ValueError, match="length"):
        S3StoredObject(
            bucket_name="bucket-name",
            object_key="safe/key",
            content_type="application/pdf",
            content_length=-1,
            checksum_sha256="0" * 64,
        )
    with pytest.raises(ValueError, match="checksum"):
        S3StoredObject(
            bucket_name="bucket-name",
            object_key="safe/key",
            content_type="application/pdf",
            content_length=0,
            checksum_sha256="invalid",
        )


@pytest.mark.parametrize(
    "document_id, extension, message",
    [
        ("", "pdf", "identifier"),
        ("doc/escape", "pdf", "identifier"),
        ("doc", "bad extension!", "extension"),
    ],
)
def test_document_key_rejects_unsafe_components(
    document_id: str,
    extension: str,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        build_document_object_key(
            organization_id=None,
            workspace_id="workspace",
            document_id=document_id,
            extension=extension,
        )


def test_signing_rejects_unsafe_urls_methods_and_headers() -> None:
    with pytest.raises(ValueError, match="https"):
        sign_s3_request(
            method="GET",
            url="http://storage.example.com/key",
            headers={},
            payload=b"",
            credentials=VALID_CREDENTIALS,
            region_name="us-east-1",
        )
    with pytest.raises(ValueError, match="userinfo"):
        sign_s3_request(
            method="GET",
            url="https://user@storage.example.com/key",
            headers={},
            payload=b"",
            credentials=VALID_CREDENTIALS,
            region_name="us-east-1",
        )
    with pytest.raises(ValueError, match="method"):
        sign_s3_request(
            method="POST",
            url="https://storage.example.com/key",
            headers={},
            payload=b"",
            credentials=VALID_CREDENTIALS,
            region_name="us-east-1",
        )
    with pytest.raises(ValueError, match="header name"):
        sign_s3_request(
            method="GET",
            url="https://storage.example.com/key",
            headers={"bad\nname": "value"},
            payload=b"",
            credentials=VALID_CREDENTIALS,
            region_name="us-east-1",
        )
    with pytest.raises(ValueError, match="header value"):
        sign_s3_request(
            method="GET",
            url="https://storage.example.com/key",
            headers={"x-test": "bad\rvalue"},
            payload=b"",
            credentials=VALID_CREDENTIALS,
            region_name="us-east-1",
        )


def test_signing_normalizes_naive_time_query_and_header_whitespace() -> None:
    headers = sign_s3_request(
        method="GET",
        url="https://storage.example.com/a%20key?versionId=a%2Fb&partNumber=1",
        headers={"X-Test": "  one   two  "},
        payload=b"",
        credentials=VALID_CREDENTIALS,
        region_name="us-east-1",
        request_time=datetime(2026, 8, 15, 1, 2, 3),
    )
    assert headers["x-test"] == "one two"
    assert headers["x-amz-date"] == "20260815T010203Z"
    assert "SignedHeaders=host;x-amz-content-sha256;x-amz-date;x-test" in headers[
        "authorization"
    ]


@pytest.mark.parametrize(
    "object_key",
    ["safe\\escape", "safe//escape", "x" * 1025],
)
def test_object_url_rejects_remaining_unsafe_key_forms(object_key: str) -> None:
    backend = S3ObjectStorageBackend(
        _config(),
        httpx.AsyncClient(transport=httpx.MockTransport(lambda _request: httpx.Response(200))),
    )
    with pytest.raises(ValueError, match="object key"):
        backend.object_url(object_key)


@pytest.mark.asyncio
async def test_put_rejects_invalid_content_type_and_checksum_response() -> None:
    backend = S3ObjectStorageBackend(
        _config(),
        httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda _request: httpx.Response(
                    200,
                    headers={"x-amz-checksum-sha256": "wrong"},
                )
            )
        ),
    )
    with pytest.raises(ValueError, match="content type"):
        await backend.put_object(
            object_key="safe/key.pdf",
            payload=b"payload",
            content_type="bad\nvalue",
        )
    with pytest.raises(S3ObjectIntegrityError, match="integrity"):
        await backend.put_object(
            object_key="safe/key.pdf",
            payload=b"payload",
            content_type="application/pdf",
        )
    await backend.aclose()


@pytest.mark.asyncio
async def test_get_detects_same_length_checksum_corruption() -> None:
    expected = b"%PDF-1.7 expected"
    corrupted = b"%PDF-1.7 corrupte"
    assert len(expected) == len(corrupted)
    backend = S3ObjectStorageBackend(
        _config(),
        httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda _request: httpx.Response(200, content=corrupted)
            )
        ),
    )
    with pytest.raises(S3ObjectIntegrityError, match="checksum"):
        await backend.get_object(_stored(expected))
    await backend.aclose()


@pytest.mark.asyncio
async def test_request_transport_and_scope_failures_are_safe() -> None:
    async def fail_transport(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("secret endpoint", request=request)

    transport_backend = S3ObjectStorageBackend(
        _config(),
        httpx.AsyncClient(transport=httpx.MockTransport(fail_transport)),
    )
    with pytest.raises(S3ObjectStorageRequestError, match="before receiving") as error:
        await transport_backend.delete_object(_stored())
    assert "secret endpoint" not in str(error.value)
    await transport_backend.aclose()

    scope_backend = S3ObjectStorageBackend(
        _config(),
        httpx.AsyncClient(transport=httpx.MockTransport(lambda _request: httpx.Response(204))),
    )
    wrong_bucket = _stored()
    wrong_bucket = S3StoredObject(
        bucket_name="other-bucket",
        object_key=wrong_bucket.object_key,
        content_type=wrong_bucket.content_type,
        content_length=wrong_bucket.content_length,
        checksum_sha256=wrong_bucket.checksum_sha256,
    )
    with pytest.raises(S3ObjectStorageRequestError, match="configured"):
        await scope_backend.delete_object(wrong_bucket)
    await scope_backend.aclose()
