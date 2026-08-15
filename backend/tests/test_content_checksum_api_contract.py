"""Public API contract tests for the bounded content-checksum tool."""

import base64
import hashlib
import hmac
import json
import os
import secrets
import time

from fastapi.testclient import TestClient

os.environ.setdefault("AUTH_SESSION_HMAC_SECRET", secrets.token_urlsafe(48))

from main import app


EXPECTED_SHA256_ABC = (
    "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
)


def _base64url_encode(raw: bytes) -> str:
    """Encode JWT bytes using unpadded base64url."""
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _signed_session_token() -> str:
    """Build a short-lived session token accepted by the real auth dependency."""
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
                "sub": "checksum-contract-user",
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


def test_checksum_execute_route_requires_authenticated_session() -> None:
    """The private checksum endpoint must reject requests without auth."""
    with TestClient(app) as client:
        response = client.post(
            "/api/tools/content_checksum_generator/execute",
            json={"parameters": {"text": "abc", "algorithm": "sha256"}},
        )

    assert response.status_code == 401
    assert response.json() == {"detail": "Authentication required"}


def test_checksum_execute_route_returns_authenticated_digest() -> None:
    """Startup must expose the checksum tool through the documented envelope."""
    with TestClient(app) as client:
        response = client.post(
            "/api/tools/content_checksum_generator/execute",
            headers={"Authorization": f"Bearer {_signed_session_token()}"},
            json={"parameters": {"text": "abc", "algorithm": "sha256"}},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["message"] is None
    assert payload["result"]["algorithm_code"] == "sha256"
    assert payload["result"]["digest_hex"] == EXPECTED_SHA256_ABC
    assert payload["result"]["byte_length"] == 3
    assert payload["result"]["encoding_code"] == "utf-8"


def test_checksum_execute_route_maps_invalid_algorithm_to_execute_failure() -> None:
    """Tool validation failures must use the generic ExecuteResponse contract."""
    with TestClient(app) as client:
        response = client.post(
            "/api/tools/content_checksum_generator/execute",
            headers={"Authorization": f"Bearer {_signed_session_token()}"},
            json={"parameters": {"text": "abc", "algorithm": "sha1"}},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "failed"
    assert payload["result"] is None
    assert "Unsupported checksum algorithm" in payload["message"]
