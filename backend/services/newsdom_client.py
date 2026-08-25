"""SSRF-safe client for the NewsDOM PDF DOM recognition sidecar.

This mirrors :mod:`services.llm_provider_urls`: the configured base URL is
validated against a dedicated allowlist (``ALLOWED_NEWSDOM_HOSTS``), the
hostname is resolved to concrete IP addresses, every address is checked to be
globally routable (unless ``ALLOW_LOCAL_NEWSDOM_PROVIDERS`` is set for docker /
loopback development), and the outbound connection is *pinned* to those
validated addresses so a DNS-rebind between validation and connect cannot
redirect the request to an internal host.

The base URL and bearer token are always supplied by the caller from the
database (see :class:`db.models.NewsdomProvider`) — this module never reads
service configuration or secrets from the environment at request time.
"""

from __future__ import annotations

import asyncio
import ipaddress
import socket
from dataclasses import dataclass
from urllib.parse import SplitResult, urlsplit, urlunsplit

import httpcore
import httpx
from httpcore._backends.auto import AutoBackend
from httpx._config import DEFAULT_LIMITS, create_ssl_context
from httpx._transports.default import AsyncResponseStream, map_httpcore_exceptions

from core.config import settings

NEWSDOM_BASE_URL_NOT_ALLOWED = "NewsDOM base URL is not allowed"
_DNS_RESOLUTION_TIMEOUT_SECONDS = 5.0
_LOCAL_DEV_HOSTNAMES = {"localhost", "localhost.localdomain"}
_LOCAL_DEV_IP_LITERALS = {"127.0.0.1", "::1"}
_DEFAULT_PARSE_TIMEOUT_SECONDS = 300.0
# The deployed NewsDOM ``/parse`` contract accepts at most 20 MiB. Keep this
# boundary explicit so deferred 64 MiB retention cannot remain pending forever.
NEWSDOM_MAX_PARSE_UPLOAD_BYTES = 20 * 1024 * 1024


class NewsdomConfigurationError(RuntimeError):
    """Raised when the NewsDOM sidecar is not usably configured."""


class NewsdomRequestError(RuntimeError):
    """Raised when the NewsDOM sidecar cannot fulfil a parse request."""


class NewsdomPayloadTooLargeError(NewsdomRequestError):
    """Raised before network I/O when a PDF exceeds the sidecar contract."""


class NewsdomEmptyRecognitionError(NewsdomRequestError):
    """Raised when a 200 sidecar response carries no usable recognized text.

    Treated as a retryable recognition failure so the caller records an error
    status instead of marking the source ``parsed`` with empty content.
    """


@dataclass(frozen=True)
class ValidatedNewsdomBaseURL:
    normalized_url: str
    hostname: str
    port: int
    addresses: tuple[str, ...]


def _has_url_control_character(value: str) -> bool:
    return any(ord(character) < 32 or ord(character) == 127 for character in value)


def _parse_allowed_hosts() -> set[str]:
    return {
        item.strip().lower().rstrip(".")
        for item in settings.ALLOWED_NEWSDOM_HOSTS.split(",")
        if item.strip()
    }


def _is_ip_literal(candidate: str) -> bool:
    try:
        ipaddress.ip_address(candidate)
    except ValueError:
        return False
    return True


def _looks_like_ip_literal(candidate: str) -> bool:
    compact_candidate = candidate.replace(".", "").lower()
    return (
        ":" in candidate
        or compact_candidate.isdigit()
        or compact_candidate.startswith("0x")
    )


def _is_local_dev_host(hostname: str) -> bool:
    normalized_hostname = hostname.lower().rstrip(".")
    return (
        normalized_hostname in _LOCAL_DEV_HOSTNAMES
        or normalized_hostname in _LOCAL_DEV_IP_LITERALS
    )


