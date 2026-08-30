"""Organization-admin API for encrypted S3-compatible provider configuration."""

from __future__ import annotations

import datetime
import hashlib

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import AuthContext, get_auth_context, is_admin_role
from db.models import AuditLog, SecurityAuditEvent
from db.object_storage_provider import ObjectStorageProvider
from db.session import get_db
from services.document_object_storage import _configuration_from_provider


router = APIRouter(
    prefix="/api/object-storage-providers",
    tags=["object-storage-providers"],
)


class ObjectStorageProviderCreate(BaseModel):
    """Create one organization-scoped S3-compatible provider."""

    provider_name: str = Field(min_length=1, max_length=120)
    bucket_name: str = Field(min_length=3, max_length=63)
    region_name: str = Field(min_length=1, max_length=63)
    endpoint_url: str | None = None
    addressing_style: str = "virtual"
    access_key_id: str = Field(min_length=1, max_length=512)
    secret_access_key: str = Field(min_length=1, max_length=4096)
    session_token: str | None = Field(default=None, max_length=8192)
    server_side_encryption: str = "AES256"
    kms_key_id: str | None = Field(default=None, max_length=2048)
    expected_bucket_owner: str | None = Field(default=None, max_length=12)
    is_active: bool = False

    model_config = ConfigDict(extra="forbid")


class ObjectStorageProviderUpdate(BaseModel):
    """Rotate credentials/write policy without moving retained object authority.

    Bucket, region, endpoint, addressing style, and expected bucket owner define
    the locator/signing authority retained by object rows. Moving any of those
    values in-place could make already persisted objects unreadable or
    undeletable. Administrators must create and activate a new provider for a
    different storage location; this update contract is therefore limited to
    metadata, credentials, write-encryption policy, and activation state.
    """

    provider_name: str | None = Field(default=None, min_length=1, max_length=120)
    access_key_id: str | None = Field(default=None, min_length=1, max_length=512)
    secret_access_key: str | None = Field(default=None, min_length=1, max_length=4096)
    session_token: str | None = Field(default=None, max_length=8192)
    server_side_encryption: str | None = None
    kms_key_id: str | None = Field(default=None, max_length=2048)
    is_active: bool | None = None

    model_config = ConfigDict(extra="forbid")


class ObjectStorageProviderResponse(BaseModel):
    """Redacted provider metadata safe for organization administration UI."""

    object_storage_provider_id: int
    provider_name: str
    provider_type: str
    bucket_name: str
    region_name: str
    endpoint_url: str | None
    addressing_style: str
    server_side_encryption: str
    expected_bucket_owner: str | None
    is_active: bool
    access_key_fingerprint: str | None
    secret_access_key_configured: bool
    session_token_configured: bool
    kms_key_configured: bool
    updated_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


