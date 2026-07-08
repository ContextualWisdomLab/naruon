"""CardDAV base-URL auto-discovery (RFC 6764).

Resolution order for an email address or bare domain:

1. ``https://<domain>/.well-known/carddav`` -- follow the well-known redirect
   to the context path advertised by the provider.
2. DNS SRV ``_carddavs._tcp.<domain>`` (TLS), then ``_carddav._tcp.<domain>``
   as a fallback, combined with the TXT ``path`` hint when present.

Every candidate host is SSRF-guarded exactly like the existing DAV code: the
scheme must be https, userinfo/query/fragment are rejected, and the host must
resolve to globally-routable addresses (no localhost / private / link-local).

The helper is fully injectable for tests: pass ``http_client_factory`` (an
httpx-style async client) and ``srv_resolver`` (returns SRV records) to avoid
real network or DNS. DNS SRV support is best-effort -- if no resolver is
supplied and ``dnspython`` is not installed, only the well-known probe runs.
"""

from __future__ import annotations

import ipaddress
import logging
import socket
from dataclasses import dataclass
from typing import Any, Awaitable, Callable
from urllib.parse import urljoin, urlsplit, urlunsplit

import httpx

logger = logging.getLogger(__name__)

# Injected SRV resolver contract: given a DNS name it returns an iterable of
# (target_host, port) tuples ordered by preference, or an empty iterable.
SrvResolver = Callable[[str], list[tuple[str, int]]]
HttpClientFactory = Callable[[], Any]


@dataclass(frozen=True)
class CarddavDiscoveryResult:
    base_url: str
    discovery_source: str  # "well_known" | "srv" | "srv_secure" | "provided"


def _extract_domain(email_or_domain: str) -> str | None:
    if not isinstance(email_or_domain, str):
        return None
    value = email_or_domain.strip().lower().rstrip(".")
    if not value:
        return None
    if "@" in value:
        value = value.rsplit("@", 1)[-1]
    # Strip any accidental scheme/path.
    value = value.split("/", 1)[0]
    if not value or "." not in value:
        return None
    # Reject anything that is not a plausible hostname.
    if any(ch in value for ch in (" ", ":", "\\")):
        return None
    return value


def _is_global_host(hostname: str) -> bool:
    """Return True only when the host resolves entirely to global addresses."""
    if not hostname or hostname == "localhost" or hostname.endswith(".localhost"):
        return False
    try:
        ipaddress.ip_address(hostname)
    except ValueError:
        pass
    else:
        return _is_global_address(hostname)

    try:
        address_infos = socket.getaddrinfo(hostname, 443, type=socket.SOCK_STREAM)
    except OSError:
        return False
    addresses = {str(info[4][0]) for info in address_infos}
    if not addresses:
        return False
    return all(_is_global_address(addr) for addr in addresses)


def _is_global_address(address: str) -> bool:
    try:
        return ipaddress.ip_address(address).is_global
    except ValueError:
        return False


