import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, ValidationInfo, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import (
    AuthContext,
    get_auth_context,
    get_current_user_role,
    is_admin_role,
)
from db.email_writing_orchestrator_config import EmailWritingOrchestratorConfig
from db.models import TenantConfig
from db.session import get_db
from services.access_policy import (
    AccessRequest,
    PolicyRoleName,
    ResourcePolicy,
    evaluate_access,
)
from services.email_client import (
    validate_imap_destination,
    validate_imap_port,
    validate_pop3_destination,
    validate_pop3_port,
    validate_smtp_destination,
    validate_smtp_host,
    validate_smtp_port,
)
from services.llm_provider_urls import (
    validate_llm_provider_base_url_details_async,
)
from services.tenant_config_scope import (
    get_scoped_email_writing_orchestrator_config,
    get_scoped_tenant_config,
    new_scoped_email_writing_orchestrator_config,
    new_scoped_tenant_config,
)

router = APIRouter(prefix="/api/config")
logger = logging.getLogger(__name__)


@router.get("/global")
async def get_global_config(
    role: str = Depends(get_current_user_role),
):
    if not is_admin_role(role):
        raise HTTPException(status_code=403, detail="Not enough privileges")
    return {"status": "ok", "global_settings": {}}


class TenantConfigCreate(BaseModel):
    user_id: str
    smtp_server: Optional[str] = None
    smtp_port: Optional[int] = None
    smtp_username: Optional[str] = None
    smtp_password: Optional[str] = None
    imap_server: Optional[str] = None
    imap_port: Optional[int] = None
    imap_username: Optional[str] = None
    imap_password: Optional[str] = None
    pop3_server: Optional[str] = None
    pop3_port: Optional[int] = None
    pop3_username: Optional[str] = None
    pop3_password: Optional[str] = None
    oauth_client_id: Optional[str] = None
    oauth_client_secret: Optional[str] = None
    oauth_redirect_uri: Optional[str] = None
    openai_api_key: Optional[str] = None
    google_client_id: Optional[str] = None
    google_client_secret: Optional[str] = None


class TenantConfigResponse(BaseModel):
    user_id: str
    smtp_server: Optional[str] = None
    smtp_port: Optional[int] = None
    smtp_username: Optional[str] = None
    smtp_password: Optional[str] = None
    imap_server: Optional[str] = None
    imap_port: Optional[int] = None
    imap_username: Optional[str] = None
    imap_password: Optional[str] = None
    pop3_server: Optional[str] = None
    pop3_port: Optional[int] = None
    pop3_username: Optional[str] = None
    pop3_password: Optional[str] = None
    oauth_client_id: Optional[str] = None
    oauth_client_secret: Optional[str] = None
    oauth_redirect_uri: Optional[str] = None
    openai_api_key: Optional[str] = None
    google_client_id: Optional[str] = None
    google_client_secret: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class EmailWritingOrchestratorConfigUpdate(BaseModel):
    """Owner-scoped update for the email-writing orchestration connection."""

    orchestrator_enabled: bool | None = None
    orchestrator_base_url: str | None = None
    model_profile_id: str | None = None
    inference_credential: str | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator(
        "orchestrator_base_url",
        "model_profile_id",
        "inference_credential",
        mode="before",
    )
    @classmethod
    def normalize_optional_text(
        cls, value: object, info: ValidationInfo
    ) -> object:
        """Trim bounded text fields without coercing non-string values."""
        if value is None or not isinstance(value, str):
            return value
        normalized = value.strip()
        limits = {
            "orchestrator_base_url": 2048,
            "model_profile_id": 255,
            "inference_credential": 8192,
        }
        if len(normalized) > limits[info.field_name]:
            raise ValueError("configuration value is too long")
        if any(
            ord(character) < 32 or ord(character) == 127
            for character in normalized
        ):
            raise ValueError("configuration value contains control characters")
        return normalized or None


class EmailWritingOrchestratorConfigResponse(BaseModel):
    """Secret-free email-writing orchestration configuration status."""

    orchestrator_enabled: bool
    orchestrator_base_url: str | None
    model_profile_id: str | None
    has_inference_credential: bool

    model_config = ConfigDict(extra="forbid")


SECRET_FIELDS = {
    "smtp_password",
    "imap_password",
    "pop3_password",
    "oauth_client_secret",
    "openai_api_key",
    "google_client_secret",
}

MAILBOX_MANAGE_FORBIDDEN = (
    "Mailbox settings are personal and can only be managed by the authenticated user"
)
MAILBOX_VIEW_FORBIDDEN = (
    "Mailbox settings are personal and can only be viewed by the authenticated user"
)
MAILBOX_SELF_SERVICE_ROLES: tuple[PolicyRoleName, ...] = (
    "system_admin",
    "platform_admin",
    "tenant_admin",
    "organization_admin",
    "group_admin",
    "member",
)
_EMAIL_WRITING_ORCHESTRATOR_INVALID = (
    "Invalid email-writing orchestrator configuration"
)


