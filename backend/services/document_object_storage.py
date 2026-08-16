"""Document-payload persistence across database and S3 backends.

PostgreSQL remains the authoritative metadata, authorization, workflow, and
parsed-text store. Raw PDF bytes move behind a small persistence seam. The
process environment selects only ``database`` or ``s3``; organization-scoped S3
metadata and credentials are resolved from the Fernet-encrypted provider
registry before a DNS-pinned request is built.
"""

from __future__ import annotations

import asyncio
import base64
import binascii
from collections.abc import AsyncIterator
from dataclasses import dataclass
import datetime
import hashlib
from urllib.parse import urlsplit

from fastapi import UploadFile
from sqlalchemy import select

from core.object_storage_config import object_storage_settings as settings
from core.url_validation import (
    parse_allowed_hosts,
    validate_https_url_host_details,
)
from db.document_object_record import DocumentObjectRecord
from db.models import Document
from db.object_storage_provider import ObjectStorageProvider
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
PDF_UPLOAD_CHUNK_BYTES = 64 * 1024


class DocumentObjectStorageError(RuntimeError):
    """Raised when a configured document backend cannot safely serve a payload."""


class DocumentUploadTooLargeError(ValueError):
    """Raised when a streamed document exceeds the configured upload ceiling."""


class DocumentUploadValidationError(ValueError):
    """Raised when streamed document bytes do not satisfy the PDF contract."""


@dataclass(frozen=True)
class DocumentStorageRuntimeConfig:
    """Resolved backend authority for one organization-scoped operation."""

    storage_backend: str
    s3_configuration: S3ClientConfiguration | None = None
    object_storage_provider_id: int | None = None
    allowed_hosts: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        if self.storage_backend not in {"database", "s3"}:
            raise ValueError("Document storage runtime backend is unsupported")
        if self.storage_backend == "database" and self.s3_configuration is not None:
            raise ValueError("Database runtime must not include S3 configuration")
        if self.storage_backend == "s3" and self.s3_configuration is None:
            raise ValueError("S3 runtime requires S3 configuration")


@dataclass(frozen=True)
class ValidatedPDFUpload:
    """Integrity metadata produced by a bounded first pass over an upload."""

    content_length: int
    checksum_sha256: str

    def __post_init__(self) -> None:
        if self.content_length < 0:
            raise ValueError("Validated PDF length must not be negative")
        if len(self.checksum_sha256) != 64 or any(
            character not in "0123456789abcdef"
            for character in self.checksum_sha256
        ):
            raise ValueError("Validated PDF checksum must be lowercase SHA-256")


@dataclass(frozen=True)
class StoredDocumentPayload:
    """Result of persisting raw document bytes to one configured backend."""

    storage_backend: str
    document_content: str | None
    s3_object: S3StoredObject | None
    object_storage_provider_id: int | None = None

    @classmethod
    def for_database(cls, payload: bytes) -> "StoredDocumentPayload":
        """Encode a validated PDF for the backward-compatible database backend."""
        _validate_pdf_bytes(payload)
        return cls(
            storage_backend="database",
            document_content=base64.b64encode(payload).decode("ascii"),
            s3_object=None,
            object_storage_provider_id=None,
        )

    @classmethod
    def for_s3(
        cls,
        stored_object: S3StoredObject,
        *,
        object_storage_provider_id: int | None = None,
    ) -> "StoredDocumentPayload":
        """Represent an S3 payload without duplicating its bytes in SQL."""
        return cls(
            storage_backend="s3",
            document_content=None,
            s3_object=stored_object,
            object_storage_provider_id=object_storage_provider_id,
        )

    def to_object_record(self, document_id: str) -> DocumentObjectRecord | None:
        """Build normalized SQL metadata for S3, or no row for inline storage."""
        if self.s3_object is None:
            return None
        return DocumentObjectRecord(
            document_id=document_id,
            object_storage_provider_id=self.object_storage_provider_id,
            storage_backend="s3",
            bucket_name=self.s3_object.bucket_name,
            object_key=self.s3_object.object_key,
            inline_payload=None,
            content_type=self.s3_object.content_type,
            content_length=self.s3_object.content_length,
            checksum_sha256=self.s3_object.checksum_sha256,
            storage_state="active",
        )


