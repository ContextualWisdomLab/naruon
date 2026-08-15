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
    """Encode one JWT segment without padding."""
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _signed_session_token() -> str:
    """Create a real short-lived HMAC session accepted by the private tools API."""
    now = int(time.time())
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
                "org": "checksum-contract-org",
                "groups": [],
                "workspace": "workspace-checksum-contract-org",
                "iat": now,
                "exp": now + 300,
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


def test_content_checksum_api_executes_authenticated_request() -> None:
    """Startup registration and the authenticated execute route must work together."""
    with TestClient(app) as client:
        response = client.post(
            "/api/tools/content_checksum_generator/execute",
            headers={"Authorization": f"Bearer {_signed_session_token()}"},
            json={"parameters": {"text": "abc", "algorithm": "sha256"}},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["result"]["digest_hex"] == EXPECTED_SHA256_ABC
    assert payload["result"]["byte_length"] == 3
    assert payload["message"] == "Tool executed successfully"


def test_content_checksum_api_rejects_unauthenticated_request() -> None:
    """The checksum execute route must retain the generic tools auth boundary."""
    with TestClient(app) as client:
        response = client.post(
            "/api/tools/content_checksum_generator/execute",
            json={"parameters": {"text": "abc", "algorithm": "sha256"}},
        )

    assert response.status_code == 401
    assert response.json() == {"detail": "Authentication required"}


def test_content_checksum_api_maps_invalid_algorithm_to_execute_failure() -> None:
    """Invalid tool input must use the generic ExecuteResponse failure contract."""
    with TestClient(app) as client:
        response = client.post(
            "/api/tools/content_checksum_generator/execute",
            headers={"Authorization": f"Bearer {_signed_session_token()}"},
            json={"parameters": {"text": "abc", "algorithm": "md5"}},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "failed"
    assert payload["result"] is None
    assert "Unsupported checksum algorithm" in payload["message"]
