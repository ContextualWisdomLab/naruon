from __future__ import annotations

import datetime
import hashlib
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from db.models import (
    ContentSegmentRecord,
    ProjectGraphCorrectionRecord,
    ProjectGraphEdgeRecord,
    ProjectGraphObjectRecord,
)

from .models import ProjectObjectType
from .projection import apply_project_graph_correction

# Canonical value of the typed decision-point entity (added in #1058). The
# decision-focused read model keys off this so it never drifts from the
# extractor's ProjectObjectType.DECISION member.
DECISION_OBJECT_TYPE: str = ProjectObjectType.DECISION.value

PROJECT_OBJECT_SCORE_WEIGHTS: Mapping[str, float] = {
    "project_candidate": 0.26,
    "requirement": 0.18,
    "feature": 0.1,
    "issue": 0.1,
    "milestone": 0.12,
    "wbs_item": 0.1,
    "deliverable": 0.12,
    "participant": 0.08,
    "data_requirement": 0.1,
    "erd_candidate": 0.08,
    "infra_requirement": 0.1,
    "report_delta": 0.06,
    "wiki_projection": 0.06,
}


class ProjectGraphNotFoundError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ProjectGraphQueryScope:
    user_id: str
    organization_id: str | None
    workspace_id: str
    can_read_organization_scope: bool = False


@dataclass(frozen=True, slots=True)
class ProjectCitation:
    content_segment_uid: str
    source_kind: str
    source_record_uid: str
    heading_path: str | None
    segment_path: str | None
    ordinal_index: int
    safe_text_excerpt: str


@dataclass(frozen=True, slots=True)
class ProjectCandidateSummary:
    candidate_uid: str
    project_uid: str
    title: str
    status_code: str
    score: float
    object_count: int
    requirement_count: int
    issue_count: int
    milestone_count: int
    deliverable_count: int
    participant_count: int
    source_segment_count: int
    representative_object_uids: tuple[str, ...]
    citation_bundle: tuple[ProjectCitation, ...]
    updated_at: datetime.datetime | None


@dataclass(frozen=True, slots=True)
class ProjectTraceObject:
    object_uid: str
    object_type: str
    title: str
    summary: str
    status_code: str
    confidence: float
    source_segment_uids: tuple[str, ...]
    citation_bundle: tuple[ProjectCitation, ...]
    attributes: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class ProjectTraceEdge:
    edge_uid: str
    source_uid: str
    target_uid: str
    edge_type: str
    confidence: float
    source_segment_uids: tuple[str, ...]
    citation_bundle: tuple[ProjectCitation, ...]


@dataclass(frozen=True, slots=True)
class ProjectTraceRelationEndpoint:
    object_uid: str
    object_type: str
    title: str


@dataclass(frozen=True, slots=True)
class ProjectTraceRelation:
    """A typed object-to-object relation with both endpoints resolved.

    Derived from the persisted graph edges, but — unlike a raw
    :class:`ProjectTraceEdge` — a relation only exists when BOTH endpoints
    resolve to project objects in the traceability group, and it inlines each
    endpoint's ``object_type`` and ``title``. That lets a consumer render *why*
    two objects connect (a feature *implements* a requirement, an issue
    *blocks* a milestone) with citations, without re-joining edges to objects.
    Segment-evidence edges (``segment:<uid>`` sources) are structurally excluded
    because their source never resolves to an object.
    """

    relation_uid: str
    relation_type: str
    source: ProjectTraceRelationEndpoint
    target: ProjectTraceRelationEndpoint
    confidence: float
    source_segment_uids: tuple[str, ...]
    citation_bundle: tuple[ProjectCitation, ...]


