from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass
from urllib.parse import urlsplit


@dataclass(frozen=True)
class ValidatedHTTPSURLHost:
    normalized_url: str
    hostname: str
    port: int
    addresses: tuple[str, ...]


def parse_allowed_hosts(raw_hosts: str) -> frozenset[str]:
    hosts: set[str] = set()
    for raw_host in raw_hosts.split(","):
        host = _normalize_host(raw_host)
        if host:
            hosts.add(host)
    return frozenset(hosts)


def validate_https_url_host(
    setting_name: str,
    url_value: str,
    allowed_hosts: frozenset[str],
    allowed_hosts_setting_name: str,
) -> None:
    validate_https_url_host_details(
        setting_name,
        url_value,
        allowed_hosts,
        allowed_hosts_setting_name,
    )


def validate_same_or_subdomain_host(
    setting_name: str,
    host: str,
    base_setting_name: str,
    base_host: str,
) -> None:
    if host == base_host or host.endswith(f".{base_host}"):
        return
    raise ValueError(
        f"{setting_name} host must match or be a subdomain of {base_setting_name} host"
    )


def validate_https_url_host_details(
    setting_name: str,
    url_value: str,
    allowed_hosts: frozenset[str],
    allowed_hosts_setting_name: str,
) -> ValidatedHTTPSURLHost:
    parsed = urlsplit(url_value)
    if parsed.scheme.lower() != "https":
        raise ValueError(f"{setting_name} must use https")
    if parsed.username or parsed.password:
        raise ValueError(f"{setting_name} must not include userinfo")
    if parsed.fragment:
        raise ValueError(f"{setting_name} must not include a fragment")
    if not parsed.hostname:
        raise ValueError(f"{setting_name} must include a host")

    host = _normalize_host(parsed.hostname)
    if host not in allowed_hosts:
        raise ValueError(
            f"{setting_name} host must be listed in {allowed_hosts_setting_name}"
        )
    _reject_unsafe_ip_literal(setting_name, host)
    port = parsed.port or 443
    addresses = _resolve_global_addresses(setting_name, host, port)
    normalized_netloc = _format_normalized_netloc(
        host,
        port,
        explicit_port=parsed.port is not None,
    )
    normalized_url = parsed._replace(netloc=normalized_netloc).geturl()
    return ValidatedHTTPSURLHost(
        normalized_url=normalized_url,
        hostname=host,
        port=port,
        addresses=addresses,
    )


def _normalize_host(raw_host: str) -> str:
    host = raw_host.strip().lower().rstrip(".")
    if host.startswith("[") and host.endswith("]"):
        host = host[1:-1]
    return host


def _format_normalized_netloc(host: str, port: int, *, explicit_port: bool) -> str:
    """Rebuild a URL authority while preserving the brackets IPv6 requires."""
    host_part = f"[{host}]" if ":" in host else host
    return f"{host_part}:{port}" if explicit_port else host_part


def _parse_legacy_ipv4_literal(host: str) -> ipaddress.IPv4Address | None:
    """Parse the historical numbers-and-dots IPv4 syntax deterministically."""
    parts = host.split(".")
    if not 1 <= len(parts) <= 4:
        return None

    numbers: list[int] = []
    for part in parts:
        normalized_part = part.lower()
        if normalized_part.startswith("0x"):
            digits = normalized_part[2:]
            base = 16
            valid_digits = "0123456789abcdef"
        elif len(normalized_part) > 1 and normalized_part.startswith("0"):
            digits = normalized_part[1:]
            base = 8
            valid_digits = "01234567"
        else:
            digits = normalized_part
            base = 10
            valid_digits = "0123456789"
        if not digits or any(character not in valid_digits for character in digits):
            return None
        numbers.append(int(digits, base))

    if len(numbers) == 1:
        if numbers[0] > 0xFFFFFFFF:
            return None
        packed = numbers[0]
    elif len(numbers) == 2:
        if numbers[0] > 0xFF or numbers[1] > 0xFFFFFF:
            return None
        packed = (numbers[0] << 24) | numbers[1]
    elif len(numbers) == 3:
        if numbers[0] > 0xFF or numbers[1] > 0xFF or numbers[2] > 0xFFFF:
            return None
        packed = (numbers[0] << 24) | (numbers[1] << 16) | numbers[2]
    else:
        if any(number > 0xFF for number in numbers):
            return None
        packed = (
            (numbers[0] << 24) | (numbers[1] << 16) | (numbers[2] << 8) | numbers[3]
        )
    return ipaddress.IPv4Address(packed)


def _reject_unsafe_ip_literal(setting_name: str, host: str) -> None:
    try:
        ip_address = ipaddress.ip_address(host)
    except ValueError:
        ip_address = _parse_legacy_ipv4_literal(host)
        if ip_address is not None:
            if not ip_address.is_global:
                raise ValueError(f"{setting_name} IP host must be globally routable")
            return
        if host == "localhost" or host.endswith(".localhost"):
            raise ValueError(f"{setting_name} host must not be localhost")
        return

    if not ip_address.is_global:
        raise ValueError(f"{setting_name} IP host must be globally routable")


def _validate_global_address(setting_name: str, address: str) -> str:
    try:
        ip_address = ipaddress.ip_address(address)
    except ValueError as exc:
        raise ValueError(
            f"{setting_name} resolved IP host must be globally routable"
        ) from exc
    if not ip_address.is_global:
        raise ValueError(f"{setting_name} resolved IP host must be globally routable")
    return str(ip_address)


def _resolve_global_addresses(
    setting_name: str, hostname: str, port: int
) -> tuple[str, ...]:
    try:
        address_infos = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise ValueError(
            f"{setting_name} host must resolve to a global address"
        ) from exc

    addresses: list[str] = []
    seen_addresses: set[str] = set()
    for address_info in address_infos:
        address = _validate_global_address(setting_name, str(address_info[4][0]))
        if address not in seen_addresses:
            seen_addresses.add(address)
            addresses.append(address)
    if not addresses:
        raise ValueError(f"{setting_name} host must resolve to a global address")
    return tuple(addresses)