async def resolve_document_storage_runtime_config(
    session,
    organization_id: str | None,
) -> DocumentStorageRuntimeConfig:
    """Resolve the selected backend without reading provider secrets from env."""
    if settings.OBJECT_STORAGE_BACKEND == "database":
        return DocumentStorageRuntimeConfig(storage_backend="database")
    if settings.OBJECT_STORAGE_BACKEND != "s3":
        raise DocumentObjectStorageError("Configured document backend is unsupported")
    return await _resolve_s3_provider_runtime_config(session, organization_id)


async def _resolve_s3_provider_runtime_config(
    session,
    organization_id: str | None,
    *,
    object_storage_provider_id: int | None = None,
) -> DocumentStorageRuntimeConfig:
    """Resolve an active or explicitly retained organization S3 provider row."""
    if not organization_id:
        raise DocumentObjectStorageError(
            "S3 document storage requires an organization scope"
        )

    statement = select(ObjectStorageProvider).where(
        ObjectStorageProvider.organization_id == organization_id,
        ObjectStorageProvider.provider_type == "s3",
    )
    if object_storage_provider_id is None:
        statement = statement.where(ObjectStorageProvider.is_active.is_(True)).order_by(
            ObjectStorageProvider.updated_at.desc(),
            ObjectStorageProvider.object_storage_provider_id.desc(),
        )
    else:
        statement = statement.where(
            ObjectStorageProvider.object_storage_provider_id
            == object_storage_provider_id
        )
    provider = await session.scalar(statement.limit(1))
    if provider is None:
        raise DocumentObjectStorageError(
            "No configured S3 document-storage provider is available"
        )

    try:
        configuration, allowed_hosts = _configuration_from_provider(provider)
    except (AttributeError, TypeError, ValueError) as exc:
        raise DocumentObjectStorageError(
            "Configured S3 document storage failed validation"
        ) from exc
    return DocumentStorageRuntimeConfig(
        storage_backend="s3",
        s3_configuration=configuration,
        object_storage_provider_id=getattr(
            provider,
            "object_storage_provider_id",
            None,
        ),
        allowed_hosts=allowed_hosts,
    )


def _configuration_from_provider(
    provider: ObjectStorageProvider,
) -> tuple[S3ClientConfiguration, frozenset[str]]:
    """Build a validated S3 client configuration from one decrypted DB row."""
    endpoint_url, allowed_hosts = _provider_endpoint_and_allowlist(provider)
    configuration = S3ClientConfiguration(
        region_name=provider.region_name,
        endpoint_url=endpoint_url,
        bucket_name=provider.bucket_name,
        addressing_style=provider.addressing_style,
        credentials=AwsCredentials(
            access_key_id=provider.access_key_id,
            secret_access_key=provider.secret_access_key,
            session_token=provider.session_token,
        ),
        server_side_encryption=provider.server_side_encryption,
        kms_key_id=provider.kms_key_id,
        expected_bucket_owner=provider.expected_bucket_owner,
        request_timeout_seconds=settings.OBJECT_STORAGE_REQUEST_TIMEOUT_SECONDS,
    )
    return configuration, allowed_hosts


def _provider_endpoint_and_allowlist(
    provider: ObjectStorageProvider,
) -> tuple[str, frozenset[str]]:
    """Derive AWS endpoints or enforce the operator custom-host allowlist."""
    configured_endpoint = (provider.endpoint_url or "").strip()
    if configured_endpoint:
        if provider.addressing_style != "path":
            raise ValueError("Custom S3 endpoints require path addressing")
        normalized_endpoint = configured_endpoint.rstrip("/")
        parsed = urlsplit(normalized_endpoint)
        host = (parsed.hostname or "").lower().rstrip(".")
        allowed_hosts = parse_allowed_hosts(settings.OBJECT_STORAGE_S3_ALLOWED_HOSTS)
        if host not in allowed_hosts:
            raise ValueError("Configured S3 endpoint host is not allowlisted")
        return normalized_endpoint, allowed_hosts

    bucket_name = provider.bucket_name
    region_name = provider.region_name
    if provider.addressing_style == "path":
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


