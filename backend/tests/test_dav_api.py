import defusedxml.ElementTree as ET

from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from api.auth import get_auth_context
from main import app

AUTH_HEADERS = {
    "X-User-Id": "user123",
    "X-User-Role": "organization_admin",
    "X-Organization-Id": "org-acme",
}


def test_dav_rejects_missing_auth():
    with TestClient(app) as client:
        response = client.request("PROPFIND", "/dav/user123/projects/")
        assert response.status_code == 401


def test_dav_route_uses_signed_session_dependency():
    route = next(
        (
            route
            for route in app.routes
            if isinstance(route, APIRoute)
            and route.path == "/dav/{path:path}"
        ),
        None,
    )

    assert route is not None, "DAV route is not registered"
    dependencies = {dependency.dependency for dependency in route.dependencies}
    assert get_auth_context in dependencies


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


def test_dav_propfind(dev_auth_dependency_overrides):
    with TestClient(app) as client:
        response = client.request(
            "PROPFIND", "/dav/user123/projects/", headers=AUTH_HEADERS
        )
        assert response.status_code == 207
        assert "<D:multistatus" in response.text
        root = ET.fromstring(response.text)
        assert root.find(".//{DAV:}collection") is not None


def test_dav_propfind_escapes_path_values(dev_auth_dependency_overrides):
    with TestClient(app) as client:
        response = client.request(
            "PROPFIND", "/dav/user123/projects/x%26y%3Cz%3E", headers=AUTH_HEADERS
        )
        assert response.status_code == 207
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
    """
    Test that DAV handlers safely encode control characters in the requested path,
    preventing log injection vulnerabilities.
    """
    import logging

    caplog.set_level(logging.INFO)
    malicious_path = "user123/projects/test\x1b[31minjected\n\r"

    # Since HTTP clients block raw control chars and starlette unquotes but might reject it before reaching our route,
    # we test the handler directly to ensure the logger is using repr().
    import asyncio
    from fastapi import Request

    scope = {
        "type": "http",
        "method": "OPTIONS",
        "headers": [],
    }

    async def run_handler():
        req = Request(scope)
        from api.auth import AuthContext
        auth_ctx = AuthContext(user_id="user123", organization_id="org1", role="user", group_ids=[], workspace_id="ws1")

        from api.dav import dav_handler
        await dav_handler(request=req, path=malicious_path, auth_context=auth_ctx)

    asyncio.run(run_handler())

    # In some fastapi versions, returning an unexpected path might return 404. Let's just assert the log was captured.
    # The vulnerability is about the logger.

    # Assert that the raw ansi escape / newline was not logged, but encoded
    raw_ansi = "\x1b[31m"
    found_in_logs = False
    for record in caplog.records:
        if "DAV Request" in record.message:
            assert raw_ansi not in record.message, "Raw ANSI escape sequence found in logs!"
            assert "\n" not in record.message[12:], "Raw newline found in log message body!"
            assert "\\x1b[31minjected\\n\\r" in record.message or "\\x1b[31minjected\\r\\n" in record.message, "Escaped characters missing from log message!"
            found_in_logs = True

    assert found_in_logs, "DAV Request log was not found"