@dataclass(frozen=True, slots=True)
class ProjectRelationTypeSummary:
    """Aggregate shape of one relation type across a project's graph.

    Folds every :class:`ProjectTraceRelation` of a single ``relation_type`` into
    counts plus the distinct, sorted object types the relation connects on each
    side. ``grounded_relation_count`` counts only relations that carry a
    citation bundle, so the aggregate never claims grounding it does not have.
    """

    relation_type: str
    relation_count: int
    grounded_relation_count: int
    source_object_types: tuple[str, ...]
    target_object_types: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ProjectRelationSummary:
    """A project's typed-relation distribution — the KG's shape at a glance.

    Derived purely from the same object-to-object relations exposed by
    :class:`ProjectTraceability`, but folded into per-type counts so a consumer
    can render *how* dense and *how* grounded a project's knowledge graph is
    without fetching and walking every relation and its citations. ``relation_types``
    is ordered by ``relation_count`` descending with a ``relation_type``-ascending
    tie-break, so the ordering is deterministic across runs.
    """

    project_uid: str
    relation_count: int
    grounded_relation_count: int
    relation_types: tuple[ProjectRelationTypeSummary, ...]


@dataclass(frozen=True, slots=True)
class ProjectTraceability:
    project_uid: str
    candidate: ProjectCandidateSummary
    objects: tuple[ProjectTraceObject, ...]
    edges: tuple[ProjectTraceEdge, ...]
    relations: tuple[ProjectTraceRelation, ...]


@dataclass(frozen=True, slots=True)
class ProjectEvidence:
    project_uid: str
    object_uid: str
    object_type: str
    title: str
    summary: str
    status_code: str
    confidence: float
    citation_bundle: tuple[ProjectCitation, ...]
    # Typed object-to-object relations incident to this object (this object is
    # either endpoint). Denormalized like :class:`ProjectTraceability.relations`
    # so an evidence drill-down can render *why* this object connects to others
    # — grounded in citations — without re-fetching and re-joining the whole
    # traceability graph. Defaults to empty for backward-compatible construction.
    relations: tuple[ProjectTraceRelation, ...] = ()


@dataclass(frozen=True, slots=True)
class ProjectDecisionRecord:
    """One ``decision``-typed knowledge-graph object with grounding and relations.

    A decision point (a resolved approval / chosen option) extracted into the
    graph as a ``decision`` object since #1058. It carries its own citation
    bundle (grounded, never asserted) and the typed object-to-object relations
    incident to it — inbound and outbound — so a consumer can render *what was
    decided* and *why it connects* to the requirements, features, or issues it
    resolves without re-walking the whole traceability graph.
    """

    object_uid: str
    title: str
    summary: str
    status_code: str
    confidence: float
    citation_bundle: tuple[ProjectCitation, ...]
    relations: tuple[ProjectTraceRelation, ...]


@dataclass(frozen=True, slots=True)
class ProjectDecisionView:
    """The ``decision``-typed slice of a project's knowledge graph.

    Folds a project's decision objects into a focused, grounded view: every
    decision with its citations and incident relations, plus
    ``grounded_decision_count`` so the aggregate never claims grounding it does
    not have. Derived from the same objects and relations exposed by
    :class:`ProjectTraceability`, filtered to decisions — read-only and
    backward compatible. ``decisions`` preserves the upstream object load order,
    so the result is deterministic across runs.
    """

    project_uid: str
    decision_count: int
    grounded_decision_count: int
    decisions: tuple[ProjectDecisionRecord, ...]


@dataclass(frozen=True, slots=True)
class ProjectCorrection:
    correction_uid: str
    object_uid: str
    correction_action: str
    before_json: Mapping[str, Any]
    after_json: Mapping[str, Any]
    rationale: str | None
    actor_user_id: str
    source_segment_uids: tuple[str, ...]
    created_at: datetime.datetime


@dataclass(slots=True)
class _CandidateGroup:
    project_uid: str
    records: tuple[ProjectGraphObjectRecord, ...]


