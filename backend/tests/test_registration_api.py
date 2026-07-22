"""Anonymous self-registration relay: /api/auth/register."""

from __future__ import annotations

import socket

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from api import registration as registration_module
from core import url_validation as url_validation_module
from core.config import settings
from main import app


@pytest.fixture(autouse=True)
def _configured_relay(monkeypatch):
    monkeypatch.setattr(
        settings, "REGISTRATION_SERVICE_URL", "https://registration.example.com"
    )
    monkeypatch.setattr(
        settings, "REGISTRATION_SERVICE_TOKEN", SecretStr("relay-token-under-test")
    )
    monkeypatch.setattr(
        settings, "ALLOWED_REGISTRATION_SERVICE_HOSTS", "registration.example.com"
    )
    monkeypatch.setattr(settings, "ALLOW_LOCAL_REGISTRATION_SERVICE", False)
    monkeypatch.setattr(
        url_validation_module.socket,
        "getaddrinfo",
        lambda host, port, type: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", port))
        ],
    )
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
    async def stub(target, payload):
        if captured is not None:
            captured["target"] = target
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
    assert captured["target"].endpoint_url == (
        "https://registration.example.com/registration/accounts"
    )
    assert captured["target"].token_value == "relay-token-under-test"
    assert captured["target"].addresses == ("8.8.8.8",)
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


@pytest.mark.parametrize(
    "service_url",
    [
        "https://evil.example.com",
        "https://registration.example.com.evil.example",
    ],
)
def test_register_refuses_non_allowlisted_relay_host(client, monkeypatch, service_url):
    monkeypatch.setattr(settings, "REGISTRATION_SERVICE_URL", service_url)

    response = client.post("/api/auth/register", json=_submission())

    assert response.status_code == 503
    assert response.json()["detail"]["error_code"] == "registration_unavailable"


@pytest.mark.parametrize(
    "email",
    [
        "not-an-email",
        "two@@example.com",
        "missing-domain@",
        "missing-local.example.com",
        "dotless@example",
        "leading-dot@.example.com",
        "trailing-dot@example.com.",
        "space @example.com",
        "consecutive..dots@example.com",
        "hyphen@-example.com",
        "!@!." + "!." * 60,
    ],
)
def test_register_rejects_malformed_email(client, monkeypatch, email):
    monkeypatch.setattr(
        registration_module, "submit_registration_to_service", _relay_stub(201)
    )

    response = client.post("/api/auth/register", json=_submission(email=email))

    assert response.status_code == 422
    assert response.json()["detail"]["error_code"] == "invalid_email_address"


def test_register_maps_relay_outage_to_unavailable(client, monkeypatch):
    async def failing_relay(target, payload):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(
        registration_module, "submit_registration_to_service", failing_relay
    )

    response = client.post("/api/auth/register", json=_submission())

    assert response.status_code == 503
    assert response.json()["detail"]["error_code"] == "registration_unavailable"


def test_register_maps_upstream_rate_limit(client, monkeypatch):
    monkeypatch.setattr(
        registration_module, "submit_registration_to_service", _relay_stub(429)
    )

    response = client.post("/api/auth/register", json=_submission())

    assert response.status_code == 429
    assert response.json()["detail"]["error_code"] == "registration_rate_limited"


def test_register_does_not_apply_a_process_global_rate_limit(client, monkeypatch):
    monkeypatch.setattr(
        registration_module, "submit_registration_to_service", _relay_stub(201)
    )

    responses = [
        client.post("/api/auth/register", json=_submission()) for _ in range(35)
    ]

    assert {response.status_code for response in responses} == {200}


@pytest.mark.parametrize(
    "service_url",
    [
        "http://registration.example.com",
        "ftp://registration.example.com",
        "https://user:password@registration.example.com",
        "https://registration.example.com/unexpected",
        "https://registration.example.com?unexpected=true",
        "https://registration.example.com#unexpected",
        "https://registration.example.com\\@evil.example.com",
        "https://registration.example.com\n@evil.example.com",
    ],
)
def test_register_refuses_unsafe_relay_base_urls(client, monkeypatch, service_url):
    monkeypatch.setattr(settings, "REGISTRATION_SERVICE_URL", service_url)

    response = client.post("/api/auth/register", json=_submission())

    assert response.status_code == 503
    assert response.json()["detail"]["error_code"] == "registration_unavailable"


def test_register_allows_explicit_compose_local_relay(client, monkeypatch):
    captured: dict = {}
    monkeypatch.setattr(
        settings, "REGISTRATION_SERVICE_URL", "http://account-unification:8099"
    )
    monkeypatch.setattr(
        settings, "ALLOWED_REGISTRATION_SERVICE_HOSTS", "account-unification"
    )
    monkeypatch.setattr(settings, "ALLOW_LOCAL_REGISTRATION_SERVICE", True)
    monkeypatch.setattr(
        url_validation_module.socket,
        "getaddrinfo",
        lambda host, port, type: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.20.0.8", port))
        ],
    )
    monkeypatch.setattr(
        registration_module,
        "submit_registration_to_service",
        _relay_stub(201, captured),
    )

    response = client.post("/api/auth/register", json=_submission())

    assert response.status_code == 200
    assert captured["target"].endpoint_url == (
        "http://account-unification:8099/registration/accounts"
    )
    assert captured["target"].addresses == ("10.20.0.8",)


def test_register_refuses_compose_local_relay_without_opt_in(client, monkeypatch):
    monkeypatch.setattr(
        settings, "REGISTRATION_SERVICE_URL", "http://account-unification:8099"
    )
    monkeypatch.setattr(
        settings, "ALLOWED_REGISTRATION_SERVICE_HOSTS", "account-unification"
    )

    response = client.post("/api/auth/register", json=_submission())

    assert response.status_code == 503
    assert response.json()["detail"]["error_code"] == "registration_unavailable"


@pytest.mark.asyncio
async def test_registration_submit_uses_validated_pinned_transport(monkeypatch):
    captured: dict = {}

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return False

        async def post(self, url, **kwargs):
            captured["url"] = url
            captured["request"] = kwargs
            return httpx.Response(status_code=201, json={})

    def fake_builder(**kwargs):
        captured["builder"] = kwargs
        return FakeClient()

    monkeypatch.setattr(
        registration_module, "build_pinned_validated_url_async_client", fake_builder
    )
    target = registration_module.RegistrationRelayTarget(
        endpoint_url="https://registration.example.com/registration/accounts",
        token_value="relay-token-under-test",
        hostname="registration.example.com",
        port=443,
        addresses=("8.8.8.8", "1.1.1.1"),
    )

    response = await registration_module.submit_registration_to_service(
        target, _submission()
    )

    assert response.status_code == 201
    assert captured["builder"] == {
        "normalized_url": target.endpoint_url,
        "hostname": target.hostname,
        "port": target.port,
        "addresses": target.addresses,
    }
    assert captured["url"] == target.endpoint_url
    assert captured["request"]["headers"] == {
        "Authorization": "Bearer relay-token-under-test"
    }
