"""Read-only, tenant-scoped registry surface until publisher trust is configured."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import AuthContext, get_auth_context, is_admin_role
from db.models import PluginRegistration
from db.session import get_db

router = APIRouter(prefix="/api/plugins", tags=["plugins"])


class PluginRegistrationSummary(BaseModel):
    registration_uid: str
    plugin_id: str
    plugin_version: str
    artifact_sha256: str
    enabled: bool


@router.get("", response_model=list[PluginRegistrationSummary])
async def list_plugin_registrations(
    auth_context: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
) -> list[PluginRegistrationSummary]:
    if (
        auth_context.session_verifier == "hmac"
        or not is_admin_role(auth_context.role)
        or not auth_context.organization_id
    ):
        raise HTTPException(status_code=403, detail="Plugin registry access denied")

    result = await db.execute(
        select(PluginRegistration)
        .where(
            PluginRegistration.organization_id == auth_context.organization_id,
            PluginRegistration.workspace_id == auth_context.workspace_id,
        )
        .order_by(PluginRegistration.plugin_id, PluginRegistration.plugin_version)
    )
    return [
        PluginRegistrationSummary(
            registration_uid=row.registration_uid,
            plugin_id=row.plugin_id,
            plugin_version=row.plugin_version,
            artifact_sha256=row.artifact_sha256,
            enabled=row.enabled,
        )
        for row in result.scalars().all()
    ]