async def list_project_candidates(
    session: AsyncSession,
    *,
    scope: ProjectGraphQueryScope,
    limit: int = 25,
) -> tuple[ProjectCandidateSummary, ...]:
    records = await _load_project_objects(session, scope=scope)
    groups = _candidate_groups(records, scope=scope)
    segment_map = await _load_citation_map(
        session,
        _record_segment_uids(records),
        scope=scope,
    )
    candidates = [
        _candidate_summary(group, segment_map=segment_map) for group in groups
    ]
    candidates.sort(key=lambda candidate: (-candidate.score, candidate.title))
    return tuple(candidates[:limit])


async def confirm_project_candidate(
    session: AsyncSession,
    *,
    scope: ProjectGraphQueryScope,
    candidate_uid: str,
    actor_user_id: str,
) -> ProjectCandidateSummary:
    group = await _get_candidate_group(
        session,
        scope=scope,
        project_uid=candidate_uid,
    )
    confirmed_at = _utcnow().isoformat()
    for record in group.records:
        record.status_code = "confirmed"
        attributes = dict(record.attributes_json or {})
        attributes["project_registration"] = {
            "candidate_uid": candidate_uid,
            "confirmed_by": actor_user_id,
            "confirmed_at": confirmed_at,
        }
        record.attributes_json = attributes
        record.updated_at = _utcnow()
    await session.flush()
    segment_map = await _load_citation_map(
        session,
        _record_segment_uids(group.records),
        scope=scope,
    )
    return _candidate_summary(group, segment_map=segment_map)


async def get_project_traceability(
    session: AsyncSession,
    *,
    scope: ProjectGraphQueryScope,
    project_uid: str,
) -> ProjectTraceability:
    group = await _get_candidate_group(
        session,
        scope=scope,
        project_uid=project_uid,
    )
    object_uids = tuple(record.object_uid for record in group.records)
    edges = await _load_project_edges(session, scope=scope, object_uids=object_uids)
    source_uids = _record_segment_uids(group.records) + _edge_segment_uids(edges)
    segment_map = await _load_citation_map(session, source_uids, scope=scope)
    candidate = _candidate_summary(group, segment_map=segment_map)
    trace_objects = tuple(_trace_object(record, segment_map) for record in group.records)
    trace_edges = tuple(_trace_edge(edge, segment_map) for edge in edges)
    return ProjectTraceability(
        project_uid=group.project_uid,
        candidate=candidate,
        objects=trace_objects,
        edges=trace_edges,
        relations=_trace_relations(trace_edges, trace_objects),
    )


async def get_project_relation_summary(
    session: AsyncSession,
    *,
    scope: ProjectGraphQueryScope,
    project_uid: str,
) -> ProjectRelationSummary:
    """Aggregate a project's typed object-to-object relations by relation type.

    Loads the same graph as :func:`get_project_traceability` but only resolves
    the citations reachable from edges (the objects' own citation bundles are
    not needed for the summary), then folds the projected relations into a
    per-type distribution via :func:`_relation_summary`. Backward compatible and
    read-only: it introduces no new persistence and reuses the settled relation
    projection.
    """
    group = await _get_candidate_group(
        session,
        scope=scope,
        project_uid=project_uid,
    )
    object_uids = tuple(record.object_uid for record in group.records)
    edges = await _load_project_edges(session, scope=scope, object_uids=object_uids)
    segment_map = await _load_citation_map(
        session,
        _edge_segment_uids(edges),
        scope=scope,
    )
    trace_objects = tuple(_trace_object(record, segment_map) for record in group.records)
    trace_edges = tuple(_trace_edge(edge, segment_map) for edge in edges)
    relations = _trace_relations(trace_edges, trace_objects)
    return _relation_summary(group.project_uid, relations)


