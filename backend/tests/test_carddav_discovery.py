import socket

import pytest

import services.carddav_discovery as discovery
from services.carddav_discovery import (
    CarddavDiscoveryResult,
    discover_carddav,
    discover_carddav_base_url,
)

PUBLIC_IP = "93.184.216.34"


@pytest.fixture(autouse=True)
def force_global_dns(monkeypatch):
    """Resolve every hostname to a public IP so the SSRF guard passes."""

    def fake_getaddrinfo(host, port, *args, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (PUBLIC_IP, port))]

    monkeypatch.setattr(discovery.socket, "getaddrinfo", fake_getaddrinfo)


class FakeResponse:
    def __init__(self, status_code, headers=None):
        self.status_code = status_code
        self.headers = headers or {}


class FakeClient:
    def __init__(self, response):
        self._response = response
        self.requests = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def request(self, method, url, **kwargs):
        self.requests.append((method, url))
        return self._response


def _factory(response):
    def make():
        return FakeClient(response)

    return make


@pytest.mark.asyncio
async def test_well_known_redirect_resolves_base_url():
    response = FakeResponse(
        301, headers={"Location": "https://dav.example.com/carddav/"}
    )
    result = await discover_carddav(
        "user@example.com",
        http_client_factory=_factory(response),
        srv_resolver=lambda name: [],
    )
    assert result == CarddavDiscoveryResult(
        base_url="https://dav.example.com/carddav/",
        discovery_source="well_known",
    )


@pytest.mark.asyncio
async def test_well_known_200_uses_well_known_path():
    response = FakeResponse(207)
    url = await discover_carddav_base_url(
        "example.com",
        http_client_factory=_factory(response),
        srv_resolver=lambda name: [],
    )
    assert url == "https://example.com/.well-known/carddav"


@pytest.mark.asyncio
async def test_srv_secure_fallback_when_well_known_missing():
    response = FakeResponse(404)

    def resolver(name):
        if name == "_carddavs._tcp.example.com":
            return [("dav.example.com", 443)]
        return []

    result = await discover_carddav(
        "user@example.com",
        http_client_factory=_factory(response),
        srv_resolver=resolver,
    )
    assert result is not None
    assert result.discovery_source == "srv_secure"
    assert result.base_url == "https://dav.example.com/"


@pytest.mark.asyncio
async def test_srv_plain_fallback_with_custom_port():
    response = FakeResponse(404)

    def resolver(name):
        if name == "_carddav._tcp.example.com":
            return [("dav.example.com", 8443)]
        return []

    result = await discover_carddav(
        "example.com",
        http_client_factory=_factory(response),
        srv_resolver=resolver,
    )
    assert result is not None
    assert result.discovery_source == "srv"
    assert result.base_url == "https://dav.example.com:8443/"


@pytest.mark.asyncio
async def test_no_discovery_returns_none():
    response = FakeResponse(404)
    result = await discover_carddav(
        "user@example.com",
        http_client_factory=_factory(response),
        srv_resolver=lambda name: [],
    )
    assert result is None


@pytest.mark.asyncio
async def test_invalid_input_returns_none():
    assert (
        await discover_carddav_base_url(
            "not-an-email-or-domain",
            http_client_factory=_factory(FakeResponse(200)),
            srv_resolver=lambda name: [],
        )
        is None
    )


@pytest.mark.asyncio
async def test_private_host_is_rejected_by_ssrf_guard():
    # A well-known redirect pointing at a private IP must be discarded.
    response = FakeResponse(302, headers={"Location": "https://10.0.0.5/carddav/"})
    result = await discover_carddav(
        "user@example.com",
        http_client_factory=_factory(response),
        srv_resolver=lambda name: [],
    )
    assert result is None
