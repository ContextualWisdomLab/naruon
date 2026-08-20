import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.exc import StatementError

from api.auth import AuthContext, get_auth_context
from core.runtime_secrets import EncryptionConfigurationError
from db.models import AuditLog, SecurityAuditEvent, TenantConfig
from db.session import get_db
from main import app


class _Result:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


class _Session:
    def __init__(self, config=None, commit_error=None):
        self.config = config
        self.commit_error = commit_error
        self.added = []
        self.committed = False

    async def execute(self, _query):
        return _Result(self.config)

    def add(self, value):
        self.added.append(value)
        if isinstance(value, TenantConfig):
            self.config = value

    async def commit(self):
        self.committed = True
        if self.commit_error is not None:
            raise self.commit_error


@pytest.fixture
def auth_context():
    return AuthContext(
        user_id="user-1",
        role="member",
        organization_id="org-1",
        group_ids=(),
        workspace_id="workspace-org-1",
    )


@pytest.fixture
def override_dependencies(auth_context):
    session = _Session()

    async def get_test_db():
        yield session

    async def get_test_auth():
        return auth_context

    app.dependency_overrides[get_db] = get_test_db
    app.dependency_overrides[get_auth_context] = get_test_auth
    yield session
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_auth_context, None)


async def _client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _allow_gateway_url(value):
    return value


@pytest.mark.asyncio
async def test_noema_gateway_update_masks_token_and_writes_audit(
    override_dependencies, monkeypatch
):
    monkeypatch.setattr(
        "api.noema_config.validate_llm_provider_base_url_async",
        _allow_gateway_url,
    )

    async with await _client() as client:
        response = await client.put(
            "/api/noema-gateway",
            json={
                "base_url": "https://orchestrator.example/v1",
                "token": "gateway-secret",
            },
        )

    assert response.status_code == 200
    assert response.json() == {
        "base_url": "https://orchestrator.example/v1",
        "configured": True,
        "has_token": True,
    }
    config = override_dependencies.config
    assert config.noema_orchestrator_token == "gateway-secret"
    assert "gateway-secret" not in response.text
    assert any(isinstance(item, AuditLog) for item in override_dependencies.added)
    event = next(
        item
        for item in override_dependencies.added
        if isinstance(item, SecurityAuditEvent)
    )
    assert event.resource_type == "noema_gateway"
    assert event.detail_text == "Updated Noema gateway settings"
    assert "gateway-secret" not in event.detail_text


@pytest.mark.asyncio
async def test_noema_gateway_get_returns_readiness_without_secret(
    override_dependencies, monkeypatch
):
    monkeypatch.setattr(
        "api.noema_config.validate_llm_provider_base_url_async",
        _allow_gateway_url,
    )
    override_dependencies.config = TenantConfig(
        user_id="user-1",
        organization_id="org-1",
        noema_orchestrator_base_url="https://orchestrator.example/v1",
        noema_orchestrator_token="gateway-secret",
    )

    async with await _client() as client:
        response = await client.get("/api/noema-gateway")

    assert response.status_code == 200
    assert response.json() == {
        "base_url": "https://orchestrator.example/v1",
        "configured": True,
        "has_token": True,
    }
    assert "gateway-secret" not in response.text


@pytest.mark.asyncio
async def test_noema_gateway_get_without_config_is_not_ready(override_dependencies):
    async with await _client() as client:
        response = await client.get("/api/noema-gateway")

    assert response.status_code == 200
    assert response.json() == {
        "base_url": None,
        "configured": False,
        "has_token": False,
    }


@pytest.mark.asyncio
async def test_noema_gateway_rejects_unallowlisted_normalized_url(
    override_dependencies, monkeypatch
):
    async def reject_url(_value):
        return None

    monkeypatch.setattr(
        "api.noema_config.validate_llm_provider_base_url_async", reject_url
    )
    async with await _client() as client:
        response = await client.put(
            "/api/noema-gateway",
            json={
                "base_url": "https://orchestrator.example/v1",
                "token": "gateway-secret",
            },
        )

    assert response.status_code == 422
    assert response.json()["detail"] == "Noema gateway base URL is not allowed"


@pytest.mark.asyncio
@pytest.mark.parametrize("token", [None, "********"])
async def test_noema_gateway_preserves_existing_token_for_masked_or_null_input(
    override_dependencies, monkeypatch, token
):
    override_dependencies.config = TenantConfig(
        user_id="user-1",
        organization_id="org-1",
        noema_orchestrator_base_url="https://orchestrator.example/v1",
        noema_orchestrator_token="gateway-secret",
    )
    monkeypatch.setattr(
        "api.noema_config.validate_llm_provider_base_url_async",
        _allow_gateway_url,
    )
    async with await _client() as client:
        response = await client.put(
            "/api/noema-gateway",
            json={"base_url": "https://orchestrator.example/v1", "token": token},
        )

    assert response.status_code == 200
    assert override_dependencies.config.noema_orchestrator_token == "gateway-secret"


