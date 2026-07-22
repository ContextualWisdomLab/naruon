from fastapi.testclient import TestClient
import pytest

from api import runner_config as runner_config_api
from core.config import settings
from db.models import WorkspaceRunnerConfig
from db.session import get_db
from main import app

pytestmark = pytest.mark.usefixtures("dev_auth_dependency_overrides")


class MockResult:
    def __init__(self, obj):
        self.obj = obj

    def scalar_one_or_none(self):
        return self.obj


class MockAsyncSession:
    def __init__(self):
        self.runner = None

    async def execute(self, query):
        return MockResult(self.runner)

    def add(self, obj):
        if isinstance(obj, WorkspaceRunnerConfig):
            obj.id = 1
            self.runner = obj

    async def commit(self):
        pass

    async def refresh(self, obj):
        pass


@pytest.fixture
def mock_db():
    return MockAsyncSession()


@pytest.fixture
def member_client(mock_db):
    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(
            app, headers={"X-User-Id": "testuser", "X-Organization-Id": "org-acme"}
        ) as c:
            yield c
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def admin_client(mock_db):
    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(
            app,
            headers={
                "X-User-Id": "admin",
                "X-User-Role": "tenant_admin",
                "X-Organization-Id": "org-acme",
            },
        ) as c:
            yield c
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def second_org_admin_client(mock_db):
    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(
            app,
            headers={
                "X-User-Id": "org-admin-2",
                "X-User-Role": "tenant_admin",
                "X-Organization-Id": "org-acme",
            },
        ) as c:
            yield c
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def system_admin_client(mock_db):
    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(
            app,
            headers={
                "X-User-Id": "platform-root",
                "X-User-Role": "system_admin",
                "X-Organization-Id": "org-acme",
            },
        ) as c:
            yield c
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_member_cannot_manage_runner_config(member_client):
    response = member_client.get("/api/runner-config")
    assert response.status_code == 403

    response = member_client.post("/api/runner-config/rotate")
    assert response.status_code == 403


def test_org_scoped_runner_config_uses_shared_workspace(
    admin_client, second_org_admin_client, mock_db
):
    rotate_response = admin_client.post("/api/runner-config/rotate")
    assert rotate_response.status_code == 200
    rotate_data = rotate_response.json()
    assert rotate_data["workspace_id"] == "workspace-org-acme"
    assert rotate_data["configured"] is True
    assert rotate_data["fingerprint"] is not None
    assert "registration_token" not in rotate_data
    assert mock_db.runner.organization_id == "org-acme"

    read_response = second_org_admin_client.get("/api/runner-config")
    assert read_response.status_code == 200
    read_data = read_response.json()
    assert read_data["workspace_id"] == "workspace-org-acme"
    assert read_data["configured"] is True
    assert read_data["fingerprint"] is not None
    assert "registration_token" not in read_data


def test_runner_config_exposes_outbound_connector_manifest(admin_client):
    response = admin_client.get("/api/runner-config")

    assert response.status_code == 200
    data = response.json()
    assert data["connector_manifest"] == {
        "role": "self-hosted_connector",
        "network_mode": "outbound_only",
        "control_plane_domain": "naruon.net",
        "local_protocols": ["imap", "pop3", "smtp", "caldav", "carddav", "webdav"],
        "prohibited_roles": ["smtp_server", "imap_server", "mx_host"],
        "runner_usage": "ci_smoke_only",
    }


def test_runner_config_uses_configured_control_plane_domain(admin_client):
    previous_domain = settings.CONTROL_PLANE_DOMAIN
    settings.CONTROL_PLANE_DOMAIN = "staging.naruon.net"
    try:
        response = admin_client.get("/api/runner-config")
    finally:
        settings.CONTROL_PLANE_DOMAIN = previous_domain

    assert response.status_code == 200
    assert (
        response.json()["connector_manifest"]["control_plane_domain"]
        == "staging.naruon.net"
    )


def test_runner_rotation_includes_connector_bootstrap_contract(
    admin_client, monkeypatch
):
    revoked_organizations: list[str] = []

    async def revoke_connections(organization_id: str) -> int:
        revoked_organizations.append(organization_id)
        return 1

    monkeypatch.setattr(
        runner_config_api.runner_connection_manager,
        "revoke_organization_connections",
        revoke_connections,
    )

    response = admin_client.post("/api/runner-config/rotate")

    assert response.status_code == 200
    data = response.json()
    assert "registration_token" not in data
    assert data["connector_manifest"]["network_mode"] == "outbound_only"
    assert data["connector_manifest"]["control_plane_domain"] == "naruon.net"
    assert "registration_token" not in data["connector_manifest"]
    assert revoked_organizations == ["org-acme"]


def test_system_admin_can_manage_runner_config(system_admin_client):
    rotate_response = system_admin_client.post("/api/runner-config/rotate")
    assert rotate_response.status_code == 200
    assert rotate_response.json()["workspace_id"] == "workspace-org-acme"


def test_org_admin_without_org_scope_is_rejected(mock_db):
    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(
            app,
            headers={
                "X-User-Id": "admin",
                "X-User-Role": "tenant_admin",
            },
        ) as client:
            response = client.get("/api/runner-config")
            assert response.status_code == 403
            assert response.json()["detail"] == "Organization scope is required"
    finally:
        app.dependency_overrides.pop(get_db, None)