async def inspect_pdf_upload(
    upload: UploadFile,
    *,
    max_bytes: int = MAX_PDF_DOCUMENT_BYTES,
    chunk_size: int = PDF_UPLOAD_CHUNK_BYTES,
) -> ValidatedPDFUpload:
    """Validate, hash, and rewind one PDF without buffering it in application RAM.

    FastAPI's ``UploadFile`` is a spooled file. This first pass reads only
    positive bounded chunks, enforces the byte ceiling while data is consumed,
    validates the PDF signature, records the exact SHA-256 used for SigV4 and S3
    checksum headers, and rewinds the spool for the persistence pass.
    """
    if max_bytes <= 0:
        raise ValueError("PDF upload max_bytes must be positive")
    if chunk_size <= 0:
        raise ValueError("PDF upload chunk_size must be positive")

    digest = hashlib.sha256()
    prefix = bytearray()
    content_length = 0
    await upload.seek(0)
    try:
        while True:
            chunk = await upload.read(chunk_size)
            if not chunk:
                break
            if not isinstance(chunk, bytes):
                raise DocumentUploadValidationError("PDF upload did not yield bytes")
            content_length += len(chunk)
            if content_length > max_bytes:
                raise DocumentUploadTooLargeError("PDF upload exceeds the size limit")
            if len(prefix) < 5:
                prefix.extend(chunk[: 5 - len(prefix)])
            digest.update(chunk)
    finally:
        await upload.seek(0)

    if bytes(prefix) != b"%PDF-":
        raise DocumentUploadValidationError("PDF upload does not have a PDF signature")
    return ValidatedPDFUpload(
        content_length=content_length,
        checksum_sha256=digest.hexdigest(),
    )


async def _iter_verified_upload(
    upload: UploadFile,
    *,
    validated_upload: ValidatedPDFUpload,
    chunk_size: int,
) -> AsyncIterator[bytes]:
    """Yield a second bounded pass and reject content changed after inspection."""
    digest = hashlib.sha256()
    content_length = 0
    await upload.seek(0)
    try:
        while True:
            chunk = await upload.read(chunk_size)
            if not chunk:
                break
            if not isinstance(chunk, bytes):
                raise ValueError("PDF upload did not yield bytes during persistence")
            content_length += len(chunk)
            if content_length > validated_upload.content_length:
                raise ValueError("PDF upload changed after integrity inspection")
            digest.update(chunk)
            yield chunk
        if (
            content_length != validated_upload.content_length
            or digest.hexdigest() != validated_upload.checksum_sha256
        ):
            raise ValueError("PDF upload changed after integrity inspection")
    finally:
        await upload.seek(0)


async def _read_verified_upload_bytes(
    upload: UploadFile,
    *,
    validated_upload: ValidatedPDFUpload,
    chunk_size: int,
) -> bytes:
    """Collect bounded verified chunks for the legacy inline database backend."""
    chunks = [
        chunk
        async for chunk in _iter_verified_upload(
            upload,
            validated_upload=validated_upload,
            chunk_size=chunk_size,
        )
    ]
    return b"".join(chunks)


async def store_configured_pdf_upload(
    *,
    upload: UploadFile,
    validated_upload: ValidatedPDFUpload,
    document_id: str,
    organization_id: str | None,
    workspace_id: str,
    chunk_size: int = PDF_UPLOAD_CHUNK_BYTES,
    runtime_config: DocumentStorageRuntimeConfig | None = None,
) -> StoredDocumentPayload:
    """Persist an inspected upload through bounded database or S3 reads."""
    if chunk_size <= 0:
        raise ValueError("PDF upload chunk_size must be positive")
    if validated_upload.content_length > MAX_PDF_DOCUMENT_BYTES:
        raise DocumentUploadTooLargeError("PDF upload exceeds the size limit")

    backend_name = (
        runtime_config.storage_backend
        if runtime_config is not None
        else settings.OBJECT_STORAGE_BACKEND
    )
    if backend_name == "database":
        payload = await _read_verified_upload_bytes(
            upload,
            validated_upload=validated_upload,
            chunk_size=chunk_size,
        )
        return StoredDocumentPayload.for_database(payload)
    if backend_name != "s3":
        raise DocumentObjectStorageError("Configured document backend is unsupported")

    backend = await _backend_for_runtime(runtime_config)
    try:
        stored_object = await backend.put_object_stream(
            object_key=build_document_object_key(
                organization_id=organization_id,
                workspace_id=workspace_id,
                document_id=document_id,
                extension="pdf",
            ),
            content_stream=_iter_verified_upload(
                upload,
                validated_upload=validated_upload,
                chunk_size=chunk_size,
            ),
            content_length=validated_upload.content_length,
            checksum_sha256=validated_upload.checksum_sha256,
            content_type="application/pdf",
        )
    except (S3ObjectStorageError, ValueError) as exc:
        raise DocumentObjectStorageError(
            "Configured S3 document storage could not persist the payload"
        ) from exc
    finally:
        await backend.aclose()
    return StoredDocumentPayload.for_s3(
        stored_object,
        object_storage_provider_id=(
            runtime_config.object_storage_provider_id
            if runtime_config is not None
            else None
        ),
    )


