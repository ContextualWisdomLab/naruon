import socket

import httpx
import pytest

from runner.local_dav_adapters import LocalDavAdapters, LocalDavSourceConfig


class FakeDavResponse:
    def __init__(self, status_code: int, headers: dict[str, str] | None = None):
        self.status_code = status_code
        self.headers = headers or {}


class FakeDavClient:
    def __init__(self, response: FakeDavResponse):
        self.response = response
        self.requests = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def put(self, url, *, content, headers, auth):
        self.requests.append(
            {
                "url": url,
                "content": content,
                "headers": headers,
                "auth": auth,
            }
        )
        return self.response


@pytest.fixture(autouse=True)
def stub_dav_dns(monkeypatch):
    def fake_getaddrinfo(host, port, type=socket.SOCK_STREAM):
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
        "runner.local_dav_adapters.socket.getaddrinfo", fake_getaddrinfo
    )


@pytest.mark.asyncio
async def test_webdav_adapter_puts_content_with_if_match():
    fake_client = FakeDavClient(
        FakeDavResponse(204, headers={"ETag": "etag-after-write"})
    )
    adapters = LocalDavAdapters(
        [
            LocalDavSourceConfig(
                source_id="webdav_src_1",
                protocol="webdav",
                base_url="https://webdav.example.com/remote.php/dav/files/alice",
                username="alice",
                password="dav-secret",
                writeback_enabled=True,
            )
        ],
        http_client_factory=lambda: fake_client,
    )

    result = await adapters.write_webdav(
        {
            "source_id": "webdav_src_1",
            "target_path": "/Naruon/Notes/task.md",
            "content": "# Note\n",
            "content_type": "text/markdown; charset=utf-8",
            "if_match": "etag-before-write",
        }
    )

    assert result == {
        "status": "success",
        "provider_write_executed": True,
        "provider_status": 204,
        "etag": "etag-after-write",
    }
    assert fake_client.requests == [
        {
            "url": "https://webdav.example.com/remote.php/dav/files/alice/Naruon/Notes/task.md",
            "content": b"# Note\n",
            "headers": {
                "Content-Type": "text/markdown; charset=utf-8",
                "If-Match": "etag-before-write",
            },
            "auth": ("alice", "dav-secret"),
        }
    ]


@pytest.mark.asyncio
async def test_webdav_adapter_requires_if_match_before_network_request():
    fake_client = FakeDavClient(FakeDavResponse(204))
    adapters = LocalDavAdapters(
        [
            LocalDavSourceConfig(
                source_id="webdav_src_1",
                protocol="webdav",
                base_url="https://webdav.example.com",
                writeback_enabled=True,
            )
        ],
        http_client_factory=lambda: fake_client,
    )

    result = await adapters.write_webdav(
        {
            "source_id": "webdav_src_1",
            "target_path": "/Naruon/Notes/task.md",
            "content": "# Note\n",
        }
    )

    assert result == {
        "status": "error",
        "error": "missing_if_match",
        "error_code": "missing_if_match",
        "provider_write_executed": False,
    }
    assert fake_client.requests == []


@pytest.mark.asyncio
async def test_webdav_adapter_reports_provider_conflict_without_write_success():
    fake_client = FakeDavClient(FakeDavResponse(412))
    adapters = LocalDavAdapters(
        [
            LocalDavSourceConfig(
                source_id="webdav_src_1",
                protocol="webdav",
                base_url="https://webdav.example.com",
                writeback_enabled=True,
            )
        ],
        http_client_factory=lambda: fake_client,
    )

    result = await adapters.write_webdav(
        {
            "source_id": "webdav_src_1",
            "target_path": "/Naruon/Notes/task.md",
            "content": "# Note\n",
            "if_match": "stale-etag",
        }
    )

    assert result == {
        "status": "conflict",
        "error": "provider_conflict",
        "error_code": "provider_conflict",
        "provider_write_executed": False,
        "provider_status": 412,
    }


