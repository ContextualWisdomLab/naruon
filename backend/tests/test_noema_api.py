"""Signed-session tests for the in-process Noema decision API."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient
from pydantic import SecretStr

from api.auth import get_auth_context, get_current_user
from core.config import settings
from db.session import get_db
from main import app
from services.noema_agent import NoemaDecisionResult

TEST_SESSION_HMAC_SECRET = "noema-decision-hmac-material-32-bytes"  # noqa: S105


def _base64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _signed_session_token(payload: dict[str, object]) -> str:
    header_segment = _base64url_encode(
        json.dumps(
            {"alg": "HS256", "typ": "JWT"}, separators=(",", ":"), sort_keys=True
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
    return f"{signing_input}.{_base64url_encode(signature)}"


def _valid_session_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "ver": 1,
        "iss": "naruon-control-plane",
        "aud": "naruon-api",
        "sub": "alice",
        "role": "member",
        "org": "org-acme",
        "groups": [],
        "workspace": "workspace-org-acme",
        "exp": int(time.time()) + 300,
    }
    payload.update(overrides)
    return payload


def _request_with_signed_session(method: str, path: str, json_body: dict | None = None):
    previous_secret = settings.AUTH_SESSION_HMAC_SECRET
    original_overrides = dict(app.dependency_overrides)
    settings.AUTH_SESSION_HMAC_SECRET = SecretStr(TEST_SESSION_HMAC_SECRET)
    token = _signed_session_token(_valid_session_payload())
    app.dependency_overrides.pop(get_auth_context, None)
    app.dependency_overrides.pop(get_current_user, None)

    async def _fake_db():
        yield None

    app.dependency_overrides[get_db] = _fake_db
    try:
        with TestClient(app) as client:
            return client.request(
                method,
                path,
                json=json_body,
                headers={"Authorization": f"Bearer {token}"},
            )
    finally:
        settings.AUTH_SESSION_HMAC_SECRET = previous_secret
        app.dependency_overrides.clear()
        app.dependency_overrides.update(original_overrides)


def _request_without_signed_session(method: str, path: str, json_body: dict | None = None):
    original_overrides = dict(app.dependency_overrides)
    app.dependency_overrides.pop(get_auth_context, None)
    app.dependency_overrides.pop(get_current_user, None)
    try:
        with TestClient(app) as client:
            return client.request(
                method,
                path,
                json=json_body,
                headers={
                    "X-User-Id": "alice",
                    "X-Organization-Id": "org-acme",
                },
            )
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(original_overrides)


def test_noema_decision_route_rejects_public_identity_headers():
    response = _request_without_signed_session(
        "POST",
        "/api/noema/decisions",
        {"judgment_kind": "mail.triage", "prompt": "Should I reply today?"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Authentication required"


def test_noema_decision_route_returns_orchestrator_decision(monkeypatch):
    async def _fake_decision(_session, **kwargs):
        assert kwargs["user_id"] == "alice"
        assert kwargs["organization_id"] == "org-acme"
        assert kwargs["judgment_kind"] == "mail.triage"
        return NoemaDecisionResult(
            status="ok",
            judgment_kind="mail.triage",
            recommendation="Reply today with the budget confirmation.",
            rationale="The thread is waiting on a yes/no.",
            model_alias="contextual-orchestrator",
            error_code=None,
        )

    monkeypatch.setattr("api.noema.run_noema_decision", _fake_decision)
    response = _request_with_signed_session(
        "POST",
        "/api/noema/decisions",
        {"judgment_kind": "mail.triage", "prompt": "Should I reply today?"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "ok"
    assert body["judgment_kind"] == "mail.triage"
    assert body["model_alias"] == "contextual-orchestrator"
    assert body["error_code"] is None
    assert "Reply today" in body["recommendation"]


def test_noema_decision_route_rejects_unknown_judgment_kind():
    response = _request_with_signed_session(
        "POST",
        "/api/noema/decisions",
        {"judgment_kind": "does-not-exist", "prompt": "x"},
    )
    assert response.status_code == 400
    assert response.json()["error_code"] == "unknown_judgment_kind"


def test_noema_decision_route_surfaces_gateway_unavailable(monkeypatch):
    monkeypatch.setattr(
        "api.noema.run_noema_decision",
        AsyncMock(
            return_value=NoemaDecisionResult(
                status="unavailable",
                judgment_kind="judgment.decide",
                error_code="orchestrator_gateway_unavailable",
                notice="The contextual-orchestrator gateway is not configured.",
            )
        ),
    )
    response = _request_with_signed_session(
        "POST",
        "/api/noema/decisions",
        {"judgment_kind": "judgment.decide", "prompt": "Approve this change?"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "unavailable"
    assert body["error_code"] == "orchestrator_gateway_unavailable"
