from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import TenantConfig


def tenant_config_owner_filters(user_id: str, organization_id: str | None):
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
    return TenantConfig(user_id=user_id, organization_id=organization_id)
