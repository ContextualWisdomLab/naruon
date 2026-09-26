"""Regression contracts for opaque workspace document authorization."""

from api.auth import AuthContext
import api.data as data_api
from db.models import Document, Workspace
from sqlalchemy import and_, exists, or_, select


def _opaque_workspace_auth(*, organization_id: str = "org-acme") -> AuthContext:
    """Build a signed-session shape whose opaque workspace is not org-derived."""

    return AuthContext(
        user_id="member-a",
        role="member",
        organization_id=organization_id,
        group_ids=(),
        workspace_id="tenant-space-7f3c",
    )


def _expected_organization_filter(auth_context: AuthContext):
    """Describe the exact trusted binding required for historical NULL rows."""

    assert hasattr(Workspace, "organization_id"), (
        "workspace_entities must persist organization_id before opaque workspace "
        "claims can authorize organization-null documents"
    )
    assert hasattr(Workspace, "owner_user_id"), (
        "organization workspace bindings must prove they are not personal-owner rows"
    )
    trusted_workspace_binding = exists(
        select(1)
        .select_from(Workspace)
        .where(
            Workspace.workspace_id == auth_context.workspace_id,
            Workspace.organization_id == auth_context.organization_id,
            Workspace.owner_user_id.is_(None),
        )
    )
    return or_(
        Document.organization_id == auth_context.organization_id,
        and_(Document.organization_id.is_(None), trusted_workspace_binding),
    )


def _compiled_document_scope(auth_context: AuthContext) -> tuple[str, dict[str, object]]:
    """Compile the document scope so tenant-binding predicates stay observable."""

    statement = select(Document.document_id).where(
        Document.workspace_id == auth_context.workspace_id,
        data_api._document_organization_filter(auth_context),
    )
    compiled = statement.compile()
    return str(statement.whereclause), compiled.params


def test_opaque_workspace_legacy_null_requires_correlated_organization_binding() -> None:
    """Legacy NULL access requires one workspace row matching both signed claims."""

    auth_context = _opaque_workspace_auth()

    assert data_api._document_organization_filter(auth_context).compare(
        _expected_organization_filter(auth_context)
    )

    rendered, params = _compiled_document_scope(auth_context)
    assert "workspace_documents.workspace_id" in rendered
    assert "workspace_entities.workspace_id" in rendered
    assert "workspace_entities.organization_id" in rendered
    assert "workspace_entities.owner_user_id" in rendered
    assert "IS NULL" in rendered.upper()
    assert "EXISTS" in rendered.upper()
    assert auth_context.workspace_id in params.values()
    assert auth_context.organization_id in params.values()


def test_same_opaque_workspace_different_organization_cannot_share_null_branch() -> None:
    """Each organization must correlate against its own registry binding."""

    owner = _opaque_workspace_auth(organization_id="org-acme")
    other = _opaque_workspace_auth(organization_id="org-other")

    owner_expected = _expected_organization_filter(owner)
    other_expected = _expected_organization_filter(other)

    assert not owner_expected.compare(other_expected)
    assert data_api._document_organization_filter(owner).compare(owner_expected)
    assert data_api._document_organization_filter(other).compare(other_expected)

    owner_rendered, owner_params = _compiled_document_scope(owner)
    other_rendered, other_params = _compiled_document_scope(other)
    for rendered in (owner_rendered, other_rendered):
        assert "workspace_entities.workspace_id" in rendered
        assert "workspace_entities.organization_id" in rendered
        assert "workspace_entities.owner_user_id" in rendered
        assert "EXISTS" in rendered.upper()
        assert "IS NULL" in rendered.upper()

    assert owner.organization_id in owner_params.values()
    assert other.organization_id in other_params.values()
    assert owner.workspace_id in owner_params.values()
    assert other.workspace_id in other_params.values()
