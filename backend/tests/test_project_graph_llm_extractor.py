"""Tests for the LLM-grounded project extractor and its import selection."""

import types

import pytest
from unittest.mock import AsyncMock, Mock

import services.email_import_service as import_service
import services.project_graph.extractor_registry as extractor_registry
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


def _object(
    *,
    object_type: str,
    title: str,
    summary: str,
    segment_uids: list[str],
    confidence: float,
    local_key: str,
) -> "llm_extractor.ExtractedObjectPayload":
    return llm_extractor.ExtractedObjectPayload(
        object_type=object_type,
        title=title,
        summary=summary,
        source_segment_uids=segment_uids,
        confidence=confidence,
        local_key=local_key,
    )


def _relation(
    *,
    source_local_key: str,
    target_local_key: str,
    relation_type: str,
    confidence: float,
) -> "llm_extractor.ExtractedRelationPayload":
    return llm_extractor.ExtractedRelationPayload(
        source_local_key=source_local_key,
        target_local_key=target_local_key,
        relation_type=relation_type,
        confidence=confidence,
    )


def _two_grounded_objects() -> list["llm_extractor.ExtractedObjectPayload"]:
    return [
        _object(
            object_type="feature",
            title="Card-decline retry banner",
            summary="Show a retry banner when a card is declined.",
            segment_uids=["seg1"],
            confidence=0.8,
            local_key="feat-a",
        ),
        _object(
            object_type="requirement",
            title="Card declines must be handled",
            summary="The checkout must handle card declines gracefully.",
            segment_uids=["seg2"],
            confidence=0.9,
            local_key="req-b",
        ),
    ]


def _two_grounded_segments() -> list[ProjectSourceSegment]:
    return [
        _segment("seg1", "Show a retry banner when a card is declined."),
        _segment("seg2", "The checkout must handle card declines gracefully."),
    ]


@pytest.mark.asyncio
async def test_grounded_relations_link_extracted_objects(monkeypatch):
    monkeypatch.setattr(
        llm_extractor,
        "_call_llm",
        AsyncMock(
            return_value=llm_extractor.ExtractionPayload(
                objects=_two_grounded_objects(),
                relations=[
                    _relation(
                        source_local_key="feat-a",
                        target_local_key="req-b",
                        relation_type="implements",
                        confidence=0.72,
                    )
                ],
            )
        ),
    )

    result = await llm_extractor.extract_project_semantics_llm(
        _two_grounded_segments(), api_key="key", model="gpt-test"
    )

    feature = next(o for o in result.objects if o.object_type.value == "feature")
    requirement = next(o for o in result.objects if o.object_type.value == "requirement")
    relation_edges = [
        edge for edge in result.edges if edge.edge_type == "implements"
    ]
    assert len(relation_edges) == 1
    relation_edge = relation_edges[0]
    assert relation_edge.source_uid == feature.uid
    assert relation_edge.target_uid == requirement.uid
    # The object-to-object edge is grounded in the union of both endpoints'
    # cited segments, so it never introduces an uncited segment reference.
    assert set(relation_edge.source_segment_uids) == {"seg1", "seg2"}
    assert 0.0 <= relation_edge.confidence <= 1.0
    # Segment evidence edges are still emitted alongside the relation edges.
    assert any(
        edge.edge_type == "segment_evidences_project_object"
        for edge in result.edges
    )


@pytest.mark.asyncio
async def test_relations_with_unknown_type_are_dropped(monkeypatch):
    monkeypatch.setattr(
        llm_extractor,
        "_call_llm",
        AsyncMock(
            return_value=llm_extractor.ExtractionPayload(
                objects=_two_grounded_objects(),
                relations=[
                    _relation(
                        source_local_key="feat-a",
                        target_local_key="req-b",
                        relation_type="frobnicates",
                        confidence=0.9,
                    )
                ],
            )
        ),
    )

    result = await llm_extractor.extract_project_semantics_llm(
        _two_grounded_segments(), api_key="key", model="gpt-test"
    )

    assert all(
        edge.edge_type == "segment_evidences_project_object"
        for edge in result.edges
    )


@pytest.mark.asyncio
async def test_relations_to_ungrounded_objects_are_dropped(monkeypatch):
    monkeypatch.setattr(
        llm_extractor,
        "_call_llm",
        AsyncMock(
            return_value=llm_extractor.ExtractionPayload(
                objects=[
                    _object(
                        object_type="feature",
                        title="Grounded feature",
                        summary="Grounded in seg1.",
                        segment_uids=["seg1"],
                        confidence=0.8,
                        local_key="feat-a",
                    ),
                    _object(
                        object_type="issue",
                        title="Ungrounded issue",
                        summary="Cites a hallucinated segment.",
                        segment_uids=["hallucinated"],
                        confidence=0.9,
                        local_key="issue-x",
                    ),
                ],
                relations=[
                    _relation(
                        source_local_key="feat-a",
                        target_local_key="issue-x",
                        relation_type="blocks",
                        confidence=0.9,
                    ),
                    _relation(
                        source_local_key="feat-a",
                        target_local_key="ghost-key",
                        relation_type="depends_on",
                        confidence=0.9,
                    ),
                ],
            )
        ),
    )

    result = await llm_extractor.extract_project_semantics_llm(
        [_segment("seg1", "Grounded in seg1.")], api_key="key", model="gpt-test"
    )

    # The ungrounded object is dropped, so any relation touching it (or an
    # unknown key) cannot resolve to two grounded objects and is dropped too.
    assert len(result.objects) == 1
    assert all(
        edge.edge_type == "segment_evidences_project_object"
        for edge in result.edges
    )


