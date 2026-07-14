"""Standard-port auto-inference for mail and DAV protocols.

This helper ONLY fills in the standard port for a protocol when the operator
did not supply one. SSL/TLS remains implicit and is handled per-port by the
existing protocol clients (IMAP4_SSL 993, POP3_SSL 995, SMTP implicit-TLS 465
else STARTTLS 587, DAV over https 443). Nothing here opens a socket or decides
how TLS is negotiated -- it returns an integer port only.
"""

from __future__ import annotations

# Canonical default ports keyed by lowercased protocol name.
# SMTP intentionally defaults to the submission port (587, STARTTLS); the
# implicit-TLS submission port (465) is selected explicitly via implicit_tls.
DEFAULT_PORTS: dict[str, int] = {
    "imap": 993,
    "pop3": 995,
    "smtp": 587,
    "caldav": 443,
    "carddav": 443,
    "webdav": 443,
}

# Implicit-TLS SMTP submission port ("smtps").
SMTP_IMPLICIT_TLS_PORT = 465


def normalize_protocol(protocol: str) -> str:
    """Return the canonical lowercase protocol key or raise ValueError."""
    if not isinstance(protocol, str):
        raise ValueError("protocol must be a string")
    key = protocol.strip().lower()
    if key not in DEFAULT_PORTS:
        raise ValueError(f"unsupported protocol: {protocol!r}")
    return key


def infer_port(
    protocol: str,
    provided_port: int | None = None,
    *,
    implicit_tls: bool = False,
) -> int:
    """Infer the standard port for ``protocol`` when ``provided_port`` is unset.

    - When ``provided_port`` is a positive integer it is returned unchanged
      (the operator's explicit choice always wins).
    - Otherwise the canonical default for the protocol is returned. For SMTP,
      pass ``implicit_tls=True`` to select the implicit-TLS submission port
      (465) instead of the STARTTLS submission port (587).

    SSL negotiation is NOT decided here; only the port number is returned.
    """
    key = normalize_protocol(protocol)

    if provided_port is not None:
        try:
            port_int = int(provided_port)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"invalid port: {provided_port!r}") from exc
        if port_int > 0:
            if not (1 <= port_int <= 65535):
                raise ValueError(f"port out of range: {port_int}")
            return port_int
        # port_int <= 0 falls through to the inferred default.

    if key == "smtp" and implicit_tls:
        return SMTP_IMPLICIT_TLS_PORT
    return DEFAULT_PORTS[key]


def split_host_port(address: str) -> tuple[str, int | None]:
    """Split ``host:port`` into ``(host, port)`` without inferring a default.

    Bare hosts (``"imap.example.com"``) return ``(host, None)``. Bracketed
    IPv6 literals (``"[::1]:993"``) are supported. A trailing ``:port`` is only
    treated as a port when it is all digits; otherwise it is left on the host
    (so ``"::1"`` is not mistaken for ``host="" port=1``).
    """
    if not isinstance(address, str):
        raise ValueError("address must be a string")
    value = address.strip()
    if not value:
        raise ValueError("address must not be empty")

    # Bracketed IPv6, optionally with a port: [host] or [host]:port
    if value.startswith("["):
        closing = value.find("]")
        if closing == -1:
            raise ValueError(f"invalid bracketed address: {address!r}")
        host = value[1:closing]
        rest = value[closing + 1 :]
        if not rest:
            return host, None
        if rest.startswith(":") and rest[1:].isdigit():
            return host, int(rest[1:])
        raise ValueError(f"invalid bracketed address: {address!r}")

    # Only split on the final colon when the suffix is numeric and there is
    # exactly one colon (more than one colon means a bare IPv6 literal).
    if value.count(":") == 1:
        host, _, maybe_port = value.rpartition(":")
        if host and maybe_port.isdigit():
            return host, int(maybe_port)

    return value, None


def infer_address_port(
    protocol: str,
    address: str,
    *,
    implicit_tls: bool = False,
) -> tuple[str, int]:
    """Return ``(host, port)`` for ``address``, inferring the port if absent.

    ``address`` may be a bare host or ``host:port``. When it already carries an
    explicit port that port is preserved; otherwise the protocol default is
    filled in. SSL remains implicit in the downstream clients.
    """
    host, port = split_host_port(address)
    return host, infer_port(protocol, port, implicit_tls=implicit_tls)


__all__ = [
    "DEFAULT_PORTS",
    "SMTP_IMPLICIT_TLS_PORT",
    "normalize_protocol",
    "infer_port",
    "split_host_port",
    "infer_address_port",
]
