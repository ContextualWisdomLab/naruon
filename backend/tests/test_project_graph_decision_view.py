"""Unit tests for the decision-focused slice of the project graph read model.

Since #1058 the project-graph extractor emits a typed ``decision`` object (a
resolved approval / chosen option) alongside requirements, features, issues, and
milestones, grounded in citations and wired through the traceability, evidence,
and relation-summary read models. Those read models expose *every* object type;
a consumer that only wants the decision points of a project — what was decided,
how confident the extraction is, and which requirements/features/issues each
decision connects to — would otherwise have to fetch the whole traceability
graph and filter it itself.

``_decision_view`` folds the loaded objects and projected relations into that
focused slice as a pure function (no database required). These tests pin the
projection: only ``decision``-typed objects surface, each carries its own
citation bundle (grounding preserved, never asserted) and its incident
relations in both directions, ``grounded_decision_count`` is driven by citation
presence, and object load order is preserved deterministically.
"""

from __future__ import annotations

from services.project_graph.project_registration import (
    DECISION_OBJECT_TYPE,
    ProjectCitation,
    ProjectTraceEdge,
    ProjectTraceObject,
    _decision_view,
    _trace_relations,
)


def _citation(segment_uid: str) -> ProjectCitation:
    return ProjectCitation(
        content_segment_uid=segment_uid,
        source_kind="email_body",
        source_record_uid="<launch@example.com>",
        heading_path="Decisions",
        segment_path="/document[1]/paragraph[1]",
        ordinal_index=1,
        safe_text_excerpt="결제 재시도 안내 도입을 최종 확정했습니다",
    )


def _trace_object(
    object_uid: str,
    object_type: str,
    title: str,
    *,
    grounded: bool = True,
    status_code: str = "candidate",
    confidence: float = 0.8,
) -> ProjectTraceObject:
    segment_uids = ("seg-1",) if grounded else ()
    citations = (_citation("seg-1"),) if grounded else ()
    return ProjectTraceObject(
        object_uid=object_uid,
        object_type=object_type,
        title=title,
        summary=f"{title} summary",
        status_code=status_code,
        confidence=confidence,
        source_segment_uids=segment_uids,
        citation_bundle=citations,
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


def test_decision_object_type_matches_canonical_enum():
    # The filter keys off the canonical ProjectObjectType.DECISION value so the
    # read model never drifts from the extractor's typed entity.
    assert DECISION_OBJECT_TYPE == "decision"


def test_decision_view_selects_only_decision_objects():
    decision = _trace_object("decision:aaa", "decision", "Decision: adopt retry")
    requirement = _trace_object(
        "requirement:bbb", "requirement", "Requirement: retry guidance"
    )
    feature = _trace_object("feature:ccc", "feature", "Feature: checkout retry")

    view = _decision_view(
        "project_candidate:x",
        (decision, requirement, feature),
        (),
    )

    assert view.project_uid == "project_candidate:x"
    assert view.decision_count == 1
    assert view.grounded_decision_count == 1
    assert [record.object_uid for record in view.decisions] == ["decision:aaa"]
    surfaced = view.decisions[0]
    assert surfaced.title == "Decision: adopt retry"
    assert surfaced.status_code == "candidate"
    assert surfaced.confidence == 0.8
    # Grounded, not asserted: the decision carries its own citation bundle.
    assert [c.content_segment_uid for c in surfaced.citation_bundle] == ["seg-1"]


def test_decision_view_inlines_incident_relations_in_both_directions():
    decision = _trace_object("decision:aaa", "decision", "Decision: adopt retry")
    requirement = _trace_object(
        "requirement:bbb", "requirement", "Requirement: retry guidance"
    )
    issue = _trace_object("issue:ccc", "issue", "Issue: approval blocker")
    edges = (
        # Outbound: the decision resolves an issue.
        _edge(
            edge_uid="project_edge:1",
            source_uid="decision:aaa",
            target_uid="issue:ccc",
            edge_type="resolves",
        ),
        # Inbound: a requirement is decided by the decision.
        _edge(
            edge_uid="project_edge:2",
            source_uid="requirement:bbb",
            target_uid="decision:aaa",
            edge_type="decided_by",
        ),
    )
    relations = _trace_relations(edges, (decision, requirement, issue))

    view = _decision_view(
        "project_candidate:x",
        (decision, requirement, issue),
        relations,
    )

    assert view.decision_count == 1
    surfaced = view.decisions[0]
    # Both the outbound (source) and inbound (target) relations surface, in the
    # projected edge order, each with its endpoints resolved and grounded.
    assert [relation.relation_uid for relation in surfaced.relations] == [
        "project_edge:1",
        "project_edge:2",
    ]
    assert [relation.relation_type for relation in surfaced.relations] == [
        "resolves",
        "decided_by",
    ]
    assert surfaced.relations[0].target.object_type == "issue"
    assert surfaced.relations[1].source.object_type == "requirement"
    assert surfaced.relations[0].citation_bundle


def test_decision_view_counts_grounded_by_citation_presence():
    grounded = _trace_object("decision:aaa", "decision", "Decision: adopt retry")
    ungrounded = _trace_object(
        "decision:bbb", "decision", "Decision: unresolved", grounded=False
    )

    view = _decision_view(
        "project_candidate:x",
        (grounded, ungrounded),
        (),
    )

    # A decision is grounded only when it carries a citation bundle; the
    # ungrounded decision is counted in decision_count but not grounded_count.
    assert view.decision_count == 2
    assert view.grounded_decision_count == 1


def test_decision_view_preserves_object_load_order():
    first = _trace_object("decision:zzz", "decision", "Decision: last uid")
    second = _trace_object("decision:aaa", "decision", "Decision: first uid")

    # Objects are passed in load order (upstream: updated_at/confidence/uid); the
    # view must not re-sort them, so the ordering stays deterministic upstream.
    view = _decision_view("project_candidate:x", (first, second), ())

    assert [record.object_uid for record in view.decisions] == [
        "decision:zzz",
        "decision:aaa",
    ]


def test_decision_view_empty_when_no_decisions():
    requirement = _trace_object(
        "requirement:bbb", "requirement", "Requirement: retry guidance"
    )

    view = _decision_view("project_candidate:x", (requirement,), ())

    assert view.project_uid == "project_candidate:x"
    assert view.decision_count == 0
    assert view.grounded_decision_count == 0
    assert view.decisions == ()
