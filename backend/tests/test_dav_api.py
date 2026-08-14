import defusedxml.ElementTree as ET

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from api.dav import _normalize_dav_authorization_path
from main import app
from services.webdav_service import webdav_service

AUTH_HEADERS = {
    "X-User-Id": "user123",
    "X-User-Role": "organization_admin",
    "X-Organization-Id": "org-acme",
}


@pytest.fixture
def stub_dav_project_folders(monkeypatch):
    async def fake_project_folders(db, user_id, organization_id, folder_uid=None):
        assert user_id == "user123"
        assert organization_id == "org-acme"
        if folder_uid is None:
            return [
                {
                    "folder_uid": "demo",
                    "project_name": "demo",
                    "webdav_path": "/projects/demo",
                    "owner_user_id": user_id,
                    "organization_id": organization_id,
                }
            ]
        return [
            {
                "folder_uid": folder_uid,
                "project_name": folder_uid,
                "webdav_path": f"/projects/{folder_uid}",
                "owner_user_id": user_id,
                "organization_id": organization_id,
            }
        ]

    monkeypatch.setattr(
        webdav_service,
        "get_project_folders_from_db",
        fake_project_folders,
    )


def test_dav_rejects_missing_auth():
    with TestClient(app) as client:
        response = client.request("PROPFIND", "/dav/user123/projects/")
        assert response.status_code == 401


def test_dav_route_uses_signed_session_dependency():
    with TestClient(app) as client:
        response = client.options(
            "/dav/user123/projects/",
            headers={"Authorization": "Bearer not-a-signed-session"},
        )

    assert response.status_code == 401


def test_dav_options(dev_auth_dependency_overrides):
    with TestClient(app) as client:
        response = client.options("/dav/user123/projects/", headers=AUTH_HEADERS)
        assert response.status_code == 200
        assert "calendar-access" in response.headers.get("DAV", "")


def test_dav_rejects_different_user_path(dev_auth_dependency_overrides):
    with TestClient(app) as client:
        response = client.request(
            "PROPFIND", "/dav/other-user/projects/", headers=AUTH_HEADERS
        )
        assert response.status_code == 403
        assert response.json()["detail"] == "DAV path belongs to a different user"


def test_dav_rejects_ownerless_path(dev_auth_dependency_overrides):
    with TestClient(app) as client:
        response = client.request("PROPFIND", "/dav/", headers=AUTH_HEADERS)
        assert response.status_code == 403
        assert response.json()["detail"] == "DAV path must include an owner user"


def test_dav_rejects_ownerless_options_before_capability_discovery(
    dev_auth_dependency_overrides,
):
    with TestClient(app) as client:
        response = client.options("/dav/", headers=AUTH_HEADERS)
        assert response.status_code == 403
        assert "dav" not in {header.lower() for header in response.headers}
        assert response.json()["detail"] == "DAV path must include an owner user"


def test_dav_authorization_path_preserves_literal_percent_data():
    assert (
        _normalize_dav_authorization_path("user123/projects/literal%25")
        == "user123/projects/literal%25"
    )
    assert (
        _normalize_dav_authorization_path("user123/projects/분석%zz")
        == "user123/projects/분석%zz"
    )


@pytest.mark.parametrize(
    "path",
    [
        "user123/projects/%2e%2e/secret",
        "user123/projects/%252e%252e/secret",
        "user123/projects/%2fsecret",
        "user123/projects/%5csecret",
        "user123/projects/%00secret",
        "user123/projects/%250asecret",
    ],
)
def test_dav_authorization_path_rejects_nested_structural_decoding(path):
    with pytest.raises(HTTPException) as exc_info:
        _normalize_dav_authorization_path(path)

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "DAV path contains ambiguous percent encoding"


