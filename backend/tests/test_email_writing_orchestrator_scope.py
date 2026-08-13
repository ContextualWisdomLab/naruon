"""Test-first tenant-scoped configuration contracts for email-writing orchestration."""

from __future__ import annotations

from typing import Any

import pytest

from db.email_writing_orchestrator_config import EmailWritingOrchestratorConfig
from services.tenant_config_scope import (
    EmailWritingOrchestratorConfigurationError,
    email_writing_orchestrator_owner_filters,
    get_scoped_email_writing_orchestrator_config,
    new_scoped_email_writing_orchestrator_config,
    resolve_email_writing_orchestrator_settings,
)


class _ScalarResult:
    def __init__(self, value: Any) -> None:
        self._value = value

    def scalar_one_or_none(self) -> Any:
        return self._value


class _Session:
    def __init__(self, value: Any) -> None:
        self.value = value
        self.queries: list[Any] = []

    async def execute(self, query: Any) -> _ScalarResult:
        self.queries.append(query)
        return _ScalarResult(self.value)


def _config(**overrides: Any) -> EmailWritingOrchestratorConfig:
    values: dict[str, Any] = {
        "owner_user_id": "user_alpha",
        "organization_id": "organization_alpha",
        "orchestrator_enabled": True,
        "orchestrator_base_url": "https://orchestrator.example",
        "model_profile_id": "email-review-v1",
        "inference_credential": "tenant-secret-token",
    }
    values.update(overrides)
    return EmailWritingOrchestratorConfig(**values)


def test_email_writing_orchestrator_owner_filters_are_tenant_exact() -> None:
    with_org = email_writing_orchestrator_owner_filters(
        "user_alpha", "organization_alpha"
    )
    assert len(with_org) == 2
    assert str(with_org[0].left) == "email_writing_orchestrator_config.owner_user_id"
    assert with_org[0].right.value == "user_alpha"
    assert str(with_org[1].left) == "email_writing_orchestrator_config.organization_id"
    assert with_org[1].right.value == "organization_alpha"

    personal = email_writing_orchestrator_owner_filters("user_alpha", None)
    assert personal[1].operator.__name__ == "is_"


@pytest.mark.asyncio
async def test_scoped_orchestrator_config_query_and_constructor() -> None:
    existing = _config()
    session = _Session(existing)
    assert (
        await get_scoped_email_writing_orchestrator_config(
            session, "user_alpha", "organization_alpha"
        )
        is existing
    )
    assert len(session.queries) == 1

    created = new_scoped_email_writing_orchestrator_config(
        "user_alpha", "organization_alpha"
    )
    assert created.owner_user_id == "user_alpha"
    assert created.organization_id == "organization_alpha"
    assert created.orchestrator_enabled is False


@pytest.mark.asyncio
async def test_settings_resolver_is_disabled_by_default_and_trims_values() -> None:
    assert (
        await resolve_email_writing_orchestrator_settings(
            _Session(None),
            user_id="user_alpha",
            organization_id="organization_alpha",
        )
        is None
    )
    disabled = _config(orchestrator_enabled=False)
    assert (
        await resolve_email_writing_orchestrator_settings(
            _Session(disabled),
            user_id="user_alpha",
            organization_id="organization_alpha",
        )
        is None
    )

    enabled = _config(
        orchestrator_base_url="  https://orchestrator.example  ",
        model_profile_id="  email-review-v1  ",
        inference_credential="  tenant-secret-token  ",
    )
    resolved = await resolve_email_writing_orchestrator_settings(
        _Session(enabled),
        user_id="user_alpha",
        organization_id="organization_alpha",
    )
    assert resolved is not None
    assert resolved.base_url == "https://orchestrator.example"
    assert resolved.model_profile_id == "email-review-v1"
    assert resolved.inference_credential == "tenant-secret-token"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "field_name",
    ["orchestrator_base_url", "model_profile_id", "inference_credential"],
)
async def test_enabled_incomplete_settings_fail_closed(field_name: str) -> None:
    config = _config(**{field_name: " "})
    with pytest.raises(EmailWritingOrchestratorConfigurationError) as captured:
        await resolve_email_writing_orchestrator_settings(
            _Session(config),
            user_id="user_alpha",
            organization_id="organization_alpha",
        )
    assert captured.value.code == "email_writing_orchestrator_incomplete"
    assert str(captured.value) == "email_writing_orchestrator_incomplete"


def test_config_repr_and_evidence_surface_never_expose_inference_credential() -> None:
    config = _config()
    representation = repr(config)
    evidence = config.to_evidence_dict()
    assert "tenant-secret-token" not in representation
    assert "tenant-secret-token" not in repr(evidence)
    assert evidence == {
        "orchestrator_config_id": None,
        "owner_user_id": "user_alpha",
        "organization_id": "organization_alpha",
        "orchestrator_enabled": True,
        "orchestrator_base_url": "https://orchestrator.example",
        "model_profile_id": "email-review-v1",
        "has_inference_credential": True,
    }
