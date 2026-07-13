"""Minimal httpx-based CardDAV client.

Mirrors the CalDAV/WebDAV runner pattern: it is intentionally small -- enough
to connect, PROPFIND for address books, and PUT a vCard for smoke testing.
SSL/TLS is implicit (https over 443 unless the URL carries an explicit port),
and every request target is SSRF-guarded against private/link-local hosts, the
same way ``LocalDavAdapters`` guards its writes.

Two properties bind the guard to the actual connection instead of a hostname
snapshot:

- Requests are DNS-pinned: the hostname is resolved once, every address is
  validated as globally routable, and the request connects to that validated
  address (with SNI/Host preserved for TLS verification), so a rebinding
  between validation and connect cannot redirect credentials.
- Clients are built with ``trust_env=False`` so ambient ``HTTPS_PROXY`` /
  ``ALL_PROXY`` configuration on the runner cannot reroute requests.
"""

from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass
from typing import Any, Callable
from urllib.parse import quote, unquote, urlsplit, urlunsplit

import httpx

_ADDRESSBOOK_PROPFIND = (
    '<?xml version="1.0" encoding="utf-8"?>'
    '<D:propfind xmlns:D="DAV:" xmlns:C="urn:ietf:params:xml:ns:carddav">'
    "<D:prop><D:resourcetype/><D:displayname/>"
    "<C:addressbook-home-set/></D:prop></D:propfind>"
)

_MAX_VCARD_PATH_LENGTH = 4096
_MAX_URL_DECODE_ROUNDS = 4


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


def _resolved_global_addresses(hostname: str, port: int) -> list[str]:
    """Resolve a hostname once and require every address to be global."""
    if hostname == "localhost" or hostname.endswith(".localhost"):
        raise ValueError("invalid_carddav_url")
    try:
        ipaddress.ip_address(hostname)
    except ValueError:
        pass
    else:
        _validate_global_address(hostname)
        return [hostname]
    try:
        address_infos = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise ValueError("invalid_carddav_url") from exc
    addresses = [str(info[4][0]) for info in address_infos]
    if not addresses:
        raise ValueError("invalid_carddav_url")
    for address in dict.fromkeys(addresses):
        _validate_global_address(address)
    return addresses


def _validate_global_host(hostname: str, port: int) -> None:
    _resolved_global_addresses(hostname, port)


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


def pinned_request_target(url: str) -> tuple[str, dict[str, str], dict[str, Any]]:
    """Pin a validated URL to one resolved global address (anti-rebinding).

    Returns ``(pinned_url, headers, extensions)``: the URL rewritten to a
    validated literal address, a ``Host`` header carrying the original
    authority, and the ``sni_hostname`` extension so TLS still negotiates and
    verifies against the original hostname. Using the same resolution for
    validation and connection closes the validate-then-reconnect DNS window.
    """
    parsed = urlsplit(url)
    hostname = parsed.hostname or ""
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError("invalid_carddav_url") from exc
    addresses = _resolved_global_addresses(hostname, port or 443)
    address = next(
        (candidate for candidate in addresses if ":" not in candidate),
        addresses[0],
    )
    literal = f"[{address}]" if ":" in address else address
    netloc = literal if port is None else f"{literal}:{port}"
    pinned = urlunsplit(
        (parsed.scheme, netloc, parsed.path, parsed.query, parsed.fragment)
    )
    return pinned, {"Host": parsed.netloc}, {"sni_hostname": hostname}


def _safe_vcard_path(raw_path: Any) -> str | None:
    """Canonicalize a caller-supplied vCard path or reject traversal/URL input.

    Mirrors ``LocalDavAdapters._safe_target_path``: multi-round decode, then
    reject absolute URLs, backslashes, query/fragment, control characters, and
    dot segments, so the composed target can never leave the configured
    address-book subtree or change host.
    """
    if (
        not isinstance(raw_path, str)
        or not raw_path
        or len(raw_path) > _MAX_VCARD_PATH_LENGTH
    ):
        return None

    decoded_path = raw_path
    try:
        for _ in range(_MAX_URL_DECODE_ROUNDS):
            next_path = unquote(decoded_path, errors="strict")
            if next_path == decoded_path:
                break
            decoded_path = next_path
        else:
            if unquote(decoded_path, errors="strict") != decoded_path:
                return None
    except UnicodeDecodeError:
        return None

    if (
        "\\" in decoded_path
        or "://" in decoded_path
        or "?" in decoded_path
        or "#" in decoded_path
        or decoded_path.startswith("//")
        or any(
            ord(character) < 32 or ord(character) == 127
            for character in decoded_path
        )
    ):
        return None
    segments = [segment for segment in decoded_path.split("/") if segment]
    if not segments or any(segment in {".", ".."} for segment in segments):
        return None
    return "/".join(
        quote(segment, safe="@:$&'()*+,;=-._~") for segment in segments
    )


def _default_http_client() -> httpx.AsyncClient:
    # trust_env=False keeps runner proxy environment variables from rerouting
    # credentialed CardDAV requests.
    return httpx.AsyncClient(follow_redirects=False, timeout=30, trust_env=False)


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
            target, pinned_headers, extensions = pinned_request_target(self._base_url)
            async with self._http_client_factory() as client:
                response = await client.request(
                    "PROPFIND",
                    target,
                    headers={**headers, **pinned_headers},
                    content=_ADDRESSBOOK_PROPFIND.encode("utf-8"),
                    auth=self._auth(),
                    extensions=extensions,
                )
        except (httpx.HTTPError, ValueError):
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
        safe_path = _safe_vcard_path(relative_path)
        if safe_path is None:
            raise ValueError("invalid_carddav_path")
        composed = self._base_url.rstrip("/") + "/" + safe_path
        # Re-validate the composed URL to keep the SSRF guard on joins.
        _validated_base_url(composed)
        target, pinned_headers, extensions = pinned_request_target(composed)
        content = vcard.encode("utf-8") if isinstance(vcard, str) else vcard
        headers = {"Content-Type": "text/vcard; charset=utf-8", **pinned_headers}
        if if_match is not None:
            headers["If-Match"] = if_match
        async with self._http_client_factory() as client:
            response = await client.put(
                target,
                content=content,
                headers=headers,
                auth=self._auth(),
                extensions=extensions,
            )
        return int(response.status_code)


__all__ = ["CardDavClient", "CarddavProbeResult", "pinned_request_target"]
