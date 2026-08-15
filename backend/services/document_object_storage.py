"""Document-payload persistence across legacy database and S3 backends.

PostgreSQL remains the authoritative metadata, authorization, workflow, and
parsed-text store. This module only moves immutable raw PDF bytes behind a
small persistence seam so deployments can retain the current inline database
mode or select an S3-compatible object store without changing API semantics.
"""

from __future__ import annotations

import asyncio
import base64
import binascii
from dataclasses import dataclass
from urllib.parse import urlsplit

from sqlalchemy import select

from core.object_storage_config import object_storage_settings as settings
from core.url_validation import (
    parse_allowed_hosts,
    validate_https_url_host_details,
)
from db.document_object_record import DocumentObjectRecord
from db.models import Document
from services.llm_provider_urls import build_pinned_https_async_client
from services.s3_object_storage import (
    AwsCredentials,
    S3ClientConfiguration,
    S3ObjectStorageBackend,
    S3ObjectStorageError,
    S3StoredObject,
    build_document_object_key,
)


MAX_PDF_DOCUMENT_BYTES = 20 * 1024 * 1024


class DocumentObjectStorageError(RuntimeError):
    """Raised when a configured document backend cannot safely serve a payload."""


@dataclass(frozen=True)
class StoredDocumentPayload:
    """Result of persisting raw document bytes to one configured backend."""

    storage_backend: str
    document_content: str | None
    s3_object: S3StoredObject | None

    @classmethod
    def for_database(cls, payload: bytes) -> "StoredDocumentPayload":
        """Encode a validated PDF for the backward-compatible database backend."""
        _validate_pdf_bytes(payload)
        return cls(
            storage_backend="database",
            document_content=base64.b64encode(payload).decode("ascii"),
            s3_object=None,
        )

    @classmethod
    def for_s3(cls, stored_object: S3StoredObject) -> "StoredDocumentPayload":
        """Represent an S3-backed payload without duplicating its bytes in SQL."""
        return cls(
            storage_backend="s3",
            document_content=None,
            s3_object=stored_object,
        )

    def to_object_record(self, document_id: str) -> DocumentObjectRecord | None:
        """Build normalized SQL metadata for S3, or no row for inline storage."""
        if self.s3_object is None:
            return None
        return DocumentObjectRecord(
            document_id=document_id,
            storage_backend="s3",
            bucket_name=self.s3_object.bucket_name,
            object_key=self.s3_object.object_key,
            inline_payload=None,
            content_type=self.s3_object.content_type,
            content_length=self.s3_object.content_length,
            checksum_sha256=self.s3_object.checksum_sha256,
            storage_state="active",
        )


def decode_legacy_pdf_payload(encoded_payload: str | None) -> bytes:
    """Decode and validate a legacy base64 PDF stored in ``workspace_documents``."""
    try:
        encoded_bytes = (encoded_payload or "").encode("ascii")
        payload = base64.b64decode(encoded_bytes, validate=True)
    except (binascii.Error, UnicodeEncodeError, ValueError) as exc:
        raise ValueError("Pending PDF document payload is not valid base64") from exc
    _validate_pdf_bytes(payload)
    return payload


async def store_configured_pdf_document(
    *,
    payload: bytes,
    document_id: str,
    organization_id: str | None,
    workspace_id: str,
) -> StoredDocumentPayload:
    """Persist a PDF using the configured database or S3 backend."""
    _validate_pdf_bytes(payload)
    if settings.OBJECT_STORAGE_BACKEND == "database":
        return StoredDocumentPayload.for_database(payload)
    if settings.OBJECT_STORAGE_BACKEND != "s3":
        raise DocumentObjectStorageError("Configured document backend is unsupported")

    backend = await _build_s3_backend_from_settings()
    try:
        stored_object = await backend.put_object(
            object_key=build_document_object_key(
                organization_id=organization_id,
                workspace_id=workspace_id,
                document_id=document_id,
                extension="pdf",
            ),
            payload=payload,
            content_type="application/pdf",
        )
    except (S3ObjectStorageError, ValueError) as exc:
        raise DocumentObjectStorageError(
            "Configured S3 document storage could not persist the payload"
        ) from exc
    finally:
        await backend.aclose()
    return StoredDocumentPayload.for_s3(stored_object)


async def delete_configured_document_payload(stored: StoredDocumentPayload) -> None:
    """Compensate a persisted S3 object after a metadata commit failure."""
    if stored.s3_object is None:
        return
    backend = await _build_s3_backend_from_settings()
    try:
        await backend.delete_object(stored.s3_object)
    except (S3ObjectStorageError, ValueError) as exc:
        raise DocumentObjectStorageError(
            "Configured S3 document storage could not delete the payload"
        ) from exc
    finally:
        await backend.aclose()


