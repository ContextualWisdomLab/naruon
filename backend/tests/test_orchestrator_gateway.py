"""Tests for the contextual-orchestrator inference gateway resolver.

Noema (and any other in-process decision agent) may call only this gateway.
These tests prove the consumer-side contract:

* dedicated gateway inference token + HTTPS ``/v1`` base URL from the Fernet KV
* model alias is always ``contextual-orchestrator`` (no sequential model list)
* upstream provider keys and GitHub Models tokens are never read at request time
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from pydantic import SecretStr
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from core.config import settings
from db.models import TenantConfig
from services.orchestrator_gateway import (
    FORBIDDEN_GATEWAY_HOSTS,
    ORCHESTRATOR_MODEL_ALIAS,
    UPSTREAM_PROVIDER_SECRET_NAMES,
    OrchestratorGateway,
    resolve_orchestrator_gateway,
    validate_orchestrator_gateway_url,
)

ORCH_URL = "https://orchestrator.example/v1"
GATEWAY_TOKEN = "naruon-orch-inference-token"


class _FakeResult:
    def __init__(self, tenant_config):
        self._tenant_config = tenant_config

    def scalar_one_or_none(self):
        return self._tenant_config


class _FakeAsyncSession:
    def __init__(self, tenant_config=None):
        self.tenant_config = tenant_config

    async def execute(self, _stmt):
        return _FakeResult(self.tenant_config)


@pytest.fixture(autouse=True)
def encryption_key():
    old_key = settings.ENCRYPTION_KEY
    settings.ENCRYPTION_KEY = SecretStr(Fernet.generate_key().decode("ascii"))
    yield
    settings.ENCRYPTION_KEY = old_key


def test_model_alias_is_the_single_orchestrator_name():
    assert ORCHESTRATOR_MODEL_ALIAS == "contextual-orchestrator"
    gateway = OrchestratorGateway(
        inference_token=GATEWAY_TOKEN,
        base_url=ORCH_URL,
    )
    assert gateway.model_alias == "contextual-orchestrator"
    assert gateway.model_candidates == ()


def test_validate_gateway_url_requires_https_v1_suffix():
    assert validate_orchestrator_gateway_url(ORCH_URL) == ORCH_URL
    assert validate_orchestrator_gateway_url("https://orchestrator.example/v1/") == (
        "https://orchestrator.example/v1"
    )
    with pytest.raises(ValueError):
        validate_orchestrator_gateway_url("http://orchestrator.example/v1")
    with pytest.raises(ValueError):
        validate_orchestrator_gateway_url("https://orchestrator.example/openai")
    with pytest.raises(ValueError):
        validate_orchestrator_gateway_url("https://orchestrator.example")


@pytest.mark.parametrize("host", sorted(FORBIDDEN_GATEWAY_HOSTS))
def test_validate_gateway_url_rejects_github_models_hosts(host):
    with pytest.raises(ValueError):
        validate_orchestrator_gateway_url(f"https://{host}/v1")


def test_upstream_provider_secret_names_are_denylisted_not_consumed():
    assert "NVIDIA_NIM_API_KEY" in UPSTREAM_PROVIDER_SECRET_NAMES
    assert "NVIDIA_NIM_API_KEY_SUB" in UPSTREAM_PROVIDER_SECRET_NAMES
    assert "BYTEZ_API_KEY" in UPSTREAM_PROVIDER_SECRET_NAMES
    assert "OPENROUTER_API_KEY" in UPSTREAM_PROVIDER_SECRET_NAMES
    assert "OPENAI_API_KEY" in UPSTREAM_PROVIDER_SECRET_NAMES
    assert "COPILOT_GITHUB_TOKEN" in UPSTREAM_PROVIDER_SECRET_NAMES


def test_gateway_modules_do_not_read_env_or_hold_provider_keys():
    roots = [
        Path(__file__).resolve().parents[1] / "services" / "orchestrator_gateway.py",
        Path(__file__).resolve().parents[1] / "services" / "noema_agent.py",
    ]
    for path in roots:
        source = path.read_text(encoding="utf-8")
        assert "os.getenv(" not in source
        assert "os.environ[" not in source
        assert "os.environ.get(" not in source
        for secret_name in UPSTREAM_PROVIDER_SECRET_NAMES:
            # The denylist constant may name the secrets; runtime reads must not.
            if path.name == "orchestrator_gateway.py":
                continue
            assert secret_name not in source


@pytest.mark.asyncio
async def test_resolve_gateway_from_fernet_kv_not_env(monkeypatch):
    for name in UPSTREAM_PROVIDER_SECRET_NAMES:
        monkeypatch.setenv(name, f"env-leak-{name}")
    monkeypatch.setattr(
        "services.orchestrator_gateway.validate_llm_provider_base_url",
        lambda value: value,
    )

    engine = create_engine("sqlite:///:memory:")
    TenantConfig.__table__.create(engine)
    try:
        with Session(engine) as session:
            session.add(
                TenantConfig(
                    user_id="user-1",
                    organization_id="org-acme",
                    noema_orchestrator_base_url=ORCH_URL,
                    noema_orchestrator_token=GATEWAY_TOKEN,
                    openai_api_key="tenant-openai-must-not-be-used",
                )
            )
            session.commit()
            raw_token = session.execute(
                text("SELECT noema_orchestrator_token FROM tenant_configs")
            ).scalar_one()
            assert raw_token != GATEWAY_TOKEN
            reloaded = session.query(TenantConfig).one()
    finally:
        engine.dispose()

    resolved = await resolve_orchestrator_gateway(
        _FakeAsyncSession(reloaded),
        user_id="user-1",
        organization_id="org-acme",
    )
    assert resolved is not None
    assert resolved.base_url == ORCH_URL
    assert resolved.inference_token == GATEWAY_TOKEN
    assert resolved.model_alias == "contextual-orchestrator"
    assert resolved.model_candidates == ()
    assert resolved.inference_token != os.environ["OPENAI_API_KEY"]
    assert resolved.inference_token != os.environ["NVIDIA_NIM_API_KEY"]
    assert resolved.inference_token != "tenant-openai-must-not-be-used"


@pytest.mark.asyncio
async def test_resolve_gateway_unavailable_when_kv_missing():
    resolved = await resolve_orchestrator_gateway(
        _FakeAsyncSession(None),
        user_id="user-1",
        organization_id="org-acme",
    )
    assert resolved is None


@pytest.mark.asyncio
async def test_resolve_gateway_rejects_invalid_url(monkeypatch):
    monkeypatch.setattr(
        "services.orchestrator_gateway.validate_llm_provider_base_url",
        lambda value: value,
    )
    config = TenantConfig(
        user_id="user-1",
        organization_id="org-acme",
        noema_orchestrator_base_url="https://models.github.ai/v1",
        noema_orchestrator_token=GATEWAY_TOKEN,
    )
    resolved = await resolve_orchestrator_gateway(
        _FakeAsyncSession(config),
        user_id="user-1",
        organization_id="org-acme",
    )
    assert resolved is None
