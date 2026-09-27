"""Tests for wiring project-graph extraction into the email import pipeline.

The projection is flag-gated and best-effort: it must never affect the (already
committed) email import. These tests exercise the real deterministic extractor
and mock only the DB persistence layer.
"""

import types

import pytest
from unittest.mock import AsyncMock

import services.email_import_service as import_service
from services.content_graph import parse_content
from services.project_graph.extractors import extract_attachment_facts
from services.project_graph.models import ProjectObjectType
from services.project_graph.models import ProjectSourceSegment
from services.project_graph.project_registration import _candidate_groups


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

    result = import_service._project_source_segments(email_obj)

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

    await import_service._persist_project_graph_projection(
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

    await import_service._persist_project_graph_projection(
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

    await import_service._persist_project_graph_projection(
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

    await import_service._persist_project_graph_projection(
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
    await import_service._persist_project_graph_projection(
        session, segments, user_id="u", organization_id="o"
    )

    session.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_attachment_facts_persist_without_optional_project_extraction(
    monkeypatch,
):
    persist_mock = AsyncMock()
    project_mock = AsyncMock(
        side_effect=AssertionError("project extraction must stay off")
    )
    monkeypatch.setattr(
        import_service, "persist_project_graph_projection", persist_mock
    )
    monkeypatch.setattr(
        import_service, "_extract_project_semantics_for_import", project_mock
    )
    session = AsyncMock()
    attachment = _segment(
        "attachment-segment",
        "Invoice date: 2026-09-27\nTotal: ₩1,200,000\nVendor: Acme Ltd\nCommitment: Pay by Friday",
    )
    attachment.source_kind = "attachment"
    body = _segment("body-segment", "Total: $999")

    await import_service._persist_project_graph_projection(
        session,
        [body, attachment],
        user_id="owner",
        organization_id="org",
        include_project_semantics=False,
    )

    extraction = persist_mock.await_args.kwargs["extraction"]
    assert len(extraction.objects) == len(extraction.edges) == 4
    assert {obj.attributes["fact_kind"] for obj in extraction.objects} == {
        "date",
        "amount",
        "party",
        "commitment",
    }
    assert all(
        obj.object_type is ProjectObjectType.ATTACHMENT_FACT
        for obj in extraction.objects
    )
    assert all(
        obj.source_segment_uids == ("attachment-segment",) for obj in extraction.objects
    )
    assert all(
        edge.source_uid == "segment:attachment-segment" for edge in extraction.edges
    )
    assert len({obj.uid for obj in extraction.objects}) == 4
    project_mock.assert_not_awaited()
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_attachment_fact_rejects_invalid_or_unlabelled_values(monkeypatch):
    persist_mock = AsyncMock()
    monkeypatch.setattr(
        import_service, "persist_project_graph_projection", persist_mock
    )
    segment = _segment(
        "attachment-segment",
        "Due date: 2026-02-30\nAmount: 12345\nSomebody promised $10\nVendor: ",
    )
    segment.source_kind = "attachment"
    await import_service._persist_project_graph_projection(
        AsyncMock(),
        [segment],
        user_id="owner",
        organization_id="org",
        include_project_semantics=False,
    )
    persist_mock.assert_not_awaited()


def test_attachment_facts_do_not_create_project_candidates():
    fact = types.SimpleNamespace(
        object_type=ProjectObjectType.ATTACHMENT_FACT.value,
        email_id=1,
    )
    assert _candidate_groups([fact], scope=types.SimpleNamespace()) == ()


def test_parsed_attachment_segments_produce_cited_literal_facts():
    parsed = parse_content(
        source_kind="attachment",
        source_record_uid="attachment:test",
        content="Invoice date: 2026-09-27\nTotal: ₩1,200,000",
        content_type="text/plain",
        display_name="invoice.txt",
    )
    segments = [
        ProjectSourceSegment(
            content_segment_uid=item.content_segment_uid,
            source_kind=item.source_kind,
            source_record_uid=item.source_record_uid,
            safe_text_content=item.safe_text_content,
        )
        for item in parsed.segments
    ]
    result = extract_attachment_facts(segments)
    assert {obj.attributes["fact_kind"] for obj in result.objects} == {
        "date", "amount"
    }, [(item.segment_kind, item.safe_text_content) for item in parsed.segments]
    assert {obj.source_segment_uids[0] for obj in result.objects} <= {
        item.content_segment_uid for item in parsed.segments
    }