async def load_pending_pdf_document_bytes(session, document: Document) -> bytes:
    """Load a pending PDF from inline SQL or its normalized S3 object record."""
    if document.document_content:
        return decode_legacy_pdf_payload(document.document_content)

    record = await session.scalar(
        select(DocumentObjectRecord).where(
            DocumentObjectRecord.document_id == document.document_id
        )
    )
    if record is None:
        raise DocumentObjectStorageError("Pending document payload is not available")
    if record.document_id != document.document_id:
        raise DocumentObjectStorageError("Document object record does not match document")
    if record.storage_state != "active":
        raise DocumentObjectStorageError("Document object record is not active")
    if record.storage_backend != "s3":
        raise DocumentObjectStorageError("Document object backend is unsupported")
    if not record.bucket_name or not record.object_key:
        raise DocumentObjectStorageError("Document object locator is incomplete")

    try:
        stored_object = S3StoredObject(
            bucket_name=record.bucket_name,
            object_key=record.object_key,
            content_type=record.content_type,
            content_length=record.content_length,
            checksum_sha256=record.checksum_sha256,
        )
    except ValueError as exc:
        raise DocumentObjectStorageError(
            "Document object metadata failed validation"
        ) from exc

    backend = await _build_s3_backend_from_settings()
    try:
        payload = await backend.get_object(stored_object)
    except (S3ObjectStorageError, ValueError) as exc:
        raise DocumentObjectStorageError(
            "Configured S3 document storage could not load the payload"
        ) from exc
    finally:
        await backend.aclose()
    try:
        _validate_pdf_bytes(payload)
    except ValueError as exc:
        raise DocumentObjectStorageError(
            "Retrieved document payload is not a valid PDF"
        ) from exc
    return payload


async def _build_s3_backend_from_settings() -> S3ObjectStorageBackend:
    try:
        endpoint_url, allowed_hosts = _resolve_endpoint_and_allowlist()
        validated_endpoint = await asyncio.to_thread(
            validate_https_url_host_details,
            "OBJECT_STORAGE_S3_ENDPOINT_URL",
            endpoint_url,
            allowed_hosts,
            "OBJECT_STORAGE_S3_ALLOWED_HOSTS",
        )
        http_client = build_pinned_https_async_client(
            validated_endpoint.normalized_url,
            validated_endpoint.hostname,
            validated_endpoint.port,
            validated_endpoint.addresses,
        )
        access_key = settings.OBJECT_STORAGE_S3_ACCESS_KEY_ID
        secret_key = settings.OBJECT_STORAGE_S3_SECRET_ACCESS_KEY
        if access_key is None or secret_key is None:
            raise ValueError("S3 credentials are incomplete")
        session_token = settings.OBJECT_STORAGE_S3_SESSION_TOKEN
        configuration = S3ClientConfiguration(
            region_name=settings.OBJECT_STORAGE_S3_REGION_NAME,
            endpoint_url=validated_endpoint.normalized_url.rstrip("/"),
            bucket_name=settings.OBJECT_STORAGE_S3_BUCKET_NAME or "",
            addressing_style=settings.OBJECT_STORAGE_S3_ADDRESSING_STYLE,
            credentials=AwsCredentials(
                access_key_id=access_key.get_secret_value(),
                secret_access_key=secret_key.get_secret_value(),
                session_token=(
                    session_token.get_secret_value() if session_token is not None else None
                ),
            ),
            server_side_encryption=(
                settings.OBJECT_STORAGE_S3_SERVER_SIDE_ENCRYPTION
            ),
            kms_key_id=settings.OBJECT_STORAGE_S3_KMS_KEY_ID,
            expected_bucket_owner=settings.OBJECT_STORAGE_S3_EXPECTED_BUCKET_OWNER,
            request_timeout_seconds=(
                settings.OBJECT_STORAGE_REQUEST_TIMEOUT_SECONDS
            ),
        )
    except ValueError as exc:
        raise DocumentObjectStorageError(
            "Configured S3 document storage failed validation"
        ) from exc
    return S3ObjectStorageBackend(configuration, http_client)


def _resolve_endpoint_and_allowlist() -> tuple[str, frozenset[str]]:
    configured_endpoint = settings.OBJECT_STORAGE_S3_ENDPOINT_URL
    if configured_endpoint:
        parsed = urlsplit(configured_endpoint)
        host = (parsed.hostname or "").lower().rstrip(".")
        allowed_hosts = parse_allowed_hosts(settings.OBJECT_STORAGE_S3_ALLOWED_HOSTS)
        if host not in allowed_hosts:
            raise ValueError("Configured S3 endpoint host is not allowlisted")
        return configured_endpoint, allowed_hosts

    bucket_name = settings.OBJECT_STORAGE_S3_BUCKET_NAME or ""
    region_name = settings.OBJECT_STORAGE_S3_REGION_NAME
    if settings.OBJECT_STORAGE_S3_ADDRESSING_STYLE == "path":
        host = (
            "s3.amazonaws.com"
            if region_name == "us-east-1"
            else f"s3.{region_name}.amazonaws.com"
        )
    else:
        host = (
            f"{bucket_name}.s3.amazonaws.com"
            if region_name == "us-east-1"
            else f"{bucket_name}.s3.{region_name}.amazonaws.com"
        )
    return f"https://{host}", frozenset({host})


def _validate_pdf_bytes(payload: bytes) -> None:
    """Reject oversized or non-PDF bytes before persistence or recognition."""
    if len(payload) > MAX_PDF_DOCUMENT_BYTES:
        raise ValueError("Pending PDF document exceeds the size limit")
    if not payload.startswith(b"%PDF-"):
        raise ValueError("Pending PDF document payload is not a PDF")
