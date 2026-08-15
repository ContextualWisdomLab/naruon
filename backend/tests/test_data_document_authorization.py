"""Authorization regressions for workspace document actions."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest
from fastapi import HTTPException

import api.data as data_api
from api.auth import AuthContext
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

    async def execute(self, statement: Any) -> _ScalarResult:
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


def _document(
    *,
    document_id: str,
    organization_id: str | None,
    document_name: str,
) -> Document:
    """Build a workspace document with a stable timestamp for surface tests."""

    return Document(
        document_id=document_id,
        workspace_id="workspace-shared-identifier",
        organization_id=organization_id,
        document_name=document_name,
        document_type="text/markdown",
        document_content="tenant evidence",
        document_status="uploaded",
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )


def _document_visible_in_scope(
    document: Document,
    values: tuple[Any, ...],
    rendered_scope: str,
) -> bool:
    """Return whether a compiled document scope includes the fake document."""

    if document.workspace_id not in values:
        return False
    if "workspace_documents.organization_id" not in rendered_scope:
        return True
    if document.organization_id is None:
        return "IS NULL" in rendered_scope.upper()
    return document.organization_id in values


def _install_quality_surface_fixtures(
    monkeypatch: pytest.MonkeyPatch,
    documents: list[Document],
) -> None:
    """Patch the expensive quality-surface dependencies with deterministic fakes."""

    async def scoped_rows(_db: object, statement: Any) -> list[object]:
        statement_text = str(statement)
        if "workspace_documents" not in statement_text:
            return []
        compiled = statement.compile()
        rendered_scope = str(statement.whereclause)
        values = tuple(compiled.params.values())
        return [
            document
            for document in documents
            if _document_visible_in_scope(document, values, rendered_scope)
        ]

    async def zero_email_stats(
        _db: object,
        _email_scope: object,
    ) -> data_api.EmailQualityStats:
        return data_api.EmailQualityStats(
            count=0,
            missing_thread_count=0,
            missing_fingerprint_count=0,
            embedded_count=0,
        )

    async def zero_attachment_stats(
        _db: object,
        _email_scope: object,
    ) -> data_api.AttachmentQualityStats:
        return data_api.AttachmentQualityStats(
            count=0,
            blank_content_count=0,
            embedded_count=0,
        )

    async def zero_content_graph_stats(
        _db: object,
        _email_scope: object,
    ) -> data_api.ContentGraphQualityStats:
        return data_api.ContentGraphQualityStats(
            segmented_email_count=0,
            segment_count=0,
        )

    async def zero_knowledge_graph_stats(
        _db: object,
        _email_scope: object,
    ) -> data_api.KnowledgeGraphQualityStats:
        return data_api.KnowledgeGraphQualityStats(
            edged_email_count=0,
            edge_count=0,
        )

    async def zero_content_segment_readiness_stats(
        _db: object,
        _email_scope: object,
    ) -> data_api.ContentSegmentTextReadinessStats:
        return data_api.ContentSegmentTextReadinessStats(
            total_count=0,
            issue_count=0,
        )

    async def zero_knowledge_graph_endpoint_stats(
        _db: object,
        _email_scope: object,
    ) -> data_api.KnowledgeGraphEvidenceEndpointStats:
        return data_api.KnowledgeGraphEvidenceEndpointStats(
            total_count=0,
            issue_count=0,
        )

    async def zero_semantic_relation_stats(
        _db: object,
        _auth_context: AuthContext,
    ) -> data_api.SemanticRelationEvidenceStats:
        return data_api.SemanticRelationEvidenceStats(
            total_count=0,
            source_backed_count=0,
        )

    async def zero_attachment_parse_stats(
        _db: object,
        _email_scope: object,
    ) -> data_api.AttachmentParseQualityStats:
        return data_api.AttachmentParseQualityStats(
            parsed_count=0,
            unparsed_count=0,
        )

    async def empty_list(*_args: object, **_kwargs: object) -> list[object]:
        return []

    monkeypatch.setattr(data_api, "_scoped_rows", scoped_rows)
    monkeypatch.setattr(data_api, "_get_email_stats", zero_email_stats)
    monkeypatch.setattr(data_api, "_get_attachment_stats", zero_attachment_stats)
    monkeypatch.setattr(data_api, "_get_content_graph_stats", zero_content_graph_stats)
    monkeypatch.setattr(
        data_api,
        "_get_knowledge_graph_stats",
        zero_knowledge_graph_stats,
    )
    monkeypatch.setattr(
        data_api,
        "_get_content_segment_text_readiness_stats",
        zero_content_segment_readiness_stats,
    )
    monkeypatch.setattr(
        data_api,
        "_get_knowledge_graph_evidence_endpoint_stats",
        zero_knowledge_graph_endpoint_stats,
    )
    monkeypatch.setattr(data_api, "_get_content_graph_breakdown", empty_list)
    monkeypatch.setattr(data_api, "_get_knowledge_graph_breakdown", empty_list)
    monkeypatch.setattr(data_api, "_get_content_graph_evidence_samples", empty_list)
    monkeypatch.setattr(data_api, "_get_knowledge_graph_evidence_samples", empty_list)
    monkeypatch.setattr(
        data_api,
        "_get_semantic_relation_evidence_stats",
        zero_semantic_relation_stats,
    )
    monkeypatch.setattr(
        data_api,
        "_get_semantic_relation_evidence_samples",
        empty_list,
    )
    monkeypatch.setattr(
        data_api,
        "_get_attachment_parse_stats",
        zero_attachment_parse_stats,
    )
    monkeypatch.setattr(data_api, "_get_attachment_parse_breakdown", empty_list)
    monkeypatch.setattr(data_api, "_get_connector_events", empty_list)
    monkeypatch.setattr(data_api, "_get_attachment_assets", empty_list)


@pytest.mark.asyncio
async def test_workspace_document_lookup_rejects_cross_organization_idor() -> None:
    """A reused workspace identifier must not cross the tenant boundary."""

    document = _document(
        document_id="doc-org-b",
        organization_id="org-b",
        document_name="private.md",
    )
    session = _OrganizationAwareSession(document)

    with pytest.raises(HTTPException) as exc_info:
        await data_api._get_workspace_document(
            session,  # type: ignore[arg-type]
            _auth_context("org-a"),
            document.document_id,
        )

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_workspace_document_lookup_preserves_same_organization_collaboration() -> None:
    """Workspace members in the owning organization retain shared-document access."""

    document = _document(
        document_id="doc-org-a",
        organization_id="org-a",
        document_name="shared.md",
    )
    session = _OrganizationAwareSession(document)

    resolved = await data_api._get_workspace_document(
        session,  # type: ignore[arg-type]
        _auth_context("org-a"),
        document.document_id,
    )

    assert resolved is document


@pytest.mark.asyncio
async def test_personal_workspace_document_lookup_rejects_organization_document() -> None:
    """Personal-scope sessions cannot read organization-owned workspace documents."""

    document = _document(
        document_id="doc-org-owned",
        organization_id="org-a",
        document_name="org.md",
    )
    session = _OrganizationAwareSession(document)

    with pytest.raises(HTTPException) as exc_info:
        await data_api._get_workspace_document(
            session,  # type: ignore[arg-type]
            _auth_context(None),
            document.document_id,
        )

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_personal_workspace_document_lookup_preserves_personal_document() -> None:
    """Personal-scope sessions can read organization-less workspace documents."""

    document = _document(
        document_id="doc-personal",
        organization_id=None,
        document_name="personal.md",
    )
    session = _OrganizationAwareSession(document)

    resolved = await data_api._get_workspace_document(
        session,  # type: ignore[arg-type]
        _auth_context(None),
        document.document_id,
    )

    assert resolved is document


@pytest.mark.asyncio
async def test_data_quality_surface_excludes_foreign_organization_document(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The data-quality surface lists only documents owned by the organization."""

    documents = [
        _document(
            document_id="doc-org-a",
            organization_id="org-a",
            document_name="visible.md",
        ),
        _document(
            document_id="doc-org-b",
            organization_id="org-b",
            document_name="hidden.md",
        ),
    ]
    _install_quality_surface_fixtures(monkeypatch, documents)

    surface = await data_api.get_data_quality_surface(
        _auth_context("org-a"),
        object(),  # type: ignore[arg-type]
    )

    document_repository = next(
        repository
        for repository in surface.repositories
        if repository.repository_type == "document_repository"
    )
    assert document_repository.object_count == 1
    assert [
        asset.asset_key
        for asset in surface.repository_assets
        if asset.asset_type == "workspace_document"
    ] == ["doc-org-a"]
