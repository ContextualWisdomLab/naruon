"""Real PostgreSQL and S3-compatible integration for document object storage.

This suite runs only in the dedicated CI job. It applies migrations 0018 and
0019 to PostgreSQL, proves provider credentials are encrypted in the database,
resolves the decrypted organization runtime, persists normalized provider-linked
object metadata, and exercises signed S3 PUT/GET/DELETE against LocalStack. It
also injects a partial upload and a transport timeout to verify fail-closed,
retryable behavior without requiring an AWS account.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
import hashlib
import os
from pathlib import Path

from alembic import command
import asyncpg
import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from db.document_object_record import DocumentObjectRecord
from db.models import Document
from db.object_storage_provider import ObjectStorageProvider
from scripts.migrate_db import alembic_config
from services.document_object_storage import (
    StoredDocumentPayload,
    resolve_document_storage_runtime_config,
)
from services.s3_object_storage import (
    AwsCredentials,
    S3ClientConfiguration,
    S3ObjectStorageBackend,
    S3ObjectStorageRequestError,
    sign_s3_request,
)


pytestmark = pytest.mark.skipif(
    os.environ.get("NARUON_S3_INTEGRATION") != "1",
    reason="requires dedicated PostgreSQL and LocalStack services",
)

_BUCKET_NAME = "naruon-integration"
_ENDPOINT_URL = "https://s3.us-east-1.localhost.localstack.cloud:4566"
_ACCESS_KEY = "integration-access-key"
_SECRET_KEY = "integration-secret-key"
_PROVIDER_ID: int | None = None


def _async_database_url() -> str:
    value = os.environ["DATABASE_URL"]
    if not value.startswith("postgresql+asyncpg://"):
        raise AssertionError("integration DATABASE_URL must use postgresql+asyncpg")
    return value


def _asyncpg_database_url() -> str:
    return _async_database_url().replace("postgresql+asyncpg://", "postgresql://", 1)


async def _prepare_pre_migration_schema() -> None:
    connection = await asyncpg.connect(_asyncpg_database_url())
    try:
        await connection.execute(
            """
            DROP TABLE IF EXISTS document_object_records CASCADE;
            DROP TABLE IF EXISTS object_storage_providers CASCADE;
            DROP TABLE IF EXISTS workspace_documents CASCADE;
            DROP TABLE IF EXISTS alembic_version CASCADE;

            CREATE TABLE workspace_documents (
                document_id varchar PRIMARY KEY,
                workspace_id varchar NOT NULL,
                organization_id varchar,
                document_name varchar NOT NULL,
                document_type varchar NOT NULL,
                document_content text,
                document_status varchar NOT NULL DEFAULT 'pending',
                created_at timestamptz NOT NULL DEFAULT now()
            );
            """
        )
    finally:
        await connection.close()


def _apply_storage_migrations() -> None:
    configuration = alembic_config()
    command.stamp(configuration, "0017_merge_newsdom_carddav_heads")
    command.upgrade(configuration, "head")


async def _create_bucket(client: httpx.AsyncClient) -> None:
    bucket_url = f"{_ENDPOINT_URL}/{_BUCKET_NAME}"
    credentials = AwsCredentials(_ACCESS_KEY, _SECRET_KEY)
    headers = sign_s3_request(
        method="PUT",
        url=bucket_url,
        headers={},
        payload=b"",
        credentials=credentials,
        region_name="us-east-1",
    )
    response = await client.put(bucket_url, headers=headers, content=b"")
    if response.status_code not in {200, 409}:
        raise AssertionError(
            f"LocalStack bucket creation failed with {response.status_code}"
        )


def _integration_configuration() -> S3ClientConfiguration:
    return S3ClientConfiguration(
        region_name="us-east-1",
        endpoint_url=_ENDPOINT_URL,
        bucket_name=_BUCKET_NAME,
        addressing_style="path",
        credentials=AwsCredentials(_ACCESS_KEY, _SECRET_KEY),
        server_side_encryption="AES256",
        request_timeout_seconds=5.0,
    )


async def _payload_stream(payload: bytes, *, chunk_size: int = 8192) -> AsyncIterator[bytes]:
    for offset in range(0, len(payload), chunk_size):
        yield payload[offset : offset + chunk_size]


async def _exercise_postgres_and_s3() -> None:
    global _PROVIDER_ID
    engine = create_async_engine(_async_database_url(), pool_pre_ping=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    payload = b"%PDF-1.7\n" + b"integration-payload" * 4096
    object_key = "workspace-documents/opaque/document-one/source.pdf"

    async with session_factory() as session:
        provider = ObjectStorageProvider(
            user_id="integration-admin",
            organization_id="organization-one",
            provider_name="primary-s3",
            provider_type="s3",
            bucket_name=_BUCKET_NAME,
            region_name="us-east-1",
            endpoint_url=_ENDPOINT_URL,
            addressing_style="path",
            access_key_id=_ACCESS_KEY,
            secret_access_key=_SECRET_KEY,
            session_token=None,
            server_side_encryption="AES256",
            kms_key_id=None,
            expected_bucket_owner=None,
            is_active=True,
        )
        document = Document(
            document_id="document-one",
            workspace_id="workspace-one",
            organization_id="organization-one",
            document_name="integration.pdf",
            document_type="pdf",
            document_content=None,
            document_status="pdf_dom_recognition_pending",
        )
        session.add_all([provider, document])
        await session.commit()
        await session.refresh(provider)
        _PROVIDER_ID = provider.object_storage_provider_id

        runtime = await resolve_document_storage_runtime_config(
            session,
            "organization-one",
        )
        assert runtime.object_storage_provider_id == provider.object_storage_provider_id
        assert runtime.s3_configuration is not None
        assert runtime.s3_configuration.credentials.access_key_id == _ACCESS_KEY
        assert runtime.s3_configuration.credentials.secret_access_key == _SECRET_KEY

        async with httpx.AsyncClient(verify=True, trust_env=False) as client:
            await _create_bucket(client)
            backend = S3ObjectStorageBackend(_integration_configuration(), client)
            stored = await backend.put_object_stream(
                object_key=object_key,
                content_stream=_payload_stream(payload),
                content_length=len(payload),
                checksum_sha256=hashlib.sha256(payload).hexdigest(),
                content_type="application/pdf",
            )
            assert await backend.get_object(stored) == payload

            object_record = StoredDocumentPayload.for_s3(
                stored,
                object_storage_provider_id=provider.object_storage_provider_id,
            ).to_object_record(document.document_id)
            assert object_record is not None
            session.add(object_record)
            await session.commit()

            persisted = await session.scalar(
                select(DocumentObjectRecord).where(
                    DocumentObjectRecord.document_id == document.document_id
                )
            )
            assert persisted is not None
            assert persisted.object_storage_provider_id == provider.object_storage_provider_id
            assert persisted.checksum_sha256 == hashlib.sha256(payload).hexdigest()

            await backend.delete_object(stored)
            with pytest.raises(S3ObjectStorageRequestError):
                await backend.get_object(stored)

            partial_key = "workspace-documents/opaque/document-two/source.pdf"

            async def broken_stream() -> AsyncIterator[bytes]:
                yield payload[:4096]
                raise RuntimeError("injected partial upload failure")

            with pytest.raises(S3ObjectStorageRequestError):
                await backend.put_object_stream(
                    object_key=partial_key,
                    content_stream=broken_stream(),
                    content_length=len(payload),
                    checksum_sha256=hashlib.sha256(payload).hexdigest(),
                    content_type="application/pdf",
                )

            missing_partial = stored.__class__(
                bucket_name=_BUCKET_NAME,
                object_key=partial_key,
                content_type="application/pdf",
                content_length=len(payload),
                checksum_sha256=hashlib.sha256(payload).hexdigest(),
            )
            with pytest.raises(S3ObjectStorageRequestError):
                await backend.get_object(missing_partial)

    raw_connection = await asyncpg.connect(_asyncpg_database_url())
    try:
        encrypted_row = await raw_connection.fetchrow(
            """
            SELECT access_key_id, secret_access_key
            FROM object_storage_providers
            WHERE object_storage_provider_id = $1
            """,
            _PROVIDER_ID,
        )
        assert encrypted_row is not None
        for column_name, plaintext in (
            ("access_key_id", _ACCESS_KEY),
            ("secret_access_key", _SECRET_KEY),
        ):
            stored_value = encrypted_row[column_name]
            assert plaintext not in stored_value
            assert stored_value.startswith("fernet:v1:")

        provider_fk = await raw_connection.fetchval(
            """
            SELECT object_storage_provider_id
            FROM document_object_records
            WHERE document_id = 'document-one'
            """
        )
        assert provider_fk == _PROVIDER_ID
    finally:
        await raw_connection.close()
        await engine.dispose()


class _TimeoutTransport(httpx.AsyncBaseTransport):
    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("injected timeout", request=request)


async def _exercise_timeout_mapping() -> None:
    backend = S3ObjectStorageBackend(
        _integration_configuration(),
        httpx.AsyncClient(transport=_TimeoutTransport(), trust_env=False),
    )
    try:
        with pytest.raises(S3ObjectStorageRequestError):
            await backend.put_object(
                object_key="workspace-documents/opaque/timeout/source.pdf",
                payload=b"%PDF-1.7 timeout",
                content_type="application/pdf",
            )
    finally:
        await backend.aclose()


def test_storage_migrations_and_real_s3_lifecycle() -> None:
    asyncio.run(_prepare_pre_migration_schema())
    _apply_storage_migrations()
    asyncio.run(_exercise_postgres_and_s3())
    asyncio.run(_exercise_timeout_mapping())
