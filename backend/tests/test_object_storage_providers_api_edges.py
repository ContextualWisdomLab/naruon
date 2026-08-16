"""Branch-complete lifecycle tests for object-storage provider administration."""

from __future__ import annotations

import datetime
from types import SimpleNamespace

from fastapi import HTTPException
import pytest
from sqlalchemy.exc import IntegrityError

import api.object_storage_providers as provider_api
from db.object_storage_provider import ObjectStorageProvider
import services.document_object_storage as storage_module


class _Rows:
    """Expose one queued ORM result through the methods used by the API."""

    def __init__(self, rows=()) -> None:
        self.rows = list(rows)

    def scalars(self):
        return self

    def all(self):
        return list(self.rows)

    def first(self):
        return self.rows[0] if self.rows else None


class _Session:
    """Queue SQL results and inject flush or commit integrity failures."""

    def __init__(
        self,
        results=(),
        *,
        flush_error: bool = False,
        commit_error: bool = False,
    ) -> None:
        self.results = list(results)
        self.flush_error = flush_error
        self.commit_error = commit_error
        self.added: list[object] = []
        self.deleted: list[object] = []
        self.execute_count = 0
        self.flush_count = 0
        self.commit_count = 0
        self.rollback_count = 0
        self.refresh_count = 0

    async def execute(self, _statement):
        self.execute_count += 1
        return self.results.pop(0) if self.results else _Rows()

    def add(self, value: object) -> None:
        self.added.append(value)

    async def flush(self) -> None:
        self.flush_count += 1
        if self.flush_error:
            raise IntegrityError("insert", {}, RuntimeError("duplicate"))
        for value in self.added:
            if isinstance(value, ObjectStorageProvider):
                value.object_storage_provider_id = 21

    async def commit(self) -> None:
        self.commit_count += 1
        if self.commit_error:
            raise IntegrityError("commit", {}, RuntimeError("conflict"))

    async def rollback(self) -> None:
        self.rollback_count += 1

    async def refresh(self, _value: object) -> None:
        self.refresh_count += 1

    async def delete(self, value: object) -> None:
        self.deleted.append(value)


def _auth() -> SimpleNamespace:
    return SimpleNamespace(
        user_id="admin-one",
        role="organization_admin",
        organization_id="organization-one",
        workspace_id="workspace-one",
    )


def _provider(**overrides) -> ObjectStorageProvider:
    now = datetime.datetime.now(datetime.timezone.utc)
    values = {
        "object_storage_provider_id": 21,
        "user_id": "admin-one",
        "organization_id": "organization-one",
        "provider_name": "primary-s3",
        "provider_type": "s3",
        "bucket_name": "naruon-documents",
        "region_name": "us-east-1",
        "endpoint_url": None,
        "addressing_style": "virtual",
        "access_key_id": "access-key",
        "secret_access_key": "secret-key",
        "session_token": None,
        "server_side_encryption": "AES256",
        "kms_key_id": None,
        "expected_bucket_owner": None,
        "is_active": False,
        "created_at": now,
        "updated_at": now,
    }
    values.update(overrides)
    return ObjectStorageProvider(**values)


def _create_data(**overrides) -> provider_api.ObjectStorageProviderCreate:
    values = {
        "provider_name": "primary-s3",
        "bucket_name": "naruon-documents",
        "region_name": "us-east-1",
        "access_key_id": "access-key",
        "secret_access_key": "secret-key",
    }
    values.update(overrides)
    return provider_api.ObjectStorageProviderCreate(**values)


def test_redaction_helpers_cover_empty_and_short_optional_values() -> None:
    provider = _provider(
        access_key_id="",
        secret_access_key="",
        session_token=None,
        kms_key_id=None,
    )
    response = provider_api._provider_response(provider)
    assert response.access_key_fingerprint is None
    assert response.secret_access_key_configured is False
    assert response.session_token_configured is False
    assert response.kms_key_configured is False
    assert provider_api._stripped_optional(None) is None
    assert provider_api._stripped_optional("   ") is None
    assert provider_api._stripped_optional(" value ") == "value"
    with pytest.raises(HTTPException, match="provider_name is required"):
        provider_api._stripped_required("   ", "provider_name")


@pytest.mark.asyncio
async def test_admin_access_success_and_provider_list() -> None:
    auth_context = _auth()
    assert await provider_api.check_object_storage_admin_access(auth_context) is auth_context
    provider = _provider()
    session = _Session([_Rows([provider])])

    responses = await provider_api.list_object_storage_providers(
        db=session,
        auth_context=auth_context,
    )

    assert [item.object_storage_provider_id for item in responses] == [21]
    assert session.execute_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("failure_stage", ["flush", "commit"])
async def test_create_integrity_conflict_rolls_back(failure_stage: str) -> None:
    session = _Session(
        flush_error=failure_stage == "flush",
        commit_error=failure_stage == "commit",
    )

    with pytest.raises(HTTPException) as error:
        await provider_api.create_object_storage_provider(
            _create_data(),
            db=session,
            auth_context=_auth(),
        )

    assert error.value.status_code == 409
    assert session.rollback_count == 1


