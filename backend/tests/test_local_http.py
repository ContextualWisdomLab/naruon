import pytest
import urllib.parse
from unittest.mock import patch

from core.local_http import (
    LocalHTTPOrigin,
    LocalHTTPValidationError,
    validate_local_request_target,
    validate_loopback_http_origin,
)


def test_loopback_origin_is_canonicalized() -> None:
    assert validate_loopback_http_origin("http://[::1]:18080/") == LocalHTTPOrigin(
        origin="http://[::1]:18080",
        scheme="http",
        hostname="::1",
        port=18080,
    )


@pytest.mark.parametrize(
    "value",
    [
        "http://[::1",
        "http://[localhost]:18080",
    ],
)
def test_loopback_origin_normalizes_malformed_parser_errors(value: str) -> None:
    with pytest.raises(
        LocalHTTPValidationError,
        match=r"must be a loopback HTTP\(S\) origin",
    ):
        validate_loopback_http_origin(value)


def test_local_request_target_preserves_safe_path_and_query() -> None:
    assert (
        validate_local_request_target("/api/emails?limit=10") == "/api/emails?limit=10"
    )
    assert (
        validate_local_request_target(
            "/auth/session",
            allowed_exact_paths=frozenset({"/auth/session"}),
        )
        == "/auth/session"
    )


@pytest.mark.parametrize(
    "path",
    [
        "/api/../auth/session",
        "/api/%2e%2e/auth/session",
        "/api/%2E%2E/auth/session",
        "/api/%2fadmin",
        "/api/%2Fadmin",
        "/api/%5cadmin",
        "/api/%5Cadmin",
        r"/api/\admin",
    ],
)
def test_local_request_target_rejects_raw_and_encoded_traversal(path: str) -> None:
    with pytest.raises(LocalHTTPValidationError, match="traversal"):
        validate_local_request_target(path)


@pytest.mark.parametrize(
    "path",
    [
        "/api/%",
        "/api/%2",
        "/api/%GG",
        "/api/%FF",
    ],
)
def test_local_request_target_rejects_invalid_percent_encoding(path: str) -> None:
    with pytest.raises(LocalHTTPValidationError, match="percent encoding"):
        validate_local_request_target(path)


def test_local_request_target_normalizes_malformed_parser_errors() -> None:
    with pytest.raises(LocalHTTPValidationError, match="local API path"):
        validate_local_request_target("//[::1")


class FakeParseResultWithNegativePort(urllib.parse.SplitResult):
    @property
    def port(self):
        return -1


def test_missing_coverage():
    with pytest.raises(LocalHTTPValidationError, match="control characters"):
        validate_loopback_http_origin("http://127.0.0.1\x00/")

    with pytest.raises(LocalHTTPValidationError, match="must be a loopback HTTP"):
        validate_loopback_http_origin("ftp://127.0.0.1/")
    with pytest.raises(LocalHTTPValidationError, match="must be a loopback HTTP"):
        validate_loopback_http_origin("http://user@127.0.0.1/")
    with pytest.raises(LocalHTTPValidationError, match="must be a loopback HTTP"):
        validate_loopback_http_origin("http://127.0.0.1/foo")
    with pytest.raises(LocalHTTPValidationError, match="must be a loopback HTTP"):
        validate_loopback_http_origin("http://127.0.0.1/?query=1")
    with pytest.raises(LocalHTTPValidationError, match="must be a loopback HTTP"):
        validate_loopback_http_origin("http://127.0.0.1/#frag")

    origin = validate_loopback_http_origin("http://localhost:8080/")
    assert origin.hostname == "localhost"

    with pytest.raises(LocalHTTPValidationError, match="allowlisted"):
        validate_loopback_http_origin("http://not-an-ip/")

    with pytest.raises(LocalHTTPValidationError, match="allowlisted"):
        validate_loopback_http_origin("http://8.8.8.8/")

    with pytest.raises(LocalHTTPValidationError, match="port is invalid"):
        validate_loopback_http_origin("http://127.0.0.1:port/")

    with patch("core.local_http.urlsplit") as mock_split:
        mock_split.return_value = FakeParseResultWithNegativePort(
            "http", "127.0.0.1:-1", "/", "", ""
        )
        with pytest.raises(LocalHTTPValidationError, match="port is invalid"):
            validate_loopback_http_origin("http://127.0.0.1:-1/")

    with pytest.raises(LocalHTTPValidationError, match="control characters"):
        validate_local_request_target("/api/path\x00")

    with pytest.raises(LocalHTTPValidationError, match="local API path"):
        validate_local_request_target("http://127.0.0.1/api/path")
    with pytest.raises(LocalHTTPValidationError, match="local API path"):
        validate_local_request_target("/api/path#frag")

    with pytest.raises(LocalHTTPValidationError, match="allowed local endpoint"):
        validate_local_request_target("/other/path")

    with pytest.raises(LocalHTTPValidationError, match="control characters"):
        validate_local_request_target("/api/%00path")
