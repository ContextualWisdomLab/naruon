"""Minimal, auditable S3-compatible object storage with AWS SigV4 signing.

The implementation deliberately uses Naruon's existing hardened ``httpx``
transport rather than a provider SDK. That keeps the runtime dependency set
stable while preserving exact-host validation, DNS pinning, bounded timeouts,
checksums, server-side encryption, redacted failure messages, and bounded
request-body streaming.
"""

from __future__ import annotations

import base64
from collections.abc import AsyncIterable
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import hmac
import re
from typing import Mapping
from urllib.parse import parse_qsl, quote, unquote, urlsplit

import httpx


_ALGORITHM = "AWS4-HMAC-SHA256"
_SERVICE_NAME = "s3"
_BUCKET_PATTERN = re.compile(r"^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$")
_REGION_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")
_EXPECTED_OWNER_PATTERN = re.compile(r"^[0-9]{12}$")
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_CONTROL_CHARACTER_PATTERN = re.compile(r"[\x00-\x1f\x7f]")


class S3ObjectStorageError(RuntimeError):
    """Base error for fail-closed S3 object-storage operations."""


class S3ObjectStorageRequestError(S3ObjectStorageError):
    """Raised when a signed S3 request cannot be completed successfully."""


class S3ObjectIntegrityError(S3ObjectStorageError):
    """Raised when stored or retrieved bytes fail an integrity contract."""


@dataclass(frozen=True)
class AwsCredentials:
    """Static or temporary AWS-compatible credentials used for SigV4 signing."""

    access_key_id: str
    secret_access_key: str
    session_token: str | None = None

    def __post_init__(self) -> None:
        if not self.access_key_id.strip() or not self.secret_access_key:
            raise ValueError("S3 credentials must include an access key and secret key")
        if _CONTROL_CHARACTER_PATTERN.search(self.access_key_id):
            raise ValueError("S3 access key must not contain control characters")
        if self.session_token is not None and _CONTROL_CHARACTER_PATTERN.search(
            self.session_token
        ):
            raise ValueError("S3 session token must not contain control characters")


@dataclass(frozen=True)
class S3ClientConfiguration:
    """Validated connection, addressing, encryption, and timeout configuration."""

    region_name: str
    endpoint_url: str
    bucket_name: str
    addressing_style: str
    credentials: AwsCredentials
    server_side_encryption: str = "AES256"
    kms_key_id: str | None = None
    expected_bucket_owner: str | None = None
    request_timeout_seconds: float = 30.0

    def __post_init__(self) -> None:
        parsed = urlsplit(self.endpoint_url)
        if parsed.scheme.lower() != "https" or not parsed.hostname:
            raise ValueError("S3 endpoint URL must use https and include a host")
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("S3 endpoint URL must not include userinfo, query, or fragment")
        if self.addressing_style not in {"virtual", "path"}:
            raise ValueError("S3 addressing style must be virtual or path")
        if not _BUCKET_PATTERN.fullmatch(self.bucket_name):
            raise ValueError("S3 bucket name is invalid")
        if not _REGION_PATTERN.fullmatch(self.region_name):
            raise ValueError("S3 region name is invalid")
        if self.server_side_encryption not in {"AES256", "aws:kms"}:
            raise ValueError("S3 server-side encryption must be AES256 or aws:kms")
        if self.server_side_encryption == "aws:kms" and not self.kms_key_id:
            raise ValueError("S3 KMS encryption requires a KMS key identifier")
        if self.expected_bucket_owner is not None and not _EXPECTED_OWNER_PATTERN.fullmatch(
            self.expected_bucket_owner
        ):
            raise ValueError("S3 expected bucket owner must be a 12-digit account ID")
        if not 0 < self.request_timeout_seconds <= 300:
            raise ValueError("S3 request timeout must be between 0 and 300 seconds")


@dataclass(frozen=True)
class S3StoredObject:
    """Persistent metadata required to retrieve and verify one S3 object."""

    bucket_name: str
    object_key: str
    content_type: str
    content_length: int
    checksum_sha256: str

    def __post_init__(self) -> None:
        if self.content_length < 0:
            raise ValueError("S3 stored-object length must not be negative")
        if not _SHA256_PATTERN.fullmatch(self.checksum_sha256):
            raise ValueError("S3 stored-object checksum must be lowercase SHA-256")
        _validate_object_key(self.object_key)


