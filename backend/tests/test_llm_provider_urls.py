import socket

import pytest

from core.config import settings
from services.llm_provider_urls import (
    LLM_BASE_URL_NOT_ALLOWED,
    _is_ip_literal,
    _validate_global_address,
    validate_llm_provider_base_url,
)


def test_validate_global_address_valid_ipv4():
    """Test that a valid global IPv4 address is accepted."""
    assert _validate_global_address("93.184.216.34") == "93.184.216.34"


def test_validate_global_address_valid_ipv6():
    """Test that a valid global IPv6 address is accepted."""
    assert (
        _validate_global_address("2606:2800:220:1:248:1893:25c8:1946")
        == "2606:2800:220:1:248:1893:25c8:1946"
    )


def test_validate_global_address_invalid_ip():
    """Test that an invalid IP address string raises a ValueError."""
    with pytest.raises(ValueError, match=LLM_BASE_URL_NOT_ALLOWED):
        _validate_global_address("not-an-ip-address")


def test_validate_global_address_private_ip():
    """Test that a private IP address is rejected."""
    with pytest.raises(ValueError, match=LLM_BASE_URL_NOT_ALLOWED):
        _validate_global_address("192.168.1.1")


def test_validate_global_address_loopback_ip_rejected():
    """Test that a loopback IP address is rejected by default."""
    with pytest.raises(ValueError, match=LLM_BASE_URL_NOT_ALLOWED):
        _validate_global_address("127.0.0.1")


def test_validate_global_address_link_local_ip_rejected():
    """Test that a link-local IP address is rejected."""
    with pytest.raises(ValueError, match=LLM_BASE_URL_NOT_ALLOWED):
        _validate_global_address("169.254.1.1")


def test_validate_global_address_multicast_ip_rejected():
    """Test that a multicast IP address is rejected."""
    with pytest.raises(ValueError, match=LLM_BASE_URL_NOT_ALLOWED):
        _validate_global_address("224.0.0.1")


def test_validate_global_address_loopback_allowed_for_explicit_localhost(monkeypatch):
    """Explicit local hostname identity may resolve to loopback under local opt-in."""
    monkeypatch.setattr(settings, "ALLOW_LOCAL_LLM_PROVIDERS", True)
    assert (
        _validate_global_address("127.0.0.1", hostname="localhost")
        == "127.0.0.1"
    )


def test_validate_global_address_loopback_rejected_without_local_host_identity(
    monkeypatch,
):
    """Local opt-in alone must not authorize a DNS-derived loopback address."""
    monkeypatch.setattr(settings, "ALLOW_LOCAL_LLM_PROVIDERS", True)

    with pytest.raises(ValueError, match=LLM_BASE_URL_NOT_ALLOWED):
        _validate_global_address("127.0.0.1")


@pytest.mark.parametrize(
    "provider_url, hostname",
    [
        ("https://provider.example/v1", "provider.example"),
        ("http://ollama:11434/v1", "ollama"),
    ],
)
def test_validate_provider_base_url_rejects_loopback_dns_rebinding(
    monkeypatch, provider_url, hostname
):
    """An allowlisted non-local hostname must not gain loopback access via DNS."""
    monkeypatch.setattr(settings, "ALLOW_LOCAL_LLM_PROVIDERS", True)
    monkeypatch.setattr(settings, "ALLOWED_LLM_BASE_URL_HOSTS", hostname)

    def resolve_to_loopback(resolved_hostname, port, *, type):
        """Resolve the candidate hostname to loopback to simulate DNS rebinding."""
        assert resolved_hostname == hostname
        assert type == socket.SOCK_STREAM
        return [
            (
                socket.AF_INET,
                socket.SOCK_STREAM,
                socket.IPPROTO_TCP,
                "",
                ("127.0.0.1", port),
            )
        ]

    monkeypatch.setattr(socket, "getaddrinfo", resolve_to_loopback)

    with pytest.raises(ValueError, match=LLM_BASE_URL_NOT_ALLOWED):
        validate_llm_provider_base_url(provider_url)


