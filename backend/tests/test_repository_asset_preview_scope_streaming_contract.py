"""Regression contracts for repository-asset preview isolation and streaming.

These tests deliberately exercise the query boundary rather than a permissive
mock of ``AsyncSession.execute``. A preview lookup must include the signed
organization scope for workspace documents, and a ``yield_per`` attachment scan
must use the asynchronous streaming API.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi import HTTPException

from api import data as data_api
from api.auth import AuthContext


class _ScalarResult:
    """Minimal scalar result used to capture document lookup statements."""

    def __init__(self, value: object | None) -> None:
        self._value = value

    def scalar_one_or_none(self) -> object | None:
        return self._value


class _CaptureDocumentSession:
    """Capture the exact SQL statement used for a workspace-document lookup."""

    def __init__(self) -> None:
        self.statement: Any | None = None

    async def execute(self, statement: Any) -> _ScalarResult:
        self.statement = statement
        return _ScalarResult(None)


class _EmptyAsyncRows:
    """Asynchronous row iterator for an attachment scan with no matching row."""

    def __aiter__(self):
        async def _rows():
            if False:  # pragma: no cover - keeps this an async generator.
                yield None

        return _rows()


class _StreamingOnlyPreviewSession:
    """Reject attachment candidate scans sent through ``execute``."""

    def __init__(self) -> None:
        self.streamed_statements: list[Any] = []

    async def execute(self, statement: Any) -> _ScalarResult:
        rendered = str(statement).lower()
        if "workspace_documents" in rendered:
            return _ScalarResult(None)
        if "email_attachments" in rendered:
            raise AssertionError(
                "yield_per attachment candidates must use AsyncSession.stream"
            )
        return _ScalarResult(None)

    async def stream(self, statement: Any) -> _EmptyAsyncRows:
        self.streamed_statements.append(statement)
        return _EmptyAsyncRows()


def _auth_context(*, organization_id: str | None) -> AuthContext:
    return AuthContext(
        user_id="member-a",
        role="member",
        organization_id=organization_id,
        group_ids=("group-data",),
        workspace_id="workspace-shared",
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("organization_id", ["org-acme", None])
async def test_document_preview_lookup_carries_signed_organization_scope(
    organization_id: str | None,
) -> None:
    """Workspace id alone is not a tenant boundary for persisted documents."""

    session = _CaptureDocumentSession()

    await data_api._find_workspace_document(
        session,  # type: ignore[arg-type]
        _auth_context(organization_id=organization_id),
        "doc-shared",
    )

    assert session.statement is not None
    sql = str(session.statement).lower()
    assert "workspace_documents.workspace_id" in sql
    assert "workspace_documents.organization_id" in sql
    if organization_id is None:
        assert "workspace_documents.organization_id is null" in sql
    else:
        params = session.statement.compile().params
        assert organization_id in params.values()


@pytest.mark.asyncio
async def test_attachment_preview_streams_yield_per_candidates() -> None:
    """A yield-per candidate scan must not go through AsyncSession.execute."""

    session = _StreamingOnlyPreviewSession()

    with pytest.raises(HTTPException) as exc_info:
        await data_api.get_repository_asset_preview(
            "asset_missing_preview_key",
            _auth_context(organization_id="org-acme"),
            session,  # type: ignore[arg-type]
        )

    assert exc_info.value.status_code == 404
    assert len(session.streamed_statements) == 1
    execution_options = session.streamed_statements[0].get_execution_options()
    assert execution_options.get("yield_per") == 500
