"""Private tenant archive routes (slice 1).

Both endpoints sit behind the default signed-session dependency registered at
the router level and scope every operation to the authenticated session's
owner + organization. The bundle body itself is never trusted as identity
material: imports re-scope every record to the signed session's destination
scope, so a stolen or forged bundle cannot write into another tenant.
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import AuthContext, get_auth_context
from db.session import get_db
from services.tenant_archive_service import (
    TenantArchiveBundleInvalid,
    TenantArchiveError,
    TenantArchiveScopeMismatch,
    TenantArchiveSchemaUnsupported,
    export_tenant_archive,
    import_tenant_archive,
)

router = APIRouter(prefix="/api/tenant-archive", tags=["tenant-archive"])

_ERROR_STATUS_BY_EXCEPTION_TYPE: tuple[tuple[type[TenantArchiveError], int], ...] = (
    (TenantArchiveScopeMismatch, 403),
    (TenantArchiveSchemaUnsupported, 422),
    (TenantArchiveBundleInvalid, 422),
)


class TenantArchiveImportRequest(BaseModel):
    """Request envelope carrying the archive bundle to import."""

    model_config = ConfigDict(extra="forbid")

    bundle: dict[str, Any]


def _organization_scope(auth_context: AuthContext) -> str:
    """Require a non-null organization scope from the signed session."""
    organization_id = auth_context.organization_id
    if not organization_id:
        raise HTTPException(
            status_code=403,
            detail={
                "error_code": "archive_scope_mismatch",
                "message": "Signed session organization scope is required",
            },
        )
    return organization_id


def _deterministic_archive_http_error(
    exc: TenantArchiveError,
) -> HTTPException:
    """Map typed archive failures to fixed statuses and error codes."""
    status_code = next(
        (
            status
            for exception_type, status in _ERROR_STATUS_BY_EXCEPTION_TYPE
            if isinstance(exc, exception_type)
        ),
        400,
    )
    return HTTPException(
        status_code=status_code,
        detail={"error_code": exc.error_code, "message": exc.public_message},
    )


@router.post("/export")
async def export_archive_bundle(
    db: AsyncSession = Depends(get_db),
    auth_context: AuthContext = Depends(get_auth_context),
) -> dict[str, Any]:
    """Export the signed-session owner's scoped archive bundle."""
    return await export_tenant_archive(
        db,
        owner_user_id=auth_context.user_id,
        organization_id=_organization_scope(auth_context),
    )


@router.post("/import")
async def import_archive_bundle(
    request: TenantArchiveImportRequest,
    db: AsyncSession = Depends(get_db),
    auth_context: AuthContext = Depends(get_auth_context),
) -> dict[str, Any]:
    """Import an archive bundle into the signed-session owner's scope."""
    try:
        return await import_tenant_archive(
            db,
            bundle=request.bundle,
            owner_user_id=auth_context.user_id,
            organization_id=_organization_scope(auth_context),
        )
    except TenantArchiveError as exc:
        raise _deterministic_archive_http_error(exc) from None
