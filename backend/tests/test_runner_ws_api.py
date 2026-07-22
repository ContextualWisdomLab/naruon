import asyncio
import base64
import hashlib
import hmac
import json
import os
import time

import pytest
from fastapi import WebSocketException, status
from fastapi.testclient import TestClient
from pydantic import SecretStr
from starlette.websockets import WebSocketDisconnect

from api import runner_ws
from api.auth import AuthContext
from core.config import settings
from main import app

TEST_SESSION_HMAC_SECRET = os.environ["AUTH_SESSION_HMAC_SECRET"]


class _MockResult:
    def __init__(self, token: str | None):
        self.token = token

    def scalar_one_or_none(self):
        return self.token


class _MockRunnerSession:
    def __init__(self, token: str | None):
        self.token = token

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return None

    async def execute(self, query):
        return _MockResult(self.token)


class _FailingSendWebSocket:
    headers: dict[str, str]

    def __init__(self):
        authorization = _valid_session_headers()["Authorization"]
        self.headers = {"authorization": authorization}

    async def accept(self):
        return None

    async def receive_text(self):
        return "ping"

    async def send_text(self, text: str):
        raise RuntimeError("simulated runner send failure")


class _AcceptOnlyWebSocket:
    async def accept(self):
        return None


class _RecordingWebSocket:
    def __init__(self):
        self.accepted = False
        self.sent: list[str] = []
        self.send_event = asyncio.Event()
        self.close_code: int | None = None
        self.close_reason: str | None = None

    async def accept(self):
        self.accepted = True

    async def send_text(self, text: str):
        self.sent.append(text)
        self.send_event.set()

    async def close(self, *, code: int, reason: str):
        self.close_code = code
        self.close_reason = reason


