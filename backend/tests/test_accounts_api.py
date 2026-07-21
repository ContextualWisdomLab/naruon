import base64
import hashlib
import hmac
import json
import time

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from api.auth import SESSION_AUDIENCE, SESSION_ISSUER
from api.tenant_config import MAILBOX_MANAGE_FORBIDDEN, MAILBOX_VIEW_FORBIDDEN
from core.config import settings
from db.session import get_db
from main import app

TEST_SESSION_HMAC_SECRET = "accounts-mailbox-owner-hmac-value-20260529"  # noqa: S105


class MockTenantConfig:
    def __init__(self, user_id, organization_id=None):
        self.user_id = user_id
        self.organization_id = organization_id
        self.smtp_server = None
        self.smtp_port = None
        self.smtp_username = None
        self.smtp_password = None
        self.imap_server = None
        self.imap_port = None
        self.imap_username = None
        self.imap_password = None
        self.pop3_server = None
        self.pop3_port = None
        self.pop3_username = None
        self.pop3_password = None
        self.oauth_client_id = None
        self.oauth_client_secret = None
        self.oauth_redirect_uri = None
        self.openai_api_key = None

class MockResult:
    def __init__(self, config=None):
        self.config = config
    def scalar_one_or_none(self):
        return self.config

class MockSession:
    def __init__(self):
        self.configs = {}
        self.commits = 0
        self.execute_calls = 0

    def _query_key(self, stmt):
        params = dict(stmt.compile().params)
        user_id = params.get("user_id_1")
        organization_id = params.get("organization_id_1")
        return user_id, organization_id

    async def execute(self, stmt):
        self.execute_calls += 1
        return MockResult(self.configs.get(self._query_key(stmt)))

    def add(self, obj):
        self.configs[(obj.user_id, obj.organization_id)] = obj

    async def commit(self):
        self.commits += 1

    async def refresh(self, obj):
        pass

async def override_get_db():
    yield MockSession()


def _base64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _signed_session_token(payload: dict[str, object]) -> str:
    header_segment = _base64url_encode(
        json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode()
    )
    payload_segment = _base64url_encode(
        json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    )
    signing_input = f"{header_segment}.{payload_segment}"
    signature = hmac.new(
        TEST_SESSION_HMAC_SECRET.encode("utf-8"),
        signing_input.encode("ascii"),
        hashlib.sha256,
    ).digest()
    return f"{signing_input}.{_base64url_encode(signature)}"


def _valid_session_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "ver": 1,
        "iss": SESSION_ISSUER,
        "aud": SESSION_AUDIENCE,
        "sub": "mailbox-owner",
        "role": "member",
        "org": "org-acme",
        "groups": [],
        "workspace": "workspace-org-acme",
        "exp": int(time.time()) + 300,
    }
    payload.update(overrides)
    return payload


def _request_with_signed_session(
    method: str,
    path: str,
    db_session: MockSession,
    payload: dict[str, object],
    json_body: dict[str, object] | None = None,
):
    previous_secret = settings.AUTH_SESSION_HMAC_SECRET

    async def scoped_db():
        yield db_session

    settings.AUTH_SESSION_HMAC_SECRET = SecretStr(TEST_SESSION_HMAC_SECRET)
    app.dependency_overrides[get_db] = scoped_db
    try:
        token = _signed_session_token(payload)
        with TestClient(app) as c:
            kwargs: dict[str, object] = {
                "headers": {"Authorization": f"Bearer {token}"}
            }
            if json_body is not None:
                kwargs["json"] = json_body
            return c.request(method, path, **kwargs)
    finally:
        settings.AUTH_SESSION_HMAC_SECRET = previous_secret
        app.dependency_overrides.clear()


@pytest.fixture
def client(dev_auth_dependency_overrides):
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, headers={"X-User-Id": "testuser"}) as c:
        yield c
    app.dependency_overrides.clear()

