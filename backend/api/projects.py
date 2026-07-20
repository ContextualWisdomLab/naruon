from __future__ import annotations

import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import AuthContext, get_auth_context, is_admin_role
from db.session import get_db
from services.project_graph.project_registration import (
    ProjectCandidateSummary,
    ProjectCitation,
    ProjectCorrection,
    ProjectGraphNotFoundError,
    ProjectGraphQueryScope,
    apply_project_correction,
    confirm_project_candidate,
    list_project_candidates,
)
from services.project_graph.traceability import (
    ProjectEvidence,
    ProjectTraceability,
    get_project_evidence,
    get_project_traceability,
)
from services.scopeweave_client import ScopeweaveConfigError, ScopeweavePushError
from services.scopeweave_promotion import (
    ScopeweaveNotConfiguredError,
    ScopeweavePromotionOutcome,
    promote_project_object,
)

router = APIRouter(prefix="/api/projects", tags=["projects"])


class ProjectCitationResponse(BaseModel):
    content_segment_uid: str
    source_kind: str
    source_record_uid: str
    heading_path: str | None
    segment_path: str | None
    ordinal_index: int
    safe_text_excerpt: str


class ProjectCandidateResponse(BaseModel):
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
    representative_object_uids: list[str]
    citation_bundle: list[ProjectCitationResponse]
    updated_at: datetime.datetime | None


class ProjectCandidateListResponse(BaseModel):
    candidates: list[ProjectCandidateResponse]


class ProjectTraceObjectResponse(BaseModel):
    object_uid: str
    object_type: str
    title: str
    summary: str
    status_code: str
    confidence: float
    source_segment_uids: list[str]
    citation_bundle: list[ProjectCitationResponse]
    attributes: dict[str, Any]


class ProjectTraceEdgeResponse(BaseModel):
    edge_uid: str
    source_uid: str
    target_uid: str
    edge_type: str
    confidence: float
    source_segment_uids: list[str]
    citation_bundle: list[ProjectCitationResponse]


class ProjectTraceabilityResponse(BaseModel):
    project_uid: str
    candidate: ProjectCandidateResponse
    objects: list[ProjectTraceObjectResponse]
    edges: list[ProjectTraceEdgeResponse]


class ProjectEvidenceResponse(BaseModel):
    project_uid: str
    object_uid: str
    object_type: str
    title: str
    summary: str
    status_code: str
    confidence: float
    citation_bundle: list[ProjectCitationResponse]


class ProjectPromoteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    object_uid: str = Field(min_length=1, max_length=160)


class ProjectPromoteResponse(BaseModel):
    project_uid: str
    object_uid: str
    object_type: str
    scopeweave_work_item_id: str
    scopeweave_work_item_url: str | None
    promoted_confidence: float
    citation_count: int
    created: bool


class ProjectCorrectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    object_uid: str = Field(min_length=1, max_length=160)
    correction_action: str = Field(min_length=1, max_length=64)
    after_json: dict[str, Any] = Field(default_factory=dict)
    rationale: str | None = Field(default=None, max_length=2000)
    source_segment_uids: list[str] | None = None


class ProjectCorrectionResponse(BaseModel):
    correction_uid: str
    object_uid: str
    correction_action: str
    before_json: dict[str, Any]
    after_json: dict[str, Any]
    rationale: str | None
    actor_user_id: str
    source_segment_uids: list[str]
    created_at: datetime.datetime


def _project_scope(auth_context: AuthContext) -> ProjectGraphQueryScope:
    return ProjectGraphQueryScope(
        user_id=auth_context.user_id,
        organization_id=auth_context.organization_id,
        workspace_id=auth_context.workspace_id,
        can_read_organization_scope=(
            is_admin_role(auth_context.role)
            and auth_context.organization_id is not None
        ),
    )


@router.get("/candidates", response_model=ProjectCandidateListResponse)
async def get_project_candidates(
    limit: int = Query(default=25, ge=1, le=100),
    auth_context: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
):
    candidates = await list_project_candidates(
        db,
        scope=_project_scope(auth_context),
        limit=limit,
    )
    return ProjectCandidateListResponse(
        candidates=[_candidate_response(candidate) for candidate in candidates]
    )


@router.post(
    "/candidates/{candidate_uid}/confirm",
    response_model=ProjectCandidateResponse,
)
async def confirm_project_candidate_endpoint(
    candidate_uid: str,
    auth_context: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
):
    try:
        candidate = await confirm_project_candidate(
            db,
            scope=_project_scope(auth_context),
            candidate_uid=candidate_uid,
            actor_user_id=auth_context.user_id,
        )
        await db.commit()
    except ProjectGraphNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _candidate_response(candidate)


@router.get(
    "/{project_uid}/traceability",
    response_model=ProjectTraceabilityResponse,
)
async def get_project_traceability_endpoint(
    project_uid: str,
    auth_context: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
):
    try:
        traceability = await get_project_traceability(
            db,
            scope=_project_scope(auth_context),
            project_uid=project_uid,
        )
    except ProjectGraphNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _traceability_response(traceability)


@router.get(
    "/{project_uid}/evidence/{object_uid}",
    response_model=ProjectEvidenceResponse,
)
async def get_project_evidence_endpoint(
    project_uid: str,
    object_uid: str,
    auth_context: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
):
    try:
        evidence = await get_project_evidence(
            db,
            scope=_project_scope(auth_context),
            project_uid=project_uid,
            object_uid=object_uid,
        )
    except ProjectGraphNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _evidence_response(evidence)