def test_validate_provider_base_url_allows_explicit_localhost_loopback(monkeypatch):
    """Explicit localhost remains usable when the local-provider opt-in is enabled."""
    monkeypatch.setattr(settings, "ALLOW_LOCAL_LLM_PROVIDERS", True)

    def resolve_localhost(resolved_hostname, port, *, type):
        """Resolve the explicit local-development hostname to loopback."""
        assert resolved_hostname == "localhost"
        assert type == socket.SOCK_STREAM
        return [
            (
                socket.AF_INET,
                socket.SOCK_STREAM,
                socket.IPPROTO_TCP,
                "",
                ("127.0.0.1", port),
            )
        ]

    monkeypatch.setattr(socket, "getaddrinfo", resolve_localhost)

    assert (
        validate_llm_provider_base_url("http://localhost:11434/v1")
        == "http://localhost:11434/v1"
    )


def test_validate_global_address_private_allowed_when_host_allowed(monkeypatch):
    """Test that a private IP is allowed when the hostname is in ALLOWED_LLM_BASE_URL_HOSTS."""
    monkeypatch.setattr(settings, "ALLOW_LOCAL_LLM_PROVIDERS", True)
    monkeypatch.setattr(settings, "ALLOWED_LLM_BASE_URL_HOSTS", "ollama,other-host")

    assert _validate_global_address("192.168.1.5", hostname="ollama") == "192.168.1.5"


@pytest.mark.parametrize(
    "address",
    [
        "169.254.169.254",
        "224.0.0.1",
        "0.0.0.0",
        "255.255.255.255",
        "::",
        "fe80::1",
        "ff02::1",
    ],
)
def test_validate_global_address_allowlisted_host_rejects_unsafe_address_classes(
    monkeypatch, address
):
    """Local-container opt-in must not authorize metadata or non-unicast addresses."""
    monkeypatch.setattr(settings, "ALLOW_LOCAL_LLM_PROVIDERS", True)
    monkeypatch.setattr(settings, "ALLOWED_LLM_BASE_URL_HOSTS", "ollama")

    with pytest.raises(ValueError, match=LLM_BASE_URL_NOT_ALLOWED):
        _validate_global_address(address, hostname="ollama")


def test_validate_global_address_allowlisted_host_accepts_unique_local_ipv6(monkeypatch):
    """An allowlisted local provider may resolve to IPv6 unique-local space."""
    monkeypatch.setattr(settings, "ALLOW_LOCAL_LLM_PROVIDERS", True)
    monkeypatch.setattr(settings, "ALLOWED_LLM_BASE_URL_HOSTS", "ollama")

    assert _validate_global_address("fd00::1", hostname="ollama") == "fd00::1"


def test_validate_global_address_private_rejected_when_host_not_allowed(monkeypatch):
    """Test that a private IP is rejected even with ALLOW_LOCAL_LLM_PROVIDERS if the hostname is not allowed."""
    monkeypatch.setattr(settings, "ALLOW_LOCAL_LLM_PROVIDERS", True)
    monkeypatch.setattr(settings, "ALLOWED_LLM_BASE_URL_HOSTS", "ollama,other-host")

    with pytest.raises(ValueError, match=LLM_BASE_URL_NOT_ALLOWED):
        _validate_global_address("192.168.1.5", hostname="unallowed-host")


def test_validate_global_address_private_rejected_without_hostname(monkeypatch):
    """Test that a private IP is rejected if ALLOW_LOCAL_LLM_PROVIDERS is True but no hostname is provided."""
    monkeypatch.setattr(settings, "ALLOW_LOCAL_LLM_PROVIDERS", True)
    monkeypatch.setattr(settings, "ALLOWED_LLM_BASE_URL_HOSTS", "ollama,other-host")

    with pytest.raises(ValueError, match=LLM_BASE_URL_NOT_ALLOWED):
        _validate_global_address("192.168.1.5")


@pytest.mark.parametrize(
    "candidate, expected",
    [
        ("192.168.1.1", True),
        ("0.0.0.0", True),  # nosec B104
        ("255.255.255.255", True),
        ("127.0.0.1", True),
        ("::1", True),
        ("2001:0db8:85a3:0000:0000:8a2e:0370:7334", True),
        ("2001:db8:85a3::8a2e:370:7334", True),
        ("fe80::1ff:fe23:4567:890a", True),
        ("256.256.256.256", False),
        ("192.168.1", False),
        ("1.2.3.4.5", False),
        ("2001:db8::85a3::8a2e:370:7334", False),
        ("localhost", False),
        ("example.com", False),
        ("api.openai.com", False),
        ("", False),
        (" ", False),
        ("invalid", False),
        ("12345", False),
        ("192.168.1.1.com", False),
    ],
)
def test_is_ip_literal(candidate, expected):
    assert _is_ip_literal(candidate) is expected
