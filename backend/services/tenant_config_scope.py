"""Owner-scoped configuration lookup helpers for tenant integrations."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.email_writing_orchestrator_config import EmailWritingOrchestratorConfig
from db.models import TenantConfig


class EmailWritingOrchestratorConfigurationError(RuntimeError):
    """Stable, secret-free tenant orchestration configuration failure."""

    def __init__(self, code: str) -> None:
        """Create a configuration error identified only by a public code."""
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class EmailWritingOrchestratorSettings:
    """Complete tenant settings required to build the orchestration client."""

    base_url: str
    model_profile_id: str
    inference_credential: str


def tenant_config_owner_filters(user_id: str, organization_id: str | None):
    """Return exact owner filters for the legacy tenant configuration row."""
    organization_filter = (
        TenantConfig.organization_id == organization_id
        if organization_id is not None
        else TenantConfig.organization_id.is_(None)
    )
    return (TenantConfig.user_id == user_id, organization_filter)


async def get_scoped_tenant_config(
    session: AsyncSession,
    user_id: str,
    organization_id: str | None,
) -> TenantConfig | None:
    """Return the tenant configuration visible to one exact owner scope."""
    result = await session.execute(
        select(TenantConfig).where(
            *tenant_config_owner_filters(user_id, organization_id)
        )
    )
    return result.scalar_one_or_none()


def new_scoped_tenant_config(
    user_id: str,
    organization_id: str | None,
) -> TenantConfig:
    """Create an unsaved legacy tenant configuration in one owner scope."""
    return TenantConfig(user_id=user_id, organization_id=organization_id)


def email_writing_orchestrator_owner_filters(
    user_id: str,
    organization_id: str | None,
):
    """Return exact owner filters for email-writing orchestration settings."""
    organization_filter = (
        EmailWritingOrchestratorConfig.organization_id == organization_id
        if organization_id is not None
        else EmailWritingOrchestratorConfig.organization_id.is_(None)
    )
    return (
        EmailWritingOrchestratorConfig.owner_user_id == user_id,
        organization_filter,
    )


async def get_scoped_email_writing_orchestrator_config(
    session: AsyncSession,
    user_id: str,
    organization_id: str | None,
) -> EmailWritingOrchestratorConfig | None:
    """Return one owner-scoped email-writing orchestration configuration."""
    result = await session.execute(
        select(EmailWritingOrchestratorConfig).where(
            *email_writing_orchestrator_owner_filters(user_id, organization_id)
        )
    )
    return result.scalar_one_or_none()


def new_scoped_email_writing_orchestrator_config(
    user_id: str,
    organization_id: str | None,
) -> EmailWritingOrchestratorConfig:
    """Create an unsaved, disabled email-writing orchestration configuration."""
    return EmailWritingOrchestratorConfig(
        owner_user_id=user_id,
        organization_id=organization_id,
        orchestrator_enabled=False,
    )


def _clean_orchestrator_value(value: str | None) -> str | None:
    """Trim one optional configuration string without coercing other values."""
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


async def resolve_email_writing_orchestrator_settings(
    session: AsyncSession,
    *,
    user_id: str,
    organization_id: str | None,
) -> EmailWritingOrchestratorSettings | None:
    """Resolve complete enabled settings or fail closed when partially configured."""
    config = await get_scoped_email_writing_orchestrator_config(
        session,
        user_id,
        organization_id,
    )
    if config is None or not config.orchestrator_enabled:
        return None

    base_url = _clean_orchestrator_value(config.orchestrator_base_url)
    model_profile_id = _clean_orchestrator_value(config.model_profile_id)
    inference_credential = _clean_orchestrator_value(config.inference_credential)
    if base_url is None or model_profile_id is None or inference_credential is None:
        raise EmailWritingOrchestratorConfigurationError(
            "email_writing_orchestrator_incomplete"
        )
    return EmailWritingOrchestratorSettings(
        base_url=base_url,
        model_profile_id=model_profile_id,
        inference_credential=inference_credential,
    )
