import asyncio
import logging

import defusedxml.ElementTree as ET
import pytest
from fastapi import Request
from fastapi.testclient import TestClient

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


def test_dav_options_advertises_only_implemented_capabilities(
    dev_auth_dependency_overrides,
):
    with TestClient(app) as client:
        response = client.options("/dav/user123/projects/", headers=AUTH_HEADERS)

    assert response.status_code == 200
    assert response.headers["DAV"] == "1"
    assert {
        method.strip()
        for method in response.headers["Allow"].split(",")
        if method.strip()
    } == {"OPTIONS", "PROPFIND"}


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
        assert "x&amp;y&lt;z&gt;" in response.text
        assert "x&y<z>" not in response.text
        ET.fromstring(response.text)


@pytest.mark.parametrize(
    "method",
    [
        "GET",
        "PUT",
        "DELETE",
        "MKCOL",
        "REPORT",
        "PROPPATCH",
        "COPY",
        "MOVE",
        "LOCK",
        "UNLOCK",
    ],
)
def test_dav_unimplemented_methods_are_not_registered(
    dev_auth_dependency_overrides,
    method,
):
    with TestClient(app) as client:
        response = client.request(
            method,
            "/dav/user123/projects/file.ics",
            content=b"BEGIN:VCALENDAR\r\nEND:VCALENDAR" if method == "PUT" else None,
            headers=AUTH_HEADERS,
        )

    assert response.status_code == 405
    assert "etag" not in {header.lower() for header in response.headers}
    assert {
        allowed.strip()
        for allowed in response.headers["Allow"].split(",")
        if allowed.strip()
    } == {"OPTIONS", "PROPFIND"}


def test_dav_log_injection_prevention(dev_auth_dependency_overrides, caplog):
    """DAV request logs encode control characters rather than emitting them."""
    caplog.set_level(logging.INFO)
    malicious_path = "user123/projects/test\x1b[31minjected\n\r"
    scope = {
        "type": "http",
        "method": "OPTIONS",
        "headers": [],
    }

    async def run_handler():
        req = Request(scope)
        from api.auth import AuthContext
        from api.dav import dav_handler

        auth_ctx = AuthContext(
            user_id="user123",
            organization_id="org1",
            role="user",
            group_ids=[],
            workspace_id="ws1",
        )
        await dav_handler(request=req, path=malicious_path, auth_context=auth_ctx)

    asyncio.run(run_handler())

    raw_ansi = "\x1b[31m"
    found_in_logs = False
    for record in caplog.records:
        if "DAV Request" in record.message:
            assert raw_ansi not in record.message, (
                "Raw ANSI escape sequence found in logs!"
            )
            assert "\n" not in record.message[12:], (
                "Raw newline found in log message body!"
            )
            assert (
                "\\x1b[31minjected\\n\\r" in record.message
                or "\\x1b[31minjected\\r\\n" in record.message
            ), "Escaped characters missing from log message!"
            found_in_logs = True

    assert found_in_logs, "DAV Request log was not found"