@router.post(
    "/{project_uid}/corrections",
    response_model=ProjectCorrectionResponse,
)
async def apply_project_correction_endpoint(
    project_uid: str,
    request: ProjectCorrectionRequest,
    auth_context: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
):
    try:
        correction = await apply_project_correction(
            db,
            scope=_project_scope(auth_context),
            project_uid=project_uid,
            object_uid=request.object_uid,
            actor_user_id=auth_context.user_id,
            correction_action=request.correction_action,
            after_json=request.after_json,
            rationale=request.rationale,
            source_segment_uids=(
                tuple(request.source_segment_uids)
                if request.source_segment_uids is not None
                else None
            ),
        )
        await db.commit()
    except ProjectGraphNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _correction_response(correction)


@router.post(
    "/{project_uid}/promote",
    response_model=ProjectPromoteResponse,
)
async def promote_project_object_endpoint(
    project_uid: str,
    request: ProjectPromoteRequest,
    auth_context: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
):
    try:
        outcome = await promote_project_object(
            db,
            scope=_project_scope(auth_context),
            project_uid=project_uid,
            object_uid=request.object_uid,
            actor_user_id=auth_context.user_id,
        )
        await db.commit()
    except ProjectGraphNotFoundError as exc:
        await db.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ScopeweaveNotConfiguredError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (ScopeweaveConfigError, ScopeweavePushError) as exc:
        await db.rollback()
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return _promote_response(outcome)


def _citation_response(citation: ProjectCitation) -> ProjectCitationResponse:
    return ProjectCitationResponse(
        content_segment_uid=citation.content_segment_uid,
        source_kind=citation.source_kind,
        source_record_uid=citation.source_record_uid,
        heading_path=citation.heading_path,
        segment_path=citation.segment_path,
        ordinal_index=citation.ordinal_index,
        safe_text_excerpt=citation.safe_text_excerpt,
    )


def _candidate_response(candidate: ProjectCandidateSummary) -> ProjectCandidateResponse:
    return ProjectCandidateResponse(
        candidate_uid=candidate.candidate_uid,
        project_uid=candidate.project_uid,
        title=candidate.title,
        status_code=candidate.status_code,
        score=candidate.score,
        object_count=candidate.object_count,
        requirement_count=candidate.requirement_count,
        issue_count=candidate.issue_count,
        milestone_count=candidate.milestone_count,
        deliverable_count=candidate.deliverable_count,
        participant_count=candidate.participant_count,
        source_segment_count=candidate.source_segment_count,
        representative_object_uids=list(candidate.representative_object_uids),
        citation_bundle=[
            _citation_response(citation) for citation in candidate.citation_bundle
        ],
        updated_at=candidate.updated_at,
    )


def _traceability_response(
    traceability: ProjectTraceability,
) -> ProjectTraceabilityResponse:
    return ProjectTraceabilityResponse(
        project_uid=traceability.project_uid,
        candidate=_candidate_response(traceability.candidate),
        objects=[
            ProjectTraceObjectResponse(
                object_uid=project_object.object_uid,
                object_type=project_object.object_type,
                title=project_object.title,
                summary=project_object.summary,
                status_code=project_object.status_code,
                confidence=project_object.confidence,
                source_segment_uids=list(project_object.source_segment_uids),
                citation_bundle=[
                    _citation_response(citation)
                    for citation in project_object.citation_bundle
                ],
                attributes=dict(project_object.attributes),
            )
            for project_object in traceability.objects
        ],
        edges=[
            ProjectTraceEdgeResponse(
                edge_uid=edge.edge_uid,
                source_uid=edge.source_uid,
                target_uid=edge.target_uid,
                edge_type=edge.edge_type,
                confidence=edge.confidence,
                source_segment_uids=list(edge.source_segment_uids),
                citation_bundle=[
                    _citation_response(citation) for citation in edge.citation_bundle
                ],
            )
            for edge in traceability.edges
        ],
    )


def _evidence_response(evidence: ProjectEvidence) -> ProjectEvidenceResponse:
    return ProjectEvidenceResponse(
        project_uid=evidence.project_uid,
        object_uid=evidence.object_uid,
        object_type=evidence.object_type,
        title=evidence.title,
        summary=evidence.summary,
        status_code=evidence.status_code,
        confidence=evidence.confidence,
        citation_bundle=[
            _citation_response(citation) for citation in evidence.citation_bundle
        ],
    )


def _promote_response(
    outcome: ScopeweavePromotionOutcome,
) -> ProjectPromoteResponse:
    return ProjectPromoteResponse(
        project_uid=outcome.project_uid,
        object_uid=outcome.object_uid,
        object_type=outcome.object_type,
        scopeweave_work_item_id=outcome.scopeweave_work_item_id,
        scopeweave_work_item_url=outcome.scopeweave_work_item_url,
        promoted_confidence=outcome.promoted_confidence,
        citation_count=outcome.citation_count,
        created=outcome.created,
    )


def _correction_response(correction: ProjectCorrection) -> ProjectCorrectionResponse:
    return ProjectCorrectionResponse(
        correction_uid=correction.correction_uid,
        object_uid=correction.object_uid,
        correction_action=correction.correction_action,
        before_json=dict(correction.before_json),
        after_json=dict(correction.after_json),
        rationale=correction.rationale,
        actor_user_id=correction.actor_user_id,
        source_segment_uids=list(correction.source_segment_uids),
        created_at=correction.created_at,
    )