async def get_project_decisions(
    session: AsyncSession,
    *,
    scope: ProjectGraphQueryScope,
    project_uid: str,
) -> ProjectDecisionView:
    """Return the ``decision``-typed slice of a project's knowledge graph.

    Loads the same objects and edges as :func:`get_project_traceability`,
    projects the typed object-to-object relations, then folds only the
    ``decision``-typed objects into a :class:`ProjectDecisionView` via
    :func:`_decision_view`. Read-only and backward compatible: it adds no
    persistence and reuses the settled object, relation, and citation
    projections, so every surfaced decision stays grounded in its citations.
    """
    group = await _get_candidate_group(
        session,
        scope=scope,
        project_uid=project_uid,
    )
    object_uids = tuple(record.object_uid for record in group.records)
    edges = await _load_project_edges(session, scope=scope, object_uids=object_uids)
    segment_map = await _load_citation_map(
        session,
        _record_segment_uids(group.records) + _edge_segment_uids(edges),
        scope=scope,
    )
    trace_objects = tuple(_trace_object(record, segment_map) for record in group.records)
    trace_edges = tuple(_trace_edge(edge, segment_map) for edge in edges)
    relations = _trace_relations(trace_edges, trace_objects)
    return _decision_view(group.project_uid, trace_objects, relations)


async def get_project_evidence(
    session: AsyncSession,
    *,
    scope: ProjectGraphQueryScope,
    project_uid: str,
    object_uid: str,
) -> ProjectEvidence:
    group = await _get_candidate_group(
        session,
        scope=scope,
        project_uid=project_uid,
    )
    record = next(
        (candidate for candidate in group.records if candidate.object_uid == object_uid),
        None,
    )
    if record is None:
        raise ProjectGraphNotFoundError("Project graph object not found")
    object_uids = tuple(candidate.object_uid for candidate in group.records)
    edges = await _load_project_edges(session, scope=scope, object_uids=object_uids)
    segment_map = await _load_citation_map(
        session,
        tuple(record.source_segment_uids) + _edge_segment_uids(edges),
        scope=scope,
    )
    citations = _citation_bundle(record.source_segment_uids, segment_map)
    if len(citations) != len(record.source_segment_uids):
        raise ProjectGraphNotFoundError("Project graph source evidence not found")
    trace_objects = tuple(_trace_object(item, segment_map) for item in group.records)
    trace_edges = tuple(_trace_edge(edge, segment_map) for edge in edges)
    relations = _incident_relations(
        _trace_relations(trace_edges, trace_objects),
        record.object_uid,
    )
    return ProjectEvidence(
        project_uid=group.project_uid,
        object_uid=record.object_uid,
        object_type=record.object_type,
        title=record.title,
        summary=record.summary,
        status_code=record.status_code,
        confidence=record.confidence,
        citation_bundle=citations,
        relations=relations,
    )


async def apply_project_correction(
    session: AsyncSession,
    *,
    scope: ProjectGraphQueryScope,
    project_uid: str,
    object_uid: str,
    actor_user_id: str,
    correction_action: str,
    after_json: Mapping[str, Any],
    rationale: str | None = None,
    source_segment_uids: tuple[str, ...] | None = None,
) -> ProjectCorrection:
    group = await _get_candidate_group(
        session,
        scope=scope,
        project_uid=project_uid,
    )
    record = next(
        (candidate for candidate in group.records if candidate.object_uid == object_uid),
        None,
    )
    if record is None:
        raise ProjectGraphNotFoundError("Project graph object not found")
    correction = await apply_project_graph_correction(
        session,
        object_uid=record.object_uid,
        user_id=record.user_id,
        organization_id=record.organization_id,
        workspace_id=record.workspace_id,
        actor_user_id=actor_user_id,
        correction_action=correction_action,
        after_json=after_json,
        rationale=rationale,
        source_segment_uids=source_segment_uids,
    )
    return _correction_response(correction, record.object_uid)


async def _get_candidate_group(
    session: AsyncSession,
    *,
    scope: ProjectGraphQueryScope,
    project_uid: str,
) -> _CandidateGroup:
    records = await _load_project_objects(session, scope=scope)
    for group in _candidate_groups(records, scope=scope):
        if group.project_uid == project_uid:
            return group
    raise ProjectGraphNotFoundError("Project candidate not found")


