"""Regression contracts for opaque workspace document authorization."""

from api.auth import AuthContext
import api.data as data_api
from db.models import Document
from sqlalchemy import select


def _opaque_workspace_auth(*, organization_id: str = "org-acme") -> AuthContext:
    """Build a signed-session shape whose opaque workspace is not org-derived."""

    return AuthContext(
        user_id="member-a",
        role="member",
        organization_id=organization_id,
        group_ids=(),
        workspace_id="tenant-space-7f3c",
    )


def _compiled_document_scope(auth_context: AuthContext) -> tuple[str, dict[str, object]]:
    """Compile the document scope so tenant-binding predicates stay observable."""

    statement = select(Document.document_id).where(
        Document.workspace_id == auth_context.workspace_id,
        data_api._document_organization_filter(auth_context),
    )
    compiled = statement.compile()
    return str(statement.whereclause), compiled.params


def test_opaque_workspace_legacy_null_requires_trusted_organization_binding() -> None:
    """Legacy NULL rows require a server-side workspace-to-org binding."""

    auth_context = _opaque_workspace_auth()
    rendered, params = _compiled_document_scope(auth_context)

    assert "workspace_documents.workspace_id" in rendered
    assert "workspace_documents.organization_id" in rendered
    assert "IS NULL" in rendered.upper()
    assert "workspace_entities" in rendered
    assert "workspace_entities.workspace_id" in rendered
    assert "workspace_entities.organization_id" in rendered
    assert "EXISTS" in rendered.upper()
    assert auth_context.workspace_id in params.values()
    assert auth_context.organization_id in params.values()


def test_same_opaque_workspace_different_organization_needs_distinct_binding() -> None:
    """A signed workspace claim alone cannot authorize another organization."""

    owner = _opaque_workspace_auth(organization_id="org-acme")
    other = _opaque_workspace_auth(organization_id="org-other")

    owner_rendered, owner_params = _compiled_document_scope(owner)
    other_rendered, other_params = _compiled_document_scope(other)

    for rendered in (owner_rendered, other_rendered):
        assert "workspace_entities.organization_id" in rendered
        assert "EXISTS" in rendered.upper()
        assert "IS NULL" in rendered.upper()

    assert owner.organization_id in owner_params.values()
    assert other.organization_id in other_params.values()
    assert owner.workspace_id in owner_params.values()
    assert other.workspace_id in other_params.values()
