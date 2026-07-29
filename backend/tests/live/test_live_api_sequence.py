"""Live HTTP smoke tests for Docker-built release candidates."""

from __future__ import annotations

import base64
import hashlib
import hmac
import http.client
import json
import os
import time
from pathlib import Path
from typing import Any

import pytest

from core.local_http import (
    LocalHTTPOrigin as _LiveHTTPOrigin,
    LocalHTTPValidationError,
    validate_local_request_target,
    validate_loopback_http_origin,
)

SESSION_COOKIE_NAME = "naruon_session"
DEFAULT_LIVE_HTTP_TIMEOUT_SECONDS = 30.0


def _validated_live_origin(value: str) -> _LiveHTTPOrigin:
    try:
        return validate_loopback_http_origin(value)
    except LocalHTTPValidationError as exc:
        raise AssertionError("LIVE_BASE_URL must be a loopback HTTP(S) origin") from exc


def _validated_live_path(path: str) -> str:
    try:
        return validate_local_request_target(path)
    except LocalHTTPValidationError as exc:
        raise AssertionError("live request path must be a local API path") from exc


@pytest.mark.parametrize(
    "value",
    [
        "http://example.com:8000",
        "http://user@127.0.0.1:8000",
        "http://127.0.0.1:8000/path",
        "http://127.0.0.1:99999",
        "http://127.0.0.1:8000\nInjected: yes",
    ],
)
def test_live_origin_rejects_untrusted_http_targets(value: str) -> None:
    with pytest.raises(AssertionError):
        _validated_live_origin(value)


def test_live_origin_and_path_preserve_loopback_api_calls() -> None:
    assert _validated_live_origin("http://localhost:18080/") == _LiveHTTPOrigin(
        origin="http://localhost:18080",
        scheme="http",
        hostname="localhost",
        port=18080,
    )
    assert _validated_live_path("/api/emails?limit=10") == "/api/emails?limit=10"
    with pytest.raises(AssertionError):
        _validated_live_path("//example.com/api/emails")


def _encode_json(value: dict[str, Any]) -> str:
    raw = json.dumps(value, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _signed_live_session_token() -> str:
    secret = os.environ.get("LIVE_E2E_SESSION_SECRET")
    if not secret:
        pytest.skip("LIVE_E2E_SESSION_SECRET is required for live API smoke")

    header = _encode_json({"alg": "HS256", "typ": "JWT"})
    payload = _encode_json(
        {
            "ver": 1,
            "iss": "naruon-control-plane",
            "aud": "naruon-api",
            "sub": "testuser",
            "role": "member",
            "org": "org-acme",
            "groups": ["group-1", "group-2"],
            "workspace": "workspace-org-acme",
            "exp": int(time.time()) + 300,
        }
    )
    signing_input = f"{header}.{payload}".encode("ascii")
    signature = (
        base64.urlsafe_b64encode(
            hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
        )
        .decode("ascii")
        .rstrip("=")
    )
    return f"{header}.{payload}.{signature}"


def _live_base_url() -> _LiveHTTPOrigin:
    live_base_url = os.environ.get("LIVE_BASE_URL")
    if not live_base_url:
        pytest.skip("LIVE_BASE_URL is required for live API smoke")
    return _validated_live_origin(live_base_url)


def _live_http_timeout_seconds() -> float:
    configured = os.environ.get("LIVE_E2E_HTTP_TIMEOUT_SECONDS")
    if not configured:
        return DEFAULT_LIVE_HTTP_TIMEOUT_SECONDS
    try:
        timeout_seconds = float(configured)
    except ValueError as exc:
        raise AssertionError("LIVE_E2E_HTTP_TIMEOUT_SECONDS must be a number") from exc
    if timeout_seconds <= 0:
        raise AssertionError("LIVE_E2E_HTTP_TIMEOUT_SECONDS must be positive")
    return timeout_seconds


def read_json(
    base_url: _LiveHTTPOrigin,
    path: str,
    token: str,
    *,
    method: str = "GET",
    body: dict[str, Any] | None = None,
    attempts: int = 12,
) -> dict[str, Any]:
    last_error: Exception | None = None
    timeout_seconds = _live_http_timeout_seconds()
    request_body = json.dumps(body).encode("utf-8") if body is not None else None
    for _ in range(attempts):
        try:
            request_path = _validated_live_path(path)
            connection_cls = (
                http.client.HTTPSConnection
                if base_url.scheme == "https"
                else http.client.HTTPConnection
            )
            connection = connection_cls(
                base_url.hostname,
                base_url.port,
                timeout=timeout_seconds,
            )
            try:
                headers = {
                    "Authorization": f"Bearer {token}",
                    "Cookie": f"{SESSION_COOKIE_NAME}={token}",
                    "Origin": base_url.origin,
                    "Referer": f"{base_url.origin}/",
                }
                if request_body is not None:
                    headers["Content-Type"] = "application/json"
                connection.request(
                    method,
                    request_path,
                    body=request_body,
                    headers=headers,
                )
                response = connection.getresponse()
                if response.status != 200:
                    raise http.client.HTTPException(
                        f"unexpected status: {response.status}"
                    )
                return json.loads(response.read().decode("utf-8"))
            finally:
                connection.close()
        except (OSError, http.client.HTTPException) as exc:
            last_error = exc
            time.sleep(1)
    raise AssertionError("live endpoint unavailable") from last_error


def test_live_api_sequence_uses_real_http() -> None:
    live_base_url = _live_base_url()
    token = _signed_live_session_token()
    for _ in range(12):
        inbox = read_json(live_base_url, "/api/emails", token)
        subjects = {item.get("subject") for item in inbox["emails"]}
        if "Live E2E Release" in subjects:
            return
        time.sleep(1)
    raise AssertionError("seeded live email was not observed in time")


def test_live_search_handles_local_embedding_dimension() -> None:
    live_base_url = _live_base_url()
    token = _signed_live_session_token()
    search_results = read_json(
        live_base_url,
        "/api/search",
        token,
        method="POST",
        body={"query": "Live E2E Release", "limit": 3},
        attempts=3,
    )

    subjects = {item.get("subject") for item in search_results["results"]}
    assert "Live E2E Release" in subjects


def test_live_harness_forbids_in_process_clients_and_mocks() -> None:
    live_root = Path(__file__).resolve().parent
    forbidden_terms = ("TestClient", "ASGITransport", "unittest.mock")
    offenders: list[str] = []
    for path in sorted(live_root.glob("*.py")):
        if path.name == "test_live_api_sequence.py":
            continue
        source = path.read_text(encoding="utf-8")
        offenders.extend(term for term in forbidden_terms if term in source)

    assert offenders == []


def test_live_harness_avoids_broad_url_opener_pattern() -> None:
    source = Path(__file__).read_text(encoding="utf-8")
    unsafe_terms = (".".join(("urllib", "request")), "".join(("url", "open")))

    for unsafe_term in unsafe_terms:
        assert unsafe_term not in source