async def _load_project_objects(
    session: AsyncSession,
    *,
    scope: ProjectGraphQueryScope,
) -> tuple[ProjectGraphObjectRecord, ...]:
    statement = (
        select(ProjectGraphObjectRecord)
        .options(selectinload(ProjectGraphObjectRecord.email))
        .where(ProjectGraphObjectRecord.workspace_id == scope.workspace_id)
    )
    statement = _apply_scope_filter(statement, ProjectGraphObjectRecord, scope)
    statement = statement.order_by(
        ProjectGraphObjectRecord.updated_at.desc(),
        ProjectGraphObjectRecord.confidence.desc(),
        ProjectGraphObjectRecord.object_uid.asc(),
    )
    result = await session.execute(statement)
    return tuple(result.scalars().all())


async def _load_project_edges(
    session: AsyncSession,
    *,
    scope: ProjectGraphQueryScope,
    object_uids: tuple[str, ...],
) -> tuple[ProjectGraphEdgeRecord, ...]:
    if not object_uids:
        return ()
    statement = (
        select(ProjectGraphEdgeRecord)
        .where(ProjectGraphEdgeRecord.workspace_id == scope.workspace_id)
        .where(
            or_(
                ProjectGraphEdgeRecord.source_uid.in_(object_uids),
                ProjectGraphEdgeRecord.target_uid.in_(object_uids),
            )
        )
    )
    statement = _apply_scope_filter(statement, ProjectGraphEdgeRecord, scope)
    statement = statement.order_by(ProjectGraphEdgeRecord.edge_type.asc())
    result = await session.execute(statement)
    return tuple(result.scalars().all())


async def _load_citation_map(
    session: AsyncSession,
    source_segment_uids: tuple[str, ...],
    *,
    scope: ProjectGraphQueryScope,
) -> dict[str, ProjectCitation]:
    if not source_segment_uids:
        return {}
    result = await session.execute(
        select(ContentSegmentRecord)
        .options(selectinload(ContentSegmentRecord.email))
        .where(ContentSegmentRecord.content_segment_uid.in_(source_segment_uids))
        .order_by(ContentSegmentRecord.ordinal_index.asc())
    )
    return {
        segment.content_segment_uid: ProjectCitation(
            content_segment_uid=segment.content_segment_uid,
            source_kind=segment.source_kind,
            source_record_uid=segment.source_record_uid,
            heading_path=segment.heading_path,
            segment_path=segment.segment_path,
            ordinal_index=segment.ordinal_index,
            safe_text_excerpt=_safe_excerpt(segment.safe_text_content),
        )
        for segment in result.scalars().all()
        if _segment_matches_scope(segment, scope)
    }


def _apply_scope_filter(statement, model, scope: ProjectGraphQueryScope):
    if scope.can_read_organization_scope and scope.organization_id is not None:
        return statement.where(model.organization_id == scope.organization_id)
    organization_filter = (
        model.organization_id == scope.organization_id
        if scope.organization_id is not None
        else model.organization_id.is_(None)
    )
    return statement.where(model.user_id == scope.user_id, organization_filter)


def _segment_matches_scope(
    segment: ContentSegmentRecord,
    scope: ProjectGraphQueryScope,
) -> bool:
    email = segment.email
    if email is None:
        return False
    expected_workspace_id = (
        f"workspace-{scope.organization_id}"
        if scope.organization_id
        else f"workspace-{scope.user_id}"
    )
    if scope.workspace_id != expected_workspace_id:
        return False
    if email.organization_id != scope.organization_id:
        return False
    if scope.can_read_organization_scope and scope.organization_id is not None:
        return True
    return email.user_id == scope.user_id