@pytest.mark.asyncio
async def test_update_rotates_all_supported_fields_and_activates_exclusively(monkeypatch) -> None:
    provider = _provider()
    session = _Session([_Rows([provider]), _Rows()])
    monkeypatch.setattr(
        storage_module.settings,
        "OBJECT_STORAGE_S3_ALLOWED_HOSTS",
        "objects.example.com",
    )

    response = await provider_api.update_object_storage_provider(
        21,
        provider_api.ObjectStorageProviderUpdate(
            provider_name=" replacement-s3 ",
            bucket_name="replacement-bucket",
            region_name="ap-northeast-2",
            endpoint_url="https://objects.example.com/",
            addressing_style="path",
            access_key_id="rotated-access",
            secret_access_key="rotated-secret",
            session_token=" rotated-token ",
            server_side_encryption="aws:kms",
            kms_key_id=" key-reference ",
            expected_bucket_owner="111122223333",
            is_active=True,
        ),
        db=session,
        auth_context=_auth(),
    )

    assert provider.provider_name == "replacement-s3"
    assert provider.endpoint_url == "https://objects.example.com/"
    assert provider.addressing_style == "path"
    assert provider.access_key_id == "rotated-access"
    assert provider.secret_access_key == "rotated-secret"
    assert provider.session_token == "rotated-token"
    assert provider.kms_key_id == "key-reference"
    assert response.is_active is True
    assert response.access_key_fingerprint == provider_api._access_key_fingerprint(
        "rotated-access"
    )
    assert session.execute_count == 2
    assert session.commit_count == 1
    assert session.refresh_count == 1


@pytest.mark.asyncio
async def test_update_can_clear_optional_values_without_rotating_required_secrets() -> None:
    provider = _provider(
        endpoint_url="https://objects.example.com",
        addressing_style="path",
        session_token="temporary",
        kms_key_id="key-reference",
    )
    session = _Session([_Rows([provider])])

    response = await provider_api.update_object_storage_provider(
        21,
        provider_api.ObjectStorageProviderUpdate(
            endpoint_url="",
            addressing_style="virtual",
            session_token="",
            kms_key_id="",
        ),
        db=session,
        auth_context=_auth(),
    )

    assert provider.endpoint_url is None
    assert provider.session_token is None
    assert provider.kms_key_id is None
    assert provider.secret_access_key == "secret-key"
    assert response.session_token_configured is False
    assert response.kms_key_configured is False


@pytest.mark.asyncio
async def test_update_invalid_configuration_rolls_back() -> None:
    provider = _provider()
    session = _Session([_Rows([provider])])

    with pytest.raises(HTTPException) as error:
        await provider_api.update_object_storage_provider(
            21,
            provider_api.ObjectStorageProviderUpdate(addressing_style="invalid"),
            db=session,
            auth_context=_auth(),
        )

    assert error.value.status_code == 422
    assert session.rollback_count == 1
    assert session.commit_count == 0


@pytest.mark.asyncio
async def test_update_missing_provider_and_commit_conflict() -> None:
    missing_session = _Session([_Rows()])
    with pytest.raises(HTTPException) as missing:
        await provider_api.update_object_storage_provider(
            21,
            provider_api.ObjectStorageProviderUpdate(is_active=False),
            db=missing_session,
            auth_context=_auth(),
        )
    assert missing.value.status_code == 404

    provider = _provider()
    conflict_session = _Session([_Rows([provider])], commit_error=True)
    with pytest.raises(HTTPException) as conflict:
        await provider_api.update_object_storage_provider(
            21,
            provider_api.ObjectStorageProviderUpdate(provider_name="renamed"),
            db=conflict_session,
            auth_context=_auth(),
        )
    assert conflict.value.status_code == 409
    assert conflict_session.rollback_count == 1


@pytest.mark.asyncio
async def test_delete_requires_inactive_provider_and_handles_retained_lineage() -> None:
    active = _provider(is_active=True)
    active_session = _Session([_Rows([active])])
    with pytest.raises(HTTPException) as active_error:
        await provider_api.delete_object_storage_provider(
            21,
            db=active_session,
            auth_context=_auth(),
        )
    assert active_error.value.status_code == 409
    assert active_session.deleted == []

    inactive = _provider(is_active=False)
    success_session = _Session([_Rows([inactive])])
    assert (
        await provider_api.delete_object_storage_provider(
            21,
            db=success_session,
            auth_context=_auth(),
        )
        is None
    )
    assert success_session.deleted == [inactive]
    assert success_session.commit_count == 1

    retained = _provider(is_active=False)
    retained_session = _Session([_Rows([retained])], commit_error=True)
    with pytest.raises(HTTPException) as retained_error:
        await provider_api.delete_object_storage_provider(
            21,
            db=retained_session,
            auth_context=_auth(),
        )
    assert retained_error.value.status_code == 409
    assert retained_session.rollback_count == 1
