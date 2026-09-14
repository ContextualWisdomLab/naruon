from types import SimpleNamespace

import pytest
from fastapi import HTTPException, WebSocketException, status

from api import runner_config, runner_ws
from api.auth import AuthContext


class _ScalarResult:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


class _RunnerConfigSession:
    def __init__(self, config=None):
        self.config = config

    async def execute(self, query):
        return _ScalarResult(self.config)

    def add(self, config):
        self.config = config

    async def commit(self):
        return None

    async def refresh(self, config):
        return None


class _RunnerRegistrationResult:
    def __init__(self, token: str, workspace_id: str):
        self.token = token
        self.workspace_id = workspace_id

    def scalar_one_or_none(self):
        # Compatibility with the pre-fix implementation, which selected only
        # the token and therefore could not enforce the workspace binding.
        return self.token

    def one_or_none(self):
        return (self.token, self.workspace_id)


class _RunnerRegistrationSession:
    def __init__(self, token: str, workspace_id: str):
        self.result = _RunnerRegistrationResult(token, workspace_id)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return None

    async def execute(self, query):
        return self.result


def _auth_context(workspace_id: str) -> AuthContext:
    return AuthContext(
        user_id="admin",
        role="tenant_admin",
        organization_id="org-acme",
        group_ids=(),
        workspace_id=workspace_id,
    )


@pytest.mark.asyncio
async def test_runner_config_uses_authenticated_opaque_workspace_on_first_registration():
    db = _RunnerConfigSession()

    response = await runner_config.rotate_runner_token(
        db=db,
        auth_context=_auth_context("opaque-workspace-7"),
    )

    assert response.workspace_id == "opaque-workspace-7"
    assert db.config.workspace_id == "opaque-workspace-7"
    assert db.config.organization_id == "org-acme"


@pytest.mark.asyncio
async def test_runner_config_rejects_cross_workspace_rotation_within_same_org():
    existing = SimpleNamespace(
        organization_id="org-acme",
        workspace_id="workspace-a",
        registration_token="nrn_existing",
        updated_at=None,
    )
    db = _RunnerConfigSession(existing)

    with pytest.raises(HTTPException) as exc:
        await runner_config.rotate_runner_token(
            db=db,
            auth_context=_auth_context("workspace-b"),
        )

    assert exc.value.status_code == 409
    assert existing.registration_token == "nrn_existing"


@pytest.mark.asyncio
async def test_runner_websocket_token_is_bound_to_registered_workspace(monkeypatch):
    monkeypatch.setattr(
        runner_ws,
        "AsyncSessionLocal",
        lambda: _RunnerRegistrationSession("nrn_registered", "workspace-a"),
    )

    with pytest.raises(WebSocketException) as exc:
        await runner_ws._runner_connection_key(
            "nrn_registered",
            _auth_context("workspace-b"),
        )

    assert exc.value.code == status.WS_1008_POLICY_VIOLATION