@pytest.mark.parametrize(
    "target_path",
    [
        None,
        "",
        "/",
        "/" + "a" * 4096,
        "/Naruon/../Secrets/task.md",
        "/Naruon/%2e%2e/Secrets/task.md",
        "/Naruon/%252e%252e/Secrets/task.md",
        "/Naruon/..%2fSecrets/task.md",
        "/Naruon/%2e%2e%5cSecrets/task.md",
        "/Naruon/%00/Secrets/task.md",
        "/Naruon/%7f/Secrets/task.md",
        "/Naruon/%FF/Secrets/task.md",
        "/Naruon/%25252525252e%25252525252e/Secrets/task.md",
        "/%68%74%74%70%3A%2F%2Fevil.example/file",
    ],
)
@pytest.mark.asyncio
async def test_webdav_adapter_rejects_path_traversal_before_network_request(
    target_path: object,
):
    fake_client = FakeDavClient(FakeDavResponse(204))
    adapters = LocalDavAdapters(
        [
            LocalDavSourceConfig(
                source_id="webdav_src_1",
                protocol="webdav",
                base_url="https://webdav.example.com",
                writeback_enabled=True,
            )
        ],
        http_client_factory=lambda: fake_client,
    )

    result = await adapters.write_webdav(
        {
            "source_id": "webdav_src_1",
            "target_path": target_path,
            "content": "# Note\n",
            "if_match": "etag-before-write",
        }
    )

    assert result == {
        "status": "error",
        "error": "invalid_target_path",
        "error_code": "invalid_target_path",
        "provider_write_executed": False,
    }
    assert fake_client.requests == []


@pytest.mark.parametrize(
    ("target_path", "expected_path"),
    [
        ("/Naruon/Notes/task.md", "/Naruon/Notes/task.md"),
        ("/Naruon/Notes/meeting%20notes.md", "/Naruon/Notes/meeting%20notes.md"),
        (
            "/Naruon/Notes/meeting%25252520notes.md",
            "/Naruon/Notes/meeting%20notes.md",
        ),
        ("/Naruon//Notes///task.md", "/Naruon/Notes/task.md"),
        ("/Naruon/노트.md", "/Naruon/%EB%85%B8%ED%8A%B8.md"),
    ],
)
def test_webdav_adapter_canonicalizes_safe_target_path(
    target_path: str,
    expected_path: str,
):
    adapters = LocalDavAdapters([])

    assert adapters._safe_target_path(target_path) == expected_path


@pytest.mark.asyncio
async def test_webdav_adapter_rejects_private_source_url_before_network_request(
    monkeypatch,
):
    def fake_private_getaddrinfo(host, port, type=socket.SOCK_STREAM):
        return [
            (
                socket.AF_INET,
                socket.SOCK_STREAM,
                6,
                "",
                ("192.168.1.10", port),
            )
        ]

    monkeypatch.setattr(
        "runner.local_dav_adapters.socket.getaddrinfo",
        fake_private_getaddrinfo,
    )
    fake_client = FakeDavClient(FakeDavResponse(204))
    adapters = LocalDavAdapters(
        [
            LocalDavSourceConfig(
                source_id="webdav_src_1",
                protocol="webdav",
                base_url="https://webdav.example.com",
                writeback_enabled=True,
            )
        ],
        http_client_factory=lambda: fake_client,
    )

    result = await adapters.write_webdav(
        {
            "source_id": "webdav_src_1",
            "target_path": "/Naruon/Notes/task.md",
            "content": "# Note\n",
            "if_match": "etag-before-write",
        }
    )

    assert result == {
        "status": "error",
        "error": "invalid_source_url",
        "error_code": "invalid_source_url",
        "provider_write_executed": False,
    }
    assert fake_client.requests == []


