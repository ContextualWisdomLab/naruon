"""Contracts for resolving S3 credentials from the encrypted provider registry."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from core.object_storage_config import ObjectStorageSettings
import services.document_object_storage as storage_module


class ScalarSession:
    """Return one selected provider row while recording registry access."""

    def __init__(self, provider) -> None:
        self.provider = provider
        self.scalar_calls = 0
        self.statement = None

    async def scalar(self, statement):
        self.scalar_calls += 1
        self.statement = statement
        return self.provider


def _provider(**overrides):
    values = {
        "provider_name": "primary-s3",
        "provider_type": "s3",
        "bucket_name": "naruon-documents",
        "region_name": "ap-northeast-2",
        "endpoint_url": None,
        "addressing_style": "virtual",
        "access_key_id": "database-access-key",
        "secret_access_key": "database-secret-key",
        "session_token": "database-session-token",
        "server_side_encryption": "aws:kms",
        "kms_key_id": "arn:aws:kms:ap-northeast-2:111122223333:key/example",
        "expected_bucket_owner": "111122223333",
        "is_active": True,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_operator_settings_do_not_accept_s3_credentials_from_environment() -> None:
    """Provider secrets must not become another runtime environment deviation."""
    secret_fields = {
        "OBJECT_STORAGE_S3_ACCESS_KEY_ID",
        "OBJECT_STORAGE_S3_SECRET_ACCESS_KEY",
        "OBJECT_STORAGE_S3_SESSION_TOKEN",
    }
    assert secret_fields.isdisjoint(ObjectStorageSettings.model_fields)


@pytest.mark.asyncio
async def test_database_backend_never_queries_provider_registry(monkeypatch) -> None:
    """The backward-compatible database mode needs no external credentials."""
    resolve = getattr(storage_module, "resolve_document_storage_runtime_config", None)
    assert callable(resolve), "document storage must expose a DB-backed resolver"
    monkeypatch.setattr(storage_module.settings, "OBJECT_STORAGE_BACKEND", "database")
    session = ScalarSession(_provider())

    runtime = await resolve(session, "organization-one")

    assert runtime.storage_backend == "database"
    assert runtime.s3_configuration is None
    assert session.scalar_calls == 0


@pytest.mark.asyncio
async def test_s3_backend_builds_runtime_credentials_from_active_db_provider(
    monkeypatch,
) -> None:
    """The active organization provider is the sole runtime credential source."""
    resolve = getattr(storage_module, "resolve_document_storage_runtime_config", None)
    assert callable(resolve), "document storage must expose a DB-backed resolver"
    monkeypatch.setattr(storage_module.settings, "OBJECT_STORAGE_BACKEND", "s3")
    monkeypatch.setattr(
        storage_module.settings,
        "OBJECT_STORAGE_REQUEST_TIMEOUT_SECONDS",
        17.5,
    )
    session = ScalarSession(_provider())

    runtime = await resolve(session, "organization-one")

    assert runtime.storage_backend == "s3"
    configuration = runtime.s3_configuration
    assert configuration is not None
    assert configuration.bucket_name == "naruon-documents"
    assert configuration.region_name == "ap-northeast-2"
    assert configuration.credentials.access_key_id == "database-access-key"
    assert configuration.credentials.secret_access_key == "database-secret-key"
    assert configuration.credentials.session_token == "database-session-token"
    assert configuration.server_side_encryption == "aws:kms"
    assert configuration.request_timeout_seconds == 17.5
    assert session.scalar_calls == 1
    assert "object_storage_providers" in str(session.statement)


@pytest.mark.asyncio
async def test_s3_backend_fails_closed_without_org_or_active_provider(monkeypatch) -> None:
    """Missing scoped registry authority must not fall back to process secrets."""
    resolve = getattr(storage_module, "resolve_document_storage_runtime_config", None)
    assert callable(resolve), "document storage must expose a DB-backed resolver"
    monkeypatch.setattr(storage_module.settings, "OBJECT_STORAGE_BACKEND", "s3")

    with pytest.raises(storage_module.DocumentObjectStorageError, match="organization"):
        await resolve(ScalarSession(_provider()), None)

    session = ScalarSession(None)
    with pytest.raises(storage_module.DocumentObjectStorageError, match="configured"):
        await resolve(session, "organization-one")
    assert session.scalar_calls == 1