@pytest.mark.parametrize("control_character", ["\x00", "\x1f", "\x7f"])
def test_dav_authorization_path_rejects_decoded_controls(control_character):
    with pytest.raises(HTTPException) as exc_info:
        _normalize_dav_authorization_path(
            f"user123/projects/report{control_character}name"
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "DAV path contains control characters"


def test_dav_authorization_path_normalizes_literal_backslashes_once():
    assert (
        _normalize_dav_authorization_path(r"user123\projects\demo")
        == "user123/projects/demo"
    )


def test_dav_authorization_path_has_explicit_resource_boundary():
    prefix = "user123/projects/"
    boundary_path = prefix + ("x" * (8192 - len(prefix)))
    assert _normalize_dav_authorization_path(boundary_path) == boundary_path

    with pytest.raises(HTTPException) as exc_info:
        _normalize_dav_authorization_path(boundary_path + "x")

    assert exc_info.value.status_code == 414
    assert exc_info.value.detail == "DAV path exceeds authorization length limit"


def test_dav_route_rejects_framework_decoded_nested_traversal(
    dev_auth_dependency_overrides,
):
    """Reject traversal after ASGI exposes the nested encoding as a literal segment."""

    with TestClient(app) as client:
        response = client.options(
            "/dav/user123/projects/%252e%252e/secret",
            headers=AUTH_HEADERS,
        )

    assert response.status_code == 403
    assert response.json()["detail"] == "DAV path must include an owner user"


def test_dav_route_preserves_encoded_percent_as_data(dev_auth_dependency_overrides):
    with TestClient(app) as client:
        response = client.options(
            "/dav/user123/projects/literal%2525",
            headers=AUTH_HEADERS,
        )

    assert response.status_code == 200


def test_dav_propfind(dev_auth_dependency_overrides, stub_dav_project_folders):
    with TestClient(app) as client:
        response = client.request(
            "PROPFIND", "/dav/user123/projects/", headers=AUTH_HEADERS
        )
        assert response.status_code == 207
        assert "<D:multistatus" in response.text
        root = ET.fromstring(response.text)
        assert root.find(".//{DAV:}collection") is not None


def test_dav_propfind_escapes_path_values(
    dev_auth_dependency_overrides,
    stub_dav_project_folders,
):
    with TestClient(app) as client:
        response = client.request(
            "PROPFIND", "/dav/user123/projects/x%26y%3Cz%3E", headers=AUTH_HEADERS
        )
        assert response.status_code == 207
        assert "<D:multistatus" in response.text
        assert "x&amp;y&lt;z&gt;" in response.text
        assert "x&y<z>" not in response.text
        ET.fromstring(response.text)


def test_dav_put(dev_auth_dependency_overrides, caplog):
    import logging

    caplog.set_level(logging.WARNING, logger="api.dav")
    with TestClient(app) as client:
        response = client.put(
            "/dav/user123/projects/file.ics",
            content=b"BEGIN:VCALENDAR\r\nEND:VCALENDAR",
            headers=AUTH_HEADERS,
        )
        assert response.status_code == 501
        assert "Provider-backed DAV writeback is not implemented" in response.text
        assert "etag" not in {header.lower() for header in response.headers}
        assert any(
            "provider-backed DAV writeback is not implemented" in record.getMessage()
            for record in caplog.records
        )


def test_dav_unsupported_method_logs_reason(dev_auth_dependency_overrides, caplog):
    import logging

    caplog.set_level(logging.WARNING, logger="api.dav")
    with TestClient(app) as client:
        response = client.delete(
            "/dav/user123/projects/file.ics",
            headers=AUTH_HEADERS,
        )

    assert response.status_code == 501
    assert "Provider-backed DAV method is not implemented" in response.text
    assert any(
        "method is not implemented for the provider-backed DAV gateway"
        in record.getMessage()
        for record in caplog.records
    )


def test_dav_log_injection_prevention(dev_auth_dependency_overrides, caplog):
    """Reject decoded control characters before they can reach DAV request logs."""
    import asyncio
    import logging

    from fastapi import Request

    from api.auth import AuthContext
    from api.dav import dav_handler

    caplog.set_level(logging.INFO, logger="api.dav")
    malicious_path = "user123/projects/test\x1b[31minjected\n\r"
    scope = {
        "type": "http",
        "method": "OPTIONS",
        "headers": [],
    }

    async def run_handler():
        request = Request(scope)
        auth_context = AuthContext(
            user_id="user123",
            organization_id="org1",
            role="user",
            group_ids=[],
            workspace_id="ws1",
        )
        await dav_handler(
            request=request,
            path=malicious_path,
            auth_context=auth_context,
        )

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(run_handler())

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "DAV path contains control characters"
    assert not any("DAV Request" in record.getMessage() for record in caplog.records)