@pytest.mark.asyncio
async def test_caldav_adapter_puts_icalendar_content_with_if_match():
    fake_client = FakeDavClient(FakeDavResponse(201, headers={"ETag": "caldav-etag"}))
    adapters = LocalDavAdapters(
        [
            LocalDavSourceConfig(
                source_id="caldav_src_1",
                protocol="caldav",
                base_url="https://calendar.example.com/dav/calendars/alice/tasks",
                writeback_enabled=True,
            )
        ],
        http_client_factory=lambda: fake_client,
    )

    result = await adapters.write_caldav(
        {
            "source_id": "caldav_src_1",
            "target_path": "/naruon-task.ics",
            "content": "BEGIN:VCALENDAR\r\nEND:VCALENDAR\r\n",
            "if_match": "caldav-before",
        }
    )

    assert result == {
        "status": "success",
        "provider_write_executed": True,
        "provider_status": 201,
        "etag": "caldav-etag",
    }
    assert fake_client.requests[0]["url"] == (
        "https://calendar.example.com/dav/calendars/alice/tasks/naruon-task.ics"
    )
    assert fake_client.requests[0]["headers"] == {
        "Content-Type": "text/calendar; charset=utf-8",
        "If-Match": "caldav-before",
    }


@pytest.mark.asyncio
async def test_webdav_adapter_rejects_unresolvable_source_url_before_network_request(
    monkeypatch,
):
    def fake_unresolvable_getaddrinfo(host, port, type=socket.SOCK_STREAM):
        raise OSError("Name or service not known")

    monkeypatch.setattr(
        "runner.local_dav_adapters.socket.getaddrinfo",
        fake_unresolvable_getaddrinfo,
    )
    fake_client = FakeDavClient(FakeDavResponse(204))
    adapters = LocalDavAdapters(
        [
            LocalDavSourceConfig(
                source_id="webdav_src_1",
                protocol="webdav",
                base_url="https://webdav.example.com",
                writeback_enabled=True,
            )
        ],
        http_client_factory=lambda: fake_client,
    )

    result = await adapters.write_webdav(
        {
            "source_id": "webdav_src_1",
            "target_path": "/Naruon/Notes/task.md",
            "content": "# Note\n",
            "if_match": "etag-before-write",
        }
    )

    assert result == {
        "status": "error",
        "error": "invalid_source_url",
        "error_code": "invalid_source_url",
        "provider_write_executed": False,
    }
    assert fake_client.requests == []


@pytest.mark.asyncio
async def test_webdav_adapter_rejects_invalid_port_before_dns_lookup(monkeypatch):
    def fail_getaddrinfo(host, port, type=socket.SOCK_STREAM):
        raise AssertionError("invalid port URL should fail before DNS lookup")

    monkeypatch.setattr(
        "runner.local_dav_adapters.socket.getaddrinfo",
        fail_getaddrinfo,
    )
    fake_client = FakeDavClient(FakeDavResponse(204))
    adapters = LocalDavAdapters(
        [
            LocalDavSourceConfig(
                source_id="webdav_src_1",
                protocol="webdav",
                base_url="https://webdav.example.com:abc",
                writeback_enabled=True,
            )
        ],
        http_client_factory=lambda: fake_client,
    )

    result = await adapters.write_webdav(
        {
            "source_id": "webdav_src_1",
            "target_path": "/Naruon/Notes/task.md",
            "content": "# Note\n",
            "if_match": "etag-before-write",
        }
    )

    assert result == {
        "status": "error",
        "error": "invalid_source_url",
        "error_code": "invalid_source_url",
        "provider_write_executed": False,
    }
    assert fake_client.requests == []