def test_get_and_update_tenant_config(client: TestClient, monkeypatch):
    monkeypatch.setattr(
        "api.tenant_config.validate_smtp_host",
        lambda host, *, resolve_host=True: host,
    )
    monkeypatch.setattr(
        "api.tenant_config.validate_smtp_destination",
        lambda host, port, *, resolve_host=True: (host, port),
    )
    monkeypatch.setattr(
        "api.tenant_config.validate_pop3_destination",
        lambda host, port, *, resolve_host=True: (host, port),
    )

    # Get config returns an empty response without creating a row.
    response = client.get("/api/accounts/config")
    assert response.status_code == 200
    data = response.json()
    assert data["smtp_server"] is None
    assert data["user_id"] == "testuser"

    # Update config
    update_data = {
        "smtp_server": "smtp.example.com",
        "smtp_port": 587,
        "smtp_username": "user@example.com",
        "pop3_server": "pop3.example.com",
        "pop3_port": 995,
        "pop3_username": "pop3-user",
        "pop3_password": "pop3-secret",
    }
    response = client.put("/api/accounts/config", json=update_data)
    assert response.status_code == 200
    data = response.json()
    assert data["smtp_server"] == "smtp.example.com"
    assert data["smtp_port"] == 587
    assert data["smtp_username"] == "user@example.com"
    assert data["pop3_server"] == "pop3.example.com"
    assert data["pop3_port"] == 995
    assert data["pop3_username"] == "pop3-user"
    assert data["has_pop3_password"] is True


def test_accounts_config_uses_signed_session_organization_scope(
    dev_auth_dependency_overrides, monkeypatch
):
    monkeypatch.setattr(
        "api.tenant_config.validate_smtp_host",
        lambda host, *, resolve_host=True: host,
    )
    monkeypatch.setattr(
        "api.tenant_config.validate_smtp_destination",
        lambda host, port, *, resolve_host=True: (host, port),
    )
    session = MockSession()

    async def scoped_db():
        yield session

    app.dependency_overrides[get_db] = scoped_db
    try:
        with TestClient(app, headers={"X-User-Id": "shared-user"}) as c:
            first = c.put(
                "/api/accounts/config",
                json={"smtp_server": "smtp.example.com", "smtp_port": 587},
                headers={"X-Organization-Id": "org-acme"},
            )
            second = c.put(
                "/api/accounts/config",
                json={"smtp_server": "smtp.other.com", "smtp_port": 587},
                headers={"X-Organization-Id": "org-rival"},
            )
            acme_read = c.get(
                "/api/accounts/config",
                headers={"X-Organization-Id": "org-acme"},
            )
            rival_read = c.get(
                "/api/accounts/config",
                headers={"X-Organization-Id": "org-rival"},
            )
    finally:
        app.dependency_overrides.clear()

    assert first.status_code == 200
    assert second.status_code == 200
    assert acme_read.json()["smtp_server"] == "smtp.example.com"
    assert rival_read.json()["smtp_server"] == "smtp.other.com"
    assert ("shared-user", "org-acme") in session.configs
    assert ("shared-user", "org-rival") in session.configs


@pytest.mark.parametrize("admin_role", ("system_admin", "platform_admin"))
def test_accounts_config_rejects_system_admin_mailbox_owner_session(admin_role: str):
    session = MockSession()
    payload = _valid_session_payload(
        sub="strix-admin",
        role=admin_role,
        org=None,
        workspace="workspace-system",
    )

    read_response = _request_with_signed_session(
        "GET",
        "/api/accounts/config",
        session,
        payload,
    )
    write_response = _request_with_signed_session(
        "PUT",
        "/api/accounts/config",
        session,
        payload,
        {"smtp_server": "smtp.example.com", "smtp_port": 587},
    )

    assert read_response.status_code == 401
    assert write_response.status_code == 401
    assert read_response.json()["detail"] == "Authentication required"
    assert session.execute_calls == 0
    assert session.configs == {}


def test_accounts_config_preserves_scoped_signed_member_session():
    session = MockSession()
    response = _request_with_signed_session(
        "GET",
        "/api/accounts/config",
        session,
        _valid_session_payload(),
    )

    assert response.status_code == 200
    assert response.json()["user_id"] == "mailbox-owner"
    assert response.json()["smtp_server"] is None
    assert session.execute_calls == 1


