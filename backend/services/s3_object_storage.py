"""Hardened S3-compatible object-storage facade with orphan adoption.

The stable signing, validation, and CRUD implementation lives in
``s3_object_storage_core``. This facade adds the saga-recovery behavior needed
when an immutable PUT succeeded but its relational metadata transaction did
not: a retry that receives HTTP 412 may adopt the occupied key only after a
server-mediated GET proves byte length and SHA-256 are exactly the intended
object. It also maps arbitrary request-body producer failures to a fixed,
redacted storage error while preserving explicit S3 integrity failures.
"""

from __future__ import annotations

from collections.abc import AsyncIterable
from typing import Mapping

import httpx

from services import s3_object_storage_core as _core
from services.s3_object_storage_core import (
    AwsCredentials,
    S3ClientConfiguration,
    S3ObjectIntegrityError,
    S3ObjectStorageError,
    S3ObjectStorageRequestError,
    S3StoredObject,
    build_document_object_key,
    sign_s3_request,
)

__all__ = [
    "AwsCredentials",
    "S3ClientConfiguration",
    "S3ObjectIntegrityError",
    "S3ObjectStorageBackend",
    "S3ObjectStorageError",
    "S3ObjectStorageRequestError",
    "S3StoredObject",
    "build_document_object_key",
    "sign_s3_request",
]


class _S3ObjectAlreadyExistsError(S3ObjectStorageRequestError):
    """Internal signal that immutable PUT found an already occupied object key."""


class S3ObjectStorageBackend(_core.S3ObjectStorageBackend):
    """S3 CRUD with exact-orphan adoption and redacted stream failures."""

    async def _put_object_content(
        self,
        *,
        object_key: str,
        content: bytes | AsyncIterable[bytes],
        content_length: int,
        checksum_sha256: str,
        content_type: str,
    ) -> S3StoredObject:
        """Create an immutable object or safely adopt its exact existing bytes."""
        try:
            return await super()._put_object_content(
                object_key=object_key,
                content=content,
                content_length=content_length,
                checksum_sha256=checksum_sha256,
                content_type=content_type,
            )
        except _S3ObjectAlreadyExistsError:
            candidate = S3StoredObject(
                bucket_name=self._configuration.bucket_name,
                object_key=object_key,
                content_type=content_type,
                content_length=content_length,
                checksum_sha256=checksum_sha256,
            )
            await self.get_object(candidate)
            return candidate

    async def _request(
        self,
        *,
        method: str,
        object_key: str,
        headers: Mapping[str, str],
        content: bytes | AsyncIterable[bytes],
        payload_sha256: str,
    ) -> httpx.Response:
        """Send one signed request while redacting transport and producer failures."""
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
        except S3ObjectStorageError:
            raise
        except httpx.HTTPError as exc:
            raise S3ObjectStorageRequestError(
                "S3 object request failed before receiving a response"
            ) from exc
        except Exception as exc:
            raise S3ObjectStorageRequestError(
                "S3 object request source failed before completion"
            ) from exc

        if method == "PUT" and response.status_code == 412:
            raise _S3ObjectAlreadyExistsError(
                "S3 immutable object key is already occupied"
            )
        if not 200 <= response.status_code < 300:
            raise S3ObjectStorageRequestError(
                f"S3 object request failed with status {response.status_code}"
            )
        return response