def _utc_now() -> datetime.datetime:
    """Return an aware UTC timestamp for object lifecycle transitions."""
    return datetime.datetime.now(datetime.timezone.utc)


def _stored_object_from_record(record: DocumentObjectRecord) -> S3StoredObject:
    """Validate persisted locator metadata and materialize an S3 object handle."""
    if record.storage_backend != "s3":
        raise DocumentObjectStorageError("Document object backend is unsupported")
    if not record.bucket_name or not record.object_key:
        raise DocumentObjectStorageError("Document object locator is incomplete")
    try:
        return S3StoredObject(
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
    runtime_config: DocumentStorageRuntimeConfig | None = None,
) -> StoredDocumentPayload:
    """Persist already-materialized legacy PDF bytes through the selected backend."""
    _validate_pdf_bytes(payload)
    backend_name = (
        runtime_config.storage_backend
        if runtime_config is not None
        else settings.OBJECT_STORAGE_BACKEND
    )
    if backend_name == "database":
        return StoredDocumentPayload.for_database(payload)
    if backend_name != "s3":
        raise DocumentObjectStorageError("Configured document backend is unsupported")

    backend = await _backend_for_runtime(runtime_config)
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
    return StoredDocumentPayload.for_s3(
        stored_object,
        object_storage_provider_id=(
            runtime_config.object_storage_provider_id
            if runtime_config is not None
            else None
        ),
    )


async def delete_configured_document_payload(
    stored: StoredDocumentPayload,
    *,
    runtime_config: DocumentStorageRuntimeConfig | None = None,
) -> None:
    """Compensate a persisted S3 object after a metadata commit failure."""
    if stored.s3_object is None:
        return
    backend = await _backend_for_runtime(runtime_config)
    try:
        await backend.delete_object(stored.s3_object)
    except (S3ObjectStorageError, ValueError) as exc:
        raise DocumentObjectStorageError(
            "Configured S3 document storage could not delete the payload"
        ) from exc
    finally:
        await backend.aclose()


async def delete_document_object_record(
    record: DocumentObjectRecord,
    *,
    runtime_config: DocumentStorageRuntimeConfig | None = None,
) -> None:
    """Delete a raw S3 object for an explicit customer document removal."""
    stored_object = _stored_object_from_record(record)
    backend = await _backend_for_runtime(runtime_config)
    try:
        await backend.delete_object(stored_object)
    except (S3ObjectStorageError, ValueError) as exc:
        raise DocumentObjectStorageError(
            "Configured S3 document storage could not delete the customer payload"
        ) from exc
    finally:
        await backend.aclose()


async def mark_document_payload_consumed(
    session,
    document_id: str,
) -> DocumentObjectRecord | None:
    """Move an S3 document record from active to consumed idempotently."""
    record = await session.scalar(
        select(DocumentObjectRecord).where(
            DocumentObjectRecord.document_id == document_id
        )
    )
    if record is None:
        return None
    if record.storage_state == "active":
        record.storage_state = "consumed"
        record.consumed_at = _utc_now()
        return record
    if record.storage_state == "consumed":
        if record.consumed_at is None or record.deleted_at is not None:
            raise DocumentObjectStorageError(
                "Consumed document object lifecycle metadata is inconsistent"
            )
        return record
    if record.storage_state == "deleted":
        if record.consumed_at is None or record.deleted_at is None:
            raise DocumentObjectStorageError(
                "Deleted document object lifecycle metadata is inconsistent"
            )
        return record
    raise DocumentObjectStorageError("Document object lifecycle state is unsupported")


