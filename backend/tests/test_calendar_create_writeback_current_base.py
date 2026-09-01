"""Regression tests for provider-backed CalDAV create writeback semantics.

A new CalDAV resource has no prior ETag, so create may omit ``If-Match`` only
when the server-authoritative command explicitly declares that precondition
unnecessary. Updates keep the fail-closed default. The same request must also
bind validation to the actual outbound address so DNS rebinding cannot move a
credentialed request after the host was checked.
"""

import socket

import pytest

from runner.local_dav_adapters import LocalDavAdapters, LocalDavSourceConfig


class _FakeDavResponse:
    def __init__(self, status_code: int):
        self.status_code = status_code
        self.headers: dict[str, str] = {}


class _FakeDavClient:
    def __init__(self, response: _FakeDavResponse):
        self.response = response
        self.requests: list[dict[str, object]] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def put(self, url, *, content, headers, auth, extensions=None):
        self.requests.append(
            {
                "url": url,
                "content": content,
                "headers": headers,
                "auth": auth,
                "extensions": extensions,
            }
        )
        return self.response


@pytest.fixture(autouse=True)
def _pin_public_dns(monkeypatch):
    def fake_getaddrinfo(host, port, *args, **kwargs):
        return [
            (
                socket.AF_INET,
                socket.SOCK_STREAM,
                6,
                "",
                ("93.184.216.34", port),
            )
        ]

    monkeypatch.setattr(
        "runner.local_dav_adapters.socket.getaddrinfo",
        fake_getaddrinfo,
    )
    monkeypatch.setattr(
        "services.carddav_client.socket.getaddrinfo",
        fake_getaddrinfo,
    )


def test_default_dav_client_does_not_trust_ambient_proxy_environment(monkeypatch):
    captured: dict[str, object] = {}
    sentinel = object()

    def fake_async_client(**kwargs):
        captured.update(kwargs)
        return sentinel

    monkeypatch.setattr(
        "runner.local_dav_adapters.httpx.AsyncClient",
        fake_async_client,
    )

    adapters = LocalDavAdapters([])

    assert adapters._default_http_client() is sentinel  # noqa: SLF001
    assert captured["follow_redirects"] is False
    assert captured["timeout"] == 60
    assert captured["trust_env"] is False


@pytest.mark.asyncio
async def test_caldav_create_without_if_match_is_pinned_and_dispatched():
    fake_client = _FakeDavClient(_FakeDavResponse(201))
    adapters = LocalDavAdapters(
        [
            LocalDavSourceConfig(
                source_id="caldav_primary",
                protocol="caldav",
                base_url="https://calendar.example.com/dav/calendars/alice",
                username="alice",
                password="dav-secret",
                writeback_enabled=True,
            )
        ],
        http_client_factory=lambda: fake_client,
    )

    result = await adapters.write_caldav(
        {
            "source_id": "caldav_primary",
            "target_path": "/Naruon/Calendar/create.ics",
            "content": "BEGIN:VCALENDAR\nEND:VCALENDAR\n",
            "requires_if_match": False,
        }
    )

    assert result == {
        "status": "success",
        "provider_write_executed": True,
        "provider_status": 201,
    }
    assert fake_client.requests == [
        {
            "url": "https://93.184.216.34/dav/calendars/alice/Naruon/Calendar/create.ics",
            "content": b"BEGIN:VCALENDAR\nEND:VCALENDAR\n",
            "headers": {
                "Content-Type": "text/calendar; charset=utf-8",
                "Host": "calendar.example.com",
            },
            "auth": ("alice", "dav-secret"),
            "extensions": {"sni_hostname": "calendar.example.com"},
        }
    ]


@pytest.mark.asyncio
async def test_caldav_update_keeps_if_match_as_fail_closed_default():
    fake_client = _FakeDavClient(_FakeDavResponse(204))
    adapters = LocalDavAdapters(
        [
            LocalDavSourceConfig(
                source_id="caldav_primary",
                protocol="caldav",
                base_url="https://calendar.example.com",
                writeback_enabled=True,
            )
        ],
        http_client_factory=lambda: fake_client,
    )

    result = await adapters.write_caldav(
        {
            "source_id": "caldav_primary",
            "target_path": "/Naruon/Calendar/update.ics",
            "content": "BEGIN:VCALENDAR\nEND:VCALENDAR\n",
        }
    )

    assert result["status"] == "error"
    assert result["error_code"] == "missing_if_match"
    assert fake_client.requests == []


@pytest.mark.asyncio
async def test_caldav_rejects_non_boolean_if_match_policy_before_network():
    fake_client = _FakeDavClient(_FakeDavResponse(201))
    adapters = LocalDavAdapters(
        [
            LocalDavSourceConfig(
                source_id="caldav_primary",
                protocol="caldav",
                base_url="https://calendar.example.com",
                writeback_enabled=True,
            )
        ],
        http_client_factory=lambda: fake_client,
    )

    result = await adapters.write_caldav(
        {
            "source_id": "caldav_primary",
            "target_path": "/Naruon/Calendar/create.ics",
            "content": "BEGIN:VCALENDAR\nEND:VCALENDAR\n",
            "requires_if_match": "false",
        }
    )

    assert result["status"] == "error"
    assert result["error_code"] == "invalid_payload"
    assert fake_client.requests == []
