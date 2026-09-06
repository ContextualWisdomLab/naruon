from dataclasses import dataclass
from typing import Literal
from urllib.parse import urlsplit

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from db.models import LLMProvider
from services.llm_provider_readiness import (
    LOCAL_PROVIDER_TYPES,
    is_llm_provider_configured,
    llm_provider_model_label,
)
from services.tenant_config_scope import get_scoped_tenant_config


ProviderSource = Literal["llm_provider", "tenant_config", "local_environment"]
LOCAL_PROVIDER_API_KEY = "local-provider"
LOCAL_RUNTIME_HOSTS = frozenset(
    {"localhost", "localhost.localdomain", "127.0.0.1", "::1", "host.docker.internal", "ollama"}
)


@dataclass(frozen=True)
class RuntimeLLMProvider:
    api_key: str
    base_url: str | None
    chat_model: str
    embedding_model: str
    provider_name: str
    provider_source: ProviderSource
    embedding_base_url: str | None = None
    provider_id: int | None = None


def _provider_type(provider: LLMProvider) -> str:
    return (provider.provider_type or "").strip().lower()


def _is_local_provider(provider: LLMProvider) -> bool:
    return _provider_type(provider) in LOCAL_PROVIDER_TYPES


def _provider_api_key(provider: LLMProvider) -> str | None:
    if provider.api_key and provider.api_key.strip():
        return provider.api_key
    if _is_local_provider(provider):
        return LOCAL_PROVIDER_API_KEY
    return None


def _is_local_runtime_base_url(base_url: str | None) -> bool:
    try:
        hostname = urlsplit(base_url or "").hostname
    except ValueError:
        return False
    return hostname in LOCAL_RUNTIME_HOSTS


async def get_active_llm_provider(
    session: AsyncSession,
    organization_id: str | None,
) -> LLMProvider | None:
    if not organization_id:
        return None

    result = await session.execute(
        select(LLMProvider)
        .where(
            LLMProvider.organization_id == organization_id,
            LLMProvider.is_active.is_(True),
        )
        .order_by(desc(LLMProvider.updated_at), desc(LLMProvider.id))
        .limit(1)
    )
    return result.scalars().first()


def _runtime_from_provider(provider: LLMProvider) -> RuntimeLLMProvider | None:
    if not is_llm_provider_configured(provider):
        return None

    if _is_local_runtime_base_url(provider.base_url):
        if not _is_local_provider(provider):
            return None
        api_key = LOCAL_PROVIDER_API_KEY
    else:
        api_key = _provider_api_key(provider)
    if not api_key:
        return None

    return RuntimeLLMProvider(
        api_key=api_key,
        base_url=provider.base_url,
        chat_model=(provider.model_identifier or "").strip() or settings.OPENAI_MODEL,
        embedding_model=(provider.embedding_model or "").strip()
        or settings.OPENAI_EMBEDDING_MODEL,
        provider_name=llm_provider_model_label(provider),
        provider_source="llm_provider",
        provider_id=provider.id,
    )


async def resolve_runtime_llm_provider(
    session: AsyncSession,
    *,
    user_id: str,
    organization_id: str | None,
) -> RuntimeLLMProvider | None:
    active_provider = await get_active_llm_provider(session, organization_id)
    if active_provider is not None:
        runtime_provider = _runtime_from_provider(active_provider)
        if runtime_provider is not None:
            return runtime_provider

    local_provider = _local_environment_provider()
    if local_provider is not None:
        return local_provider

    tenant_config = await get_scoped_tenant_config(session, user_id, organization_id)
    if tenant_config is None or not tenant_config.openai_api_key:
        return None

    return RuntimeLLMProvider(
        api_key=tenant_config.openai_api_key,
        base_url=settings.OPENAI_BASE_URL,
        chat_model=settings.OPENAI_MODEL,
        embedding_model=settings.OPENAI_EMBEDDING_MODEL,
        provider_name="OpenAI",
        provider_source="tenant_config",
        provider_id=None,
    )


def _local_environment_provider() -> RuntimeLLMProvider | None:
    if not settings.ALLOW_LOCAL_LLM_PROVIDERS:
        return None
    base_url = settings.OPENAI_BASE_URL
    hostname = urlsplit(base_url or "").hostname
    if not base_url or hostname not in LOCAL_RUNTIME_HOSTS:
        return None
    api_key = settings.OPENAI_API_KEY
    if api_key is None or not api_key.get_secret_value().strip():
        return None
    embedding_base_url = settings.OPENAI_EMBEDDING_BASE_URL
    embedding_hostname = urlsplit(embedding_base_url or "").hostname
    if embedding_base_url and embedding_hostname not in LOCAL_RUNTIME_HOSTS:
        embedding_base_url = None
    return RuntimeLLMProvider(
        api_key=api_key.get_secret_value(),
        base_url=base_url,
        embedding_base_url=embedding_base_url,
        chat_model=settings.OPENAI_MODEL,
        embedding_model=settings.OPENAI_EMBEDDING_MODEL,
        provider_name="Local runtime",
        provider_source="local_environment",
        provider_id=None,
    )
