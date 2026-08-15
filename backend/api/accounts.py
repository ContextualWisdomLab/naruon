from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_db
from api.auth import AuthContext, get_auth_context, is_system_admin_role
from api.tenant_config import (
    MAILBOX_MANAGE_FORBIDDEN,
    MAILBOX_VIEW_FORBIDDEN,
    ensure_mailbox_config_self_access,
    validate_mail_config_update,
)
from services.email_signature_service import (
    MAX_EMAIL_SIGNATURE_CHARS,
    get_email_signature_text,
    normalize_email_signature_text,
    set_email_signature_text,
)
from services.tenant_config_scope import (
    get_scoped_tenant_config,
    new_scoped_tenant_config,
)

router = APIRouter(prefix="/api/accounts", tags=["accounts"])

MAILBOX_ACCOUNT_SETTINGS_FORBIDDEN = (
    "Mailbox account settings require a scoped user session"
)


class TenantConfigUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    smtp_server: str | None = None
    smtp_port: int | None = None
    smtp_username: str | None = None
    smtp_password: str | None = None
    imap_server: str | None = None
    imap_port: int | None = None
    imap_username: str | None = None
    imap_password: str | None = None
    pop3_server: str | None = None
    pop3_port: int | None = None
    pop3_username: str | None = None
    pop3_password: str | None = None
    oauth_client_id: str | None = None
    oauth_client_secret: str | None = None
    oauth_redirect_uri: str | None = None
    email_signature_text: str | None = Field(
        default=None,
        max_length=MAX_EMAIL_SIGNATURE_CHARS,
    )

    @field_validator("email_signature_text")
    @classmethod
    def validate_email_signature_text(cls, value: str | None) -> str | None:
        """Reject unsafe signature controls and canonicalize line endings."""
        return normalize_email_signature_text(value)


class TenantConfigResponse(BaseModel):
    user_id: str
    smtp_server: str | None
    smtp_port: int | None
    smtp_username: str | None
    has_smtp_password: bool
    imap_server: str | None
    imap_port: int | None
    imap_username: str | None
    has_imap_password: bool
    pop3_server: str | None
    pop3_port: int | None
    pop3_username: str | None
    has_pop3_password: bool
    oauth_client_id: str | None
    oauth_redirect_uri: str | None
    has_oauth_client_secret: bool
    email_signature_text: str | None


def _tenant_config_response(
    config,
    *,
    email_signature_text: str | None = None,
) -> TenantConfigResponse:
    return TenantConfigResponse(
        user_id=config.user_id,
        smtp_server=config.smtp_server,
        smtp_port=config.smtp_port,
        smtp_username=config.smtp_username,
        has_smtp_password=bool(config.smtp_password),
        imap_server=config.imap_server,
        imap_port=config.imap_port,
        imap_username=config.imap_username,
        has_imap_password=bool(config.imap_password),
        pop3_server=config.pop3_server,
        pop3_port=config.pop3_port,
        pop3_username=config.pop3_username,
        has_pop3_password=bool(config.pop3_password),
        oauth_client_id=config.oauth_client_id,
        oauth_redirect_uri=config.oauth_redirect_uri,
        has_oauth_client_secret=bool(config.oauth_client_secret),
        email_signature_text=email_signature_text,
    )


def _empty_tenant_config_response(
    user_id: str,
    *,
    email_signature_text: str | None = None,
) -> TenantConfigResponse:
    config = new_scoped_tenant_config(user_id=user_id, organization_id=None)
    return _tenant_config_response(
        config,
        email_signature_text=email_signature_text,
    )


def _ensure_mailbox_account_owner_session(
    auth_ctx: AuthContext, forbidden_detail: str
) -> None:
    if is_system_admin_role(auth_ctx.role):
        raise HTTPException(status_code=403, detail=MAILBOX_ACCOUNT_SETTINGS_FORBIDDEN)
    ensure_mailbox_config_self_access(auth_ctx.user_id, auth_ctx, forbidden_detail)


@router.get("/config", response_model=TenantConfigResponse)
async def get_tenant_config(
    db: AsyncSession = Depends(get_db),
    auth_ctx: AuthContext = Depends(get_auth_context),
):
    _ensure_mailbox_account_owner_session(auth_ctx, MAILBOX_VIEW_FORBIDDEN)
    config = await get_scoped_tenant_config(
        db,
        auth_ctx.user_id,
        auth_ctx.organization_id,
    )
    email_signature_text = await get_email_signature_text(
        db,
        user_id=auth_ctx.user_id,
        organization_id=auth_ctx.organization_id,
    )
    if not config:
        return _empty_tenant_config_response(
            auth_ctx.user_id,
            email_signature_text=email_signature_text,
        )

    return _tenant_config_response(
        config,
        email_signature_text=email_signature_text,
    )


@router.put("/config", response_model=TenantConfigResponse)
async def update_tenant_config(
    update_data: TenantConfigUpdate,
    db: AsyncSession = Depends(get_db),
    auth_ctx: AuthContext = Depends(get_auth_context),
):
    _ensure_mailbox_account_owner_session(auth_ctx, MAILBOX_MANAGE_FORBIDDEN)
    config = await get_scoped_tenant_config(
        db,
        auth_ctx.user_id,
        auth_ctx.organization_id,
    )
    if not config:
        config = new_scoped_tenant_config(
            user_id=auth_ctx.user_id,
            organization_id=auth_ctx.organization_id,
        )
        db.add(config)

    from api.tenant_config import SECRET_FIELDS

    update_dict = update_data.model_dump(exclude_unset=True)
    signature_marker = object()
    signature_update = update_dict.pop("email_signature_text", signature_marker)
    validate_mail_config_update(update_dict, config)
    for key, value in update_dict.items():
        if key in SECRET_FIELDS and value == "********":
            continue
        setattr(config, key, value)

    if signature_update is not signature_marker:
        email_signature_text = await set_email_signature_text(
            db,
            user_id=auth_ctx.user_id,
            organization_id=auth_ctx.organization_id,
            signature_text=signature_update,
        )
    else:
        email_signature_text = await get_email_signature_text(
            db,
            user_id=auth_ctx.user_id,
            organization_id=auth_ctx.organization_id,
        )

    await db.commit()
    await db.refresh(config)

    return _tenant_config_response(
        config,
        email_signature_text=email_signature_text,
    )
