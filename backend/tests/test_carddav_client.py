import socket

import pytest

import services.carddav_client as carddav_client
from services.carddav_client import CardDavClient

PUBLIC_IP = "93.184.216.34"


@pytest.fixture(autouse=True)
def force_global_dns(monkeypatch):
    def fake_getaddrinfo(host, port, *args, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (PUBLIC_IP, port))]

    monkeypatch.setattr(carddav_client.socket, "getaddrinfo", fake_getaddrinfo)


class FakeResponse:
    def __init__(self, status_code, headers=None):
        self.status_code = status_code
        self.headers = headers or {}


class FakeClient:
    def __init__(self, response):
        self._response = response
        self.calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        return self._response

    async def put(self, url, **kwargs):
        self.calls.append(("PUT", url, kwargs))
        return self._response


def _factory(response, sink=None):
    def make():
        client = FakeClient(response)
        if sink is not None:
            sink.append(client)
        return client

    return make


@pytest.mark.asyncio
async def test_list_address_books_reports_reachable_on_207():
    sink = []
    client = CardDavClient(
        "https://dav.example.com/carddav/",
        username="user@example.com",
        password="secret",
        http_client_factory=_factory(FakeResponse(207), sink),
    )
    probe = await client.list_address_books()
    assert probe.reachable is True
    assert probe.status_code == 207
    method, url, kwargs = sink[0].calls[0]
    assert method == "PROPFIND"
    assert kwargs["auth"] == ("user@example.com", "secret")
    assert kwargs["headers"]["Depth"] == "1"


@pytest.mark.asyncio
async def test_list_address_books_reachable_on_401():
    client = CardDavClient(
        "https://dav.example.com/carddav/",
        http_client_factory=_factory(FakeResponse(401)),
    )
    probe = await client.list_address_books()
    assert probe.reachable is True


@pytest.mark.asyncio
async def test_list_address_books_unreachable_on_500():
    client = CardDavClient(
        "https://dav.example.com/carddav/",
        http_client_factory=_factory(FakeResponse(500)),
    )
    probe = await client.list_address_books()
    assert probe.reachable is False


@pytest.mark.asyncio
async def test_put_vcard_returns_status_and_targets_relative_path():
    sink = []
    client = CardDavClient(
        "https://dav.example.com/carddav/",
        http_client_factory=_factory(FakeResponse(201), sink),
    )
    status = await client.put_vcard("contact.vcf", "BEGIN:VCARD\nEND:VCARD")
    assert status == 201
    _method, url, _kwargs = sink[0].calls[0]
    assert url == "https://dav.example.com/carddav/contact.vcf"


def test_private_base_url_rejected():
    with pytest.raises(ValueError):
        CardDavClient("https://10.0.0.5/carddav/")


def test_non_https_base_url_rejected():
    with pytest.raises(ValueError):
        CardDavClient("http://dav.example.com/carddav/")
