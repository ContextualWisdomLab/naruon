"""Client for the Clearfolio document-viewer service.

naruon proxies document conversion + viewer bootstrap through Clearfolio so the
browser never talks to it directly; every call carries the owner's tenant
headers. Disabled until CLEARFOLIO_BASE_URL is configured
(``clearfolio_enabled()`` is False), which keeps the 미리보기 surface hidden.
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from core.config import settings

CLEARFOLIO_TIMEOUT_SECONDS = 15.0
DEFAULT_VIEWER_PERMISSIONS = "viewer:read"


class ClearfolioNotConfigured(RuntimeError):
    """Raised when a Clearfolio call is attempted without CLEARFOLIO_BASE_URL."""


@dataclass(frozen=True)
class ClearfolioTenant:
    """naruon owner identity mapped onto Clearfolio's tenant headers."""

    tenant_id: str
    subject_id: str
    permissions: str = DEFAULT_VIEWER_PERMISSIONS

    def headers(self) -> dict[str, str]:
        return {
            "X-Clearfolio-Tenant-Id": self.tenant_id,
            "X-Clearfolio-Subject-Id": self.subject_id,
            "X-Clearfolio-Permissions": self.permissions,
        }


def clearfolio_base_url() -> str | None:
    raw = settings.CLEARFOLIO_BASE_URL
    return raw.rstrip("/") if raw else None


def clearfolio_enabled() -> bool:
    return clearfolio_base_url() is not None


class ClearfolioClient:
    """Thin async client over Clearfolio's convert + viewer REST API.

    Pass ``client`` (an ``httpx.AsyncClient``, e.g. built on a MockTransport) to
    inject a transport in tests; otherwise a short-lived client is created per
    call. The base URL is operator-configured (an in-cluster Service), so no
    user-supplied-URL SSRF allowlisting is needed here.
    """

    def __init__(
        self,
        *,
        base_url: str | None = None,
        client: httpx.AsyncClient | None = None,
    ):
        resolved = base_url or clearfolio_base_url()
        if not resolved:
            raise ClearfolioNotConfigured("CLEARFOLIO_BASE_URL is not configured")
        self._base_url = resolved.rstrip("/")
        self._client = client

    async def _request(
        self, method: str, path: str, tenant: ClearfolioTenant, **kwargs
    ) -> dict:
        url = f"{self._base_url}{path}"
        headers = tenant.headers()
        if self._client is not None:
            response = await self._client.request(
                method, url, headers=headers, timeout=CLEARFOLIO_TIMEOUT_SECONDS, **kwargs
            )
        else:
            async with httpx.AsyncClient() as client:
                response = await client.request(
                    method,
                    url,
                    headers=headers,
                    timeout=CLEARFOLIO_TIMEOUT_SECONDS,
                    **kwargs,
                )
        response.raise_for_status()
        return response.json()

    async def submit_document(
        self,
        *,
        filename: str,
        content: bytes,
        content_type: str,
        tenant: ClearfolioTenant,
    ) -> dict:
        """POST a document for async conversion. Returns {jobId, status, statusUrl}."""
        files = {"file": (filename, content, content_type)}
        return await self._request(
            "POST", "/api/v1/convert/jobs", tenant, files=files
        )

    async def get_job(self, job_id: str, *, tenant: ClearfolioTenant) -> dict:
        """Poll a conversion job's status/lifecycle fields."""
        return await self._request(
            "GET", f"/api/v1/convert/jobs/{job_id}", tenant
        )

    async def get_viewer(self, doc_id: str, *, tenant: ClearfolioTenant) -> dict:
        """Fetch viewer bootstrap JSON (short-lived signed artifact URL)."""
        return await self._request("GET", f"/api/v1/viewer/{doc_id}", tenant)
