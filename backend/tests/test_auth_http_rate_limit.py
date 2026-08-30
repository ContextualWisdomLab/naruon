import pytest
from fastapi.testclient import TestClient

from api import auth as auth_module
from api.auth import get_auth_context, get_current_user
from main import app


def test_http_auth_limits_varying_invalid_tokens_within_one_client_scope(monkeypatch):
    """A single HTTP client scope must share one invalid-session attempt budget."""
    original_overrides = dict(app.dependency_overrides)
    app.dependency_overrides.pop(get_auth_context, None)
    app.dependency_overrides.pop(get_current_user, None)
    auth_module._session_auth_failure_buckets.clear()
    monkeypatch.setattr(
        auth_module,
        "SESSION_AUTH_SCOPE_RATE_LIMIT_MAX_FAILURES",
        3,
    )
    decode_attempts = 0

    def reject_header(token: str):
        nonlocal decode_attempts
        decode_attempts += 1
        raise auth_module.jwt.PyJWTError("invalid")

    monkeypatch.setattr(auth_module.jwt, "get_unverified_header", reject_header)

    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            for index in range(4):
                response = client.get(
                    "/api/auth/session",
                    headers={
                        "Authorization": f"Bearer invalid.jwt.token-{index}",
                        "Forwarded": f"for=198.51.100.{index}",
                        "X-Forwarded-For": f"198.51.100.{index}",
                    },
                )
                assert response.status_code == 401
                assert response.json() == {"detail": "Authentication required"}
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(original_overrides)
        auth_module._session_auth_failure_buckets.clear()

    assert decode_attempts == 3


def test_session_auth_aggregate_failure_scopes_are_isolated(monkeypatch):
    """Independent server-observed peer scopes retain independent abuse budgets."""
    auth_module._session_auth_failure_buckets.clear()
    monkeypatch.setattr(
        auth_module,
        "SESSION_AUTH_SCOPE_RATE_LIMIT_MAX_FAILURES",
        1,
    )
    verification_attempts: list[str] = []

    def reject_token(token: str):
        verification_attempts.append(token)
        raise auth_module._authentication_error()

    monkeypatch.setattr(auth_module, "_verify_signed_session_token", reject_token)

    with pytest.raises(auth_module.HTTPException):
        auth_module._verify_signed_session_payload(
            "Bearer invalid-a-1",
            failure_scope="peer:scope-a",
        )
    with pytest.raises(auth_module.HTTPException):
        auth_module._verify_signed_session_payload(
            "Bearer invalid-a-2",
            failure_scope="peer:scope-a",
        )
    with pytest.raises(auth_module.HTTPException):
        auth_module._verify_signed_session_payload(
            "Bearer invalid-b-1",
            failure_scope="peer:scope-b",
        )

    assert verification_attempts == ["invalid-a-1", "invalid-b-1"]


def test_valid_session_does_not_reset_aggregate_failure_scope(monkeypatch):
    """A valid bearer token cannot reset the coarse peer abuse-control budget."""
    auth_module._session_auth_failure_buckets.clear()
    monkeypatch.setattr(
        auth_module,
        "SESSION_AUTH_SCOPE_RATE_LIMIT_MAX_FAILURES",
        2,
    )
    verification_attempts: list[str] = []

    def verify_token(token: str):
        verification_attempts.append(token)
        if token == "valid-token":
            return {"role": "member"}, "hmac"
        raise auth_module._authentication_error()

    monkeypatch.setattr(auth_module, "_verify_signed_session_token", verify_token)

    with pytest.raises(auth_module.HTTPException):
        auth_module._verify_signed_session_payload(
            "Bearer invalid-1",
            failure_scope="peer:shared",
        )
    payload, verifier = auth_module._verify_signed_session_payload(
        "Bearer valid-token",
        failure_scope="peer:shared",
    )
    with pytest.raises(auth_module.HTTPException):
        auth_module._verify_signed_session_payload(
            "Bearer invalid-2",
            failure_scope="peer:shared",
        )
    with pytest.raises(auth_module.HTTPException):
        auth_module._verify_signed_session_payload(
            "Bearer invalid-3",
            failure_scope="peer:shared",
        )

    assert payload == {"role": "member"}
    assert verifier == "hmac"
    assert verification_attempts == ["invalid-1", "valid-token", "invalid-2"]


def test_direct_auth_context_keeps_exact_token_only_failure_budget(monkeypatch):
    """The non-HTTP verifier stays independent of peer-scoped throttling."""
    auth_module._session_auth_failure_buckets.clear()
    monkeypatch.setattr(
        auth_module,
        "SESSION_AUTH_SCOPE_RATE_LIMIT_MAX_FAILURES",
        1,
    )
    verification_attempts: list[str] = []

    def reject_token(token: str):
        verification_attempts.append(token)
        raise auth_module._authentication_error()

    monkeypatch.setattr(auth_module, "_verify_signed_session_token", reject_token)

    for token in ("direct-invalid-1", "direct-invalid-2"):
        with pytest.raises(auth_module.HTTPException):
            auth_module._verify_signed_session_payload(f"Bearer {token}")

    assert verification_attempts == ["direct-invalid-1", "direct-invalid-2"]