def _stripped_required(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise HTTPException(status_code=422, detail=f"{field_name} is required")
    return normalized


def _stripped_optional(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _access_key_fingerprint(access_key_id: str | None) -> str | None:
    if not access_key_id:
        return None
    digest = hashlib.sha256(access_key_id.encode("utf-8")).hexdigest()
    return f"sha256:{digest[:12]}"


def _provider_response(
    provider: ObjectStorageProvider,
) -> ObjectStorageProviderResponse:
    return ObjectStorageProviderResponse(
        object_storage_provider_id=provider.object_storage_provider_id,
        provider_name=provider.provider_name,
        provider_type=provider.provider_type,
        bucket_name=provider.bucket_name,
        region_name=provider.region_name,
        endpoint_url=provider.endpoint_url,
        addressing_style=provider.addressing_style,
        server_side_encryption=provider.server_side_encryption,
        expected_bucket_owner=provider.expected_bucket_owner,
        is_active=provider.is_active,
        access_key_fingerprint=_access_key_fingerprint(provider.access_key_id),
        secret_access_key_configured=bool(provider.secret_access_key),
        session_token_configured=bool(provider.session_token),
        kms_key_configured=bool(provider.kms_key_id),
        updated_at=provider.updated_at,
    )


async def check_object_storage_admin_access(
    auth_context: AuthContext = Depends(get_auth_context),
) -> AuthContext:
    """Require an administrative signed-session role for provider management."""
    if not is_admin_role(auth_context.role):
        raise HTTPException(
            status_code=403,
            detail="Organization admin access required",
        )
    return auth_context


def _required_organization(auth_context: AuthContext) -> str:
    if not auth_context.organization_id:
        raise HTTPException(status_code=403, detail="Organization scope required")
    return auth_context.organization_id


def _provider_scope_filter(auth_context: AuthContext):
    return ObjectStorageProvider.organization_id == _required_organization(auth_context)


def _provider_resource_uid(auth_context: AuthContext, provider_id: int) -> str:
    scope = auth_context.organization_id or auth_context.user_id
    digest = hashlib.sha256(f"{scope}:{provider_id}".encode("utf-8")).hexdigest()
    return f"object_storage_provider:{digest[:16]}"


def _security_audit_event(
    auth_context: AuthContext,
    *,
    event_action: str,
    provider_id: int,
) -> SecurityAuditEvent:
    return SecurityAuditEvent(
        actor_user_id=auth_context.user_id,
        actor_role=auth_context.role,
        organization_id=auth_context.organization_id,
        workspace_id=auth_context.workspace_id,
        event_action=event_action,
        resource_type="object_storage_provider",
        resource_uid=_provider_resource_uid(auth_context, provider_id),
        evidence_source="api.object_storage_providers",
        detail_text=f"{event_action.capitalize()} object-storage provider configuration",
    )


def _validate_provider(provider: ObjectStorageProvider) -> None:
    try:
        _configuration_from_provider(provider)
    except (AttributeError, TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=422,
            detail="Object-storage provider configuration is invalid",
        ) from exc


async def _deactivate_other_providers(
    db: AsyncSession,
    *,
    organization_id: str,
    provider_id: int | None = None,
) -> None:
    statement = update(ObjectStorageProvider).where(
        ObjectStorageProvider.organization_id == organization_id,
        ObjectStorageProvider.is_active.is_(True),
    )
    if provider_id is not None:
        statement = statement.where(
            ObjectStorageProvider.object_storage_provider_id != provider_id
        )
    await db.execute(statement.values(is_active=False))


@router.get("", response_model=list[ObjectStorageProviderResponse])
async def list_object_storage_providers(
    db: AsyncSession = Depends(get_db),
    auth_context: AuthContext = Depends(check_object_storage_admin_access),
) -> list[ObjectStorageProviderResponse]:
    """List redacted providers in the signed organization scope."""
    result = await db.execute(
        select(ObjectStorageProvider)
        .where(_provider_scope_filter(auth_context))
        .order_by(ObjectStorageProvider.provider_name)
    )
    return [_provider_response(provider) for provider in result.scalars().all()]


@router.post("", response_model=ObjectStorageProviderResponse)
async def create_object_storage_provider(
    data: ObjectStorageProviderCreate,
    db: AsyncSession = Depends(get_db),
    auth_context: AuthContext = Depends(check_object_storage_admin_access),
) -> ObjectStorageProviderResponse:
    """Create and validate an encrypted organization-owned provider row."""
    organization_id = _required_organization(auth_context)
    now = datetime.datetime.now(datetime.timezone.utc)
    provider = ObjectStorageProvider(
        user_id=auth_context.user_id,
        organization_id=organization_id,
        provider_name=_stripped_required(data.provider_name, "provider_name"),
        provider_type="s3",
        bucket_name=_stripped_required(data.bucket_name, "bucket_name"),
        region_name=_stripped_required(data.region_name, "region_name").lower(),
        endpoint_url=_stripped_optional(data.endpoint_url),
        addressing_style=_stripped_required(
            data.addressing_style,
            "addressing_style",
        ).lower(),
        access_key_id=_stripped_required(data.access_key_id, "access_key_id"),
        secret_access_key=_stripped_required(
            data.secret_access_key,
            "secret_access_key",
        ),
        session_token=_stripped_optional(data.session_token),
        server_side_encryption=_stripped_required(
            data.server_side_encryption,
            "server_side_encryption",
        ),
        kms_key_id=_stripped_optional(data.kms_key_id),
        expected_bucket_owner=_stripped_optional(data.expected_bucket_owner),
        is_active=data.is_active,
        created_at=now,
        updated_at=now,
    )
    _validate_provider(provider)
    if provider.is_active:
        await _deactivate_other_providers(
            db,
            organization_id=organization_id,
        )
    db.add(provider)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Object-storage provider name already exists",
        ) from exc

    db.add(
        AuditLog(
            user_id=auth_context.user_id,
            action="create",
            resource_type="object_storage_provider",
            resource_id=str(provider.object_storage_provider_id),
            details="Created object-storage provider configuration",
        )
    )
    db.add(
        _security_audit_event(
            auth_context,
            event_action="create",
            provider_id=provider.object_storage_provider_id,
        )
    )
    try:
        await db.commit()
        await db.refresh(provider)
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Object-storage provider name already exists",
        ) from exc
    return _provider_response(provider)


