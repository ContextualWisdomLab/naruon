"""Regression contracts for personal-scope opaque workspace authorization."""

from api.auth import AuthContext
import api.data as data_api
from db.models import Document, Workspace
from sqlalchemy import and_, exists, select


def _personal_workspace_auth(*, user_id: str = "member-a") -> AuthContext:
    """Build a personal signed-session shape with an opaque workspace claim."""

    return AuthContext(
        user_id=user_id,
        role="member",
        organization_id=None,
        group_ids=(),
        workspace_id="tenant-personal-7f3c",
    )


def _expected_personal_scope(auth_context: AuthContext):
    """Require one registry row correlating the opaque workspace to its owner."""

    assert hasattr(Workspace, "owner_user_id"), (
        "workspace_entities must persist owner_user_id before personal opaque "
        "workspace claims can authorize organization-null documents"
    )
    trusted_workspace_binding = exists(
        select(1)
        .select_from(Workspace)
        .where(
            Workspace.workspace_id == auth_context.workspace_id,
            Workspace.organization_id.is_(None),
            Workspace.owner_user_id == auth_context.user_id,
        )
    )
    return and_(Document.organization_id.is_(None), trusted_workspace_binding)


def _compiled_document_scope(auth_context: AuthContext) -> tuple[str, dict[str, object]]:
    """Compile the personal document scope so ownership correlation is observable."""

    statement = select(Document.document_id).where(
        Document.workspace_id == auth_context.workspace_id,
        data_api._document_organization_filter(auth_context),
    )
    compiled = statement.compile()
    return str(statement.whereclause), compiled.params


def test_personal_opaque_workspace_requires_correlated_owner_user_binding() -> None:
    """Personal NULL-organization access requires a server-side user binding."""

    auth_context = _personal_workspace_auth()
    expected = _expected_personal_scope(auth_context)

    assert data_api._document_organization_filter(auth_context).compare(expected)

    rendered, params = _compiled_document_scope(auth_context)
    assert "workspace_documents.workspace_id" in rendered
    assert "workspace_entities.workspace_id" in rendered
    assert "workspace_entities.owner_user_id" in rendered
    assert "workspace_entities.organization_id" in rendered
    assert "IS NULL" in rendered.upper()
    assert "EXISTS" in rendered.upper()
    assert auth_context.workspace_id in params.values()
    assert auth_context.user_id in params.values()


def test_same_personal_opaque_workspace_different_users_cannot_share_null_documents() -> None:
    """Two signed users cannot share one personal opaque-workspace NULL branch."""

    owner = _personal_workspace_auth(user_id="member-a")
    other = _personal_workspace_auth(user_id="member-b")
    owner_expected = _expected_personal_scope(owner)
    other_expected = _expected_personal_scope(other)

    assert not owner_expected.compare(other_expected)
    assert data_api._document_organization_filter(owner).compare(owner_expected)
    assert data_api._document_organization_filter(other).compare(other_expected)

    owner_rendered, owner_params = _compiled_document_scope(owner)
    other_rendered, other_params = _compiled_document_scope(other)
    for rendered in (owner_rendered, other_rendered):
        assert "workspace_entities.owner_user_id" in rendered
        assert "workspace_entities.workspace_id" in rendered
        assert "EXISTS" in rendered.upper()
        assert "IS NULL" in rendered.upper()

    assert owner.user_id in owner_params.values()
    assert other.user_id in other_params.values()
    assert owner.workspace_id in owner_params.values()
    assert other.workspace_id in other_params.values()