@pytest.mark.asyncio
async def test_noema_gateway_rejects_control_character_in_token(
    override_dependencies
):
    async with await _client() as client:
        response = await client.put(
            "/api/noema-gateway",
            json={"token": "gateway\nsecret"},
        )

    assert response.status_code == 422
    assert response.json()["detail"] == "Noema gateway token is invalid"


@pytest.mark.asyncio
async def test_noema_gateway_reports_missing_token_for_valid_url(
    override_dependencies, monkeypatch
):
    monkeypatch.setattr(
        "api.noema_config.validate_llm_provider_base_url_async",
        _allow_gateway_url,
    )
    async with await _client() as client:
        response = await client.put(
            "/api/noema-gateway",
            json={"base_url": "https://orchestrator.example/v1"},
        )

    assert response.status_code == 422
    assert response.json()["detail"] == "Noema gateway base URL and token are required"


@pytest.mark.asyncio
async def test_noema_gateway_handles_missing_encryption_key(
    override_dependencies, monkeypatch
):
    monkeypatch.setattr(
        "api.noema_config.validate_llm_provider_base_url_async",
        _allow_gateway_url,
    )
    override_dependencies.commit_error = EncryptionConfigurationError(
        "ENCRYPTION_KEY is required"
    )
    async with await _client() as client:
        response = await client.put(
            "/api/noema-gateway",
            json={
                "base_url": "https://orchestrator.example/v1",
                "token": "gateway-secret",
            },
        )

    assert response.status_code == 503
    assert "Server encryption key is not configured" in response.json()["detail"]


@pytest.mark.asyncio
async def test_noema_gateway_handles_wrapped_encryption_configuration_error(
    override_dependencies, monkeypatch
):
    monkeypatch.setattr(
        "api.noema_config.validate_llm_provider_base_url_async",
        _allow_gateway_url,
    )
    override_dependencies.commit_error = StatementError(
        "commit failed",
        None,
        None,
        EncryptionConfigurationError("ENCRYPTION_KEY is required"),
    )
    async with await _client() as client:
        response = await client.put(
            "/api/noema-gateway",
            json={
                "base_url": "https://orchestrator.example/v1",
                "token": "gateway-secret",
            },
        )

    assert response.status_code == 503


@pytest.mark.asyncio
async def test_noema_gateway_does_not_match_encryption_error_text(
    override_dependencies, monkeypatch
):
    monkeypatch.setattr(
        "api.noema_config.validate_llm_provider_base_url_async",
        _allow_gateway_url,
    )
    override_dependencies.commit_error = RuntimeError("ENCRYPTION_KEY is required downstream")
    with pytest.raises(RuntimeError, match="ENCRYPTION_KEY is required downstream"):
        async with await _client() as client:
            await client.put(
                "/api/noema-gateway",
                json={
                    "base_url": "https://orchestrator.example/v1",
                    "token": "gateway-secret",
                },
            )


@pytest.mark.asyncio
async def test_noema_gateway_propagates_unexpected_commit_error(
    override_dependencies, monkeypatch
):
    monkeypatch.setattr(
        "api.noema_config.validate_llm_provider_base_url_async",
        _allow_gateway_url,
    )
    override_dependencies.commit_error = RuntimeError("database unavailable")
    with pytest.raises(RuntimeError, match="database unavailable"):
        async with await _client() as client:
            await client.put(
                "/api/noema-gateway",
                json={
                    "base_url": "https://orchestrator.example/v1",
                    "token": "gateway-secret",
                },
            )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload,detail",
    [
        ({"base_url": "https://orchestrator.example/v2"}, "Noema gateway base URL is not allowed"),
        ({"token": ""}, "Noema gateway token is required"),
        ({"unknown": "value"}, "Extra inputs are not permitted"),
    ],
)
async def test_noema_gateway_rejects_invalid_updates(
    override_dependencies, monkeypatch, payload, detail
):
    monkeypatch.setattr(
        "api.noema_config.validate_llm_provider_base_url_async",
        _allow_gateway_url,
    )
    async with await _client() as client:
        response = await client.put("/api/noema-gateway", json=payload)

    assert response.status_code == 422
    assert detail in response.text
    assert not override_dependencies.committed


@pytest.mark.asyncio
async def test_noema_gateway_requires_a_setting_update(override_dependencies):
    async with await _client() as client:
        response = await client.put("/api/noema-gateway", json={})

    assert response.status_code == 422
    assert response.json()["detail"] == "No gateway settings supplied"
