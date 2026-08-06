"""Regression tests for the outbound Scopeweave work-item client."""

from __future__ import annotations

from typing import Any

import httpx
import pytest

import services.scopeweave_client as scopeweave_client
from core.url_validation import ValidatedHTTPSURLHost


class _StubAsyncClient:
    """Record one request and return or raise the configured outcome."""

    def __init__(
        self,
        *,
        response: httpx.Response | None = None,
        error: httpx.HTTPError | None = None,
    ) -> None:
        self.response = response
        self.error = error
        self.request: dict[str, Any] | None = None
        self.closed = False

    async def post(
        self,
        url: str,
        *,
        json: dict[str, Any],
        headers: dict[str, str],
        timeout: float,
    ) -> httpx.Response:
        """Record the POST arguments and produce the configured outcome."""
        self.request = {
            "url": url,
            "json": json,
            "headers": headers,
            "timeout": timeout,
        }
        if self.error is not None:
            raise self.error
        assert self.response is not None
        return self.response

    async def aclose(self) -> None:
        """Record that production code closed the outbound transport."""
        self.closed = True


def _validated_host() -> ValidatedHTTPSURLHost:
    """Return a deterministic already-validated Scopeweave destination."""
    return ValidatedHTTPSURLHost(
        normalized_url="https://scopeweave.example.com",
        hostname="scopeweave.example.com",
        port=443,
        addresses=("8.8.8.8",),
    )


def _install_client(
    monkeypatch: pytest.MonkeyPatch,
    client: _StubAsyncClient,
) -> list[tuple[str, str, int, tuple[str, ...]]]:
    """Install deterministic URL validation and transport construction."""
    factory_calls: list[tuple[str, str, int, tuple[str, ...]]] = []
    monkeypatch.setattr(
        scopeweave_client,
        "validate_scopeweave_base_url",
        lambda _base_url: _validated_host(),
    )

    def build_client(
        normalized_url: str,
        hostname: str,
        port: int,
        addresses: tuple[str, ...],
    ) -> _StubAsyncClient:
        factory_calls.append((normalized_url, hostname, port, addresses))
        return client

    monkeypatch.setattr(
        scopeweave_client,
        "build_pinned_https_async_client",
        build_client,
    )
    return factory_calls


def test_import_url_normalizes_trailing_slashes() -> None:
    """Construct one stable import endpoint with or without a trailing slash."""
    host = _validated_host()
    assert (
        scopeweave_client._import_url(host)
        == "https://scopeweave.example.com/api/imports/work-items"
    )
    host_with_slash = ValidatedHTTPSURLHost(
        normalized_url="https://scopeweave.example.com/",
        hostname=host.hostname,
        port=host.port,
        addresses=host.addresses,
    )
    assert (
        scopeweave_client._import_url(host_with_slash)
        == "https://scopeweave.example.com/api/imports/work-items"
    )


def test_parse_import_result_rejects_invalid_json() -> None:
    """Reject successful HTTP responses that do not contain JSON."""
    with pytest.raises(
        scopeweave_client.ScopeweavePushError,
        match="scopeweave returned a non-JSON import response",
    ):
        scopeweave_client._parse_import_result(httpx.Response(201, text="not json"))


def test_parse_import_result_rejects_non_object_json() -> None:
    """Reject JSON values that cannot represent a work-item result."""
    with pytest.raises(
        scopeweave_client.ScopeweavePushError,
        match="scopeweave import response was not an object",
    ):
        scopeweave_client._parse_import_result(httpx.Response(201, json=["list"]))


def test_parse_import_result_requires_work_item_id() -> None:
    """Reject result objects that omit both supported identifier fields."""
    with pytest.raises(
        scopeweave_client.ScopeweavePushError,
        match="scopeweave import response omitted a work item id",
    ):
        scopeweave_client._parse_import_result(
            httpx.Response(201, json={"work_item_url": "url"})
        )


def test_parse_import_result_accepts_fallback_id() -> None:
    """Accept the generic identifier field used by older Scopeweave versions."""
    result = scopeweave_client._parse_import_result(
        httpx.Response(201, json={"id": "fallback-id"})
    )
    assert result.work_item_id == "fallback-id"


@pytest.mark.asyncio
async def test_push_work_item_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """Send the exact authenticated payload through the DNS-pinned client."""
    response = httpx.Response(
        201,
        json={
            "work_item_id": "WI-42",
            "work_item_url": "https://scopeweave.example.com/w/WI-42",
        },
    )
    client = _StubAsyncClient(response=response)
    factory_calls = _install_client(monkeypatch, client)

    result = await scopeweave_client.push_work_item(
        base_url="https://scopeweave.example.com",
        access_token="pat-secret",
        payload={"hello": "world"},
    )

    assert factory_calls == [
        (
            "https://scopeweave.example.com",
            "scopeweave.example.com",
            443,
            ("8.8.8.8",),
        )
    ]
    assert client.request == {
        "url": "https://scopeweave.example.com/api/imports/work-items",
        "json": {"hello": "world"},
        "headers": {
            "authorization": "Bearer pat-secret",
            "content-type": "application/json",
            "accept": "application/json",
        },
        "timeout": 15.0,
    }
    assert client.closed is True
    assert result == scopeweave_client.ScopeweaveImportResult(
        work_item_id="WI-42",
        work_item_url="https://scopeweave.example.com/w/WI-42",
        status_code=201,
    )


@pytest.mark.asyncio
async def test_push_work_item_rejects_error_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reject non-success responses and still close the outbound transport."""
    client = _StubAsyncClient(
        response=httpx.Response(400, json={"error": "bad request"})
    )
    _install_client(monkeypatch, client)

    with pytest.raises(
        scopeweave_client.ScopeweavePushError,
        match="scopeweave import rejected the work item",
    ):
        await scopeweave_client.push_work_item(
            base_url="https://scopeweave.example.com",
            access_token="pat-secret",
            payload={"hello": "world"},
        )

    assert client.closed is True


@pytest.mark.asyncio
async def test_push_work_item_wraps_transport_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Translate HTTP transport failures and close the outbound transport."""
    client = _StubAsyncClient(error=httpx.ConnectError("Connection failed"))
    _install_client(monkeypatch, client)

    with pytest.raises(
        scopeweave_client.ScopeweavePushError,
        match="scopeweave import request failed",
    ):
        await scopeweave_client.push_work_item(
            base_url="https://scopeweave.example.com",
            access_token="pat-secret",
            payload={"hello": "world"},
        )

    assert client.closed is True
