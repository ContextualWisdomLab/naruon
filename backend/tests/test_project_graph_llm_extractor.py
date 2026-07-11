"""Tests for the LLM-grounded project extractor and its import selection."""

import types

import pytest
from unittest.mock import AsyncMock

import services.email_import_service as import_service
import services.project_graph.llm_extractor as llm_extractor
from services.project_graph import ProjectSourceSegment


def _segment(uid: str, text: str) -> ProjectSourceSegment:
    return ProjectSourceSegment(
        content_segment_uid=uid,
        source_kind="email_body",
        source_record_uid="email:1",
        safe_text_content=text,
        heading_path=None,
        segment_path="body/0",
        ordinal_index=0,
    )


def _payload(
    *objects: llm_extractor.ExtractedObjectPayload,
) -> llm_extractor.ExtractionPayload:
    return llm_extractor.ExtractionPayload(objects=list(objects))


@pytest.mark.asyncio
async def test_grounded_objects_are_mapped_with_citations(monkeypatch):
    monkeypatch.setattr(
        llm_extractor,
        "_call_llm",
        AsyncMock(
            return_value=_payload(
                llm_extractor.ExtractedObjectPayload(
                    object_type="requirement",
                    title="Export must be supported",
                    summary="The system must support export.",
                    source_segment_uids=["seg1"],
                    confidence=0.8,
                )
            )
        ),
    )

    result = await llm_extractor.extract_project_semantics_llm(
        [_segment("seg1", "The system must support export.")],
        api_key="key",
        model="gpt-test",
    )

    assert len(result.objects) == 1
    obj = result.objects[0]
    assert obj.object_type.value == "requirement"
    assert obj.source_segment_uids == ("seg1",)
    assert obj.extractor_name == llm_extractor.LLM_EXTRACTOR_NAME
    assert result.edges[0].source_uid == "segment:seg1"
    assert result.edges[0].target_uid == obj.uid


@pytest.mark.asyncio
async def test_objects_citing_unknown_segments_are_dropped(monkeypatch):
    monkeypatch.setattr(
        llm_extractor,
        "_call_llm",
        AsyncMock(
            return_value=_payload(
                llm_extractor.ExtractedObjectPayload(
                    object_type="requirement",
                    title="Fabricated",
                    summary="Cites a segment that does not exist.",
                    source_segment_uids=["seg1", "hallucinated"],
                    confidence=0.9,
                ),
                llm_extractor.ExtractedObjectPayload(
                    object_type="issue",
                    title="No citation at all",
                    summary="Empty citations.",
                    source_segment_uids=[],
                    confidence=0.9,
                ),
            )
        ),
    )

    result = await llm_extractor.extract_project_semantics_llm(
        [_segment("seg1", "real text")], api_key="key", model="gpt-test"
    )

    assert result.objects == ()
    assert result.edges == ()


@pytest.mark.asyncio
async def test_unknown_type_dropped_and_confidence_clamped(monkeypatch):
    monkeypatch.setattr(
        llm_extractor,
        "_call_llm",
        AsyncMock(
            return_value=_payload(
                llm_extractor.ExtractedObjectPayload(
                    object_type="not_a_real_type",
                    title="Bad type",
                    summary="x",
                    source_segment_uids=["seg1"],
                    confidence=0.5,
                ),
                llm_extractor.ExtractedObjectPayload(
                    object_type="milestone",
                    title="Overconfident",
                    summary="Due next week.",
                    source_segment_uids=["seg1"],
                    confidence=7.5,
                ),
            )
        ),
    )

    result = await llm_extractor.extract_project_semantics_llm(
        [_segment("seg1", "milestone text")], api_key="key", model="gpt-test"
    )

    assert len(result.objects) == 1
    assert result.objects[0].object_type.value == "milestone"
    assert result.objects[0].confidence == 1.0


@pytest.mark.asyncio
async def test_empty_segments_short_circuit_without_llm_call(monkeypatch):
    call = AsyncMock()
    monkeypatch.setattr(llm_extractor, "_call_llm", call)

    result = await llm_extractor.extract_project_semantics_llm(
        [_segment("seg1", "   ")], api_key="key", model="gpt-test"
    )

    call.assert_not_awaited()
    assert result.objects == ()


@pytest.mark.asyncio
async def test_import_selection_uses_llm_when_configured(monkeypatch):
    llm_mock = AsyncMock(return_value="llm-result")
    monkeypatch.setattr(
        import_service, "extract_project_semantics_llm", llm_mock
    )
    monkeypatch.setattr(
        import_service.settings, "PROJECT_GRAPH_EXTRACTOR", "llm", raising=False
    )
    provider = import_service.EmailImportEmbeddingProvider(
        api_key="key", base_url=None, embedding_model="embed"
    )

    result = await import_service._extract_project_semantics_for_import(
        [_segment("seg1", "text")], embedding_provider=provider
    )

    assert result == "llm-result"
    llm_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_import_selection_falls_back_to_keyword_on_llm_failure(monkeypatch):
    monkeypatch.setattr(
        import_service,
        "extract_project_semantics_llm",
        AsyncMock(side_effect=RuntimeError("provider down")),
    )
    keyword_result = types.SimpleNamespace(objects=(), edges=())
    keyword_mock = lambda segments: keyword_result  # noqa: E731
    monkeypatch.setattr(import_service, "extract_project_semantics", keyword_mock)
    monkeypatch.setattr(
        import_service.settings, "PROJECT_GRAPH_EXTRACTOR", "llm", raising=False
    )
    provider = import_service.EmailImportEmbeddingProvider(
        api_key="key", base_url=None, embedding_model="embed"
    )

    result = await import_service._extract_project_semantics_for_import(
        [_segment("seg1", "text")], embedding_provider=provider
    )

    assert result is keyword_result


@pytest.mark.asyncio
async def test_import_selection_defaults_to_keyword(monkeypatch):
    llm_mock = AsyncMock()
    monkeypatch.setattr(
        import_service, "extract_project_semantics_llm", llm_mock
    )
    keyword_result = types.SimpleNamespace(objects=(), edges=())
    monkeypatch.setattr(
        import_service, "extract_project_semantics", lambda segments: keyword_result
    )
    monkeypatch.setattr(
        import_service.settings, "PROJECT_GRAPH_EXTRACTOR", "keyword", raising=False
    )

    result = await import_service._extract_project_semantics_for_import(
        [_segment("seg1", "text")], embedding_provider=None
    )

    assert result is keyword_result
    llm_mock.assert_not_awaited()