def ensure_mailbox_config_self_access(
    target_user_id: str, auth_context: AuthContext, forbidden_detail: str
) -> None:
    decision = evaluate_access(
        AccessRequest(
            user_id=auth_context.user_id,
            role=auth_context.role,
            organization_id=auth_context.organization_id,
            group_ids=auth_context.group_ids,
            data_region=None,
            consent_scopes=(),
            workspace_id=auth_context.workspace_id,
        ),
        ResourcePolicy(
            owner_id=target_user_id,
            organization_id=auth_context.organization_id,
            permitted_roles=MAILBOX_SELF_SERVICE_ROLES,
            permitted_group_ids=(),
            data_region=None,
            required_consent_scopes=(),
            workspace_id=auth_context.workspace_id,
            require_owner_match=True,
        ),
    )
    if not decision.allowed:
        raise HTTPException(status_code=403, detail=forbidden_detail)


def _field_value(
    config_data: dict, db_config: TenantConfig | None, field_name: str
):
    if field_name in config_data:
        return config_data[field_name]
    if db_config is not None:
        return getattr(db_config, field_name)
    return None


def _validate_smtp_config(smtp_server: str | None, smtp_port: int | None) -> None:
    try:
        if smtp_server is not None:
            validate_smtp_host(smtp_server, resolve_host=True)
        if smtp_port is not None:
            validate_smtp_port(smtp_port)
        if smtp_server is not None and smtp_port is not None:
            validate_smtp_destination(smtp_server, smtp_port)
    except ValueError as exc:
        logger.warning(
            "SMTP configuration validation failed",
            extra={"error_type": type(exc).__name__},
        )
        raise HTTPException(status_code=400, detail="Invalid SMTP configuration") from exc


def _validate_imap_config(imap_server: str | None, imap_port: int | None) -> None:
    try:
        if imap_server is not None and imap_port is not None:
            validate_imap_destination(imap_server, imap_port)
        elif imap_server is not None:
            validate_imap_destination(imap_server, 993)
        elif imap_port is not None:
            validate_imap_port(imap_port)
    except ValueError as exc:
        logger.warning(
            "IMAP configuration validation failed",
            extra={"error_type": type(exc).__name__},
        )
        raise HTTPException(
            status_code=400,
            detail="Invalid IMAP configuration",
        ) from exc


def _validate_pop3_config(pop3_server: str | None, pop3_port: int | None) -> None:
    try:
        if pop3_server is not None and pop3_port is not None:
            validate_pop3_destination(pop3_server, pop3_port)
        elif pop3_server is not None:
            validate_pop3_destination(pop3_server, 995)
        elif pop3_port is not None:
            validate_pop3_port(pop3_port)
    except ValueError as exc:
        logger.warning(
            "POP3 configuration validation failed",
            extra={"error_type": type(exc).__name__},
        )
        raise HTTPException(
            status_code=400,
            detail="Invalid POP3 configuration",
        ) from exc


def validate_mail_config_update(
    config_data: dict, db_config: TenantConfig | None
) -> None:
    smtp_server = _field_value(config_data, db_config, "smtp_server")
    smtp_port = _field_value(config_data, db_config, "smtp_port")
    imap_server = _field_value(config_data, db_config, "imap_server")
    imap_port = _field_value(config_data, db_config, "imap_port")
    pop3_server = _field_value(config_data, db_config, "pop3_server")
    pop3_port = _field_value(config_data, db_config, "pop3_port")

    _validate_smtp_config(smtp_server, smtp_port)
    _validate_imap_config(imap_server, imap_port)
    _validate_pop3_config(pop3_server, pop3_port)


def _email_writing_orchestrator_response(
    config: EmailWritingOrchestratorConfig | None,
) -> EmailWritingOrchestratorConfigResponse:
    """Build the public configuration view without returning owner or secret data."""
    if config is None:
        return EmailWritingOrchestratorConfigResponse(
            orchestrator_enabled=False,
            orchestrator_base_url=None,
            model_profile_id=None,
            has_inference_credential=False,
        )
    return EmailWritingOrchestratorConfigResponse(
        orchestrator_enabled=config.orchestrator_enabled,
        orchestrator_base_url=config.orchestrator_base_url,
        model_profile_id=config.model_profile_id,
        has_inference_credential=config.inference_credential is not None,
    )


async def _validated_orchestrator_url(value: str | None) -> str | None:
    """Validate and normalize an operator-allowlisted orchestration endpoint."""
    try:
        validated = await validate_llm_provider_base_url_details_async(value)
    except ValueError as exc:
        logger.warning(
            "Email-writing orchestrator URL validation failed",
            extra={"error_type": type(exc).__name__},
        )
        raise HTTPException(
            status_code=400,
            detail=_EMAIL_WRITING_ORCHESTRATOR_INVALID,
        ) from exc
    return None if validated is None else validated.normalized_url