def test_webdav_adapter_default_client_disables_redirects(monkeypatch):
    captured = {}

    def fake_async_client(**kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(
        "runner.local_dav_adapters.httpx.AsyncClient",
        fake_async_client,
    )

    assert LocalDavAdapters([])._default_http_client() is not None
    assert captured == {"follow_redirects": False, "timeout": 60}


@pytest.mark.asyncio
async def test_webdav_adapter_rejects_source_and_payload_errors():
    fake_client = FakeDavClient(FakeDavResponse(204))

    missing_source = LocalDavAdapters([], http_client_factory=lambda: fake_client)
    result = await missing_source.write_webdav({})
    assert result["error_code"] == "source_not_configured"

    disabled = LocalDavAdapters(
        [LocalDavSourceConfig("dav", "webdav", "https://dav.example.com")],
        http_client_factory=lambda: fake_client,
    )
    result = await disabled.write_webdav({"source_id": "dav"})
    assert result["error_code"] == "source_writeback_disabled"

    wrong_protocol = LocalDavAdapters(
        [
            LocalDavSourceConfig(
                "dav", "caldav", "https://dav.example.com", writeback_enabled=True
            )
        ],
        http_client_factory=lambda: fake_client,
    )
    result = await wrong_protocol.write_webdav({"source_id": "dav"})
    assert result["error_code"] == "source_not_configured"

    enabled = LocalDavAdapters(
        [
            LocalDavSourceConfig(
                "dav", "webdav", "https://dav.example.com", writeback_enabled=True
            )
        ],
        http_client_factory=lambda: fake_client,
    )
    base_payload = {
        "source_id": "dav",
        "target_path": "/Naruon/file.bin",
        "if_match": "etag",
    }
    result = await enabled.write_webdav({**base_payload, "content": object()})
    assert result["error_code"] == "invalid_payload"

    result = await enabled.write_webdav({**base_payload, "content": b"binary"})
    assert result["status"] == "success"
    assert fake_client.requests[-1]["content"] == b"binary"


@pytest.mark.asyncio
async def test_webdav_adapter_reports_http_transport_failure():
    class FailingDavClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def put(self, *_args, **_kwargs):
            raise httpx.ConnectError("provider unavailable")

    adapters = LocalDavAdapters(
        [
            LocalDavSourceConfig(
                "dav", "webdav", "https://dav.example.com", writeback_enabled=True
            )
        ],
        http_client_factory=FailingDavClient,
    )

    result = await adapters.write_webdav(
        {
            "source_id": "dav",
            "target_path": "/Naruon/file.md",
            "content": "note",
            "if_match": "etag",
        }
    )

    assert result["error_code"] == "provider_request_failed"


@pytest.mark.parametrize(
    "base_url",
    [
        "http://dav.example.com",
        "https:///missing-host",
        "https://user@dav.example.com",
        "https://user:secret@dav.example.com",
        "https://dav.example.com?query=1",
        "https://dav.example.com#fragment",
    ],
)
def test_webdav_adapter_rejects_malformed_source_urls(base_url):
    with pytest.raises(ValueError, match="invalid_source_url"):
        LocalDavAdapters([])._target_url(base_url, "/Naruon/file.md")


def test_webdav_adapter_validates_literal_ip_and_dns_results(monkeypatch):
    adapters = LocalDavAdapters([])
    assert adapters._target_url(
        "https://93.184.216.34/dav", "/Naruon/file.md"
    ) == "https://93.184.216.34/dav/Naruon/file.md"

    monkeypatch.setattr(
        "runner.local_dav_adapters.socket.getaddrinfo",
        lambda *_args, **_kwargs: [],
    )
    with pytest.raises(ValueError, match="invalid_source_url"):
        adapters._target_url("https://empty.example", "/Naruon/file.md")

    monkeypatch.setattr(
        "runner.local_dav_adapters.socket.getaddrinfo",
        lambda host, port, **_kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("not-an-ip", port))
        ],
    )
    with pytest.raises(ValueError, match="invalid_source_url"):
        adapters._target_url("https://invalid.example", "/Naruon/file.md")


def test_webdav_adapter_maps_success_without_etag_and_provider_failure():
    adapters = LocalDavAdapters([])

    assert adapters._result_from_response(FakeDavResponse(200)) == {
        "status": "success",
        "provider_write_executed": True,
        "provider_status": 200,
    }
    assert adapters._result_from_response(FakeDavResponse(500)) == {
        "status": "error",
        "error": "provider_write_failed",
        "error_code": "provider_write_failed",
        "provider_write_executed": False,
        "provider_status": 500,
    }
