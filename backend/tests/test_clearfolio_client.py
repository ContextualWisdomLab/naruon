import httpx
import pytest

from services.clearfolio_client import (
    ClearfolioClient,
    ClearfolioNotConfigured,
    ClearfolioTenant,
    clearfolio_enabled,
)


def test_tenant_headers_map_owner_identity():
    tenant = ClearfolioTenant(tenant_id="org-acme", subject_id="alice")
    assert tenant.headers() == {
        "X-Clearfolio-Tenant-Id": "org-acme",
        "X-Clearfolio-Subject-Id": "alice",
        "X-Clearfolio-Permissions": "viewer:read",
    }


def test_client_requires_configured_base_url(monkeypatch):
    import core.config as config

    monkeypatch.setattr(config.settings, "CLEARFOLIO_BASE_URL", None, raising=False)
    assert clearfolio_enabled() is False
    with pytest.raises(ClearfolioNotConfigured):
        ClearfolioClient()


@pytest.mark.asyncio
async def test_submit_and_viewer_send_tenant_headers_and_parse(monkeypatch):
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.url.path == "/api/v1/convert/jobs":
            return httpx.Response(200, json={"jobId": "job-1", "status": "PENDING"})
        if request.url.path == "/api/v1/viewer/doc-1":
            return httpx.Response(
                200,
                json={"status": "SUCCEEDED", "artifactUrl": "https://cf/artifacts/doc-1.pdf?sig=x"},
            )
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http:
        client = ClearfolioClient(base_url="http://clearfolio:8080/", client=http)
        tenant = ClearfolioTenant(tenant_id="org-acme", subject_id="alice")

        submitted = await client.submit_document(
            filename="q2.docx", content=b"bytes", content_type="application/octet-stream", tenant=tenant
        )
        assert submitted["jobId"] == "job-1"

        viewer = await client.get_viewer("doc-1", tenant=tenant)
        assert viewer["status"] == "SUCCEEDED"
        assert viewer["artifactUrl"].endswith(".pdf?sig=x")

    # Every request carried the owner's tenant headers; base-url trailing slash normalized.
    assert len(seen) == 2
    for req in seen:
        assert req.headers["X-Clearfolio-Tenant-Id"] == "org-acme"
        assert req.headers["X-Clearfolio-Subject-Id"] == "alice"
        assert req.headers["X-Clearfolio-Permissions"] == "viewer:read"
    assert str(seen[0].url) == "http://clearfolio:8080/api/v1/convert/jobs"


@pytest.mark.asyncio
async def test_request_raises_on_error_status(monkeypatch):
    transport = httpx.MockTransport(lambda request: httpx.Response(500, json={"errorCode": "boom"}))
    async with httpx.AsyncClient(transport=transport) as http:
        client = ClearfolioClient(base_url="http://clearfolio:8080", client=http)
        tenant = ClearfolioTenant(tenant_id="org-acme", subject_id="alice")
        with pytest.raises(httpx.HTTPStatusError):
            await client.get_job("job-x", tenant=tenant)