async def delete_consumed_document_payload(
    record: DocumentObjectRecord,
    *,
    runtime_config: DocumentStorageRuntimeConfig | None = None,
) -> None:
    """Delete a consumed S3 object and mark deletion only after remote success."""
    if record.storage_state == "deleted":
        if record.consumed_at is None or record.deleted_at is None:
            raise DocumentObjectStorageError(
                "Deleted document object lifecycle metadata is inconsistent"
            )
        return
    if record.storage_state != "consumed" or record.consumed_at is None:
        raise DocumentObjectStorageError(
            "Document object must be consumed before deletion"
        )
    if record.deleted_at is not None:
        raise DocumentObjectStorageError(
            "Consumed document object must not already have a deletion timestamp"
        )

    stored_object = _stored_object_from_record(record)
    backend = await _backend_for_runtime(runtime_config)
    try:
        await backend.delete_object(stored_object)
    except (S3ObjectStorageError, ValueError) as exc:
        raise DocumentObjectStorageError(
            "Configured S3 document storage could not delete the consumed payload"
        ) from exc
    finally:
        await backend.aclose()
    record.storage_state = "deleted"
    record.deleted_at = _utc_now()


async def load_pending_pdf_document_bytes(session, document: Document) -> bytes:
    """Load a pending PDF from inline SQL or its retained S3 provider record."""
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

    runtime_config = await _resolve_s3_provider_runtime_config(
        session,
        document.organization_id,
        object_storage_provider_id=record.object_storage_provider_id,
    )
    stored_object = _stored_object_from_record(record)
    backend = await _build_s3_backend(runtime_config)
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


async def resolve_document_object_runtime_config(
    session,
    document: Document,
    record: DocumentObjectRecord,
) -> DocumentStorageRuntimeConfig:
    """Resolve the provider retained by a normalized document-object record."""
    return await _resolve_s3_provider_runtime_config(
        session,
        document.organization_id,
        object_storage_provider_id=record.object_storage_provider_id,
    )


async def _backend_for_runtime(
    runtime_config: DocumentStorageRuntimeConfig | None,
) -> S3ObjectStorageBackend:
    """Build a registry-backed backend or invoke the legacy test injection seam."""
    if runtime_config is None:
        return await _build_s3_backend_from_settings()
    return await _build_s3_backend(runtime_config)


async def _build_s3_backend(
    runtime_config: DocumentStorageRuntimeConfig,
) -> S3ObjectStorageBackend:
    """Create a DNS-pinned client from a resolved registry configuration."""
    configuration = runtime_config.s3_configuration
    if runtime_config.storage_backend != "s3" or configuration is None:
        raise DocumentObjectStorageError("Resolved document backend is not S3")
    try:
        validated_endpoint = await asyncio.to_thread(
            validate_https_url_host_details,
            "OBJECT_STORAGE_S3_ENDPOINT_URL",
            configuration.endpoint_url,
            runtime_config.allowed_hosts,
            "OBJECT_STORAGE_S3_ALLOWED_HOSTS",
        )
        http_client = build_pinned_https_async_client(
            validated_endpoint.normalized_url,
            validated_endpoint.hostname,
            validated_endpoint.port,
            validated_endpoint.addresses,
        )
        pinned_configuration = S3ClientConfiguration(
            region_name=configuration.region_name,
            endpoint_url=validated_endpoint.normalized_url.rstrip("/"),
            bucket_name=configuration.bucket_name,
            addressing_style=configuration.addressing_style,
            credentials=configuration.credentials,
            server_side_encryption=configuration.server_side_encryption,
            kms_key_id=configuration.kms_key_id,
            expected_bucket_owner=configuration.expected_bucket_owner,
            request_timeout_seconds=configuration.request_timeout_seconds,
        )
    except ValueError as exc:
        raise DocumentObjectStorageError(
            "Configured S3 document storage failed validation"
        ) from exc
    return S3ObjectStorageBackend(pinned_configuration, http_client)


async def _build_s3_backend_from_settings() -> S3ObjectStorageBackend:
    """Fail closed unless a test injects the retired environment-backed seam."""
    raise DocumentObjectStorageError(
        "S3 runtime configuration must come from the encrypted provider registry"
    )


def _validate_pdf_bytes(payload: bytes) -> None:
    """Reject oversized or non-PDF bytes before persistence or recognition."""
    if len(payload) > MAX_PDF_DOCUMENT_BYTES:
        raise ValueError("Pending PDF document exceeds the size limit")
    if not payload.startswith(b"%PDF-"):
        raise ValueError("Pending PDF document payload is not a PDF")