@router.put(
    "/email-writing-orchestrator",
    response_model=EmailWritingOrchestratorConfigResponse,
)
async def update_email_writing_orchestrator_config(
    update: EmailWritingOrchestratorConfigUpdate,
    db: AsyncSession = Depends(get_db),
    auth_context: AuthContext = Depends(get_auth_context),
) -> EmailWritingOrchestratorConfigResponse:
    """Update one authenticated owner's orchestration settings fail-closed."""
    existing = await get_scoped_email_writing_orchestrator_config(
        db,
        auth_context.user_id,
        auth_context.organization_id,
    )
    values = update.model_dump(exclude_unset=True)

    enabled = values.get(
        "orchestrator_enabled",
        existing.orchestrator_enabled if existing is not None else False,
    )
    base_url = values.get(
        "orchestrator_base_url",
        existing.orchestrator_base_url if existing is not None else None,
    )
    if "orchestrator_base_url" in values:
        base_url = await _validated_orchestrator_url(base_url)
    model_profile_id = values.get(
        "model_profile_id",
        existing.model_profile_id if existing is not None else None,
    )
    inference_credential = values.get(
        "inference_credential",
        existing.inference_credential if existing is not None else None,
    )

    if enabled and not all((base_url, model_profile_id, inference_credential)):
        raise HTTPException(
            status_code=400,
            detail=_EMAIL_WRITING_ORCHESTRATOR_INVALID,
        )

    config = existing
    if config is None:
        config = new_scoped_email_writing_orchestrator_config(
            auth_context.user_id,
            auth_context.organization_id,
        )
        db.add(config)

    config.orchestrator_enabled = enabled
    config.orchestrator_base_url = base_url
    config.model_profile_id = model_profile_id
    config.inference_credential = inference_credential

    try:
        await db.commit()
    except Exception as exc:
        if "ENCRYPTION_KEY is required" not in str(exc):
            raise
        raise HTTPException(
            status_code=503,
            detail="Server encryption key is not configured. Contact your workspace administrator.",
        ) from exc
    return _email_writing_orchestrator_response(config)


@router.get(
    "/email-writing-orchestrator",
    response_model=EmailWritingOrchestratorConfigResponse,
)
async def get_email_writing_orchestrator_config(
    db: AsyncSession = Depends(get_db),
    auth_context: AuthContext = Depends(get_auth_context),
) -> EmailWritingOrchestratorConfigResponse:
    """Return one authenticated owner's secret-free orchestration settings."""
    config = await get_scoped_email_writing_orchestrator_config(
        db,
        auth_context.user_id,
        auth_context.organization_id,
    )
    return _email_writing_orchestrator_response(config)


@router.post("")
async def create_or_update_config(
    config: TenantConfigCreate,
    db: AsyncSession = Depends(get_db),
    auth_context: AuthContext = Depends(get_auth_context),
):
    ensure_mailbox_config_self_access(
        config.user_id,
        auth_context,
        MAILBOX_MANAGE_FORBIDDEN,
    )

    db_config = await get_scoped_tenant_config(
        db,
        auth_context.user_id,
        auth_context.organization_id,
    )

    config_data = config.model_dump(exclude_unset=True)
    validate_mail_config_update(config_data, db_config)

    if db_config:
        for key, value in config_data.items():
            if key in SECRET_FIELDS and value == "********":
                continue
            setattr(db_config, key, value)
    else:
        for key in SECRET_FIELDS:
            if key in config_data and config_data[key] == "********":
                config_data[key] = None
        db_config = new_scoped_tenant_config(
            user_id=auth_context.user_id,
            organization_id=auth_context.organization_id,
        )
        for key, value in config_data.items():
            setattr(db_config, key, value)
        db.add(db_config)

    try:
        await db.commit()
    except Exception as exc:
        if "ENCRYPTION_KEY is required" not in str(exc):
            raise
        raise HTTPException(
            status_code=503,
            detail="Server encryption key is not configured. Contact your workspace administrator.",
        ) from exc
    return {"status": "ok"}


@router.get("", response_model=TenantConfigResponse)
async def get_config(
    db: AsyncSession = Depends(get_db),
    auth_context: AuthContext = Depends(get_auth_context),
):
    ensure_mailbox_config_self_access(
        auth_context.user_id,
        auth_context,
        MAILBOX_VIEW_FORBIDDEN,
    )
    session_user_id = auth_context.user_id
    db_config = await get_scoped_tenant_config(
        db,
        session_user_id,
        auth_context.organization_id,
    )

    if not db_config:
        return TenantConfigResponse(user_id=session_user_id)

    response = TenantConfigResponse.model_validate(db_config)

    for secret_field in SECRET_FIELDS:
        if getattr(response, secret_field):
            setattr(response, secret_field, "********")

    return response