def _is_allowlisted_local_host(hostname: str) -> bool:
    """A bare docker-container name (e.g. ``newsdom``) that is explicitly
    allowlisted while local providers are enabled."""
    normalized_hostname = hostname.lower().rstrip(".")
    return (
        settings.ALLOW_LOCAL_NEWSDOM_PROVIDERS
        and normalized_hostname in _parse_allowed_hosts()
        and "." not in normalized_hostname
        and not _is_ip_literal(normalized_hostname)
        and not _looks_like_ip_literal(normalized_hostname)
    )


def _format_normalized_netloc(hostname: str, port: int, *, explicit_port: bool) -> str:
    host_part = f"[{hostname}]" if ":" in hostname else hostname
    if not explicit_port:
        return host_part
    return f"{host_part}:{port}"


def _validate_global_address(address: str, *, hostname: str | None = None) -> str:
    try:
        ip_address = ipaddress.ip_address(address)
    except ValueError as exc:
        raise ValueError(NEWSDOM_BASE_URL_NOT_ALLOWED) from exc

    is_allowed_local = False
    if settings.ALLOW_LOCAL_NEWSDOM_PROVIDERS:
        if ip_address.is_loopback:
            is_allowed_local = True
        elif hostname and _is_allowlisted_local_host(hostname):
            is_allowed_local = True

    if not is_allowed_local:
        if (
            ip_address.is_private
            or ip_address.is_loopback
            or ip_address.is_link_local
            or ip_address.is_reserved
            or ip_address.is_unspecified
            or ip_address.is_multicast
            or not ip_address.is_global
        ):
            raise ValueError(NEWSDOM_BASE_URL_NOT_ALLOWED)
    return str(ip_address)


def _resolve_all_global_addresses(hostname: str, port: int) -> tuple[str, ...]:
    try:
        address_infos = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise ValueError(NEWSDOM_BASE_URL_NOT_ALLOWED) from exc

    if not address_infos:
        raise ValueError(NEWSDOM_BASE_URL_NOT_ALLOWED)
    addresses: list[str] = []
    seen_addresses: set[str] = set()
    for address_info in address_infos:
        address = _validate_global_address(str(address_info[4][0]), hostname=hostname)
        if address not in seen_addresses:
            seen_addresses.add(address)
            addresses.append(address)
    return tuple(addresses)


async def _resolve_all_global_addresses_async(
    hostname: str, port: int
) -> tuple[str, ...]:
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(_resolve_all_global_addresses, hostname, port),
            timeout=_DNS_RESOLUTION_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError as exc:
        raise ValueError(NEWSDOM_BASE_URL_NOT_ALLOWED) from exc


def _parse_and_validate_candidate_url(
    value: str | None,
) -> tuple[SplitResult | None, int | None]:
    if value is None:
        return None, None
    candidate = value.strip()
    if not candidate:
        return None, None
    if "\\" in candidate or _has_url_control_character(candidate):
        raise ValueError(NEWSDOM_BASE_URL_NOT_ALLOWED)
    try:
        parsed = urlsplit(candidate)
        default_port = 443 if parsed.scheme.lower() == "https" else 80
        port = parsed.port or default_port
        return parsed, port
    except ValueError as exc:
        raise ValueError(NEWSDOM_BASE_URL_NOT_ALLOWED) from exc


