"""Regression tests for backend browser-origin CSRF enforcement."""

from fastapi.testclient import TestClient

import main


client = TestClient(main.app)


def test_trusted_browser_origin_rejects_missing_origin() -> None:
    """A missing browser origin is never itself evidence of a trusted origin."""
    assert main._is_trusted_browser_origin(None) is False


def test_browser_state_change_without_origin_or_referer_is_rejected() -> None:
    """Browser fetch metadata cannot substitute for same-origin evidence."""
    response = client.put(
        "/api/accounts/config",
        headers={"Sec-Fetch-Site": "same-origin"},
        json={"smtp_server": "mail.example.com"},
    )

    assert response.status_code == 403
    assert response.json() == {"error_code": "csrf_origin_rejected"}


def test_non_browser_headerless_state_change_still_reaches_authentication() -> None:
    """Non-browser API clients may omit browser headers but must still authenticate."""
    response = client.put(
        "/api/accounts/config",
        json={"smtp_server": "mail.example.com"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Authentication required"}