async def _scoped_provider(
    db: AsyncSession,
    auth_context: AuthContext,
    provider_id: int,
) -> ObjectStorageProvider:
    result = await db.execute(
        select(ObjectStorageProvider).where(
            ObjectStorageProvider.object_storage_provider_id == provider_id,
            _provider_scope_filter(auth_context),
        )
    )
    provider = result.scalars().first()
    if provider is None:
        raise HTTPException(status_code=404, detail="Object-storage provider not found")
    return provider


@router.put("/{provider_id}", response_model=ObjectStorageProviderResponse)
async def update_object_storage_provider(
    provider_id: int,
    data: ObjectStorageProviderUpdate,
    db: AsyncSession = Depends(get_db),
    auth_context: AuthContext = Depends(check_object_storage_admin_access),
) -> ObjectStorageProviderResponse:
    """Rotate credentials/write policy without changing retained object location."""
    provider = await _scoped_provider(db, auth_context, provider_id)
    fields = data.model_fields_set
    text_updates = {
        "provider_name": data.provider_name,
        "access_key_id": data.access_key_id,
        "secret_access_key": data.secret_access_key,
        "server_side_encryption": data.server_side_encryption,
    }
    for field_name, value in text_updates.items():
        if field_name in fields and value is not None:
            setattr(provider, field_name, _stripped_required(value, field_name))
    for field_name, value in {
        "session_token": data.session_token,
        "kms_key_id": data.kms_key_id,
    }.items():
        if field_name in fields:
            setattr(provider, field_name, _stripped_optional(value))
    if "is_active" in fields and data.is_active is not None:
        provider.is_active = data.is_active
    provider.updated_at = datetime.datetime.now(datetime.timezone.utc)
    try:
        _validate_provider(provider)
    except HTTPException:
        await db.rollback()
        raise

    if provider.is_active:
        await _deactivate_other_providers(
            db,
            organization_id=provider.organization_id,
            provider_id=provider.object_storage_provider_id,
        )
    db.add(
        AuditLog(
            user_id=auth_context.user_id,
            action="update",
            resource_type="object_storage_provider",
            resource_id=str(provider.object_storage_provider_id),
            details="Updated object-storage provider configuration",
        )
    )
    db.add(
        _security_audit_event(
            auth_context,
            event_action="update",
            provider_id=provider.object_storage_provider_id,
        )
    )
    try:
        await db.commit()
        await db.refresh(provider)
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Object-storage provider update conflicts with retained metadata",
        ) from exc
    return _provider_response(provider)


@router.delete("/{provider_id}", status_code=204)
async def delete_object_storage_provider(
    provider_id: int,
    db: AsyncSession = Depends(get_db),
    auth_context: AuthContext = Depends(check_object_storage_admin_access),
) -> None:
    """Delete an inactive unreferenced provider while retaining object lineage."""
    provider = await _scoped_provider(db, auth_context, provider_id)
    if provider.is_active:
        raise HTTPException(
            status_code=409,
            detail="Deactivate the object-storage provider before deletion",
        )
    await db.delete(provider)
    db.add(
        AuditLog(
            user_id=auth_context.user_id,
            action="delete",
            resource_type="object_storage_provider",
            resource_id=str(provider.object_storage_provider_id),
            details="Deleted object-storage provider configuration",
        )
    )
    db.add(
        _security_audit_event(
            auth_context,
            event_action="delete",
            provider_id=provider.object_storage_provider_id,
        )
    )
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Object-storage provider is retained by stored documents",
        ) from exc
