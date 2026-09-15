import os
import secrets

os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test_db"
)
os.environ.setdefault("AUTH_SESSION_HMAC_SECRET", secrets.token_urlsafe(48))
os.environ.setdefault("ALLOWED_SMTP_HOSTS", "smtp.example.com")
os.environ.setdefault("ALLOWED_IMAP_HOSTS", "imap.example.com")
os.environ.setdefault("ALLOWED_POP3_HOSTS", "pop3.example.com")
os.environ.setdefault("ALLOWED_CORS_ORIGINS", "http://localhost:3000")
os.environ.setdefault("DISABLE_BACKGROUND_WORKERS", "1")

import pytest
from fastapi import Header, HTTPException
from typing import cast

from api.auth import AuthContext, RoleName, get_auth_context, get_current_user
from db.models import Workspace
from main import app

TEST_SCOPED_ROLES = {
    "system_admin",
    "platform_admin",
    "tenant_admin",
    "organization_admin",
    "group_admin",
    "member",
}

_HMAC_DOCUMENT_COMPATIBILITY_TESTS = frozenset(
    {
        "test_data_document_upload_creates_workspace_scoped_document",
        "test_data_document_actions_are_workspace_scoped_and_intent_only",
        "test_data_pdf_dom_upload_persists_signed_organization_scope",
    }
)


@pytest.fixture(autouse=True)
def persisted_hmac_workspace_for_document_compatibility(request):
    """Model HMAC document access as consumption of existing owner evidence.

    The signed HMAC fixture proves token integrity only. These legacy success
    cases exercise compatibility consumption, so their mock registry must already
    contain the organization binding that production requires before access.
    """
    if request.node.name not in _HMAC_DOCUMENT_COMPATIBILITY_TESTS:
        yield
        return

    mock_db = request.getfixturevalue("mock_db")
    mock_db.workspaces.append(
        Workspace(
            workspace_id="workspace-org-acme",
            workspace_name="workspace-org-acme",
            organization_id="org-acme",
            owner_user_id=None,
        )
    )
    yield


def _normalize_header_value(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _parse_group_ids(group_ids_header: str | None) -> tuple[str, ...]:
    if not group_ids_header:
        return ()
    return tuple(
        group_id.strip() for group_id in group_ids_header.split(",") if group_id.strip()
    )


def _derive_test_role(requested_role: str | None) -> RoleName:
    if requested_role in TEST_SCOPED_ROLES:
        return cast(RoleName, requested_role)
    return "member"


def _derive_workspace_id(user_id: str, organization_id: str | None) -> str:
    if organization_id:
        return f"workspace-{organization_id}"
    return f"workspace-{user_id}"


@pytest.fixture
def dev_auth_dependency_overrides():
    async def test_auth_context(
        x_user_id: str | None = Header(None, alias="X-User-Id"),
        x_user_role: str | None = Header(None, alias="X-User-Role"),
        x_organization_id: str | None = Header(None, alias="X-Organization-Id"),
        x_group_ids: str | None = Header(None, alias="X-Group-Ids"),
    ) -> AuthContext:
        user_id = _normalize_header_value(x_user_id)
        if user_id is None:
            raise HTTPException(status_code=401, detail="Authentication required")
        organization_id = _normalize_header_value(x_organization_id)
        return AuthContext(
            user_id=user_id,
            role=_derive_test_role(_normalize_header_value(x_user_role)),
            organization_id=organization_id,
            group_ids=_parse_group_ids(_normalize_header_value(x_group_ids)),
            workspace_id=_derive_workspace_id(user_id, organization_id),
        )

    async def test_current_user(
        x_user_id: str | None = Header(None, alias="X-User-Id"),
        x_user_role: str | None = Header(None, alias="X-User-Role"),
        x_organization_id: str | None = Header(None, alias="X-Organization-Id"),
        x_group_ids: str | None = Header(None, alias="X-Group-Ids"),
    ) -> str:
        return (
            await test_auth_context(
                x_user_id=x_user_id,
                x_user_role=x_user_role,
                x_organization_id=x_organization_id,
                x_group_ids=x_group_ids,
            )
        ).user_id

    app.dependency_overrides[get_auth_context] = test_auth_context
    app.dependency_overrides[get_current_user] = test_current_user
    yield
    app.dependency_overrides.pop(get_auth_context, None)
    app.dependency_overrides.pop(get_current_user, None)