def _validate_url_components(parsed, hostname: str, is_local_dev_host: bool) -> None:
    if parsed.scheme.lower() not in {"http", "https"}:
        raise ValueError(NEWSDOM_BASE_URL_NOT_ALLOWED)
    if (
        parsed.scheme.lower() == "http"
        and not is_local_dev_host
        and not _is_allowlisted_local_host(hostname)
    ):
        raise ValueError(NEWSDOM_BASE_URL_NOT_ALLOWED)
    if (
        not hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError(NEWSDOM_BASE_URL_NOT_ALLOWED)


def _validate_remote_host_is_allowed(hostname: str) -> None:
    allowed_hosts = _parse_allowed_hosts()
    if not allowed_hosts or any("*" in allowed_host for allowed_host in allowed_hosts):
        raise ValueError(NEWSDOM_BASE_URL_NOT_ALLOWED)
    if hostname not in allowed_hosts:
        raise ValueError(NEWSDOM_BASE_URL_NOT_ALLOWED)
    if _is_ip_literal(hostname) or _looks_like_ip_literal(hostname):
        raise ValueError(NEWSDOM_BASE_URL_NOT_ALLOWED)


def _normalize_newsdom_base_url(value: str | None):
    parsed, port = _parse_and_validate_candidate_url(value)
    if parsed is None or port is None:
        return None, None, None

    hostname = (parsed.hostname or "").lower().rstrip(".")
    is_local_dev_host = _is_local_dev_host(hostname)
    _validate_url_components(parsed, hostname, is_local_dev_host)

    # localhost / loopback is only usable when local providers are enabled.
    if is_local_dev_host and not settings.ALLOW_LOCAL_NEWSDOM_PROVIDERS:
        raise ValueError(NEWSDOM_BASE_URL_NOT_ALLOWED)
    if not is_local_dev_host:
        _validate_remote_host_is_allowed(hostname)

    netloc = _format_normalized_netloc(
        hostname, port, explicit_port=parsed.port is not None
    )
    return (
        urlunsplit((parsed.scheme.lower(), netloc, parsed.path or "", "", "")),
        hostname,
        port,
    )


async def validate_newsdom_base_url_details_async(
    value: str | None,
) -> ValidatedNewsdomBaseURL | None:
    normalized_url, hostname, port = _normalize_newsdom_base_url(value)
    if normalized_url is None:
        return None
    addresses = await _resolve_all_global_addresses_async(hostname, port)
    return ValidatedNewsdomBaseURL(normalized_url, hostname, port, addresses)


class _PinnedNewsdomNetworkBackend(httpcore.AsyncNetworkBackend):
    def __init__(self, hostname: str, port: int, addresses: tuple[str, ...]):
        if not addresses:
            raise ValueError(NEWSDOM_BASE_URL_NOT_ALLOWED)
        self._hostname = hostname
        self._port = port
        self._addresses = tuple(
            _validate_global_address(address, hostname=hostname)
            for address in addresses
        )
        self._backend = AutoBackend()

    def _verify_host_port(self, host: str | bytes, port: int) -> None:
        host_text = host.decode("ascii") if isinstance(host, bytes) else str(host)
        normalized_host = host_text.lower().rstrip(".")
        if normalized_host != self._hostname or int(port) != self._port:
            raise OSError("NewsDOM base URL host changed after validation")

    async def connect_tcp(
        self,
        host: str | bytes,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options=None,
    ):
        self._verify_host_port(host, port)
        last_error: Exception | None = None
        for address in self._addresses:
            pinned_address = _validate_global_address(address, hostname=self._hostname)
            try:
                return await self._backend.connect_tcp(
                    pinned_address,
                    port,
                    timeout=timeout,
                    local_address=local_address,
                    socket_options=socket_options,
                )
            except Exception as exc:  # pragma: no cover - backend-specific
                last_error = exc
        if last_error is not None:
            raise last_error
        raise OSError(NEWSDOM_BASE_URL_NOT_ALLOWED)

    async def connect_unix_socket(
        self,
        path: str,
        timeout: float | None = None,
        socket_options=None,
    ):
        raise OSError("NewsDOM base URL must not use Unix sockets")

    async def sleep(self, seconds: float) -> None:
        await self._backend.sleep(seconds)


class _PinnedNewsdomAsyncTransport(httpx.AsyncBaseTransport):
    def __init__(self, validated: ValidatedNewsdomBaseURL):
        self._validated = validated
        ssl_context = create_ssl_context(verify=True, trust_env=False)
        self._pool = httpcore.AsyncConnectionPool(
            ssl_context=ssl_context,
            max_connections=DEFAULT_LIMITS.max_connections,
            max_keepalive_connections=DEFAULT_LIMITS.max_keepalive_connections,
            keepalive_expiry=DEFAULT_LIMITS.keepalive_expiry,
            http1=True,
            http2=False,
            network_backend=_PinnedNewsdomNetworkBackend(
                validated.hostname,
                validated.port,
                validated.addresses,
            ),
        )

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        parsed_url = urlsplit(self._validated.normalized_url)
        validated_scheme = parsed_url.scheme.encode("ascii")
        validated_host = self._validated.hostname.encode("ascii")
        validated_netloc = parsed_url.netloc.encode("ascii")

        safe_headers = [
            (key, value)
            for key, value in request.headers.raw
            if key.lower() != b"host"
        ]
        safe_headers.append((b"host", validated_netloc))

        req = httpcore.Request(
            method=request.method,
            url=httpcore.URL(
                scheme=validated_scheme,
                host=validated_host,
                port=self._validated.port,
                target=request.url.raw_path,
            ),
            headers=safe_headers,
            content=request.stream,
            extensions=request.extensions,
        )
        with map_httpcore_exceptions():
            resp = await self._pool.handle_async_request(req)

        return httpx.Response(
            status_code=resp.status,
            headers=resp.headers,
            stream=AsyncResponseStream(resp.stream),
            extensions=resp.extensions,
        )

    async def aclose(self) -> None:
        await self._pool.aclose()


def _joined_url(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"


async def request_pdf_dom(
    *,
    base_url: str | None,
    api_token: str | None,
    pdf_bytes: bytes,
    filename: str = "document.pdf",
    language: str = "auto",
    mode: str = "auto",
    timeout_seconds: float = _DEFAULT_PARSE_TIMEOUT_SECONDS,
) -> dict:
    """POST the PDF bytes to ``{base_url}/parse`` and return the parsed DOM.

    Targets the generalized NewsDOM ``/parse`` contract: a multipart request
    carrying the PDF under ``file`` plus ``language`` / ``mode`` form fields and
    an optional ``Authorization: Bearer`` header. Unknown extra form fields are
    ignored by the current sidecar, keeping this forward-compatible.
    """
    if not pdf_bytes:
        raise NewsdomRequestError("Cannot recognize an empty PDF payload")
    if len(pdf_bytes) > NEWSDOM_MAX_PARSE_UPLOAD_BYTES:
        raise NewsdomPayloadTooLargeError(
            "NewsDOM PDF payload exceeds the 20 MiB parse upload contract"
        )

    validated = await validate_newsdom_base_url_details_async(base_url)
    if validated is None:
        raise NewsdomConfigurationError(
            "NewsDOM base URL is not configured for this workspace"
        )

    headers: dict[str, str] = {}
    if api_token and api_token.strip():
        headers["Authorization"] = f"Bearer {api_token.strip()}"

    files = {"file": (filename or "document.pdf", pdf_bytes, "application/pdf")}
    data = {"language": language or "auto", "mode": mode or "auto"}

    async with httpx.AsyncClient(
        follow_redirects=False,
        trust_env=False,
        timeout=timeout_seconds,
        transport=_PinnedNewsdomAsyncTransport(validated),
    ) as client:
        try:
            response = await client.post(
                _joined_url(validated.normalized_url, "/parse"),
                files=files,
                data=data,
                headers=headers,
            )
        except httpx.HTTPError as exc:
            raise NewsdomRequestError(f"NewsDOM request failed: {exc}") from exc

    if response.status_code >= 400:
        raise NewsdomRequestError(
            f"NewsDOM returned HTTP {response.status_code} for /parse"
        )
    try:
        return response.json()
    except ValueError as exc:
        raise NewsdomRequestError("NewsDOM returned a non-JSON response") from exc
