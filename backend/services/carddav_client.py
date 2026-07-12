"""Minimal httpx-based CardDAV client.

Mirrors the CalDAV/WebDAV runner pattern: it is intentionally small -- enough
to connect, PROPFIND for address books, and PUT a vCard for smoke testing.
SSL/TLS is implicit (https over 443 unless the URL carries an explicit port),
and every request target is SSRF-guarded against private/link-local hosts, the
same way ``LocalDavAdapters`` guards its writes.
"""

from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass
from typing import Any, Callable
from urllib.parse import urljoin, urlsplit, urlunsplit

import httpx

_ADDRESSBOOK_PROPFIND = (
    '<?xml version="1.0" encoding="utf-8"?>'
    '<D:propfind xmlns:D="DAV:" xmlns:C="urn:ietf:params:xml:ns:carddav">'
    "<D:prop><D:resourcetype/><D:displayname/>"
    "<C:addressbook-home-set/></D:prop></D:propfind>"
)


@dataclass(frozen=True)
class CarddavProbeResult:
    reachable: bool
    status_code: int | None
    base_url: str


def _validate_global_address(address: str) -> None:
    try:
        ip_address = ipaddress.ip_address(address)
    except ValueError as exc:
        raise ValueError("invalid_carddav_url") from exc
    if not ip_address.is_global:
        raise ValueError("invalid_carddav_url")


def _validate_global_host(hostname: str, port: int) -> None:
    if hostname == "localhost" or hostname.endswith(".localhost"):
        raise ValueError("invalid_carddav_url")
    try:
        ipaddress.ip_address(hostname)
    except ValueError:
        pass
    else:
        _validate_global_address(hostname)
        return
    try:
        address_infos = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise ValueError("invalid_carddav_url") from exc
    addresses = {str(info[4][0]) for info in address_infos}
    if not addresses:
        raise ValueError("invalid_carddav_url")
    for address in addresses:
        _validate_global_address(address)


def _validated_base_url(base_url: str) -> str:
    parsed = urlsplit(base_url)
    if (
        parsed.scheme != "https"
        or not parsed.netloc
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("invalid_carddav_url")
    try:
        port = parsed.port or 443
    except ValueError as exc:
        raise ValueError("invalid_carddav_url") from exc
    _validate_global_host(parsed.hostname, port)
    path = parsed.path or "/"
    return urlunsplit((parsed.scheme, parsed.netloc, path, "", ""))


def _default_http_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(follow_redirects=False, timeout=30)


class CardDavClient:
    """Small CardDAV client for connectivity checks and vCard writes."""

    def __init__(
        self,
        base_url: str,
        *,
        username: str | None = None,
        password: str | None = None,
        http_client_factory: Callable[[], Any] | None = None,
    ):
        self._base_url = _validated_base_url(base_url)
        self._username = username
        self._password = password
        self._http_client_factory = http_client_factory or _default_http_client

    @property
    def base_url(self) -> str:
        return self._base_url

    def _auth(self):
        if self._username is None:
            return None
        return (self._username, self._password or "")

    async def list_address_books(self) -> CarddavProbeResult:
        """PROPFIND Depth:1 for address books; returns a reachability result."""
        headers = {"Depth": "1", "Content-Type": "application/xml; charset=utf-8"}
        try:
            async with self._http_client_factory() as client:
                response = await client.request(
                    "PROPFIND",
                    self._base_url,
                    headers=headers,
                    content=_ADDRESSBOOK_PROPFIND.encode("utf-8"),
                    auth=self._auth(),
                )
        except httpx.HTTPError:
            return CarddavProbeResult(
                reachable=False, status_code=None, base_url=self._base_url
            )
        status = int(response.status_code)
        # 207 Multi-Status is the success case; 200/401/403 still prove the
        # endpoint is a live CardDAV/HTTP server (reachable), which is all a
        # smoke check asserts.
        reachable = status in {200, 207, 401, 403}
        return CarddavProbeResult(
            reachable=reachable, status_code=status, base_url=self._base_url
        )

    async def put_vcard(
        self,
        relative_path: str,
        vcard: str | bytes,
        *,
        if_match: str | None = None,
    ) -> int:
        """PUT a vCard beneath the base URL; returns the provider status code."""
        target = urljoin(self._base_url.rstrip("/") + "/", relative_path.lstrip("/"))
        # Re-validate the composed URL to keep the SSRF guard on redirects/joins.
        _validated_base_url(target)
        content = vcard.encode("utf-8") if isinstance(vcard, str) else vcard
        headers = {"Content-Type": "text/vcard; charset=utf-8"}
        if if_match is not None:
            headers["If-Match"] = if_match
        async with self._http_client_factory() as client:
            response = await client.put(
                target,
                content=content,
                headers=headers,
                auth=self._auth(),
            )
        return int(response.status_code)


__all__ = ["CardDavClient", "CarddavProbeResult"]
