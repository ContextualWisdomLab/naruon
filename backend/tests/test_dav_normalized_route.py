"""Route-level regression coverage for canonical DAV authorization paths."""

import pytest
from fastapi.testclient import TestClient

from main import app
from services.webdav_service import webdav_service

AUTH_HEADERS = {
    "X-User-Id": "user123",
    "X-User-Role": "organization_admin",
    "X-Organization-Id": "org-acme",
}


@pytest.fixture
def stub_dav_project_folder(monkeypatch):
    """Return one deterministic project folder through the production DAV service seam."""

    async def fake_project_folders(db, user_id, organization_id, folder_uid=None):
        assert user_id == "user123"
        assert organization_id == "org-acme"
        assert folder_uid == "demo"
        return [
            {
                "folder_uid": "demo",
                "project_name": "demo",
                "webdav_path": "/projects/demo",
                "owner_user_id": user_id,
                "organization_id": organization_id,
            }
        ]

    monkeypatch.setattr(
        webdav_service,
        "get_project_folders_from_db",
        fake_project_folders,
    )


def test_propfind_routes_framework_decoded_backslashes_through_canonical_path(
    dev_auth_dependency_overrides,
    stub_dav_project_folder,
):
    """A once-decoded backslash path must reach the same project route as slashes."""

    with TestClient(app) as client:
        response = client.request(
            "PROPFIND",
            "/dav/user123%5Cprojects%5Cdemo",
            headers=AUTH_HEADERS,
        )

    assert response.status_code == 207
    assert "<D:displayname>demo</D:displayname>" in response.text
