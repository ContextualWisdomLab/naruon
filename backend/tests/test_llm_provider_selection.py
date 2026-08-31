import datetime

import pytest

from db.models import LLMProvider
from services.llm_provider_selection import (
    LOCAL_PROVIDER_API_KEY,
    resolve_runtime_llm_provider,
)


class MockScalars:
    def __init__(self, items):
        self.items = items

    def first(self):
        return self.items[0] if self.items else None


class MockProviderResult:
    def __init__(self, providers):
        self.providers = providers

    def scalars(self):
        return MockScalars(self.providers)


class MockTenantResult:
    def __init__(self, tenant_config):
        self.tenant_config = tenant_config

    def scalar_one_or_none(self):
        return self.tenant_config


class MockTenantConfig:
    def __init__(self, openai_api_key="sk-tenant"):
        self.openai_api_key = openai_api_key


class MockSession:
    def __init__(self, *, providers=None, tenant_config=None):
        self.providers = providers or []
        self.tenant_config = tenant_config

    async def execute(self, stmt):
        statement_text = str(stmt).lower()
        if "llm_providers" in statement_text:
            return MockProviderResult(self.providers)
        if "tenant_configs" in statement_text:
            return MockTenantResult(self.tenant_config)
        raise AssertionError(f"unexpected statement: {stmt}")


@pytest.mark.asyncio
async def test_resolve_runtime_llm_provider_prefers_active_local_provider():
    provider = LLMProvider(
        id=10,
        user_id="admin",
        organization_id="org-acme",
        name="Local Gemma4",
        provider_type="ollama",
        base_url="http://ollama:11434/v1",
        model_identifier="gemma4",
        embedding_model="embeddinggemma",
        api_key=None,
        is_active=True,
        updated_at=datetime.datetime.now(datetime.timezone.utc),
    )

    runtime_provider = await resolve_runtime_llm_provider(
        MockSession(
            providers=[provider],
            tenant_config=MockTenantConfig(openai_api_key=None),
        ),
        user_id="testuser",
        organization_id="org-acme",
    )

    assert runtime_provider is not None
    assert runtime_provider.provider_source == "llm_provider"
    assert runtime_provider.provider_id == 10
    assert runtime_provider.api_key == LOCAL_PROVIDER_API_KEY
    assert runtime_provider.base_url == "http://ollama:11434/v1"
    assert runtime_provider.chat_model == "gemma4"
    assert runtime_provider.embedding_model == "embeddinggemma"
    assert runtime_provider.zdr_required is False


@pytest.mark.asyncio
async def test_explicit_orchestrator_provider_requires_zdr_for_nonprefixed_models():
    provider = LLMProvider(
        id=11,
        user_id="admin",
        organization_id="org-acme",
        name="Contextual Orchestrator",
        provider_type="contextual_orchestrator",
        base_url="https://gateway.example/v1",
        model_identifier="gateway-auto",
        embedding_model="gateway-embedding",
        api_key="gateway-token",
        is_active=True,
        updated_at=datetime.datetime.now(datetime.timezone.utc),
    )

    runtime_provider = await resolve_runtime_llm_provider(
        MockSession(providers=[provider]),
        user_id="testuser",
        organization_id="org-acme",
    )

    assert runtime_provider is not None
    assert runtime_provider.chat_model == "gateway-auto"
    assert runtime_provider.zdr_required is True


@pytest.mark.asyncio
async def test_model_prefix_cannot_enable_zdr_for_direct_provider():
    provider = LLMProvider(
        id=12,
        user_id="admin",
        organization_id="org-acme",
        name="Direct provider",
        provider_type="openai",
        model_identifier="orchestrator/untrusted-prefix",
        api_key="direct-token",
        is_active=True,
        updated_at=datetime.datetime.now(datetime.timezone.utc),
    )

    runtime_provider = await resolve_runtime_llm_provider(
        MockSession(providers=[provider]),
        user_id="testuser",
        organization_id="org-acme",
    )

    assert runtime_provider is not None
    assert runtime_provider.zdr_required is False


@pytest.mark.asyncio
async def test_resolve_runtime_llm_provider_falls_back_to_tenant_config():
    runtime_provider = await resolve_runtime_llm_provider(
        MockSession(providers=[], tenant_config=MockTenantConfig("sk-tenant")),
        user_id="testuser",
        organization_id="org-acme",
    )

    assert runtime_provider is not None
    assert runtime_provider.provider_source == "tenant_config"
    assert runtime_provider.api_key == "sk-tenant"
    assert runtime_provider.zdr_required is False
