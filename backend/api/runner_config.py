import datetime
import hashlib
import secrets

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import (
    AuthContext,
    ensure_organization_access,
    get_auth_context,
    is_admin_role,
    is_tenant_admin_role,
)
from api.runner_ws import manager as runner_connection_manager
from core.config import settings
from db.models import WorkspaceRunnerConfig
from db.session import get_db

router = APIRouter(prefix="/api/runner-config", tags=["runner-config"])


class RunnerConfigResponse(BaseModel):
    workspace_id: str
    configured: bool
    fingerprint: str | None = None
    updated_at: datetime.datetime | None = None
    connector_manifest: dict[str, object]

    model_config = ConfigDict(from_attributes=True)


class RunnerRotateResponse(BaseModel):
    workspace_id: str
    configured: bool
    fingerprint: str | None = None
    updated_at: datetime.datetime | None = None
    connector_manifest: dict[str, object]


def _connector_manifest() -> dict[str, object]:
    return {
        "role": "self-hosted_connector",
        "network_mode": "outbound_only",
        "control_plane_domain": settings.CONTROL_PLANE_DOMAIN,
        "local_protocols": ["imap", "pop3", "smtp", "caldav", "carddav", "webdav"],
        "prohibited_roles": ["smtp_server", "imap_server", "mx_host"],
        "runner_usage": "ci_smoke_only",
    }


def _check_org_admin(auth_context: AuthContext = Depends(get_auth_context)) -> AuthContext:
    if not is_admin_role(auth_context.role):
        raise HTTPException(status_code=403, detail="Organization admin access required")
    if is_tenant_admin_role(auth_context.role) and not auth_context.organization_id:
        raise HTTPException(status_code=403, detail="Organization scope is required")
    return auth_context


def _get_target_organization_id(auth_context: AuthContext) -> str:
    if not auth_context.organization_id:
        raise HTTPException(status_code=403, detail="Organization scope is required")
    return auth_context.organization_id


def _fingerprint(token: str | None) -> str | None:
    if not token:
        return None
    return f"***{hashlib.sha256(token.encode('utf-8')).hexdigest()[:8]}"


@router.get("", response_model=RunnerConfigResponse)
async def get_runner_config(
    db: AsyncSession = Depends(get_db),
    auth_context: AuthContext = Depends(_check_org_admin),
):
    organization_id = _get_target_organization_id(auth_context)
    workspace_id = f"workspace-{organization_id}"
    result = await db.execute(
        select(WorkspaceRunnerConfig).where(WorkspaceRunnerConfig.organization_id == organization_id)
    )
    config = result.scalar_one_or_none()

    if not config:
        return RunnerConfigResponse(
            workspace_id=workspace_id,
            configured=False,
            fingerprint=None,
            updated_at=None,
            connector_manifest=_connector_manifest(),
        )

    try:
        ensure_organization_access(auth_context, config.organization_id)
        return RunnerConfigResponse(
            workspace_id=config.workspace_id,
            configured=bool(config.registration_token),
            fingerprint=_fingerprint(config.registration_token),
            updated_at=config.updated_at,
            connector_manifest=_connector_manifest(),
        )
    except Exception as exc:
        if "ENCRYPTION_KEY is required" not in str(exc):
            raise
        raise HTTPException(
            status_code=503,
            detail="Server encryption key is not configured. Contact your workspace administrator.",
        ) from exc


@router.post("/rotate", response_model=RunnerRotateResponse)
async def rotate_runner_token(
    db: AsyncSession = Depends(get_db),
    auth_context: AuthContext = Depends(_check_org_admin),
):
    organization_id = _get_target_organization_id(auth_context)
    workspace_id = f"workspace-{organization_id}"
    result = await db.execute(
        select(WorkspaceRunnerConfig).where(WorkspaceRunnerConfig.organization_id == organization_id)
    )
    config = result.scalar_one_or_none()

    token = f"nrn_{secrets.token_urlsafe(24)}"
    if not config:
        config = WorkspaceRunnerConfig(
            organization_id=organization_id,
            workspace_id=workspace_id,
            registration_token=token,
        )
        db.add(config)
    else:
        ensure_organization_access(auth_context, config.organization_id)
        config.registration_token = token

    try:
        await db.commit()
        await db.refresh(config)
    except Exception as exc:
        if "ENCRYPTION_KEY is required" not in str(exc):
            raise
        raise HTTPException(
            status_code=503,
            detail="Server encryption key is not configured. Contact your workspace administrator.",
        ) from exc
    await runner_connection_manager.revoke_organization_connections(organization_id)
    return RunnerRotateResponse(
        workspace_id=config.workspace_id,
        configured=True,
        fingerprint=_fingerprint(token),
        updated_at=config.updated_at,
        connector_manifest=_connector_manifest(),
    )