@pytest.mark.asyncio
async def test_self_loop_and_duplicate_relations_are_dropped(monkeypatch):
    monkeypatch.setattr(
        llm_extractor,
        "_call_llm",
        AsyncMock(
            return_value=llm_extractor.ExtractionPayload(
                objects=_two_grounded_objects(),
                relations=[
                    _relation(
                        source_local_key="feat-a",
                        target_local_key="feat-a",
                        relation_type="depends_on",
                        confidence=0.9,
                    ),
                    _relation(
                        source_local_key="feat-a",
                        target_local_key="req-b",
                        relation_type="implements",
                        confidence=0.7,
                    ),
                    _relation(
                        source_local_key="feat-a",
                        target_local_key="req-b",
                        relation_type="implements",
                        confidence=0.4,
                    ),
                ],
            )
        ),
    )

    result = await llm_extractor.extract_project_semantics_llm(
        _two_grounded_segments(), api_key="key", model="gpt-test"
    )

    relation_edges = [
        edge
        for edge in result.edges
        if edge.edge_type != "segment_evidences_project_object"
    ]
    assert len(relation_edges) == 1
    assert relation_edges[0].edge_type == "implements"


# The import selector resolves through the KG extractor registry, so these
# tests patch the extraction cores where the registry imports them.
def _patch_extractor_cores(monkeypatch, *, llm, keyword):
    monkeypatch.setattr(extractor_registry, "extract_project_semantics_llm", llm)
    monkeypatch.setattr(extractor_registry, "extract_project_semantics", keyword)


@pytest.mark.asyncio
async def test_import_selection_uses_llm_when_configured(monkeypatch):
    llm_mock = AsyncMock(return_value="llm-result")
    keyword_mock = Mock()
    _patch_extractor_cores(monkeypatch, llm=llm_mock, keyword=keyword_mock)
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
    keyword_mock.assert_not_called()


@pytest.mark.asyncio
async def test_import_selection_falls_back_to_keyword_on_llm_failure(monkeypatch):
    keyword_result = types.SimpleNamespace(objects=(), edges=())
    _patch_extractor_cores(
        monkeypatch,
        llm=AsyncMock(side_effect=RuntimeError("provider down")),
        keyword=Mock(return_value=keyword_result),
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

    assert result is keyword_result


@pytest.mark.asyncio
async def test_import_selection_defaults_to_keyword(monkeypatch):
    llm_mock = AsyncMock()
    keyword_result = types.SimpleNamespace(objects=(), edges=())
    _patch_extractor_cores(
        monkeypatch, llm=llm_mock, keyword=Mock(return_value=keyword_result)
    )
    monkeypatch.setattr(
        import_service.settings, "PROJECT_GRAPH_EXTRACTOR", "keyword", raising=False
    )

    result = await import_service._extract_project_semantics_for_import(
        [_segment("seg1", "text")], embedding_provider=None
    )

    assert result is keyword_result
    llm_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_import_selection_routes_through_orchestrator_when_configured(monkeypatch):
    llm_mock = AsyncMock(return_value="orchestrator-result")
    _patch_extractor_cores(monkeypatch, llm=llm_mock, keyword=Mock())
    monkeypatch.setattr(
        import_service.settings, "PROJECT_GRAPH_EXTRACTOR", "orchestrator", raising=False
    )
    monkeypatch.setattr(
        import_service.settings,
        "PROJECT_GRAPH_ORCHESTRATOR_BASE_URL",
        "https://orchestrator.example/v1",
        raising=False,
    )
    provider = import_service.EmailImportEmbeddingProvider(
        api_key="key", base_url="https://provider.example", embedding_model="embed"
    )

    result = await import_service._extract_project_semantics_for_import(
        [_segment("seg1", "text")], embedding_provider=provider
    )

    assert result == "orchestrator-result"
    # Extraction is routed at the orchestrator endpoint, not the raw provider.
    assert (
        llm_mock.await_args.kwargs["base_url"] == "https://orchestrator.example/v1"
    )


@pytest.mark.asyncio
async def test_import_selection_orchestrator_falls_back_when_unconfigured(monkeypatch):
    llm_mock = AsyncMock()
    keyword_result = types.SimpleNamespace(objects=(), edges=())
    _patch_extractor_cores(
        monkeypatch, llm=llm_mock, keyword=Mock(return_value=keyword_result)
    )
    monkeypatch.setattr(
        import_service.settings, "PROJECT_GRAPH_EXTRACTOR", "orchestrator", raising=False
    )
    monkeypatch.setattr(
        import_service.settings,
        "PROJECT_GRAPH_ORCHESTRATOR_BASE_URL",
        None,
        raising=False,
    )
    provider = import_service.EmailImportEmbeddingProvider(
        api_key="key", base_url=None, embedding_model="embed"
    )

    result = await import_service._extract_project_semantics_for_import(
        [_segment("seg1", "text")], embedding_provider=provider
    )

    assert result is keyword_result
    llm_mock.assert_not_awaited()
