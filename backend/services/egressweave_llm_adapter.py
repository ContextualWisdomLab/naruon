"""Naruon-owned adapter from LLM provider settings to EgressWeave.

The application owns provider selection and configuration. EgressWeave owns the
provider-neutral outbound HTTP security boundary. This module is intentionally
small: it translates one selected LLM base URL into one exact allowlisted host,
then delegates DNS validation, address pinning, TLS identity,
request/response resource bounds, proxy isolation, and cleanup to EgressWeave.
"""

from __future__ import annotations

from urllib.parse import urlsplit

from egressweave import EgressNotAllowedError, EgressPolicy, build_egress_http_client

from core.config import settings

LLM_BASE_URL_NOT_ALLOWED = "LLM provider base URL is not allowed"
_OPENAI_DEFAULT_BASE_URL = "https://api.openai.com/v1"
_OPENAI_DEFAULT_AUTHORITY = ("api.openai.com", 443)

# Kept as a module seam so contract tests can verify translation without opening
# sockets or reimplementing EgressWeave internals.
_build_egress_http_client = build_egress_http_client


def _operator_allowed_hosts() -> frozenset[str]:
    """Return normalized operator LLM host entries without granting wildcards."""
    return frozenset(
        item.strip().lower().rstrip(".")
        for item in settings.ALLOWED_LLM_BASE_URL_HOSTS.split(",")
        if item.strip()
    )


def _custom_provider_authority(base_url: str) -> tuple[str, int]:
    """Derive one exact configured host before EgressWeave validates the URL.

    This is only an authorization translation step, not URL security validation.
    The selected host must already be present in naruon's operator allowlist;
    EgressWeave performs canonical URL, scheme, address, DNS, TLS, framing, and
    resource validation before any connection is opened.

    The derived port intentionally never constrains the policy:
    :class:`EgressPolicy` is host-only by design. Reading ``parsed.port`` here
    merely fails closed early on malformed ports (it raises ``ValueError``
    before any policy is built); EgressWeave re-derives and pins the effective
    host-and-port pair from the URL itself during resolution.
    """
    try:
        parsed = urlsplit(base_url.strip())
        hostname = (parsed.hostname or "").lower().rstrip(".")
        default_port = 443 if parsed.scheme.lower() == "https" else 80
        port = parsed.port if parsed.port is not None else default_port
    except (TypeError, ValueError) as exc:
        raise ValueError(LLM_BASE_URL_NOT_ALLOWED) from exc

    allowed_hosts = _operator_allowed_hosts()
    if (
        not hostname
        or not allowed_hosts
        or any("*" in host for host in allowed_hosts)
        or hostname not in allowed_hosts
    ):
        raise ValueError(LLM_BASE_URL_NOT_ALLOWED)
    return hostname, port


def _policy_for_base_url(base_url: str | None) -> tuple[str, EgressPolicy, bool]:
    """Return the effective URL, exact policy, and default-provider marker."""
    if base_url is None or not base_url.strip():
        return (
            _OPENAI_DEFAULT_BASE_URL,
            EgressPolicy.from_hosts([_OPENAI_DEFAULT_AUTHORITY[0]]),
            True,
        )

    authority = _custom_provider_authority(base_url)
    return (
        base_url,
        EgressPolicy.from_hosts(
            [authority[0]],
            allow_local=settings.ALLOW_LOCAL_LLM_PROVIDERS,
        ),
        False,
    )


async def build_llm_provider_http_client(base_url: str | None):
    """Build naruon's LLM client through the EgressWeave security boundary.

    ``None``/blank keeps the existing OpenAI SDK default-base-url contract for
    callers while the supplied HTTP client is internally pinned to
    ``api.openai.com:443``. Custom endpoints must be exact operator-allowlisted
    and map to one EgressWeave host policy. ``ALLOW_LOCAL_LLM_PROVIDERS``
    widens address classes only for an already allowlisted local/container name;
    it never grants a hostname or port by itself.

    EgressWeave errors are translated to naruon's long-standing generic
    ``ValueError`` boundary so policy details are not leaked to API callers.
    """
    try:
        effective_url, policy, is_default_provider = _policy_for_base_url(base_url)
        normalized_url, client = await _build_egress_http_client(
            effective_url,
            policy=policy,
        )
    except (EgressNotAllowedError, TypeError, ValueError) as exc:
        raise ValueError(LLM_BASE_URL_NOT_ALLOWED) from exc

    if is_default_provider:
        return None, client
    return normalized_url, client
