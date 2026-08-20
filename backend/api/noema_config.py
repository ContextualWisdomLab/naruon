"""Signed-session settings for the per-user Noema gateway credential."""

from __future__ import annotations

import hashlib

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy.exc import StatementError
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import AuthContext, get_auth_context
from core.runtime_secrets import EncryptionConfigurationError
from db.models import AuditLog, SecurityAuditEvent, TenantConfig
from db.session import get_db
from services.llm_provider_urls import validate_llm_provider_base_url_async
from services.orchestrator_gateway import validate_orchestrator_gateway_url
from services.tenant_config_scope import (
    get_scoped_tenant_config,
    new_scoped_tenant_config,
)

router = APIRouter(prefix="/api/noema-gateway", tags=["noema-gateway"])


class NoemaGatewayUpdate(BaseModel):
    """Optional values for the signed-session user's Noema gateway."""

    model_config = ConfigDict(extra="forbid")

    base_url: str | None = None
    token: str | None = None


class NoemaGatewayResponse(BaseModel):
    """Safe gateway state that never returns the Fernet-protected token."""

    base_url: str | None = None
    configured: bool = False
    has_token: bool = False


def _resource_uid(auth_context: AuthContext) -> str:
    """Return a stable, non-secret audit identifier for the scoped setting."""
    scope = f"{auth_context.organization_id or ''}:{auth_context.user_id}"
    digest = hashlib.sha256(scope.encode("utf-8")).hexdigest()[:16]
    return f"noema_gateway:{digest}"


async def _validated_base_url(value: str) -> str:
    """Validate the HTTPS /v1 shape and the configured global-host policy."""
    try:
        shaped_url = validate_orchestrator_gateway_url(value)
        normalized_url = await validate_llm_provider_base_url_async(shaped_url)
        if not normalized_url:
            raise ValueError("gateway host is not allowlisted")
        return validate_orchestrator_gateway_url(normalized_url)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail="Noema gateway base URL is not allowed",
        ) from exc


def _clean_token(value: str | None) -> str | None:
    """Normalize a submitted token without recording or returning its value."""
    if value is None:
        return None
    token = value.strip()
    if not token or token == "*" * 8:
        return None
    if any(ord(character) < 32 or ord(character) == 127 for character in token):
        raise HTTPException(status_code=422, detail="Noema gateway token is invalid")
    return token


def _response(config: TenantConfig | None) -> NoemaGatewayResponse:
    """Build a response containing only non-secret gateway state."""
    if config is None:
        return NoemaGatewayResponse()
    has_token = bool(config.noema_orchestrator_token)
    return NoemaGatewayResponse(
        base_url=config.noema_orchestrator_base_url,
        configured=bool(config.noema_orchestrator_base_url and has_token),
        has_token=has_token,
    )


def _is_encryption_configuration_error(error: BaseException) -> bool:
    """Recognize direct or SQLAlchemy-wrapped encryption configuration errors."""
    if isinstance(error, EncryptionConfigurationError):
        return True
    return isinstance(error, StatementError) and isinstance(
        error.orig, EncryptionConfigurationError
    )


@router.get("", response_model=NoemaGatewayResponse)
async def get_noema_gateway(
    db: AsyncSession = Depends(get_db),
    auth_context: AuthContext = Depends(get_auth_context),
) -> NoemaGatewayResponse:
    """Return the signed-session user's scoped gateway readiness state."""
    try:
        config = await get_scoped_tenant_config(
            db, auth_context.user_id, auth_context.organization_id
        )
        return _response(config)
    except Exception as exc:
        if not _is_encryption_configuration_error(exc):
            raise
        raise HTTPException(
            status_code=503,
            detail="Server encryption key is not configured. Contact your workspace administrator.",
        ) from exc


@router.put("", response_model=NoemaGatewayResponse)
async def update_noema_gateway(
    update: NoemaGatewayUpdate,
    db: AsyncSession = Depends(get_db),
    auth_context: AuthContext = Depends(get_auth_context),
) -> NoemaGatewayResponse:
    """Persist the current user's gateway settings with an auditable change."""
    updates = update.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=422, detail="No gateway settings supplied")

    try:
        config = await get_scoped_tenant_config(
            db, auth_context.user_id, auth_context.organization_id
        )
        if config is None:
            config = new_scoped_tenant_config(
                user_id=auth_context.user_id,
                organization_id=auth_context.organization_id,
            )
            db.add(config)

        if "token" in updates:
            token = _clean_token(updates["token"])
            if token is not None:
                config.noema_orchestrator_token = token
            elif not config.noema_orchestrator_token:
                raise HTTPException(
                    status_code=422, detail="Noema gateway token is required"
                )

        if "base_url" in updates:
            config.noema_orchestrator_base_url = await _validated_base_url(
                updates["base_url"] or ""
            )

        if not config.noema_orchestrator_base_url or not config.noema_orchestrator_token:
            raise HTTPException(
                status_code=422,
                detail="Noema gateway base URL and token are required",
            )

        resource_uid = _resource_uid(auth_context)
        db.add(
            AuditLog(
                user_id=auth_context.user_id,
                action="update",
                resource_type="noema_gateway",
                resource_id=resource_uid,
                details="Updated Noema gateway settings",
            )
        )
        db.add(
            SecurityAuditEvent(
                actor_user_id=auth_context.user_id,
                actor_role=auth_context.role,
                organization_id=auth_context.organization_id,
                workspace_id=auth_context.workspace_id,
                event_action="update",
                resource_type="noema_gateway",
                resource_uid=resource_uid,
                evidence_source="api.noema_config",
                detail_text="Updated Noema gateway settings",
            )
        )
        await db.commit()
        return _response(config)
    except Exception as exc:
        if not _is_encryption_configuration_error(exc):
            raise
        raise HTTPException(
            status_code=503,
            detail="Server encryption key is not configured. Contact your workspace administrator.",
        ) from exc
    return _response(config)
