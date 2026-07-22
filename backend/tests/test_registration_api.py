"""Anonymous self-registration relay: /api/auth/register."""
from __future__ import annotations

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from api import registration as registration_module
from core.config import settings
from main import app


@pytest.fixture(autouse=True)
def _configured_relay(monkeypatch):
    monkeypatch.setattr(
        settings, "REGISTRATION_SERVICE_URL", "http://account-unification:8099"
    )
    monkeypatch.setattr(
        settings, "REGISTRATION_SERVICE_TOKEN", SecretStr("relay-token-under-test")
    )
    monkeypatch.setattr(
        settings, "ALLOWED_REGISTRATION_SERVICE_HOSTS", "account-unification"
    )
    registration_module._attempt_window_start = 0.0
    registration_module._attempt_count = 0
    yield


@pytest.fixture
def client():
    return TestClient(app)


def _submission(email="new.user@example.com", password="bootstrap-pass-1"):
    return {
        "email_address": email,
        "initial_password": password,
        "first_name": "New",
        "last_name": "User",
    }


def _relay_stub(status_code: int, captured: dict | None = None):
    async def stub(service_url, token_value, payload):
        if captured is not None:
            captured["service_url"] = service_url
            captured["token_value"] = token_value
            captured["payload"] = payload
        return httpx.Response(status_code=status_code, json={})

    return stub


def test_register_relays_to_the_identity_platform(client, monkeypatch):
    captured: dict = {}
    monkeypatch.setattr(
        registration_module,
        "submit_registration_to_service",
        _relay_stub(201, captured),
    )

    response = client.post("/api/auth/register", json=_submission())

    assert response.status_code == 200
    assert response.json() == {"email_address": "new.user@example.com"}
    assert captured["service_url"] == "http://account-unification:8099"
    assert captured["token_value"] == "relay-token-under-test"
    assert captured["payload"]["email_address"] == "new.user@example.com"


def test_register_requires_no_session(client, monkeypatch):
    monkeypatch.setattr(
        registration_module, "submit_registration_to_service", _relay_stub(201)
    )

    response = client.post(
        "/api/auth/register", json=_submission(email="anon@example.com")
    )

    assert response.status_code == 200


def test_register_maps_duplicate_email(client, monkeypatch):
    monkeypatch.setattr(
        registration_module, "submit_registration_to_service", _relay_stub(409)
    )

    response = client.post("/api/auth/register", json=_submission())

    assert response.status_code == 409
    assert response.json()["detail"]["error_code"] == "email_already_registered"


def test_register_fails_closed_when_relay_unconfigured(client, monkeypatch):
    monkeypatch.setattr(settings, "REGISTRATION_SERVICE_URL", None)

    response = client.post("/api/auth/register", json=_submission())

    assert response.status_code == 503
    assert response.json()["detail"]["error_code"] == "registration_unavailable"


def test_register_refuses_non_allowlisted_relay_host(client, monkeypatch):
    monkeypatch.setattr(
        settings, "REGISTRATION_SERVICE_URL", "http://evil.example.com:8099"
    )

    response = client.post("/api/auth/register", json=_submission())

    assert response.status_code == 503
    assert response.json()["detail"]["error_code"] == "registration_unavailable"


def test_register_rejects_malformed_email(client, monkeypatch):
    monkeypatch.setattr(
        registration_module, "submit_registration_to_service", _relay_stub(201)
    )

    response = client.post(
        "/api/auth/register", json=_submission(email="not-an-email")
    )

    assert response.status_code == 422
    assert response.json()["detail"]["error_code"] == "invalid_email_address"


def test_register_maps_relay_outage_to_unavailable(client, monkeypatch):
    async def failing_relay(service_url, token_value, payload):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(
        registration_module, "submit_registration_to_service", failing_relay
    )

    response = client.post("/api/auth/register", json=_submission())

    assert response.status_code == 503
    assert response.json()["detail"]["error_code"] == "registration_unavailable"