def _candidate_groups(
    records: Iterable[ProjectGraphObjectRecord],
    *,
    scope: ProjectGraphQueryScope,
) -> tuple[_CandidateGroup, ...]:
    records_by_email: dict[int, list[ProjectGraphObjectRecord]] = defaultdict(list)
    for record in records:
        records_by_email[record.email_id].append(record)

    groups: list[_CandidateGroup] = []
    for group_records in records_by_email.values():
        group_records.sort(key=lambda record: (record.object_type, record.object_uid))
        explicit_candidate = next(
            (
                record
                for record in group_records
                if record.object_type == "project_candidate"
            ),
            None,
        )
        project_uid = (
            explicit_candidate.object_uid
            if explicit_candidate is not None
            else _synthetic_project_uid(group_records, scope=scope)
        )
        groups.append(
            _CandidateGroup(project_uid=project_uid, records=tuple(group_records))
        )
    return tuple(groups)


def _synthetic_project_uid(
    records: list[ProjectGraphObjectRecord],
    *,
    scope: ProjectGraphQueryScope,
) -> str:
    first_record = records[0]
    source_record_uid = (
        first_record.email.message_id
        if getattr(first_record, "email", None) is not None
        else first_record.object_uid
    )
    digest = hashlib.sha256(
        "|".join(
            (
                scope.workspace_id,
                scope.organization_id or "",
                str(first_record.email_id),
                source_record_uid,
            )
        ).encode("utf-8")
    ).hexdigest()[:20]
    return f"project_candidate:auto:{digest}"


def _candidate_summary(
    group: _CandidateGroup,
    *,
    segment_map: Mapping[str, ProjectCitation],
) -> ProjectCandidateSummary:
    type_counts = Counter(record.object_type for record in group.records)
    representative = _representative_record(group.records)
    source_segment_uids = _record_segment_uids(group.records)
    updated_values = [record.updated_at for record in group.records if record.updated_at]
    return ProjectCandidateSummary(
        candidate_uid=group.project_uid,
        project_uid=group.project_uid,
        title=_candidate_title(representative),
        status_code=_candidate_status(group.records),
        score=_candidate_score(group.records),
        object_count=len(group.records),
        requirement_count=type_counts["requirement"],
        issue_count=type_counts["issue"],
        milestone_count=type_counts["milestone"],
        deliverable_count=type_counts["deliverable"],
        participant_count=type_counts["participant"],
        source_segment_count=len(set(source_segment_uids)),
        representative_object_uids=tuple(
            record.object_uid for record in group.records[:8]
        ),
        citation_bundle=_citation_bundle(source_segment_uids[:6], segment_map),
        updated_at=max(updated_values) if updated_values else None,
    )


def _candidate_title(record: ProjectGraphObjectRecord) -> str:
    if record.object_type == "project_candidate":
        return record.title
    subject = getattr(getattr(record, "email", None), "subject", None)
    if isinstance(subject, str) and subject.strip():
        return f"Project: {' '.join(subject.split())[:180]}"
    return record.title


def _candidate_status(records: tuple[ProjectGraphObjectRecord, ...]) -> str:
    statuses = {record.status_code for record in records}
    if "confirmed" in statuses:
        return "confirmed"
    if "approved" in statuses:
        return "approved"
    if "needs_review" in statuses:
        return "needs_review"
    return "candidate"


def _candidate_score(records: tuple[ProjectGraphObjectRecord, ...]) -> float:
    type_signal = sum(
        PROJECT_OBJECT_SCORE_WEIGHTS.get(record.object_type, 0.04)
        for record in records
    )
    confidence_signal = (
        sum(record.confidence for record in records) / len(records) if records else 0.0
    )
    source_signal = min(len(set(_record_segment_uids(records))), 8) * 0.025
    return round(min(0.99, 0.18 + type_signal + confidence_signal * 0.24 + source_signal), 3)


def _representative_record(
    records: tuple[ProjectGraphObjectRecord, ...],
) -> ProjectGraphObjectRecord:
    return max(
        records,
        key=lambda record: (
            1 if record.object_type == "project_candidate" else 0,
            PROJECT_OBJECT_SCORE_WEIGHTS.get(record.object_type, 0.0),
            record.confidence,
        ),
    )


