"""Authorization regressions for workspace document actions."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from api.auth import AuthContext
from api.data import _get_workspace_document
from db.models import Document


class _ScalarResult:
    """Minimal SQLAlchemy result surface used by the authorization helper."""

    def __init__(self, value: Document | None) -> None:
        self._value = value

    def scalar_one_or_none(self) -> Document | None:
        """Return the single simulated document result."""

        return self._value


class _OrganizationAwareSession:
    """Evaluate document scope predicates against one in-memory document."""

    def __init__(self, document: Document) -> None:
        self.document = document

    async def execute(self, statement):
        """Return the document only when every emitted scope predicate matches."""

        compiled = statement.compile()
        rendered_scope = str(statement.whereclause)
        values = tuple(compiled.params.values())
        if self.document.document_id not in values:
            return _ScalarResult(None)
        if self.document.workspace_id not in values:
            return _ScalarResult(None)

        # A missing organization predicate reproduces the vulnerable behavior:
        # a document from another tenant is still returned solely because both
        # principals supplied the same workspace identifier.
        if "workspace_documents.organization_id" not in rendered_scope:
            return _ScalarResult(self.document)

        if self.document.organization_id is None:
            organization_matches = "IS NULL" in rendered_scope.upper()
        else:
            organization_matches = self.document.organization_id in values
        return _ScalarResult(self.document if organization_matches else None)


def _auth_context(organization_id: str | None) -> AuthContext:
    return AuthContext(
        user_id="member-a",
        role="member",
        organization_id=organization_id,
        group_ids=(),
        workspace_id="workspace-shared-identifier",
    )


@pytest.mark.asyncio
async def test_workspace_document_lookup_rejects_cross_organization_idor() -> None:
    """A reused workspace identifier must not cross the tenant boundary."""

    document = Document(
        document_id="doc-org-b",
        workspace_id="workspace-shared-identifier",
        organization_id="org-b",
        document_name="private.md",
        document_type="text/markdown",
        document_content="tenant B evidence",
        document_status="uploaded",
    )
    session = _OrganizationAwareSession(document)

    with pytest.raises(HTTPException) as exc_info:
        await _get_workspace_document(session, _auth_context("org-a"), document.document_id)  # type: ignore[arg-type]

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_workspace_document_lookup_preserves_same_organization_collaboration() -> None:
    """Workspace members in the owning organization retain shared-document access."""

    document = Document(
        document_id="doc-org-a",
        workspace_id="workspace-shared-identifier",
        organization_id="org-a",
        document_name="shared.md",
        document_type="text/markdown",
        document_content="shared tenant evidence",
        document_status="uploaded",
    )
    session = _OrganizationAwareSession(document)

    resolved = await _get_workspace_document(
        session,  # type: ignore[arg-type]
        _auth_context("org-a"),
        document.document_id,
    )

    assert resolved is document


@pytest.mark.asyncio
async def test_personal_workspace_document_lookup_rejects_organization_document() -> None:
    """Personal-scope sessions cannot read organization-owned workspace documents."""

    document = Document(
        document_id="doc-org-owned",
        workspace_id="workspace-shared-identifier",
        organization_id="org-a",
        document_name="org.md",
        document_type="text/markdown",
        document_content="organization evidence",
        document_status="uploaded",
    )
    session = _OrganizationAwareSession(document)

    with pytest.raises(HTTPException) as exc_info:
        await _get_workspace_document(session, _auth_context(None), document.document_id)  # type: ignore[arg-type]

    assert exc_info.value.status_code == 404