def _base64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _signed_session_token(payload: dict[str, object]) -> str:
    header_segment = _base64url_encode(
        json.dumps(
            {"alg": "HS256", "typ": "JWT"},
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    )
    payload_segment = _base64url_encode(
        json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    )
    signing_input = f"{header_segment}.{payload_segment}"
    signature = hmac.new(
        TEST_SESSION_HMAC_SECRET.encode("utf-8"),
        signing_input.encode("ascii"),
        hashlib.sha256,
    ).digest()
    return f"{header_segment}.{payload_segment}.{_base64url_encode(signature)}"


def _valid_session_headers() -> dict[str, str]:
    settings.AUTH_SESSION_HMAC_SECRET = SecretStr(TEST_SESSION_HMAC_SECRET)
    token = _signed_session_token(
        {
            "ver": 1,
            "iss": "naruon-control-plane",
            "aud": "naruon-api",
            "sub": "alice",
            "role": "member",
            "org": "org-acme",
            "groups": ["group-1"],
            "workspace": "workspace-org-acme",
            "exp": int(time.time()) + 300,
        }
    )
    return {"Authorization": f"Bearer {token}"}


def _auth_context() -> AuthContext:
    return AuthContext(
        user_id="alice",
        role="member",
        organization_id="org-acme",
        group_ids=("group-1",),
        workspace_id="workspace-org-acme",
    )


@pytest.fixture(autouse=True)
def restore_session_secret(monkeypatch):
    previous_secret = settings.AUTH_SESSION_HMAC_SECRET
    runner_ws.manager.reset()

    async def noop_record_connector_signal_event(**kwargs):
        return None

    monkeypatch.setattr(
        runner_ws,
        "record_connector_signal_event",
        noop_record_connector_signal_event,
    )
    yield
    runner_ws.manager.reset()
    settings.AUTH_SESSION_HMAC_SECRET = previous_secret


@pytest.mark.asyncio
async def test_runner_connection_key_validates_registered_token(monkeypatch):
    monkeypatch.setattr(
        runner_ws,
        "AsyncSessionLocal",
        lambda: _MockRunnerSession("nrn_registered-token"),
    )

    connection_key = await runner_ws._runner_connection_key(
        "nrn_registered-token", _auth_context()
    )

    assert connection_key.startswith("org-acme:")
    assert "nrn_registered-token" not in connection_key


@pytest.mark.asyncio
async def test_runner_connection_key_rejects_unknown_token(monkeypatch):
    monkeypatch.setattr(
        runner_ws,
        "AsyncSessionLocal",
        lambda: _MockRunnerSession("nrn_registered-token"),
    )

    with pytest.raises(WebSocketException) as exc:
        await runner_ws._runner_connection_key("nrn_other-token", _auth_context())

    assert exc.value.code == status.WS_1008_POLICY_VIOLATION


def test_runner_ws_rejects_missing_auth():
    with TestClient(app) as client:
        with pytest.raises(WebSocketDisconnect) as exc:
            with client.websocket_connect("/ws/runner/nrn_registered-token"):
                pass

    assert exc.value.status_code == 401


def test_runner_ws_route_uses_signed_session_dependency():
    with TestClient(app) as client:
        with pytest.raises(WebSocketDisconnect) as exc:
            with client.websocket_connect("/ws/runner/nrn_registered-token"):
                pass

    assert exc.value.status_code == 401


def test_runner_ws_accepts_signed_session_and_registered_token(monkeypatch):
    async def registered_key(token: str, auth_context: AuthContext) -> str:
        assert token == "nrn_registered-token"
        assert auth_context.organization_id == "org-acme"
        return "org-acme:registered"

    monkeypatch.setattr(runner_ws, "_runner_connection_key", registered_key)

    with TestClient(app) as client:
        with client.websocket_connect(
            "/ws/runner/nrn_registered-token", headers=_valid_session_headers()
        ) as websocket:
            websocket.send_text("ping")
            assert websocket.receive_text() == "Naruon ack: ping"
            snapshot = runner_ws.manager.snapshot("org-acme", "workspace-org-acme")
            assert snapshot.connection_state == "connected"
            assert snapshot.active_connection_count == 1
            assert snapshot.last_seen_at is not None
            assert snapshot.last_disconnect_at is None
            assert "nrn_registered-token" not in str(runner_ws.manager.connection_records)

    snapshot = runner_ws.manager.snapshot("org-acme", "workspace-org-acme")
    assert snapshot.connection_state == "not_connected"
    assert snapshot.active_connection_count == 0
    assert snapshot.last_disconnect_at is not None


def test_runner_snapshot_keeps_latest_touch_after_connected_at():
    runner_ws.manager.connection_records["org-acme:token-fingerprint"] = (
        runner_ws.RunnerConnectionRecord(
            organization_id="org-acme",
            workspace_id="workspace-org-acme",
            connected_at="2026-05-27T12:00:00Z",
        )
    )
    runner_ws.manager.last_seen_by_org["org-acme"] = "2026-05-27T12:01:00Z"

    snapshot = runner_ws.manager.snapshot("org-acme", "workspace-org-acme")

    assert snapshot.last_seen_at == "2026-05-27T12:01:00Z"


@pytest.mark.asyncio
async def test_runner_manager_records_durable_signal_events(monkeypatch):
    recorded_events: list[dict[str, str]] = []

    async def capture_connector_signal_event(**event):
        recorded_events.append(event)

    monkeypatch.setattr(
        runner_ws,
        "record_connector_signal_event",
        capture_connector_signal_event,
    )

    connection_id = await runner_ws.manager.connect(
        _AcceptOnlyWebSocket(),
        "org-acme:registered",
        _auth_context(),
    )
    await runner_ws.manager.touch(connection_id)
    await runner_ws.manager.disconnect(connection_id)

    assert [event["state_code"] for event in recorded_events] == [
        "connected",
        "heartbeat",
        "disconnected",
    ]
    assert {event["signal_key"] for event in recorded_events} == {
        "connector_heartbeat"
    }
    assert all(event["organization_id"] == "org-acme" for event in recorded_events)
    assert all(
        event["workspace_id"] == "workspace-org-acme" for event in recorded_events
    )
    assert "nrn_registered-token" not in str(recorded_events)


@pytest.mark.asyncio
async def test_runner_replacement_cannot_be_removed_by_stale_disconnect():
    manager = runner_ws.ConnectionManager()
    first = _RecordingWebSocket()
    replacement = _RecordingWebSocket()

    first_id = await manager.connect(first, "org-acme:registered", _auth_context())
    replacement_id = await manager.connect(
        replacement,
        "org-acme:registered",
        _auth_context(),
    )

    assert first_id != replacement_id
    assert first_id not in manager.active_connections
    assert manager.active_connections[replacement_id] is replacement
    assert first.close_code == status.WS_1008_POLICY_VIOLATION
    assert first.close_reason == "Runner connection replaced"

    await manager.disconnect(first_id)

    assert manager.active_connections[replacement_id] is replacement
    assert manager.snapshot(
        "org-acme", "workspace-org-acme"
    ).active_connection_count == 1


@pytest.mark.asyncio
async def test_runner_response_is_bound_to_dispatching_connection():
    manager = runner_ws.ConnectionManager()
    expected = _RecordingWebSocket()
    other = _RecordingWebSocket()
    expected_id = await manager.connect(
        expected,
        "org-acme:registered",
        _auth_context(),
    )
    other_id = await manager.connect(
        other,
        "org-rival:registered",
        AuthContext(
            user_id="mallory",
            role="member",
            organization_id="org-rival",
            group_ids=(),
            workspace_id="workspace-org-rival",
        ),
    )

    dispatch = asyncio.create_task(
        manager.dispatch_command(
            "org-acme",
            "workspace-org-acme",
            {"action": "probe"},
            timeout_seconds=1,
            schedule_retry=False,
        )
    )
    await asyncio.wait_for(expected.send_event.wait(), timeout=1)
    request_id = json.loads(expected.sent[0])["request_id"]
    injected = json.dumps(
        {"request_id": request_id, "status": "ok", "result": "injected"}
    )

    assert await manager.handle_runner_message(other_id, injected) is False
    assert dispatch.done() is False
    expected_response = json.dumps(
        {"request_id": request_id, "status": "ok", "result": "expected"}
    )
    assert await manager.handle_runner_message(expected_id, expected_response) is True
    assert (await dispatch)["result"] == "expected"


@pytest.mark.asyncio
async def test_runner_duplicate_request_id_does_not_replace_pending_waiter():
    manager = runner_ws.ConnectionManager()
    websocket = _RecordingWebSocket()
    connection_id = await manager.connect(
        websocket,
        "org-acme:registered",
        _auth_context(),
    )
    command = {"action": "probe", "request_id": "stable-request"}

    first_dispatch = asyncio.create_task(
        manager.dispatch_command(
            "org-acme",
            "workspace-org-acme",
            command,
            timeout_seconds=1,
            schedule_retry=False,
        )
    )
    await asyncio.wait_for(websocket.send_event.wait(), timeout=1)
    second_response = await manager.dispatch_command(
        "org-acme",
        "workspace-org-acme",
        command,
        timeout_seconds=1,
    )

    assert second_response["status"] == "error"
    assert second_response["error"] == "runner_request_conflict"
    assert second_response["error_code"] == "runner_request_conflict"
    assert second_response["provider_write_executed"] is False
    assert "retry_item_uid" not in second_response
    assert await manager.handle_runner_message(
        connection_id,
        json.dumps({"request_id": "stable-request", "status": "ok"}),
    )
    assert await first_dispatch == {"request_id": "stable-request", "status": "ok"}


@pytest.mark.asyncio
async def test_runner_revocation_closes_socket_and_fails_pending_commands():
    manager = runner_ws.ConnectionManager()
    websocket = _RecordingWebSocket()
    await manager.connect(websocket, "org-acme:registered", _auth_context())
    dispatch = asyncio.create_task(
        manager.dispatch_command(
            "org-acme",
            "workspace-org-acme",
            {"action": "probe"},
            timeout_seconds=1,
            schedule_retry=False,
        )
    )
    await asyncio.wait_for(websocket.send_event.wait(), timeout=1)

    revoked_count = await manager.revoke_organization_connections("org-acme")

    assert revoked_count == 1
    assert websocket.close_code == status.WS_1008_POLICY_VIOLATION
    assert websocket.close_reason == "Runner credentials rotated"
    dispatch_response = await dispatch
    assert dispatch_response["status"] == "error"
    assert dispatch_response["error"] == "runner_connection_revoked"
    assert dispatch_response["error_code"] == "runner_connection_revoked"
    assert dispatch_response["provider_write_executed"] is False
    assert manager.snapshot(
        "org-acme", "workspace-org-acme"
    ).connection_state == "not_connected"


@pytest.mark.asyncio
async def test_runner_endpoint_disconnects_on_send_errors(monkeypatch):
    async def registered_key(token: str, auth_context: AuthContext) -> str:
        assert token == "nrn_registered-token"
        assert auth_context.organization_id == "org-acme"
        return "org-acme:registered"

    monkeypatch.setattr(runner_ws, "_runner_connection_key", registered_key)

    with pytest.raises(RuntimeError, match="simulated runner send failure"):
        await runner_ws.runner_endpoint(_FailingSendWebSocket(), "nrn_registered-token")

    snapshot = runner_ws.manager.snapshot("org-acme", "workspace-org-acme")
    assert snapshot.connection_state == "not_connected"
    assert snapshot.active_connection_count == 0
    assert snapshot.last_disconnect_at is not None
