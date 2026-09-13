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
from main import app

TEST_SCOPED_ROLES = {
    "system_admin",
    "platform_admin",
    "tenant_admin",
    "organization_admin",
    "group_admin",
    "member",
}


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


def _resolve_test_workspace_id(
    *,
    user_id: str,
    organization_id: str | None,
    explicit_workspace_id: str | None,
) -> str:
    """Preserve an explicit workspace claim while keeping legacy tests compatible."""
    workspace_id = _normalize_header_value(explicit_workspace_id)
    if workspace_id is not None:
        return workspace_id
    return _derive_workspace_id(user_id, organization_id)


@pytest.fixture
def dev_auth_dependency_overrides():
    async def test_auth_context(
        x_user_id: str | None = Header(None, alias="X-User-Id"),
        x_user_role: str | None = Header(None, alias="X-User-Role"),
        x_organization_id: str | None = Header(None, alias="X-Organization-Id"),
        x_group_ids: str | None = Header(None, alias="X-Group-Ids"),
        x_workspace_id: str | None = Header(None, alias="X-Workspace-Id"),
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
            workspace_id=_resolve_test_workspace_id(
                user_id=user_id,
                organization_id=organization_id,
                explicit_workspace_id=x_workspace_id,
            ),
        )

    async def test_current_user(
        x_user_id: str | None = Header(None, alias="X-User-Id"),
        x_user_role: str | None = Header(None, alias="X-User-Role"),
        x_organization_id: str | None = Header(None, alias="X-Organization-Id"),
        x_group_ids: str | None = Header(None, alias="X-Group-Ids"),
        x_workspace_id: str | None = Header(None, alias="X-Workspace-Id"),
    ) -> str:
        return (
            await test_auth_context(
                x_user_id=x_user_id,
                x_user_role=x_user_role,
                x_organization_id=x_organization_id,
                x_group_ids=x_group_ids,
                x_workspace_id=x_workspace_id,
            )
        ).user_id

    app.dependency_overrides[get_auth_context] = test_auth_context
    app.dependency_overrides[get_current_user] = test_current_user
    yield
    app.dependency_overrides.pop(get_auth_context, None)
    app.dependency_overrides.pop(get_current_user, None)
