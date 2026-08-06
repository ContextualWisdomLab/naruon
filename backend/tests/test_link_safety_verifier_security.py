"""Authenticated security contracts for the link safety verifier."""

import base64
import hashlib
import hmac
import json
import os
import secrets
import time

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("AUTH_SESSION_HMAC_SECRET", secrets.token_urlsafe(48))
os.environ.setdefault("DISABLE_BACKGROUND_WORKERS", "1")

from main import app


def _base64url_encode(raw: bytes) -> str:
    """Encode JWT material without Base64 padding."""
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _signed_session_token() -> str:
    """Create a short-lived authenticated member session for API contracts."""
    header_segment = _base64url_encode(
        json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode(
            "utf-8"
        )
    )
    payload_segment = _base64url_encode(
        json.dumps(
            {
                "ver": 1,
                "iss": "naruon-control-plane",
                "aud": "naruon-api",
                "sub": "link-security-test",
                "role": "member",
                "org": "org-acme",
                "groups": ["group-1"],
                "workspace": "workspace-org-acme",
                "exp": int(time.time()) + 300,
            },
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    )
    signing_input = f"{header_segment}.{payload_segment}"
    signature = hmac.new(
        os.environ["AUTH_SESSION_HMAC_SECRET"].encode("utf-8"),
        signing_input.encode("ascii"),
        hashlib.sha256,
    ).digest()
    return f"{signing_input}.{_base64url_encode(signature)}"


def _classify(url: str) -> dict[str, object]:
    """Execute the authenticated link verifier and return its result payload."""
    with TestClient(app) as client:
        response = client.post(
            "/api/tools/link_safety_verifier/execute",
            headers={"Authorization": f"Bearer {_signed_session_token()}"},
            json={"parameters": {"url": url}},
        )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    return body["result"]


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com/%2e%2e/private",
        "https:///hostless",
        "https://[malformed",
    ],
)
def test_link_safety_verifier_rejects_malformed_or_traversal_urls(url: str) -> None:
    """Encoded traversal and malformed HTTPS-looking inputs are never Low risk."""
    result = _classify(url)

    assert result["risk_level"] != "Low"


def test_link_safety_verifier_preserves_valid_https_classification() -> None:
    """A normal HTTPS URL remains Low risk after parser hardening."""
    result = _classify("https://example.com/account")

    assert result == {
        "is_https": True,
        "has_suspicious_domain": False,
        "risk_level": "Low",
    }


def test_link_safety_verifier_distinguishes_plain_http_risk() -> None:
    """A valid ordinary HTTP URL remains a bounded Medium-risk result."""
    result = _classify("http://example.com/account")

    assert result == {
        "is_https": False,
        "has_suspicious_domain": False,
        "risk_level": "Medium",
    }
