"""Service-audience authentication tests for calendar projection reads."""

from __future__ import annotations

import datetime
import json

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException

from api import auth as auth_module
from api.calendar_projection_auth import (
    CALENDAR_PROJECTION_AUDIENCE,
    CALENDAR_PROJECTION_REQUIRED_SCOPE,
    decode_calendar_projection_service_token,
)
from core.config import settings


def _signing_material() -> tuple[object, object]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk_payload = json.loads(
        jwt.algorithms.RSAAlgorithm.to_jwk(private_key.public_key())
    )
    jwk_payload.update(
        {
            "kid": "calendar-projection-key",
            "alg": "RS256",
            "use": "sig",
        }
    )
    return private_key, jwt.PyJWK.from_dict(jwk_payload)


def _service_token(
    private_key: object,
    *,
    audience: str = CALENDAR_PROJECTION_AUDIENCE,
    scope: str = CALENDAR_PROJECTION_REQUIRED_SCOPE,
    organization_id: str = "org-acme",
    workspace_id: str = "workspace-org-acme",
    subject: str = "service-lineageweave",
) -> str:
    now = datetime.datetime.now(datetime.timezone.utc)
    return jwt.encode(
        {
            "iss": "https://identity.example/realms/cwl",
            "aud": audience,
            "sub": subject,
            "organization_id": organization_id,
            "workspace_id": workspace_id,
            "scope": scope,
            "iat": int(now.timestamp()),
            "exp": int((now + datetime.timedelta(minutes=5)).timestamp()),
        },
        private_key,
        algorithm="RS256",
        headers={"kid": "calendar-projection-key"},
    )


@pytest.fixture
def configured_service_auth(monkeypatch: pytest.MonkeyPatch):
    private_key, signing_key = _signing_material()
    monkeypatch.setattr(
        settings,
        "OIDC_ISSUER_URL",
        "https://identity.example/realms/cwl",
    )
    monkeypatch.setattr(
        auth_module,
        "_cached_oidc_signing_keys",
        (signing_key,),
    )
    return private_key


def test_decode_calendar_projection_service_token_returns_scoped_context(
    configured_service_auth,
) -> None:
    token = _service_token(configured_service_auth)

    context = decode_calendar_projection_service_token(token)

    assert context.service_subject == "service-lineageweave"
    assert context.organization_id == "org-acme"
    assert context.workspace_id == "workspace-org-acme"
    assert context.audience == CALENDAR_PROJECTION_AUDIENCE
    assert context.scopes == frozenset({CALENDAR_PROJECTION_REQUIRED_SCOPE})


@pytest.mark.parametrize(
    ("override", "value"),
    [
        ("audience", "naruon-api"),
        ("scope", "calendar:write"),
        ("organization_id", ""),
        ("workspace_id", "contains whitespace"),
        ("subject", "https://identity.example/service"),
    ],
)
def test_decode_calendar_projection_service_token_rejects_wrong_contract_claims(
    configured_service_auth,
    override: str,
    value: str,
) -> None:
    token = _service_token(
        configured_service_auth,
        **{override: value},
    )

    with pytest.raises(HTTPException) as captured:
        decode_calendar_projection_service_token(token)

    assert captured.value.status_code == 401
    assert captured.value.detail == "Calendar projection service authentication failed"


def test_decode_calendar_projection_service_token_fails_closed_without_oidc(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "OIDC_ISSUER_URL", None)
    monkeypatch.setattr(auth_module, "_cached_oidc_signing_keys", ())

    with pytest.raises(HTTPException) as captured:
        decode_calendar_projection_service_token("opaque-secret")

    assert captured.value.status_code == 503
    assert captured.value.detail == "Calendar projection service authentication unavailable"


def test_decode_calendar_projection_service_token_rejects_duplicate_key_identity(
    configured_service_auth,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _private_key, duplicate_key = _signing_material()
    duplicate_key._jwk_data["kid"] = "calendar-projection-key"  # type: ignore[attr-defined]
    monkeypatch.setattr(
        auth_module,
        "_cached_oidc_signing_keys",
        (*auth_module._cached_oidc_signing_keys, duplicate_key),
    )
    token = _service_token(configured_service_auth)

    with pytest.raises(HTTPException) as captured:
        decode_calendar_projection_service_token(token)

    assert captured.value.status_code == 401