def _trace_object(
    record: ProjectGraphObjectRecord,
    segment_map: Mapping[str, ProjectCitation],
) -> ProjectTraceObject:
    return ProjectTraceObject(
        object_uid=record.object_uid,
        object_type=record.object_type,
        title=record.title,
        summary=record.summary,
        status_code=record.status_code,
        confidence=record.confidence,
        source_segment_uids=tuple(record.source_segment_uids),
        citation_bundle=_citation_bundle(tuple(record.source_segment_uids), segment_map),
        attributes=dict(record.attributes_json or {}),
    )


def _trace_edge(
    edge: ProjectGraphEdgeRecord,
    segment_map: Mapping[str, ProjectCitation],
) -> ProjectTraceEdge:
    return ProjectTraceEdge(
        edge_uid=edge.edge_uid,
        source_uid=edge.source_uid,
        target_uid=edge.target_uid,
        edge_type=edge.edge_type,
        confidence=edge.confidence,
        source_segment_uids=tuple(edge.source_segment_uids),
        citation_bundle=_citation_bundle(tuple(edge.source_segment_uids), segment_map),
    )


def _relation_endpoint(
    trace_object: ProjectTraceObject,
) -> ProjectTraceRelationEndpoint:
    return ProjectTraceRelationEndpoint(
        object_uid=trace_object.object_uid,
        object_type=trace_object.object_type,
        title=trace_object.title,
    )


def _trace_relations(
    edges: tuple[ProjectTraceEdge, ...],
    objects: tuple[ProjectTraceObject, ...],
) -> tuple[ProjectTraceRelation, ...]:
    """Project the loaded edges onto typed object-to-object relations.

    An edge becomes a relation only when both of its endpoints resolve to
    project objects in this traceability group. Segment-evidence edges
    (``segment:<uid>`` source) never resolve on the source side, so they are
    excluded and the raw ``edges`` collection stays the place to read them.
    """
    objects_by_uid = {trace_object.object_uid: trace_object for trace_object in objects}
    relations: list[ProjectTraceRelation] = []
    for edge in edges:
        source_object = objects_by_uid.get(edge.source_uid)
        target_object = objects_by_uid.get(edge.target_uid)
        if source_object is None or target_object is None:
            continue
        relations.append(
            ProjectTraceRelation(
                relation_uid=edge.edge_uid,
                relation_type=edge.edge_type,
                source=_relation_endpoint(source_object),
                target=_relation_endpoint(target_object),
                confidence=edge.confidence,
                source_segment_uids=edge.source_segment_uids,
                citation_bundle=edge.citation_bundle,
            )
        )
    return tuple(relations)


def _incident_relations(
    relations: tuple[ProjectTraceRelation, ...],
    object_uid: str,
) -> tuple[ProjectTraceRelation, ...]:
    """Relations where ``object_uid`` is either endpoint (inbound + outbound).

    A relation surfaces on an object's evidence view whether the object is the
    relation's source (outbound — this feature *implements* that requirement) or
    its target (inbound — that issue *blocks* this milestone). Each relation
    already carries both fully resolved endpoints, so direction stays legible.
    Edge order (and therefore relation order) from :func:`_trace_relations` is
    preserved.
    """
    return tuple(
        relation
        for relation in relations
        if relation.source.object_uid == object_uid
        or relation.target.object_uid == object_uid
    )