def test_accounts_config_enforces_current_user_self_access_policy(monkeypatch):
    session = MockSession()
    calls = []

    def record_self_access(target_user_id, auth_ctx, forbidden_detail):
        calls.append(
            (
                target_user_id,
                auth_ctx.user_id,
                auth_ctx.organization_id,
                forbidden_detail,
            )
        )

    monkeypatch.setattr(
        "api.accounts.ensure_mailbox_config_self_access", record_self_access
    )
    payload = _valid_session_payload(sub="mailbox-owner", org="org-acme")

    read_response = _request_with_signed_session(
        "GET",
        "/api/accounts/config",
        session,
        payload,
    )
    write_response = _request_with_signed_session(
        "PUT",
        "/api/accounts/config",
        session,
        payload,
        {},
    )

    assert read_response.status_code == 200
    assert write_response.status_code == 200
    assert calls == [
        (
            "mailbox-owner",
            "mailbox-owner",
            "org-acme",
            MAILBOX_VIEW_FORBIDDEN,
        ),
        (
            "mailbox-owner",
            "mailbox-owner",
            "org-acme",
            MAILBOX_MANAGE_FORBIDDEN,
        ),
    ]


def test_accounts_config_registers_llm_api_key_write_only(
    dev_auth_dependency_overrides,
):
    # Owner-scoped LLM API key registration: the key is write-only and the
    # response only exposes a masked presence flag, never the raw value.
    session = MockSession()

    async def scoped_db():
        yield session

    app.dependency_overrides[get_db] = scoped_db
    try:
        with TestClient(app, headers={"X-User-Id": "llm-key-owner"}) as c:
            response = c.put(
                "/api/accounts/config",
                json={"openai_api_key": "sk-live-test-key-1234"},
            )
            read_response = c.get("/api/accounts/config")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["has_openai_api_key"] is True
    assert "sk-live-test-key-1234" not in response.text
    assert read_response.status_code == 200
    assert read_response.json()["has_openai_api_key"] is True
    assert "sk-live-test-key-1234" not in read_response.text


def test_accounts_config_masked_llm_api_key_sentinel_preserves_value(
    dev_auth_dependency_overrides,
):
    session = MockSession()

    async def scoped_db():
        yield session

    app.dependency_overrides[get_db] = scoped_db
    try:
        with TestClient(app, headers={"X-User-Id": "llm-key-owner"}) as c:
            first = c.put(
                "/api/accounts/config",
                json={"openai_api_key": "sk-live-test-key-1234"},
            )
            # Saving the masked sentinel (what the UI shows for a stored
            # secret) must keep the stored key instead of overwriting it.
            second = c.put(
                "/api/accounts/config",
                json={"openai_api_key": "********"},
            )
    finally:
        app.dependency_overrides.clear()

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["has_openai_api_key"] is True
    stored = session.configs[("llm-key-owner", None)]
    assert stored.openai_api_key == "sk-live-test-key-1234"


def test_accounts_config_rejects_private_imap_host(client: TestClient):
    response = client.put(
        "/api/accounts/config",
        json={"imap_server": "127.0.0.1", "imap_port": 993},
    )

    assert response.status_code == 400
    assert "Invalid IMAP configuration" in response.json()["detail"]


def test_accounts_config_rejects_private_pop3_host(client: TestClient):
    response = client.put(
        "/api/accounts/config",
        json={"pop3_server": "127.0.0.1", "pop3_port": 995},
    )

    assert response.status_code == 400
    assert "Invalid POP3 configuration" in response.json()["detail"]


def test_accounts_config_rejects_unsafe_imap_port(client: TestClient, monkeypatch):
    def reject_imap_port(host, port, *, resolve_host=True):
        from services.email_client import validate_imap_port

        validate_imap_port(port)
        return host, port

    monkeypatch.setattr(
        "api.tenant_config.validate_imap_destination",
        reject_imap_port,
    )

    response = client.put(
        "/api/accounts/config",
        json={"imap_server": "imap.example.com", "imap_port": 22},
    )

    assert response.status_code == 400
    assert "Invalid IMAP configuration" in response.json()["detail"]


def test_accounts_config_rejects_unsafe_pop3_port(client: TestClient, monkeypatch):
    def reject_pop3_port(host, port, *, resolve_host=True):
        raise ValueError("POP3 port is not allowed")

    monkeypatch.setattr(
        "api.tenant_config.validate_pop3_destination",
        reject_pop3_port,
    )

    response = client.put(
        "/api/accounts/config",
        json={"pop3_server": "pop3.example.com", "pop3_port": 22},
    )

    assert response.status_code == 400
    assert "Invalid POP3 configuration" in response.json()["detail"]
