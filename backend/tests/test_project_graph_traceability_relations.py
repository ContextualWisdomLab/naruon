"""Unit tests for typed object-to-object relation projection in traceability.

The LLM project-graph extractor persists two kinds of edges into
``project_graph_edges``: segment-evidence edges (``segment:<uid>`` source) and
typed object-to-object relations (a feature *implements* a requirement, an issue
*blocks* a milestone). ``_trace_relations`` denormalizes only the latter into a
read model that names both endpoints, so a traceability view can render *why*
two objects connect without re-joining edges against objects. These tests pin
that projection as a pure function (no database required).
"""

from __future__ import annotations

from services.project_graph.project_registration import (
    ProjectCitation,
    ProjectTraceEdge,
    ProjectTraceObject,
    _trace_relations,
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


def _trace_object(object_uid: str, object_type: str, title: str) -> ProjectTraceObject:
    return ProjectTraceObject(
        object_uid=object_uid,
        object_type=object_type,
        title=title,
        summary=f"{title} summary",
        status_code="candidate",
        confidence=0.8,
        source_segment_uids=("seg-1",),
        citation_bundle=(_citation("seg-1"),),
        attributes={},
    )


def _edge(
    *,
    edge_uid: str,
    source_uid: str,
    target_uid: str,
    edge_type: str,
    segment_uids: tuple[str, ...] = ("seg-1",),
    confidence: float = 0.77,
) -> ProjectTraceEdge:
    return ProjectTraceEdge(
        edge_uid=edge_uid,
        source_uid=source_uid,
        target_uid=target_uid,
        edge_type=edge_type,
        confidence=confidence,
        source_segment_uids=segment_uids,
        citation_bundle=tuple(_citation(uid) for uid in segment_uids),
    )


def test_trace_relations_resolves_object_to_object_endpoints():
    feature = _trace_object("feature:aaa", "feature", "Feature: checkout retry")
    requirement = _trace_object(
        "requirement:bbb", "requirement", "Requirement: retry guidance"
    )
    edge = _edge(
        edge_uid="project_edge:rel1",
        source_uid=feature.object_uid,
        target_uid=requirement.object_uid,
        edge_type="implements",
        confidence=0.91,
    )

    relations = _trace_relations((edge,), (feature, requirement))

    assert len(relations) == 1
    relation = relations[0]
    assert relation.relation_uid == "project_edge:rel1"
    assert relation.relation_type == "implements"
    assert relation.confidence == 0.91
    assert relation.source.object_uid == feature.object_uid
    assert relation.source.object_type == "feature"
    assert relation.source.title == "Feature: checkout retry"
    assert relation.target.object_uid == requirement.object_uid
    assert relation.target.object_type == "requirement"
    # Citations are carried through so the relation is grounded, not asserted.
    assert relation.source_segment_uids == ("seg-1",)
    assert [c.content_segment_uid for c in relation.citation_bundle] == ["seg-1"]


def test_trace_relations_excludes_segment_evidence_edges():
    requirement = _trace_object(
        "requirement:bbb", "requirement", "Requirement: retry guidance"
    )
    evidence_edge = _edge(
        edge_uid="project_edge:ev1",
        source_uid="segment:seg-1",
        target_uid=requirement.object_uid,
        edge_type="segment_evidences_project_object",
    )

    relations = _trace_relations((evidence_edge,), (requirement,))

    # A segment-evidence edge is not an object-to-object relation: its source
    # never resolves to a project object, so it must not surface as a relation.
    assert relations == ()


def test_trace_relations_excludes_edges_with_unresolved_endpoint():
    issue = _trace_object("issue:ccc", "issue", "Issue: approval blocker")
    dangling_edge = _edge(
        edge_uid="project_edge:dangling",
        source_uid=issue.object_uid,
        target_uid="milestone:not-in-group",
        edge_type="blocks",
    )

    relations = _trace_relations((dangling_edge,), (issue,))

    assert relations == ()


def test_trace_relations_preserves_edge_order_and_multiplicity():
    feature = _trace_object("feature:aaa", "feature", "Feature: checkout retry")
    requirement = _trace_object(
        "requirement:bbb", "requirement", "Requirement: retry guidance"
    )
    milestone = _trace_object("milestone:ddd", "milestone", "Milestone: 2026-08-01")
    edges = (
        _edge(
            edge_uid="project_edge:1",
            source_uid=feature.object_uid,
            target_uid=requirement.object_uid,
            edge_type="implements",
        ),
        _edge(
            edge_uid="project_edge:evidence",
            source_uid="segment:seg-1",
            target_uid=feature.object_uid,
            edge_type="segment_evidences_project_object",
        ),
        _edge(
            edge_uid="project_edge:2",
            source_uid=requirement.object_uid,
            target_uid=milestone.object_uid,
            edge_type="refines",
        ),
    )

    relations = _trace_relations(edges, (feature, requirement, milestone))

    assert [relation.relation_uid for relation in relations] == [
        "project_edge:1",
        "project_edge:2",
    ]
    assert [relation.relation_type for relation in relations] == [
        "implements",
        "refines",
    ]
