"""Read-only, tenant-scoped registry surface until publisher trust is configured."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import AuthContext, get_auth_context, is_admin_role
from db.models import (
    PluginArtifact,
    PluginDefinition,
    PluginRegistration,
    PluginRelease,
)
from db.session import get_db

router = APIRouter(prefix="/api/plugins", tags=["plugins"])


class PluginRegistrationSummary(BaseModel):
    """Buyer-safe metadata for one tenant registration of one exact artifact."""

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
    """List this administrator's workspace registrations without loading plugins."""
    if (
        auth_context.session_verifier == "hmac"
        or not is_admin_role(auth_context.role)
        or not auth_context.organization_id
    ):
        raise HTTPException(status_code=403, detail="Plugin registry access denied")

    result = await db.execute(
        select(PluginRegistration, PluginArtifact, PluginRelease, PluginDefinition)
        .join(PluginRegistration.artifact)
        .join(PluginArtifact.release)
        .join(PluginRelease.definition)
        .where(
            PluginRegistration.organization_id == auth_context.organization_id,
            PluginRegistration.workspace_id == auth_context.workspace_id,
        )
        .order_by(PluginDefinition.plugin_id, PluginRelease.plugin_version)
    )
    return [
        PluginRegistrationSummary(
            registration_uid=registration.registration_uid,
            plugin_id=definition.plugin_id,
            plugin_version=release.plugin_version,
            artifact_sha256=artifact.artifact_sha256,
            enabled=registration.enabled,
        )
        for registration, artifact, release, definition in result.all()
    ]
