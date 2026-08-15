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
        raising=False,
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
                    headers={"Authorization": f"Bearer invalid.jwt.token-{index}"},
                )
                assert response.status_code == 401
                assert response.json() == {"detail": "Authentication required"}
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(original_overrides)
        auth_module._session_auth_failure_buckets.clear()

    assert decode_attempts == 3
