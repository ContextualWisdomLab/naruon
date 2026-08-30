"""Contracts for the encrypted organization object-storage provider API."""

from __future__ import annotations

import datetime
from types import SimpleNamespace

from fastapi import HTTPException
import pytest

import api.object_storage_providers as provider_api
from db.object_storage_provider import ObjectStorageProvider


class _ScalarRows:
    """Expose a deterministic ORM list through SQLAlchemy-like result methods."""

    def __init__(self, rows) -> None:
        self.rows = list(rows)

    def scalars(self):
        return self

    def all(self):
        return list(self.rows)

    def first(self):
        return self.rows[0] if self.rows else None


class _ProviderSession:
    """Track provider writes and audit rows without a live database."""

    def __init__(self, providers=None) -> None:
        self.providers = list(providers or [])
        self.added: list[object] = []
        self.deleted: list[object] = []
        self.commit_count = 0
        self.rollback_count = 0
        self.flush_count = 0
        self.refresh_count = 0
        self.execute_count = 0

    async def execute(self, _statement):
        self.execute_count += 1
        return _ScalarRows(self.providers)

    def add(self, value: object) -> None:
        self.added.append(value)
        if isinstance(value, ObjectStorageProvider) and value not in self.providers:
            self.providers.append(value)

    async def flush(self) -> None:
        self.flush_count += 1
        for index, provider in enumerate(self.providers, start=1):
            if provider.object_storage_provider_id is None:
                provider.object_storage_provider_id = index

    async def commit(self) -> None:
        self.commit_count += 1

    async def rollback(self) -> None:
        self.rollback_count += 1

    async def refresh(self, _value: object) -> None:
        self.refresh_count += 1

    async def delete(self, value: object) -> None:
        self.deleted.append(value)


def _auth(*, role: str = "organization_admin", organization_id="organization-one"):
    return SimpleNamespace(
        user_id="admin-one",
        role=role,
        organization_id=organization_id,
        workspace_id="workspace-one",
    )


def _provider(**overrides) -> ObjectStorageProvider:
    values = {
        "object_storage_provider_id": 7,
        "user_id": "admin-one",
        "organization_id": "organization-one",
        "provider_name": "primary-s3",
        "provider_type": "s3",
        "bucket_name": "naruon-documents",
        "region_name": "ap-northeast-2",
        "endpoint_url": None,
        "addressing_style": "virtual",
        "access_key_id": "AKIAEXAMPLE1234",
        "secret_access_key": "never-return-this-secret",
        "session_token": "never-return-this-token",
        "server_side_encryption": "aws:kms",
        "kms_key_id": "arn:aws:kms:ap-northeast-2:111122223333:key/example",
        "expected_bucket_owner": "111122223333",
        "is_active": True,
        "created_at": datetime.datetime.now(datetime.timezone.utc),
        "updated_at": datetime.datetime.now(datetime.timezone.utc),
    }
    values.update(overrides)
    return ObjectStorageProvider(**values)


def test_provider_response_redacts_all_credentials() -> None:
    response = provider_api._provider_response(_provider())
    serialized = response.model_dump()

    assert response.object_storage_provider_id == 7
    assert response.access_key_fingerprint is not None
    assert response.secret_access_key_configured is True
    assert response.session_token_configured is True
    assert response.kms_key_configured is True
    for forbidden in (
        "AKIAEXAMPLE1234",
        "never-return-this-secret",
        "never-return-this-token",
        "arn:aws:kms",
    ):
        assert forbidden not in str(serialized)


@pytest.mark.asyncio
async def test_admin_and_organization_scope_are_required() -> None:
    with pytest.raises(HTTPException) as forbidden:
        await provider_api.check_object_storage_admin_access(_auth(role="member"))
    assert forbidden.value.status_code == 403

    with pytest.raises(HTTPException) as missing_scope:
        await provider_api.create_object_storage_provider(
            provider_api.ObjectStorageProviderCreate(
                provider_name="primary-s3",
                bucket_name="naruon-documents",
                region_name="ap-northeast-2",
                access_key_id="access-key",
                secret_access_key="secret-key",
            ),
            db=_ProviderSession(),
            auth_context=_auth(organization_id=None),
        )
    assert missing_scope.value.status_code == 403


@pytest.mark.asyncio
async def test_create_provider_persists_encrypted_fields_but_returns_only_flags() -> None:
    session = _ProviderSession()
    response = await provider_api.create_object_storage_provider(
        provider_api.ObjectStorageProviderCreate(
            provider_name=" primary-s3 ",
            bucket_name="naruon-documents",
            region_name="ap-northeast-2",
            access_key_id="access-key",
            secret_access_key="secret-key",
            session_token="temporary-token",
            server_side_encryption="AES256",
            is_active=True,
        ),
        db=session,
        auth_context=_auth(),
    )

    provider = next(
        value for value in session.added if isinstance(value, ObjectStorageProvider)
    )
    assert provider.provider_name == "primary-s3"
    assert provider.organization_id == "organization-one"
    assert provider.access_key_id == "access-key"
    assert provider.secret_access_key == "secret-key"
    assert response.secret_access_key_configured is True
    assert response.session_token_configured is True
    assert "secret-key" not in str(response.model_dump())
    assert session.flush_count == 1
    assert session.commit_count == 1
    assert session.refresh_count == 1


@pytest.mark.asyncio
async def test_invalid_custom_endpoint_fails_before_database_write() -> None:
    session = _ProviderSession()
    with pytest.raises(HTTPException) as error:
        await provider_api.create_object_storage_provider(
            provider_api.ObjectStorageProviderCreate(
                provider_name="primary-s3",
                bucket_name="naruon-documents",
                region_name="ap-northeast-2",
                endpoint_url="http://127.0.0.1:9000",
                addressing_style="path",
                access_key_id="access-key",
                secret_access_key="secret-key",
            ),
            db=session,
            auth_context=_auth(),
        )

    assert error.value.status_code == 422
    assert session.added == []
    assert session.commit_count == 0