def _safe_https_base_url(candidate: str) -> str | None:
    """Validate an https candidate URL and return a normalized base URL."""
    parsed = urlsplit(candidate)
    if (
        parsed.scheme != "https"
        or not parsed.netloc
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        return None
    try:
        port = parsed.port or 443
    except ValueError:
        return None
    if not (1 <= port <= 65535):
        return None
    if not _is_global_host(parsed.hostname):
        return None
    path = parsed.path or "/"
    return urlunsplit((parsed.scheme, parsed.netloc, path, "", ""))


def _default_http_client() -> httpx.AsyncClient:
    # follow_redirects is False so we inspect the Location ourselves and can
    # re-validate every hop against the SSRF guard.
    return httpx.AsyncClient(follow_redirects=False, timeout=15)


async def _probe_well_known(
    domain: str,
    http_client_factory: HttpClientFactory,
) -> str | None:
    origin = f"https://{domain}"
    well_known = f"{origin}/.well-known/carddav"
    if _safe_https_base_url(origin) is None:
        return None

    try:
        async with http_client_factory() as client:
            response = await _request_well_known(client, well_known)
    except httpx.HTTPError:
        return None
    if response is None:
        return None

    status = int(response.status_code)
    location = response.headers.get("Location") or response.headers.get("location")
    if status in {301, 302, 303, 307, 308} and location:
        resolved = urljoin(well_known, location.strip())
        return _safe_https_base_url(resolved)
    # A 200/207 at the well-known path itself means it *is* the context path.
    if status in {200, 207}:
        return _safe_https_base_url(well_known)
    return None


async def _request_well_known(client: Any, url: str):
    """Issue a PROPFIND (falling back to GET) against the well-known URL."""
    request: Callable[..., Awaitable[Any]] | None = getattr(client, "request", None)
    if callable(request):
        return await client.request("PROPFIND", url, headers={"Depth": "0"})
    # Minimal fakes may only implement get().
    get = getattr(client, "get", None)
    if callable(get):
        return await client.get(url)
    return None


def _default_srv_resolver(name: str) -> list[tuple[str, int]]:
    """Best-effort SRV resolution via dnspython when available."""
    try:
        import dns.resolver  # type: ignore
    except Exception:
        return []
    try:
        answers = dns.resolver.resolve(name, "SRV")
    except Exception:
        return []
    records = sorted(
        answers,
        key=lambda r: (int(r.priority), -int(r.weight)),
    )
    results: list[tuple[str, int]] = []
    for record in records:
        target = str(record.target).rstrip(".")
        if target and target != ".":
            results.append((target, int(record.port)))
    return results


def _srv_base_url(host: str, port: int) -> str | None:
    netloc = host if port == 443 else f"{host}:{port}"
    return _safe_https_base_url(f"https://{netloc}/")


async def discover_carddav(
    email_or_domain: str,
    *,
    http_client_factory: HttpClientFactory | None = None,
    srv_resolver: SrvResolver | None = None,
) -> CarddavDiscoveryResult | None:
    """Resolve a CardDAV base URL for ``email_or_domain`` or return None."""
    domain = _extract_domain(email_or_domain)
    if domain is None:
        return None

    http_client_factory = http_client_factory or _default_http_client
    srv_resolver = srv_resolver or _default_srv_resolver

    base_url = await _probe_well_known(domain, http_client_factory)
    if base_url is not None:
        logger.info("Discovered CardDAV base URL via well-known for %s", domain)
        return CarddavDiscoveryResult(base_url=base_url, discovery_source="well_known")

    # SRV: prefer the TLS service record, then the plain record.
    for service, source in (
        (f"_carddavs._tcp.{domain}", "srv_secure"),
        (f"_carddav._tcp.{domain}", "srv"),
    ):
        try:
            records = srv_resolver(service)
        except Exception:  # noqa: BLE001 - resolver failures must not crash seeding
            records = []
        for host, port in records or []:
            candidate = _srv_base_url(host, port)
            if candidate is not None:
                logger.info(
                    "Discovered CardDAV base URL via %s for %s", service, domain
                )
                return CarddavDiscoveryResult(
                    base_url=candidate, discovery_source=source
                )

    logger.info("No CardDAV base URL could be discovered for %s", domain)
    return None


async def discover_carddav_base_url(
    email_or_domain: str,
    *,
    http_client_factory: HttpClientFactory | None = None,
    srv_resolver: SrvResolver | None = None,
) -> str | None:
    """Convenience wrapper returning only the discovered base URL (or None)."""
    result = await discover_carddav(
        email_or_domain,
        http_client_factory=http_client_factory,
        srv_resolver=srv_resolver,
    )
    return result.base_url if result is not None else None


__all__ = [
    "CarddavDiscoveryResult",
    "discover_carddav",
    "discover_carddav_base_url",
]
