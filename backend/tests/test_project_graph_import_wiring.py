"""Tests for wiring project-graph extraction into the email import pipeline.

The projection is flag-gated and best-effort: it must never affect the (already
committed) email import. These tests exercise the real deterministic extractor
and mock only the DB persistence layer.
"""

import types

import pytest
from unittest.mock import AsyncMock

import services.email_import_service as import_service
from services.email_import_service import (
    _persist_project_graph_projection,
    _project_source_segments,
)


def _segment(uid: str, text: str, ordinal: int = 0):
    return types.SimpleNamespace(
        content_segment_uid=uid,
        source_kind="email_body",
        source_record_uid="email:1",
        safe_text_content=text,
        heading_path=None,
        segment_path=f"body/{ordinal}",
        ordinal_index=ordinal,
    )


def test_project_source_segments_maps_content_segments():
    email_obj = types.SimpleNamespace(
        content_segments=[_segment("seg1", "hello", 0), _segment("seg2", "world", 1)]
    )

    result = _project_source_segments(email_obj)

    assert [segment.content_segment_uid for segment in result] == ["seg1", "seg2"]
    assert result[0].safe_text_content == "hello"
    assert result[0].source_kind == "email_body"
    assert result[1].ordinal_index == 1


@pytest.mark.asyncio
async def test_projection_persists_with_workspace_scope_when_objects_found(monkeypatch):
    persist_mock = AsyncMock()
    monkeypatch.setattr(
        import_service, "persist_project_graph_projection", persist_mock
    )
    session = AsyncMock()
    segments = [
        _segment("seg1", "The system must support export. This is a requirement.", 0)
    ]

    await _persist_project_graph_projection(
        session, segments, user_id="user1", organization_id="org1"
    )

    persist_mock.assert_awaited_once()
    kwargs = persist_mock.await_args.kwargs
    assert kwargs["user_id"] == "user1"
    assert kwargs["organization_id"] == "org1"
    # Mirrors the scope convention enforced by the project graph repository.
    assert kwargs["workspace_id"] == "workspace-org1"
    assert kwargs["extraction"].objects  # real extractor produced candidates
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_projection_falls_back_to_user_workspace_without_org(monkeypatch):
    persist_mock = AsyncMock()
    monkeypatch.setattr(
        import_service, "persist_project_graph_projection", persist_mock
    )
    session = AsyncMock()
    segments = [_segment("seg1", "We must deliver the milestone by 2026-01-01.", 0)]

    await _persist_project_graph_projection(
        session, segments, user_id="user1", organization_id=""
    )

    kwargs = persist_mock.await_args.kwargs
    assert kwargs["workspace_id"] == "workspace-user1"


@pytest.mark.asyncio
async def test_projection_noop_when_no_segments(monkeypatch):
    persist_mock = AsyncMock()
    monkeypatch.setattr(
        import_service, "persist_project_graph_projection", persist_mock
    )
    session = AsyncMock()

    await _persist_project_graph_projection(
        session, [], user_id="u", organization_id="o"
    )

    persist_mock.assert_not_awaited()
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_projection_noop_when_no_objects_extracted(monkeypatch):
    persist_mock = AsyncMock()
    monkeypatch.setattr(
        import_service, "persist_project_graph_projection", persist_mock
    )
    session = AsyncMock()
    # Neutral text with no rule keywords -> extractor yields nothing.
    segments = [_segment("seg1", "hello there, nice weather today", 0)]

    await _persist_project_graph_projection(
        session, segments, user_id="u", organization_id="o"
    )

    persist_mock.assert_not_awaited()
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_projection_swallows_failure_and_rolls_back(monkeypatch):
    persist_mock = AsyncMock(side_effect=RuntimeError("boom"))
    monkeypatch.setattr(
        import_service, "persist_project_graph_projection", persist_mock
    )
    session = AsyncMock()
    segments = [_segment("seg1", "The system must support export requirement.", 0)]

    # Best-effort: a projection failure must not propagate to the import.
    await _persist_project_graph_projection(
        session, segments, user_id="u", organization_id="o"
    )

    session.rollback.assert_awaited_once()
