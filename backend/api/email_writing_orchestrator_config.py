"""Owner-scoped HTTP configuration for email-writing orchestration."""

from __future__ import annotations

import logging
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, ValidationInfo, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import AuthContext, get_auth_context
from db.email_writing_orchestrator_config import EmailWritingOrchestratorConfig
from db.session import get_db
from services.llm_provider_urls import validate_llm_provider_base_url_details_async
from services.tenant_config_scope import (
    get_scoped_email_writing_orchestrator_config,
    new_scoped_email_writing_orchestrator_config,
)

router = APIRouter(prefix="/api/config")
logger = logging.getLogger(__name__)
_INVALID_CONFIGURATION = "Invalid email-writing orchestrator configuration"
_ENCRYPTION_CONFIGURATION_REQUIRED = (
    "Server encryption key is not configured. Contact your workspace administrator."
)


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
        cls,
        value: object,
        info: ValidationInfo,
    ) -> object:
        """Trim bounded text fields without coercing non-string values."""
        if value is None or not isinstance(value, str):
            return value
        normalized = value.strip()
        limits = {
            "orchestrator_base_url": 2_048,
            "model_profile_id": 255,
            "inference_credential": 8_192,
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


def _public_configuration(
    config: EmailWritingOrchestratorConfig | None,
) -> EmailWritingOrchestratorConfigResponse:
    """Build the public configuration view without owner or secret values."""
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
            detail=_INVALID_CONFIGURATION,
        ) from exc
    if validated is None:
        return None
    parsed = urlsplit(validated.normalized_url)
    if (
        parsed.scheme.lower() != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
    ):
        raise HTTPException(
            status_code=400,
            detail=_INVALID_CONFIGURATION,
        )
    return validated.normalized_url


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
            detail=_INVALID_CONFIGURATION,
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
            detail=_ENCRYPTION_CONFIGURATION_REQUIRED,
        ) from exc
    return _public_configuration(config)


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
    return _public_configuration(config)
