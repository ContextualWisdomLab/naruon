"""Unit tests for the project-level relation-summary aggregate.

The traceability read model denormalizes the persisted graph edges into typed
object-to-object :class:`ProjectTraceRelation` records (a feature *implements* a
requirement, an issue *blocks* a milestone). For a dense knowledge graph the raw
relation list is legible per-edge but not *at a glance*: a consumer that wants
the shape of the graph — how many relations of each type, which object types
those relations connect, and how much of the graph is grounded in citations —
would otherwise have to walk the whole list itself.

``_relation_summary`` folds the relation list into that shape as a pure function
(no database required). These tests pin the aggregation: grouping by relation
type, count-descending ordering with a deterministic type-ascending tie-break,
grounded counts driven by citation presence (grounding preserved, never
asserted), and distinct sorted endpoint object types.
"""

from __future__ import annotations

from services.project_graph.project_registration import (
    ProjectCitation,
    ProjectTraceRelation,
    ProjectTraceRelationEndpoint,
    _relation_summary,
)


def _citation(segment_uid: str) -> ProjectCitation:
    return ProjectCitation(
        content_segment_uid=segment_uid,
        source_kind="email_body",
        source_record_uid="<launch@example.com>",
        heading_path="Requirements",
        segment_path="/document[1]/paragraph[1]",
        ordinal_index=1,
        safe_text_excerpt="결제 화면은 카드 승인 실패 시 재시도 안내를 보여준다",
    )


def _endpoint(object_uid: str, object_type: str) -> ProjectTraceRelationEndpoint:
    return ProjectTraceRelationEndpoint(
        object_uid=object_uid,
        object_type=object_type,
        title=f"{object_type}: {object_uid}",
    )


def _relation(
    *,
    relation_uid: str,
    relation_type: str,
    source_uid: str,
    source_type: str,
    target_uid: str,
    target_type: str,
    grounded: bool = True,
    confidence: float = 0.8,
) -> ProjectTraceRelation:
    citations = (_citation("seg-1"),) if grounded else ()
    segment_uids = ("seg-1",) if grounded else ()
    return ProjectTraceRelation(
        relation_uid=relation_uid,
        relation_type=relation_type,
        source=_endpoint(source_uid, source_type),
        target=_endpoint(target_uid, target_type),
        confidence=confidence,
        source_segment_uids=segment_uids,
        citation_bundle=citations,
    )


def test_relation_summary_groups_by_type_ordered_by_count_desc():
    relations = (
        _relation(
            relation_uid="e1",
            relation_type="implements",
            source_uid="feature:a",
            source_type="feature",
            target_uid="requirement:b",
            target_type="requirement",
        ),
        _relation(
            relation_uid="e2",
            relation_type="implements",
            source_uid="feature:c",
            source_type="feature",
            target_uid="requirement:d",
            target_type="requirement",
        ),
        _relation(
            relation_uid="e3",
            relation_type="blocks",
            source_uid="issue:e",
            source_type="issue",
            target_uid="milestone:f",
            target_type="milestone",
        ),
    )

    summary = _relation_summary("project_candidate:x", relations)

    assert summary.project_uid == "project_candidate:x"
    assert summary.relation_count == 3
    assert summary.grounded_relation_count == 3
    # Ordered by relation_count descending: implements(2) before blocks(1).
    assert [item.relation_type for item in summary.relation_types] == [
        "implements",
        "blocks",
    ]
    implements = summary.relation_types[0]
    assert implements.relation_count == 2
    assert implements.grounded_relation_count == 2


def test_relation_summary_counts_grounded_by_citation_presence():
    relations = (
        _relation(
            relation_uid="e1",
            relation_type="implements",
            source_uid="feature:a",
            source_type="feature",
            target_uid="requirement:b",
            target_type="requirement",
            grounded=True,
        ),
        _relation(
            relation_uid="e2",
            relation_type="implements",
            source_uid="feature:c",
            source_type="feature",
            target_uid="requirement:d",
            target_type="requirement",
            grounded=False,
        ),
    )

    summary = _relation_summary("project_candidate:x", relations)

    # A relation is grounded only when it carries a citation bundle; the stale
    # relation is counted in relation_count but not grounded_relation_count.
    assert summary.relation_count == 2
    assert summary.grounded_relation_count == 1
    implements = summary.relation_types[0]
    assert implements.relation_count == 2
    assert implements.grounded_relation_count == 1


def test_relation_summary_collects_distinct_sorted_endpoint_types():
    relations = (
        _relation(
            relation_uid="e1",
            relation_type="relates_to",
            source_uid="feature:a",
            source_type="feature",
            target_uid="requirement:b",
            target_type="requirement",
        ),
        _relation(
            relation_uid="e2",
            relation_type="relates_to",
            source_uid="issue:c",
            source_type="issue",
            target_uid="requirement:d",
            target_type="requirement",
        ),
        _relation(
            relation_uid="e3",
            relation_type="relates_to",
            source_uid="feature:e",
            source_type="feature",
            target_uid="milestone:f",
            target_type="milestone",
        ),
    )

    summary = _relation_summary("project_candidate:x", relations)

    relates_to = summary.relation_types[0]
    # Distinct and sorted so the shape is deterministic across runs.
    assert relates_to.source_object_types == ("feature", "issue")
    assert relates_to.target_object_types == ("milestone", "requirement")


def test_relation_summary_ties_broken_by_relation_type_ascending():
    relations = (
        _relation(
            relation_uid="e1",
            relation_type="refines",
            source_uid="requirement:a",
            source_type="requirement",
            target_uid="requirement:b",
            target_type="requirement",
        ),
        _relation(
            relation_uid="e2",
            relation_type="blocks",
            source_uid="issue:c",
            source_type="issue",
            target_uid="milestone:d",
            target_type="milestone",
        ),
    )

    summary = _relation_summary("project_candidate:x", relations)

    # Equal counts (1 each): deterministic ascending relation_type tie-break.
    assert [item.relation_type for item in summary.relation_types] == [
        "blocks",
        "refines",
    ]


def test_relation_summary_empty_when_no_relations():
    summary = _relation_summary("project_candidate:x", ())

    assert summary.project_uid == "project_candidate:x"
    assert summary.relation_count == 0
    assert summary.grounded_relation_count == 0
    assert summary.relation_types == ()
