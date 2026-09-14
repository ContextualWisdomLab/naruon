"""Regression contracts for opaque workspace document authorization."""

from api.auth import AuthContext
import api.data as data_api
from db.models import Document
from sqlalchemy import or_, select


def _opaque_workspace_auth() -> AuthContext:
    """Build a valid signed-session shape whose workspace is not derived from org id."""

    return AuthContext(
        user_id="member-a",
        role="member",
        organization_id="org-acme",
        group_ids=(),
        workspace_id="tenant-space-7f3c",
    )


def test_opaque_workspace_allows_historical_null_org_inside_exact_workspace() -> None:
    """Legacy NULL organization rows remain readable inside the signed workspace."""

    auth_context = _opaque_workspace_auth()
    statement = select(Document.document_id).where(
        Document.workspace_id == auth_context.workspace_id,
        data_api._document_organization_filter(auth_context),
    )
    compiled = statement.compile()
    rendered = str(statement.whereclause)

    assert "workspace_documents.workspace_id" in rendered
    assert "workspace_documents.organization_id" in rendered
    assert "IS NULL" in rendered.upper()
    assert auth_context.workspace_id in compiled.params.values()
    assert auth_context.organization_id in compiled.params.values()


def test_document_organization_filter_rejects_other_non_null_organizations() -> None:
    """The compatibility branch is exactly current organization OR historical NULL."""

    auth_context = _opaque_workspace_auth()
    expected = or_(
        Document.organization_id == auth_context.organization_id,
        Document.organization_id.is_(None),
    )

    assert data_api._document_organization_filter(auth_context).compare(expected)
