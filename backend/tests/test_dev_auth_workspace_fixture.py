"""Regression contract for workspace-aware API test authentication."""

import pytest

from api.auth import get_auth_context
from main import app

pytestmark = pytest.mark.usefixtures("dev_auth_dependency_overrides")


@pytest.mark.asyncio
async def test_dev_auth_override_preserves_explicit_opaque_workspace():
    override = app.dependency_overrides[get_auth_context]

    auth_context = await override(
        x_user_id="user-1",
        x_user_role="member",
        x_organization_id="org-acme",
        x_group_ids=None,
        x_workspace_id="opaque-project-blue",
    )

    assert auth_context.organization_id == "org-acme"
    assert auth_context.workspace_id == "opaque-project-blue"


@pytest.mark.asyncio
async def test_dev_auth_override_keeps_same_org_workspaces_distinct():
    override = app.dependency_overrides[get_auth_context]

    workspace_a = await override(
        x_user_id="user-1",
        x_user_role="member",
        x_organization_id="org-acme",
        x_group_ids=None,
        x_workspace_id="workspace-a",
    )
    workspace_b = await override(
        x_user_id="user-1",
        x_user_role="member",
        x_organization_id="org-acme",
        x_group_ids=None,
        x_workspace_id="workspace-b",
    )

    assert workspace_a.workspace_id == "workspace-a"
    assert workspace_b.workspace_id == "workspace-b"
    assert workspace_a.workspace_id != workspace_b.workspace_id
