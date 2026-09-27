"""Tests for the LLM-grounded project extractor and its import selection."""

import types

import pytest
from unittest.mock import AsyncMock, Mock

import services.email_import_service as import_service
import services.project_graph.extractor_registry as extractor_registry
import services.project_graph.llm_extractor as llm_extractor
from services.project_graph import ProjectObjectType, ProjectSourceSegment


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


def test_project_llm_cannot_forge_literal_attachment_facts():
    segment = _segment("seg1", "Total: ₩1,200,000")
    payload = _payload(
        llm_extractor.ExtractedObjectPayload(
            object_type="attachment_fact",
            title="Total: ₩1,200,000",
            summary="Total: ₩1,200,000",
            source_segment_uids=["seg1"],
            confidence=0.9,
        )
    )
    assert llm_extractor._validated_objects(payload, {"seg1": segment}) == []


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
async def test_decision_typed_objects_are_grounded(monkeypatch):
    # The DECISION entity is admitted through the same enum-derived allow-list as
    # every other object type, so the LLM extractor grounds it with no bespoke
    # wiring — a decision point cited to a real segment survives; its evidence
    # edge is emitted like any other grounded object's.
    monkeypatch.setattr(
        llm_extractor,
        "_call_llm",
        AsyncMock(
            return_value=_payload(
                llm_extractor.ExtractedObjectPayload(
                    object_type="decision",
                    title="Adopt Stripe as the payment gateway",
                    summary="The steering committee approved Stripe.",
                    source_segment_uids=["seg1"],
                    confidence=0.85,
                )
            )
        ),
    )

    result = await llm_extractor.extract_project_semantics_llm(
        [_segment("seg1", "The steering committee approved Stripe as the gateway.")],
        api_key="key",
        model="gpt-test",
    )

    assert len(result.objects) == 1
    decision = result.objects[0]
    assert decision.object_type is ProjectObjectType.DECISION
    assert decision.object_type.value == "decision"
    assert decision.source_segment_uids == ("seg1",)
    assert result.edges[0].source_uid == "segment:seg1"
    assert result.edges[0].target_uid == decision.uid


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
    requirement = next(
        o for o in result.objects if o.object_type.value == "requirement"
    )
    relation_edges = [edge for edge in result.edges if edge.edge_type == "implements"]
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
        edge.edge_type == "segment_evidences_project_object" for edge in result.edges
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
        edge.edge_type == "segment_evidences_project_object" for edge in result.edges
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
        edge.edge_type == "segment_evidences_project_object" for edge in result.edges
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


def _two_grounded_decisions() -> list["llm_extractor.ExtractedObjectPayload"]:
    # A superseding decision (seg1) and the prior decision it replaces (seg2),
    # each grounded in its own cited segment so a supersedes relation between
    # them is evidenced by the union of both citations.
    return [
        _object(
            object_type="decision",
            title="Adopt Stripe as the payment gateway",
            summary="The committee now standardizes on Stripe.",
            segment_uids=["seg1"],
            confidence=0.86,
            local_key="dec-new",
        ),
        _object(
            object_type="decision",
            title="Adopt PayPal as the payment gateway",
            summary="The earlier decision had chosen PayPal.",
            segment_uids=["seg2"],
            confidence=0.71,
            local_key="dec-old",
        ),
    ]


def _two_decision_segments() -> list[ProjectSourceSegment]:
    return [
        _segment("seg1", "We now standardize on Stripe, replacing the prior choice."),
        _segment("seg2", "The earlier decision had chosen PayPal as the gateway."),
    ]


def test_decision_centric_relations_are_in_controlled_vocabulary():
    # The DECISION entity (#1058) and the decision read model (#1061) speak in
    # terms of a decision resolving an issue, a requirement being decided by a
    # decision, and a decision superseding a prior one. Those relation tokens
    # must live in the controlled vocabulary or the grounded LLM extractor would
    # silently drop every decision-centric relation at the vocabulary gate,
    # leaving decisions connectable only through the generic ``relates_to``.
    assert {"resolves", "decided_by", "supersedes"} <= (
        llm_extractor.ALLOWED_RELATION_TYPES
    )