def build_document_object_key(
    *,
    organization_id: str | None,
    workspace_id: str,
    document_id: str,
    extension: str,
) -> str:
    """Build a deterministic key without exposing tenant or workspace identifiers."""
    normalized_document_id = document_id.strip()
    if not normalized_document_id or _CONTROL_CHARACTER_PATTERN.search(
        normalized_document_id
    ):
        raise ValueError("document identifier is invalid for an object key")
    if "/" in normalized_document_id or "\\" in normalized_document_id:
        raise ValueError("document identifier is invalid for an object key")
    normalized_extension = extension.strip().lower().lstrip(".")
    if not re.fullmatch(r"[a-z0-9]{1,16}", normalized_extension):
        raise ValueError("document extension is invalid for an object key")
    scope_material = f"{organization_id or 'personal'}\x00{workspace_id}".encode()
    scope_hash = hashlib.sha256(scope_material).hexdigest()[:32]
    return (
        f"workspace-documents/{scope_hash}/{normalized_document_id}/"
        f"source.{normalized_extension}"
    )


def sign_s3_request(
    *,
    method: str,
    url: str,
    headers: Mapping[str, str],
    payload: bytes | None = None,
    payload_sha256: str | None = None,
    credentials: AwsCredentials,
    region_name: str,
    request_time: datetime | None = None,
) -> dict[str, str]:
    """Return lower-case SigV4 request headers for one S3 REST request.

    Canonicalization follows the AWS S3 Signature Version 4 header-authentication
    specification, including URI/query encoding, whitespace normalization,
    signed payload hashes, and temporary-credential session tokens. Streaming
    callers may supply a precomputed lower-case SHA-256 digest instead of an
    in-memory payload; callers supplying both must provide matching values.
    """
    parsed = urlsplit(url)
    if parsed.scheme.lower() != "https" or not parsed.hostname:
        raise ValueError("S3 request URL must use https and include a host")
    if parsed.username or parsed.password or parsed.fragment:
        raise ValueError("S3 request URL must not include userinfo or fragment")
    normalized_method = method.strip().upper()
    if normalized_method not in {"GET", "PUT", "DELETE", "HEAD"}:
        raise ValueError("S3 request method is not supported")

    if payload_sha256 is None:
        if payload is None:
            raise ValueError("S3 request requires a payload or precomputed SHA-256")
        payload_hash = hashlib.sha256(payload).hexdigest()
    else:
        if not _SHA256_PATTERN.fullmatch(payload_sha256):
            raise ValueError("S3 payload SHA-256 must be lowercase hexadecimal")
        if payload is not None and hashlib.sha256(payload).hexdigest() != payload_sha256:
            raise ValueError("S3 payload bytes do not match the supplied SHA-256")
        payload_hash = payload_sha256

    instant = request_time or datetime.now(timezone.utc)
    if instant.tzinfo is None:
        instant = instant.replace(tzinfo=timezone.utc)
    instant = instant.astimezone(timezone.utc)
    amz_date = instant.strftime("%Y%m%dT%H%M%SZ")
    date_stamp = instant.strftime("%Y%m%d")

    canonical_headers = _normalize_headers(headers)
    canonical_headers["host"] = parsed.netloc
    canonical_headers["x-amz-content-sha256"] = payload_hash
    canonical_headers["x-amz-date"] = amz_date
    if credentials.session_token:
        canonical_headers["x-amz-security-token"] = credentials.session_token

    signed_header_names = ";".join(sorted(canonical_headers))
    canonical_header_block = "".join(
        f"{name}:{canonical_headers[name]}\n" for name in sorted(canonical_headers)
    )
    canonical_request = "\n".join(
        (
            normalized_method,
            _canonical_uri(parsed.path),
            _canonical_query(parsed.query),
            canonical_header_block,
            signed_header_names,
            payload_hash,
        )
    )
    credential_scope = f"{date_stamp}/{region_name}/{_SERVICE_NAME}/aws4_request"
    string_to_sign = "\n".join(
        (
            _ALGORITHM,
            amz_date,
            credential_scope,
            hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
        )
    )
    signing_key = _derive_signing_key(
        credentials.secret_access_key,
        date_stamp,
        region_name,
    )
    signature = hmac.new(
        signing_key,
        string_to_sign.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    canonical_headers["authorization"] = (
        f"{_ALGORITHM} "
        f"Credential={credentials.access_key_id}/{credential_scope},"
        f"SignedHeaders={signed_header_names},"
        f"Signature={signature}"
    )
    return canonical_headers


class S3ObjectStorageBackend:
    """Signed S3 CRUD operations with checksum verification and safe errors."""

    def __init__(
        self,
        configuration: S3ClientConfiguration,
        http_client: httpx.AsyncClient,
    ) -> None:
        self._configuration = configuration
        self._http_client = http_client

    def object_url(self, object_key: str) -> str:
        """Return the configured virtual-hosted or path-style URL for a safe key."""
        _validate_object_key(object_key)
        base_url = self._configuration.endpoint_url.rstrip("/")
        encoded_key = "/".join(
            quote(segment, safe="-_.~") for segment in object_key.split("/")
        )
        if self._configuration.addressing_style == "path":
            encoded_bucket = quote(self._configuration.bucket_name, safe="-_.~")
            return f"{base_url}/{encoded_bucket}/{encoded_key}"
        return f"{base_url}/{encoded_key}"

    async def put_object(
        self,
        *,
        object_key: str,
        payload: bytes,
        content_type: str,
    ) -> S3StoredObject:
        """Create one immutable in-memory object and return integrity metadata."""
        checksum_sha256 = hashlib.sha256(payload).hexdigest()
        return await self._put_object_content(
            object_key=object_key,
            content=payload,
            content_length=len(payload),
            checksum_sha256=checksum_sha256,
            content_type=content_type,
        )

    async def put_object_stream(
        self,
        *,
        object_key: str,
        content_stream: AsyncIterable[bytes],
        content_length: int,
        checksum_sha256: str,
        content_type: str,
    ) -> S3StoredObject:
        """Create one immutable object from a bounded prehashed async byte stream."""
        if content_length < 0:
            raise ValueError("S3 streamed object length must not be negative")
        if not _SHA256_PATTERN.fullmatch(checksum_sha256):
            raise ValueError("S3 streamed object checksum must be lowercase SHA-256")
        return await self._put_object_content(
            object_key=object_key,
            content=content_stream,
            content_length=content_length,
            checksum_sha256=checksum_sha256,
            content_type=content_type,
        )

    async def _put_object_content(
        self,
        *,
        object_key: str,
        content: bytes | AsyncIterable[bytes],
        content_length: int,
        checksum_sha256: str,
        content_type: str,
    ) -> S3StoredObject:
        """Execute the common signed immutable PUT for bytes or an async stream."""
        _validate_content_type(content_type)
        checksum_base64 = base64.b64encode(
            bytes.fromhex(checksum_sha256)
        ).decode("ascii")
        headers = {
            "content-type": content_type,
            "content-length": str(content_length),
            "if-none-match": "*",
            "x-amz-checksum-sha256": checksum_base64,
            "x-amz-server-side-encryption": (
                self._configuration.server_side_encryption
            ),
        }
        if self._configuration.kms_key_id:
            headers["x-amz-server-side-encryption-aws-kms-key-id"] = (
                self._configuration.kms_key_id
            )
        self._add_expected_owner_header(headers)
        response = await self._request(
            method="PUT",
            object_key=object_key,
            headers=headers,
            content=content,
            payload_sha256=checksum_sha256,
        )
        returned_checksum = response.headers.get("x-amz-checksum-sha256")
        if returned_checksum is not None and returned_checksum != checksum_base64:
            raise S3ObjectIntegrityError("S3 write response failed integrity verification")
        return S3StoredObject(
            bucket_name=self._configuration.bucket_name,
            object_key=object_key,
            content_type=content_type,
            content_length=content_length,
            checksum_sha256=checksum_sha256,
        )

    async def get_object(self, stored_object: S3StoredObject) -> bytes:
        """Read one object and verify its exact byte length and SHA-256 digest."""
        self._validate_stored_object_scope(stored_object)
        headers = {"x-amz-checksum-mode": "ENABLED"}
        self._add_expected_owner_header(headers)
        response = await self._request(
            method="GET",
            object_key=stored_object.object_key,
            headers=headers,
            content=b"",
            payload_sha256=hashlib.sha256(b"").hexdigest(),
        )
        payload = response.content
        if len(payload) != stored_object.content_length:
            raise S3ObjectIntegrityError("S3 read failed integrity length verification")
        if hashlib.sha256(payload).hexdigest() != stored_object.checksum_sha256:
            raise S3ObjectIntegrityError("S3 read failed integrity checksum verification")
        return payload

    async def delete_object(self, stored_object: S3StoredObject) -> None:
        """Delete one object after validating it belongs to the configured bucket."""
        self._validate_stored_object_scope(stored_object)
        headers: dict[str, str] = {}
        self._add_expected_owner_header(headers)
        await self._request(
            method="DELETE",
            object_key=stored_object.object_key,
            headers=headers,
            content=b"",
            payload_sha256=hashlib.sha256(b"").hexdigest(),
        )

    async def aclose(self) -> None:
        """Close the injected asynchronous HTTP client."""
        await self._http_client.aclose()

    async def _request(
        self,
        *,
        method: str,
        object_key: str,
        headers: Mapping[str, str],
        content: bytes | AsyncIterable[bytes],
        payload_sha256: str,
    ) -> httpx.Response:
        url = self.object_url(object_key)
        signed_headers = sign_s3_request(
            method=method,
            url=url,
            headers=headers,
            payload_sha256=payload_sha256,
            credentials=self._configuration.credentials,
            region_name=self._configuration.region_name,
        )
        try:
            response = await self._http_client.request(
                method,
                url,
                headers=signed_headers,
                content=content,
                timeout=self._configuration.request_timeout_seconds,
            )
        except httpx.HTTPError as exc:
            raise S3ObjectStorageRequestError(
                "S3 object request failed before receiving a response"
            ) from exc
        if not 200 <= response.status_code < 300:
            raise S3ObjectStorageRequestError(
                f"S3 object request failed with status {response.status_code}"
            )
        return response

    def _validate_stored_object_scope(self, stored_object: S3StoredObject) -> None:
        if stored_object.bucket_name != self._configuration.bucket_name:
            raise S3ObjectStorageRequestError(
                "Stored object does not belong to the configured S3 bucket"
            )

    def _add_expected_owner_header(self, headers: dict[str, str]) -> None:
        if self._configuration.expected_bucket_owner:
            headers["x-amz-expected-bucket-owner"] = (
                self._configuration.expected_bucket_owner
            )


def _validate_object_key(object_key: str) -> None:
    if not object_key or object_key.startswith(("/", "\\")):
        raise ValueError("S3 object key is invalid")
    if _CONTROL_CHARACTER_PATTERN.search(object_key) or "\\" in object_key:
        raise ValueError("S3 object key is invalid")
    segments = object_key.split("/")
    if any(segment in {"", ".", ".."} for segment in segments):
        raise ValueError("S3 object key is invalid")
    if len(object_key.encode("utf-8")) > 1024:
        raise ValueError("S3 object key is too long")


def _validate_content_type(content_type: str) -> None:
    if not content_type.strip() or _CONTROL_CHARACTER_PATTERN.search(content_type):
        raise ValueError("S3 content type is invalid")


def _normalize_headers(headers: Mapping[str, str]) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for name, value in headers.items():
        normalized_name = name.strip().lower()
        if not normalized_name or _CONTROL_CHARACTER_PATTERN.search(normalized_name):
            raise ValueError("S3 request header name is invalid")
        raw_value = str(value)
        if _CONTROL_CHARACTER_PATTERN.search(raw_value):
            raise ValueError("S3 request header value is invalid")
        normalized[normalized_name] = " ".join(raw_value.strip().split())
    return normalized


def _canonical_uri(path: str) -> str:
    decoded_path = unquote(path or "/")
    return quote(decoded_path, safe="/-_.~") or "/"


def _canonical_query(query: str) -> str:
    encoded_pairs = [
        (quote(key, safe="-_.~"), quote(value, safe="-_.~"))
        for key, value in parse_qsl(query, keep_blank_values=True)
    ]
    encoded_pairs.sort()
    return "&".join(f"{key}={value}" for key, value in encoded_pairs)


def _derive_signing_key(secret_key: str, date_stamp: str, region_name: str) -> bytes:
    date_key = hmac.new(
        f"AWS4{secret_key}".encode("utf-8"),
        date_stamp.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    region_key = hmac.new(
        date_key,
        region_name.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    service_key = hmac.new(
        region_key,
        _SERVICE_NAME.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return hmac.new(service_key, b"aws4_request", hashlib.sha256).digest()
