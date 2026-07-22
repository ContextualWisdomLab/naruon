"""Compose-local OIDC provider opt-in (ALLOW_LOCAL_OIDC_PROVIDERS).

Mirrors the existing ALLOW_LOCAL_LLM_PROVIDERS / ALLOW_LOCAL_NEWSDOM_PROVIDERS
pattern: the strict default stays https + exact-host allowlist + global-only
resolution, and an explicit operator opt-in permits plain-http single-label /
localhost hosts (e.g. a Keycloak container on the compose network) for local
development stacks.
"""

import socket

import pytest

from core import url_validation
from core.url_validation import (
    is_local_dev_identity_host,
    parse_allowed_hosts,
    validate_https_url_host_details,
)


def _stub_resolver(monkeypatch, address: str):
    monkeypatch.setattr(
        url_validation.socket,
        "getaddrinfo",
        lambda *args, **kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, 0))
        ],
    )


def test_local_dev_identity_host_shape():
    assert is_local_dev_identity_host("localhost")
    assert is_local_dev_identity_host("keyverse")
    assert is_local_dev_identity_host("host.docker.internal")
    assert not is_local_dev_identity_host("login.example.com")
    assert not is_local_dev_identity_host("127.0.0.1")


def test_http_issuer_rejected_without_local_opt_in(monkeypatch):
    _stub_resolver(monkeypatch, "127.0.0.1")
    with pytest.raises(ValueError, match="must use https"):
        validate_https_url_host_details(
            "OIDC_ISSUER_URL",
            "http://localhost:18085/realms/cwl",
            parse_allowed_hosts("localhost"),
            "ALLOWED_OIDC_HOSTS",
        )


def test_http_issuer_accepted_with_local_opt_in(monkeypatch):
    _stub_resolver(monkeypatch, "127.0.0.1")
    validated = validate_https_url_host_details(
        "OIDC_ISSUER_URL",
        "http://localhost:18085/realms/cwl",
        parse_allowed_hosts("localhost"),
        "ALLOWED_OIDC_HOSTS",
        allow_local=True,
    )
    assert validated.hostname == "localhost"
    assert validated.port == 18085
    assert validated.url_scheme == "http"
    assert validated.addresses == ("127.0.0.1",)


def test_local_opt_in_accepts_private_single_label_compose_host(monkeypatch):
    _stub_resolver(monkeypatch, "172.20.0.7")
    validated = validate_https_url_host_details(
        "OIDC_JWKS_URL",
        "http://keyverse:8080/realms/cwl/protocol/openid-connect/certs",
        parse_allowed_hosts("localhost,keyverse"),
        "ALLOWED_OIDC_HOSTS",
        allow_local=True,
    )
    assert validated.hostname == "keyverse"
    assert validated.addresses == ("172.20.0.7",)


def test_local_opt_in_normalizes_resolved_ip_addresses(monkeypatch):
    monkeypatch.setattr(
        url_validation.socket,
        "getaddrinfo",
        lambda *args, **kwargs: [
            (
                socket.AF_INET6,
                socket.SOCK_STREAM,
                6,
                "",
                ("2001:0db8:0000:0000:0000:0000:0000:0001", 8080, 0, 0),
            )
        ],
    )

    validated = validate_https_url_host_details(
        "OIDC_JWKS_URL",
        "http://keyverse:8080/jwks",
        parse_allowed_hosts("keyverse"),
        "ALLOWED_OIDC_HOSTS",
        allow_local=True,
    )

    assert validated.addresses == ("2001:db8::1",)


def test_local_opt_in_rejects_malformed_resolver_output(monkeypatch):
    _stub_resolver(monkeypatch, "not-an-ip-address")

    with pytest.raises(ValueError, match="resolved host must be an IP address"):
        validate_https_url_host_details(
            "OIDC_JWKS_URL",
            "http://keyverse:8080/jwks",
            parse_allowed_hosts("keyverse"),
            "ALLOWED_OIDC_HOSTS",
            allow_local=True,
        )


def test_local_opt_in_still_requires_allowlist_membership(monkeypatch):
    _stub_resolver(monkeypatch, "172.20.0.7")
    with pytest.raises(ValueError, match="ALLOWED_OIDC_HOSTS"):
        validate_https_url_host_details(
            "OIDC_JWKS_URL",
            "http://keyverse:8080/realms/cwl",
            parse_allowed_hosts("localhost"),
            "ALLOWED_OIDC_HOSTS",
            allow_local=True,
        )


def test_local_opt_in_does_not_relax_public_dotted_hosts(monkeypatch):
    _stub_resolver(monkeypatch, "8.8.8.8")
    # A dotted public hostname stays on the strict https path even when the
    # local opt-in flag is set.
    with pytest.raises(ValueError, match="must use https"):
        validate_https_url_host_details(
            "OIDC_ISSUER_URL",
            "http://login.example.com/realms/cwl",
            parse_allowed_hosts("login.example.com"),
            "ALLOWED_OIDC_HOSTS",
            allow_local=True,
        )


def test_settings_validator_accepts_local_oidc_pair(monkeypatch):
    _stub_resolver(monkeypatch, "127.0.0.1")
    from core.config import Settings

    settings = Settings(
        DATABASE_URL="postgresql+asyncpg://test:test@localhost:5432/test_db",
        AUTH_SESSION_HMAC_SECRET="R7mXq2LpZ8vKw4NtB6cJd1FgY3hUsA9eW5oPiT0knEx2QrVbSaDfGjHlMzCuYw",
        OIDC_ISSUER_URL="http://localhost:18085/realms/cwl",
        OIDC_CLIENT_ID="naruon-web",
        OIDC_JWKS_URL="http://keyverse:8080/realms/cwl/protocol/openid-connect/certs",
        ALLOWED_OIDC_HOSTS="localhost,keyverse",
        ALLOW_LOCAL_OIDC_PROVIDERS=True,
    )
    assert settings.OIDC_CLIENT_ID == "naruon-web"


def test_settings_validator_rejects_local_pair_without_opt_in(monkeypatch):
    _stub_resolver(monkeypatch, "127.0.0.1")
    from core.config import Settings

    with pytest.raises(ValueError):
        Settings(
            DATABASE_URL="postgresql+asyncpg://test:test@localhost:5432/test_db",
            AUTH_SESSION_HMAC_SECRET="R7mXq2LpZ8vKw4NtB6cJd1FgY3hUsA9eW5oPiT0knEx2QrVbSaDfGjHlMzCuYw",
            OIDC_ISSUER_URL="http://localhost:18085/realms/cwl",
            OIDC_CLIENT_ID="naruon-web",
            OIDC_JWKS_URL="http://keyverse:8080/realms/cwl/protocol/openid-connect/certs",
            ALLOWED_OIDC_HOSTS="localhost,keyverse",
        )