@pytest.mark.asyncio
async def test_resolves_relation_links_decision_to_issue(monkeypatch):
    objects = [
        _object(
            object_type="decision",
            title="Waive the staging gate for the hotfix",
            summary="The lead approved shipping the hotfix without staging.",
            segment_uids=["seg1"],
            confidence=0.83,
            local_key="dec-a",
        ),
        _object(
            object_type="issue",
            title="Staging environment is down",
            summary="Staging outage blocks the release.",
            segment_uids=["seg2"],
            confidence=0.9,
            local_key="iss-b",
        ),
    ]
    monkeypatch.setattr(
        llm_extractor,
        "_call_llm",
        AsyncMock(
            return_value=llm_extractor.ExtractionPayload(
                objects=objects,
                relations=[
                    _relation(
                        source_local_key="dec-a",
                        target_local_key="iss-b",
                        relation_type="resolves",
                        confidence=0.68,
                    )
                ],
            )
        ),
    )

    result = await llm_extractor.extract_project_semantics_llm(
        [
            _segment("seg1", "The lead approved shipping the hotfix without staging."),
            _segment("seg2", "Staging outage blocks the release."),
        ],
        api_key="key",
        model="gpt-test",
    )

    decision = next(o for o in result.objects if o.object_type.value == "decision")
    issue = next(o for o in result.objects if o.object_type.value == "issue")
    resolves_edges = [edge for edge in result.edges if edge.edge_type == "resolves"]
    assert len(resolves_edges) == 1
    edge = resolves_edges[0]
    # Directionality is preserved: the decision resolves the issue, not vice
    # versa.
    assert edge.source_uid == decision.uid
    assert edge.target_uid == issue.uid
    # Grounded in the union of both endpoints' cited segments — never an uncited
    # reference.
    assert set(edge.source_segment_uids) == {"seg1", "seg2"}


@pytest.mark.asyncio
async def test_decided_by_relation_preserves_direction(monkeypatch):
    objects = [
        _object(
            object_type="requirement",
            title="Payments must use a single gateway",
            summary="One gateway is required for reconciliation.",
            segment_uids=["seg2"],
            confidence=0.88,
            local_key="req-a",
        ),
        _object(
            object_type="decision",
            title="Adopt Stripe as the payment gateway",
            summary="The committee standardizes on Stripe.",
            segment_uids=["seg1"],
            confidence=0.86,
            local_key="dec-b",
        ),
    ]
    monkeypatch.setattr(
        llm_extractor,
        "_call_llm",
        AsyncMock(
            return_value=llm_extractor.ExtractionPayload(
                objects=objects,
                relations=[
                    _relation(
                        source_local_key="req-a",
                        target_local_key="dec-b",
                        relation_type="decided_by",
                        confidence=0.7,
                    )
                ],
            )
        ),
    )

    result = await llm_extractor.extract_project_semantics_llm(
        [
            _segment("seg1", "The committee standardizes on Stripe."),
            _segment("seg2", "One gateway is required for reconciliation."),
        ],
        api_key="key",
        model="gpt-test",
    )

    requirement = next(
        o for o in result.objects if o.object_type.value == "requirement"
    )
    decision = next(o for o in result.objects if o.object_type.value == "decision")
    decided_by_edges = [edge for edge in result.edges if edge.edge_type == "decided_by"]
    assert len(decided_by_edges) == 1
    edge = decided_by_edges[0]
    assert edge.source_uid == requirement.uid
    assert edge.target_uid == decision.uid


@pytest.mark.asyncio
async def test_supersedes_relation_links_two_decisions(monkeypatch):
    monkeypatch.setattr(
        llm_extractor,
        "_call_llm",
        AsyncMock(
            return_value=llm_extractor.ExtractionPayload(
                objects=_two_grounded_decisions(),
                relations=[
                    _relation(
                        source_local_key="dec-new",
                        target_local_key="dec-old",
                        relation_type="supersedes",
                        confidence=0.74,
                    )
                ],
            )
        ),
    )

    result = await llm_extractor.extract_project_semantics_llm(
        _two_decision_segments(), api_key="key", model="gpt-test"
    )

    supersedes_edges = [edge for edge in result.edges if edge.edge_type == "supersedes"]
    assert len(supersedes_edges) == 1
    edge = supersedes_edges[0]
    assert set(edge.source_segment_uids) == {"seg1", "seg2"}


