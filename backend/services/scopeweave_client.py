"""Outbound client for pushing promoted work items to a scopeweave instance.

Security posture mirrors the LLM provider egress path:

- The destination host must appear in ``ALLOWED_SCOPEWEAVE_HOSTS`` (config
  module, never ``os.getenv``) and the URL must be HTTPS.
- The host is resolved and every candidate address must be globally routable
  (blocks SSRF to loopback / RFC-1918 / link-local targets).
- The outbound connection is DNS-pinned to the validated addresses, closing the
  DNS-rebinding gap between validation and connect.

The per-workspace ``base_url`` and PAT are resolved from the encrypted database
row by the caller; this module only knows how to validate a URL and speak the
scopeweave import protocol.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from core.config import settings
from core.url_validation import (
    ValidatedHTTPSURLHost,
    parse_allowed_hosts,
    validate_https_url_host_details,
)
from services.llm_provider_urls import build_pinned_https_async_client

SCOPEWEAVE_BASE_URL_SETTING = "scopeweave base_url"
SCOPEWEAVE_ALLOWED_HOSTS_SETTING = "ALLOWED_SCOPEWEAVE_HOSTS"
SCOPEWEAVE_IMPORT_PATH = "/api/imports/work-items"
_REQUEST_TIMEOUT_SECONDS = 15.0


class ScopeweaveConfigError(ValueError):
    """The configured scopeweave base URL is missing or fails validation."""


class ScopeweavePushError(RuntimeError):
    """The scopeweave import request could not be completed successfully."""


@dataclass(frozen=True, slots=True)
class ScopeweaveImportResult:
    work_item_id: str
    work_item_url: str | None
    status_code: int


def validate_scopeweave_base_url(base_url: str) -> ValidatedHTTPSURLHost:
    """Validate ``base_url`` against the scopeweave host allowlist.

    Raises ``ScopeweaveConfigError`` when the URL is not HTTPS, its host is not
    allowlisted, or it resolves to a non-global address.
    """
    allowed_hosts = parse_allowed_hosts(settings.ALLOWED_SCOPEWEAVE_HOSTS)
    if not allowed_hosts:
        raise ScopeweaveConfigError(
            f"{SCOPEWEAVE_ALLOWED_HOSTS_SETTING} must list at least one trusted host"
        )
    try:
        return validate_https_url_host_details(
            SCOPEWEAVE_BASE_URL_SETTING,
            base_url,
            allowed_hosts,
            SCOPEWEAVE_ALLOWED_HOSTS_SETTING,
        )
    except ValueError as exc:
        raise ScopeweaveConfigError(str(exc)) from exc


def _import_url(validated: ValidatedHTTPSURLHost) -> str:
    return f"{validated.normalized_url.rstrip('/')}{SCOPEWEAVE_IMPORT_PATH}"


def _parse_import_result(response: httpx.Response) -> ScopeweaveImportResult:
    try:
        body: Any = response.json()
    except ValueError as exc:
        raise ScopeweavePushError(
            "scopeweave returned a non-JSON import response"
        ) from exc
    if not isinstance(body, dict):
        raise ScopeweavePushError("scopeweave import response was not an object")
    work_item_id = body.get("work_item_id") or body.get("id")
    if not work_item_id:
        raise ScopeweavePushError("scopeweave import response omitted a work item id")
    work_item_url = body.get("work_item_url") or body.get("url")
    return ScopeweaveImportResult(
        work_item_id=str(work_item_id),
        work_item_url=str(work_item_url) if work_item_url else None,
        status_code=response.status_code,
    )


async def push_work_item(
    *,
    base_url: str,
    access_token: str,
    payload: dict[str, Any],
) -> ScopeweaveImportResult:
    """Validate the target, then POST ``payload`` to the scopeweave import API.

    Uses a DNS-pinned, redirect-blocking HTTPS client and a bearer PAT. Raises
    ``ScopeweaveConfigError`` for invalid targets and ``ScopeweavePushError``
    for transport or non-2xx responses.
    """
    validated = validate_scopeweave_base_url(base_url)
    client = build_pinned_https_async_client(
        validated.normalized_url,
        validated.hostname,
        validated.port,
        validated.addresses,
    )
    try:
        response = await client.post(
            _import_url(validated),
            json=payload,
            headers={
                "authorization": f"Bearer {access_token}",
                "content-type": "application/json",
                "accept": "application/json",
            },
            timeout=_REQUEST_TIMEOUT_SECONDS,
        )
    except httpx.HTTPError as exc:
        raise ScopeweavePushError("scopeweave import request failed") from exc
    finally:
        await client.aclose()

    if response.status_code >= 400:
        raise ScopeweavePushError(
            f"scopeweave import rejected the work item (status {response.status_code})"
        )
    return _parse_import_result(response)
