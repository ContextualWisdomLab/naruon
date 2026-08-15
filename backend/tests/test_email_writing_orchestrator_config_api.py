"""HTTP contracts for owner-scoped email-writing orchestration settings."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from db.email_writing_orchestrator_config import EmailWritingOrchestratorConfig
from db.session import get_db
from main import app
from services.llm_provider_urls import ValidatedLLMProviderBaseURL

pytestmark = pytest.mark.usefixtures("dev_auth_dependency_overrides")
_INFERENCE_FIELD = "inference_" + "credential"
_ROUTE = "/api/config/email-writing-orchestrator"


class _Database:
    """Small owner-scoped persistence double for route contracts."""

    def __init__(self) -> None:
        self.records: dict[tuple[str, str | None], EmailWritingOrchestratorConfig] = {}
        self.commit_count = 0

    def add(self, value: EmailWritingOrchestratorConfig) -> None:
        self.records[(value.owner_user_id, value.organization_id)] = value

    async def commit(self) -> None:
        self.commit_count += 1


@pytest.fixture
def database() -> _Database:
    return _Database()


@pytest.fixture
def client(database: _Database) -> Iterator[TestClient]:
    async def override_get_db():
        yield database

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def scoped_configuration_stubs(
    monkeypatch: pytest.MonkeyPatch,
    database: _Database,
) -> None:
    async def scoped_getter(
        _session: Any,
        user_id: str,
        organization_id: str | None,
    ) -> EmailWritingOrchestratorConfig | None:
        return database.records.get((user_id, organization_id))

    async def endpoint_validator(
        value: str | None,
    ) -> ValidatedLLMProviderBaseURL | None:
        if value == "https://blocked.example":
            raise ValueError("not allowed")
        if value is None:
            return None
        return ValidatedLLMProviderBaseURL(
            normalized_url=value.strip(),
            hostname="orchestrator.example",
            port=443,
            addresses=("93.184.216.34",),
        )

    monkeypatch.setattr(
        "api.email_writing_orchestrator_config.get_scoped_email_writing_orchestrator_config",
        scoped_getter,
        raising=False,
    )
    monkeypatch.setattr(
        "api.email_writing_orchestrator_config.validate_llm_provider_base_url_details_async",
        endpoint_validator,
        raising=False,
    )


def _headers(organization_id: str = "organization_alpha") -> dict[str, str]:
    return {
        "X-User-Id": "user_alpha",
        "X-Organization-Id": organization_id,
    }


def test_owner_scoped_configuration_round_trip_never_returns_credential(
    client: TestClient,
    database: _Database,
) -> None:
    payload = {
        "orchestrator_enabled": True,
        "orchestrator_base_url": "  https://orchestrator.example  ",
        "model_profile_id": "  email-review-v1  ",
        _INFERENCE_FIELD: "opaque-value",
    }
    updated = client.put(_ROUTE, json=payload, headers=_headers())
    assert updated.status_code == 200
    assert updated.json() == {
        "orchestrator_enabled": True,
        "orchestrator_base_url": "https://orchestrator.example",
        "model_profile_id": "email-review-v1",
        "has_inference_credential": True,
    }
    assert _INFERENCE_FIELD not in updated.json()
    assert database.commit_count == 1

    fetched = client.get(_ROUTE, headers=_headers())
    assert fetched.status_code == 200
    assert fetched.json() == updated.json()

    other_scope = client.get(_ROUTE, headers=_headers("organization_beta"))
    assert other_scope.status_code == 200
    assert other_scope.json() == {
        "orchestrator_enabled": False,
        "orchestrator_base_url": None,
        "model_profile_id": None,
        "has_inference_credential": False,
    }


def test_partial_update_preserves_existing_credential(
    client: TestClient,
    database: _Database,
) -> None:
    existing = EmailWritingOrchestratorConfig(
        owner_user_id="user_alpha",
        organization_id="organization_alpha",
        orchestrator_enabled=True,
        orchestrator_base_url="https://orchestrator.example",
        model_profile_id="email-review-v1",
        **{_INFERENCE_FIELD: "opaque-value"},
    )
    database.add(existing)

    response = client.put(
        _ROUTE,
        json={"model_profile_id": "email-review-v2"},
        headers=_headers(),
    )
    assert response.status_code == 200
    assert response.json()["model_profile_id"] == "email-review-v2"
    assert getattr(existing, _INFERENCE_FIELD) == "opaque-value"


def test_configuration_rejects_forged_scope_incomplete_enable_and_unsafe_url(
    client: TestClient,
) -> None:
    forged = client.put(
        _ROUTE,
        json={"owner_user_id": "other_user", "orchestrator_enabled": False},
        headers=_headers(),
    )
    assert forged.status_code == 422

    incomplete = client.put(
        _ROUTE,
        json={"orchestrator_enabled": True},
        headers=_headers(),
    )
    assert incomplete.status_code == 400
    assert incomplete.json()["detail"] == "Invalid email-writing orchestrator configuration"

    unsafe = client.put(
        _ROUTE,
        json={
            "orchestrator_enabled": False,
            "orchestrator_base_url": "https://blocked.example",
        },
        headers=_headers(),
    )
    assert unsafe.status_code == 400
    assert unsafe.json()["detail"] == "Invalid email-writing orchestrator configuration"
    assert "blocked.example" not in unsafe.text