def _relation_summary(
    project_uid: str,
    relations: tuple[ProjectTraceRelation, ...],
) -> ProjectRelationSummary:
    """Fold typed relations into a per-type distribution (pure aggregation).

    Groups by ``relation_type`` and, per group, counts relations, counts those
    that are grounded (a non-empty citation bundle), and collects the distinct
    sorted object types on each endpoint. The per-type list is ordered by
    ``relation_count`` descending with a ``relation_type``-ascending tie-break so
    the result is deterministic regardless of relation iteration order.
    """
    grouped: dict[str, list[ProjectTraceRelation]] = defaultdict(list)
    for relation in relations:
        grouped[relation.relation_type].append(relation)
    type_summaries = [
        ProjectRelationTypeSummary(
            relation_type=relation_type,
            relation_count=len(group_relations),
            grounded_relation_count=sum(
                1 for relation in group_relations if relation.citation_bundle
            ),
            source_object_types=tuple(
                sorted({relation.source.object_type for relation in group_relations})
            ),
            target_object_types=tuple(
                sorted({relation.target.object_type for relation in group_relations})
            ),
        )
        for relation_type, group_relations in grouped.items()
    ]
    type_summaries.sort(
        key=lambda summary: (-summary.relation_count, summary.relation_type)
    )
    return ProjectRelationSummary(
        project_uid=project_uid,
        relation_count=len(relations),
        grounded_relation_count=sum(
            1 for relation in relations if relation.citation_bundle
        ),
        relation_types=tuple(type_summaries),
    )


def _decision_view(
    project_uid: str,
    objects: tuple[ProjectTraceObject, ...],
    relations: tuple[ProjectTraceRelation, ...],
) -> ProjectDecisionView:
    """Fold the decision-typed objects of a project into a grounded view.

    Selects objects whose ``object_type`` is the canonical
    :data:`DECISION_OBJECT_TYPE`, pairs each with its incident relations
    (:func:`_incident_relations`, both inbound and outbound), and counts those
    grounded by a non-empty citation bundle. Pure — no database — so it is
    unit-testable, and it preserves the ``objects`` iteration order so the
    result is deterministic in the upstream object load order.
    """
    decisions = tuple(
        ProjectDecisionRecord(
            object_uid=trace_object.object_uid,
            title=trace_object.title,
            summary=trace_object.summary,
            status_code=trace_object.status_code,
            confidence=trace_object.confidence,
            citation_bundle=trace_object.citation_bundle,
            relations=_incident_relations(relations, trace_object.object_uid),
        )
        for trace_object in objects
        if trace_object.object_type == DECISION_OBJECT_TYPE
    )
    return ProjectDecisionView(
        project_uid=project_uid,
        decision_count=len(decisions),
        grounded_decision_count=sum(
            1 for decision in decisions if decision.citation_bundle
        ),
        decisions=decisions,
    )


def _correction_response(
    correction: ProjectGraphCorrectionRecord,
    object_uid: str,
) -> ProjectCorrection:
    return ProjectCorrection(
        correction_uid=correction.correction_uid,
        object_uid=object_uid,
        correction_action=correction.correction_action,
        before_json=dict(correction.before_json or {}),
        after_json=dict(correction.after_json or {}),
        rationale=correction.rationale,
        actor_user_id=correction.actor_user_id,
        source_segment_uids=tuple(correction.source_segment_uids),
        created_at=correction.created_at,
    )


def _record_segment_uids(
    records: Iterable[ProjectGraphObjectRecord],
) -> tuple[str, ...]:
    seen: dict[str, None] = {}
    for record in records:
        for source_uid in record.source_segment_uids:
            seen.setdefault(source_uid, None)
    return tuple(seen)


def _edge_segment_uids(
    edges: Iterable[ProjectGraphEdgeRecord],
) -> tuple[str, ...]:
    seen: dict[str, None] = {}
    for edge in edges:
        for source_uid in edge.source_segment_uids:
            seen.setdefault(source_uid, None)
    return tuple(seen)


def _citation_bundle(
    source_segment_uids: Iterable[str],
    segment_map: Mapping[str, ProjectCitation],
) -> tuple[ProjectCitation, ...]:
    citations = []
    seen: set[str] = set()
    for source_uid in source_segment_uids:
        if source_uid in seen:
            continue
        seen.add(source_uid)
        citation = segment_map.get(source_uid)
        if citation is not None:
            citations.append(citation)
    return tuple(citations)


def _safe_excerpt(text: str, max_length: int = 240) -> str:
    normalized = " ".join((text or "").replace("\x00", " ").split())
    if len(normalized) <= max_length:
        return normalized
    return normalized[: max_length - 3].rstrip() + "..."


def _utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)