@pytest.mark.asyncio
async def test_decision_relation_synonym_outside_vocabulary_is_dropped(monkeypatch):
    # Disambiguation: "overrides" is a natural-language synonym of the controlled
    # ``supersedes`` token, but the vocabulary is a closed set of exact tokens,
    # not a fuzzy match. A relation labelled with the synonym is dropped so the
    # inter-object graph never accretes free-text edge labels.
    monkeypatch.setattr(
        llm_extractor,
        "_call_llm",
        AsyncMock(
            return_value=llm_extractor.ExtractionPayload(
                objects=_two_grounded_decisions(),
                relations=[
                    _relation(
                        source_local_key="dec-new",
                        target_local_key="dec-old",
                        relation_type="overrides",
                        confidence=0.9,
                    )
                ],
            )
        ),
    )

    result = await llm_extractor.extract_project_semantics_llm(
        _two_decision_segments(), api_key="key", model="gpt-test"
    )

    assert all(
        edge.edge_type == "segment_evidences_project_object" for edge in result.edges
    )


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
async def test_import_selection_routes_through_orchestrator_when_configured(
    monkeypatch,
):
    llm_mock = AsyncMock(return_value="orchestrator-result")
    _patch_extractor_cores(monkeypatch, llm=llm_mock, keyword=Mock())
    monkeypatch.setattr(
        import_service.settings,
        "PROJECT_GRAPH_EXTRACTOR",
        "orchestrator",
        raising=False,
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
    assert llm_mock.await_args.kwargs["base_url"] == "https://orchestrator.example/v1"


@pytest.mark.asyncio
async def test_import_selection_orchestrator_falls_back_when_unconfigured(monkeypatch):
    llm_mock = AsyncMock()
    keyword_result = types.SimpleNamespace(objects=(), edges=())
    _patch_extractor_cores(
        monkeypatch, llm=llm_mock, keyword=Mock(return_value=keyword_result)
    )
    monkeypatch.setattr(
        import_service.settings,
        "PROJECT_GRAPH_EXTRACTOR",
        "orchestrator",
        raising=False,
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


@pytest.mark.parametrize("invalid", [None, "body", "many", "excerpt", "value", "kind"])
def test_inferred_attachment_fact_requires_verbatim_evidence(invalid):
    from dataclasses import replace
    import hashlib

    segment = replace(
        _segment("seg1", "Acme will deliver on 2026-10-01."),
        source_kind="attachment",
        source_record_uid="attachment:91",
    )
    fields = dict(
        object_type="attachment_fact",
        title="Delivery commitment",
        summary="Acme will deliver on 2026-10-01.",
        source_segment_uids=["seg1"],
        confidence=0.8,
        fact_kind="commitment",
        fact_value="will deliver on 2026-10-01",
        evidence_excerpt="Acme will deliver on 2026-10-01.",
    )
    if invalid == "body":
        segment = replace(segment, source_kind="email_body")
    elif invalid == "many":
        fields["source_segment_uids"] = ["seg1", "seg1"]
    elif invalid == "excerpt":
        fields["evidence_excerpt"] = "Invented evidence"
    elif invalid == "value":
        fields["fact_value"] = "2027-01-01"
    elif invalid == "kind":
        fields["fact_kind"] = "approved"
    result = llm_extractor._validated_objects(
        _payload(llm_extractor.ExtractedObjectPayload(**fields)), {"seg1": segment}
    )
    if invalid:
        assert result == []
    else:
        assert len(result) == 1
        fact = result[0][1]
        assert fact.attributes["validation_status"] == "inferred_unverified"
        assert fact.attributes["value"] == fields["fact_value"]
        assert (
            fact.attributes["source_segment_hash"]
            == hashlib.sha256(
                segment.safe_text_content.encode("utf-8", errors="surrogatepass")
            ).hexdigest()
        )


@pytest.mark.asyncio
async def test_import_excludes_inferred_attachment_facts_and_incident_edges(
    monkeypatch,
):
    from services.project_graph.models import (
        ProjectSemanticEdge,
        ProjectSemanticExtractionResult,
        ProjectSemanticObject,
    )

    def obj(uid, kind):
        return ProjectSemanticObject(
            uid=uid,
            object_type=kind,
            title=uid,
            summary=uid,
            source_segment_uids=("seg1",),
            confidence=0.8,
            extractor_name="test",
            extractor_version="1",
        )

    project = ProjectSemanticExtractionResult(
        objects=(
            obj("fact", ProjectObjectType.ATTACHMENT_FACT),
            obj("requirement", ProjectObjectType.REQUIREMENT),
        ),
        edges=(
            ProjectSemanticEdge("segment:seg1", "fact", "evidence", 0.8, ("seg1",)),
            ProjectSemanticEdge("fact", "requirement", "relates_to", 0.8, ("seg1",)),
            ProjectSemanticEdge(
                "segment:seg1", "requirement", "evidence", 0.8, ("seg1",)
            ),
        ),
        extractor_name="test",
        extractor_version="1",
    )
    monkeypatch.setattr(
        import_service,
        "_extract_project_semantics_for_import",
        AsyncMock(return_value=project),
    )
    persist = AsyncMock()
    monkeypatch.setattr(import_service, "persist_project_graph_projection", persist)
    session = types.SimpleNamespace(commit=AsyncMock(), rollback=AsyncMock())
    await import_service._persist_project_graph_projection(
        session,
        [_segment("seg1", "text")],
        user_id="u",
        organization_id="o",
        include_attachment_facts=False,
    )
    extraction = persist.await_args.kwargs["extraction"]
    assert [item.uid for item in extraction.objects] == ["requirement"]
    assert [(edge.source_uid, edge.target_uid) for edge in extraction.edges] == [
        ("segment:seg1", "requirement")
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("fail_second", [False, True])
async def test_all_attachment_segments_are_processed_in_bounded_requests(
    monkeypatch, fail_second
):
    import json
    from dataclasses import replace

    segments = [
        replace(
            _segment(f"attachment-{i}", "Acme will deliver."), source_kind="attachment"
        )
        for i in range(llm_extractor._MAX_SEGMENTS_PER_REQUEST + 1)
    ]
    batches = []

    async def call(**kwargs):
        batch = json.loads(kwargs["segments_json"])["segments"]
        batches.append([segment["content_segment_uid"] for segment in batch])
        if fail_second and len(batches) == 2:
            raise RuntimeError("Synthetic provider failure")
        return _payload(
            llm_extractor.ExtractedObjectPayload(
                object_type="attachment_fact",
                title="Delivery",
                summary="Acme will deliver.",
                source_segment_uids=[batch[-1]["content_segment_uid"]],
                confidence=0.8,
                fact_kind="commitment",
                fact_value="will deliver",
                evidence_excerpt="Acme will deliver.",
            )
        )

    monkeypatch.setattr(llm_extractor, "_call_llm", call)
    if fail_second:
        with pytest.raises(RuntimeError, match="Synthetic provider failure"):
            await llm_extractor.extract_project_semantics_llm(
                segments, api_key="synthetic", model="synthetic"
            )
    else:
        result = await llm_extractor.extract_project_semantics_llm(
            segments, api_key="synthetic", model="synthetic"
        )
        assert len(result.objects) == 2
        assert result.objects[-1].source_segment_uids == (
            segments[-1].content_segment_uid,
        )
    assert [uid for batch in batches for uid in batch] == [
        segment.content_segment_uid for segment in segments
    ]
    assert all(
        len(batch) <= llm_extractor._MAX_SEGMENTS_PER_REQUEST for batch in batches
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("quote_start,padding", [(1900, 222), (2400, 222), (1900, 0)])
async def test_long_attachment_quotes_keep_original_citation_and_hash(
    monkeypatch, quote_start, padding
):
    import hashlib
    import json
    from dataclasses import replace

    quote = "Acme will deliver." + "z" * padding
    assert len(quote) <= 240
    text = "x" * quote_start + quote + "y" * 2000
    segment = replace(_segment("long-attachment", text), source_kind="attachment")
    requests = []

    async def call(**kwargs):
        entries = json.loads(kwargs["segments_json"])["segments"]
        requests.append(entries)
        return _payload(
            *[
                llm_extractor.ExtractedObjectPayload(
                    object_type="attachment_fact",
                    title="Delivery",
                    summary="Acme will deliver.",
                    source_segment_uids=[entry["content_segment_uid"]],
                    confidence=0.7 + len(requests) / 100,
                    fact_kind="commitment",
                    fact_value="will deliver",
                    evidence_excerpt=quote,
                )
                for entry in entries
                if quote in entry["text"]
            ]
        )

    monkeypatch.setattr(llm_extractor, "_call_llm", call)
    result = await llm_extractor.extract_project_semantics_llm(
        [segment], api_key="synthetic", model="synthetic"
    )
    assert len(result.objects) == len(result.edges) == 1
    fact = result.objects[0]
    assert result.edges[0].confidence == fact.confidence
    assert fact.source_segment_uids == (segment.content_segment_uid,)
    assert fact.attributes["evidence_excerpt"] == quote
    assert (
        fact.attributes["source_segment_hash"]
        == hashlib.sha256(text.encode()).hexdigest()
    )
    assert all(len(entry["text"]) <= 2000 for request in requests for entry in request)
    assert requests[-1][0]["text"].endswith("y" * 100)
