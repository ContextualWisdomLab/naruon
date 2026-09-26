"""Owner-scoped, source-cited calendar event conflicts."""

from __future__ import annotations

import datetime
import hashlib
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from api.auth import AuthContext, get_auth_context
from db.models import (
    EventRelationCorrectionRecord,
    EventRelationRecord,
    ContentSegmentRecord,
    Email,
    SourceEventRecord,
)
from db.session import get_db
from services.calendar_conflict_policy import (
    CalendarCommitment,
    evaluate_calendar_conflicts,
)

router = APIRouter(prefix="/api/events", tags=["events"])


class EventConflictResponse(BaseModel):
    source_event_uid: str
    target_event_uid: str
    reason_code: Literal["occupied_interval_overlap"]
    source_segment_uids: list[str]
    target_segment_uids: list[str]


RelationType = Literal["enables", "conflicts", "unrelated"]


class EventCitationResponse(BaseModel):
    segment_uid: str
    label: str
    excerpt: str


class EventSourceResponse(BaseModel):
    event_uid: str
    title: str
    starts_at: datetime.datetime
    ends_at: datetime.datetime
    email_id: int | None
    source_segment_uids: list[str]
    citations: list[EventCitationResponse]


class EventRelationResponse(BaseModel):
    relation_uid: str
    source_event_uid: str
    target_event_uid: str
    relation_type: RelationType
    confidence: float
    evidence_code: str
    source_segment_uids: list[str]
    corrected: bool
    source: EventSourceResponse
    target: EventSourceResponse


class EventRelationCorrectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    relation_type: RelationType


def _event_scope(model, auth_context: AuthContext, visibility_scope: str):
    organization_filter = (
        model.organization_id == auth_context.organization_id
        if auth_context.organization_id is not None
        else model.organization_id.is_(None)
    )
    return (
        model.user_id == auth_context.user_id,
        organization_filter,
        model.workspace_id == auth_context.workspace_id,
        model.visibility_scope == visibility_scope,
    )


def _source_event_scope(model, auth_context: AuthContext, visibility_scope: str):
    email_scope = [
        Email.id == model.email_id,
        *Email.owner_filters(auth_context.user_id, auth_context.organization_id),
    ]
    if visibility_scope == "organization":
        email_scope.append(Email.is_personal_reference.is_(False))
    return (
        *_event_scope(model, auth_context, visibility_scope),
        or_(model.email_id.is_(None), select(Email.id).where(*email_scope).exists()),
    )


def _commitment(event: SourceEventRecord) -> CalendarCommitment:
    return CalendarCommitment(
        commitment_id=event.event_uid,
        start_at=event.starts_at,
        end_at=event.ends_at,
        status=event.status_code,
    )


@router.get("/overlaps", response_model=list[EventConflictResponse])
async def list_event_conflicts(
    visibility_scope: Literal["personal", "organization"] = Query(),
    auth_context: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
) -> list[EventConflictResponse]:
    # ponytail: compare only the 100 newest owner-visible events; use an
    # indexed time-window candidate query when the event ledger grows.
    events = (
        (
            await db.execute(
                select(SourceEventRecord)
                .where(
                    *_source_event_scope(
                        SourceEventRecord, auth_context, visibility_scope
                    ),
                    SourceEventRecord.event_type == "calendar_event",
                    SourceEventRecord.status_code.in_(
                        ("confirmed", "tentative", "desired")
                    ),
                )
                .order_by(
                    SourceEventRecord.starts_at.desc(), SourceEventRecord.event_uid
                )
                .limit(100)
            )
        )
        .scalars()
        .all()
    )
    conflicts: list[EventConflictResponse] = []
    for index, source in enumerate(events):
        for target in events[index + 1 :]:
            if not source.source_segment_uids or not target.source_segment_uids:
                continue
            if source.source_event_key == target.source_event_key:
                continue
            decision = evaluate_calendar_conflicts(
                _commitment(source), [_commitment(target)]
            )
            if decision.conflicts:
                conflicts.append(
                    EventConflictResponse(
                        source_event_uid=source.event_uid,
                        target_event_uid=target.event_uid,
                        reason_code="occupied_interval_overlap",
                        source_segment_uids=source.source_segment_uids,
                        target_segment_uids=target.source_segment_uids,
                    )
                )
    return conflicts


def _relation_response(
    relation: EventRelationRecord,
    source: SourceEventRecord,
    target: SourceEventRecord,
    citation_map: dict[tuple[int, str], ContentSegmentRecord],
) -> EventRelationResponse:
    return EventRelationResponse(
        relation_uid=relation.relation_uid,
        source_event_uid=relation.source_event_uid,
        target_event_uid=relation.target_event_uid,
        relation_type=relation.relation_type,
        confidence=relation.confidence,
        evidence_code=relation.evidence_code,
        source_segment_uids=relation.source_segment_uids,
        corrected=relation.corrected_at is not None,
        source=_event_source_response(source, citation_map),
        target=_event_source_response(target, citation_map),
    )


_CITATION_LABELS = {
    "SUMMARY": "제목",
    "DTSTART": "시작",
    "DTEND": "종료",
    "DURATION": "기간",
    "LOCATION": "장소",
    "STATUS": "상태",
}


def _event_source_response(
    event: SourceEventRecord,
    citation_map: dict[tuple[int, str], ContentSegmentRecord],
) -> EventSourceResponse:
    citations = []
    if event.email_id is not None:
        for segment_uid in event.source_segment_uids:
            segment = citation_map.get((event.email_id, segment_uid))
            if segment is None:
                continue
            property_header, _, value = segment.safe_text_content.partition(":")
            label = _CITATION_LABELS.get(property_header.split(";", 1)[0])
            if label is None:
                continue
            timezone = next(
                (
                    part.partition("=")[2]
                    for part in property_header.split(";")[1:]
                    if part.startswith("TZID=")
                ),
                None,
            )
            excerpt = value.strip()
            if timezone:
                excerpt = f"{excerpt} ({timezone})"
            citations.append(
                EventCitationResponse(
                    segment_uid=segment_uid,
                    label=label,
                    excerpt=excerpt[:240],
                )
            )
    return EventSourceResponse(
        event_uid=event.event_uid,
        title=event.title,
        starts_at=event.starts_at,
        ends_at=event.ends_at,
        email_id=event.email_id,
        source_segment_uids=event.source_segment_uids,
        citations=citations,
    )


async def _citation_map(
    db: AsyncSession,
    rows: list[tuple[EventRelationRecord, SourceEventRecord, SourceEventRecord]],
    auth_context: AuthContext,
) -> dict[tuple[int, str], ContentSegmentRecord]:
    events = [event for _, source, target in rows for event in (source, target)]
    email_ids = {event.email_id for event in events if event.email_id is not None}
    segment_uids = {uid for event in events for uid in event.source_segment_uids}
    if not email_ids or not segment_uids:
        return {}
    segments = (
        (
            await db.execute(
                select(ContentSegmentRecord)
                .join(Email, ContentSegmentRecord.email_id == Email.id)
                .where(
                    ContentSegmentRecord.email_id.in_(email_ids),
                    ContentSegmentRecord.content_segment_uid.in_(segment_uids),
                    *Email.owner_filters(
                        auth_context.user_id, auth_context.organization_id
                    ),
                )
            )
        )
        .scalars()
        .all()
    )
    return {
        (segment.email_id, segment.content_segment_uid): segment for segment in segments
    }


async def _scoped_relations(
    db: AsyncSession,
    auth_context: AuthContext,
    visibility_scope: str,
    relation_uid: str | None = None,
    *,
    for_update: bool = False,
) -> list[tuple[EventRelationRecord, SourceEventRecord, SourceEventRecord]]:
    source = aliased(SourceEventRecord)
    target = aliased(SourceEventRecord)
    statement = (
        select(EventRelationRecord, source, target)
        .join(source, EventRelationRecord.source_event_uid == source.event_uid)
        .join(target, EventRelationRecord.target_event_uid == target.event_uid)
        .where(
            *_event_scope(EventRelationRecord, auth_context, visibility_scope),
            *_source_event_scope(source, auth_context, visibility_scope),
            *_source_event_scope(target, auth_context, visibility_scope),
        )
    )
    if relation_uid is not None:
        statement = statement.where(EventRelationRecord.relation_uid == relation_uid)
    if for_update:
        statement = statement.with_for_update(of=EventRelationRecord)
    else:
        statement = statement.order_by(EventRelationRecord.relation_uid).limit(100)
    return list((await db.execute(statement)).all())


@router.get("/relations", response_model=list[EventRelationResponse])
async def list_event_relations(
    visibility_scope: Literal["personal", "organization"] = Query(),
    auth_context: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
) -> list[EventRelationResponse]:
    relations = await _scoped_relations(db, auth_context, visibility_scope)
    citations = await _citation_map(db, relations, auth_context)
    return [
        _relation_response(relation, source, target, citations)
        for relation, source, target in relations
    ]


@router.post("/relations/reconcile", response_model=list[EventRelationResponse])
async def reconcile_event_relations(
    visibility_scope: Literal["personal", "organization"] = Query(),
    auth_context: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
) -> list[EventRelationResponse]:
    overlaps = await list_event_conflicts(visibility_scope, auth_context, db)
    for overlap in overlaps:
        source_uid, target_uid = sorted(
            (overlap.source_event_uid, overlap.target_event_uid)
        )
        relation_uid = (
            "erel_"
            + hashlib.sha256(f"{source_uid}\0{target_uid}".encode()).hexdigest()[:32]
        )
        citations = list(
            dict.fromkeys((*overlap.source_segment_uids, *overlap.target_segment_uids))
        )
        await db.execute(
            pg_insert(EventRelationRecord)
            .values(
                relation_uid=relation_uid,
                source_event_uid=source_uid,
                target_event_uid=target_uid,
                user_id=auth_context.user_id,
                organization_id=auth_context.organization_id,
                workspace_id=auth_context.workspace_id,
                visibility_scope=visibility_scope,
                relation_type="conflicts",
                # ponytail: time overlap is provisional; enrich confidence with
                # shared entities and travel context when those sources arrive.
                confidence=0.8,
                evidence_code="occupied_interval_overlap",
                source_segment_uids=citations,
                created_at=datetime.datetime.now(datetime.timezone.utc),
            )
            .on_conflict_do_nothing()
        )
    await db.commit()
    return await list_event_relations(visibility_scope, auth_context, db)


@router.patch("/relations/{relation_uid}", response_model=EventRelationResponse)
async def correct_event_relation(
    relation_uid: str,
    request: EventRelationCorrectionRequest,
    visibility_scope: Literal["personal", "organization"] = Query(),
    auth_context: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
) -> EventRelationResponse:
    relations = await _scoped_relations(
        db, auth_context, visibility_scope, relation_uid, for_update=True
    )
    if not relations:
        raise HTTPException(status_code=404, detail="Event relation not found")
    relation, source, target = relations[0]
    if relation.relation_type != request.relation_type:
        db.add(
            EventRelationCorrectionRecord(
                relation_uid=relation.relation_uid,
                actor_user_id=auth_context.user_id,
                before_type=relation.relation_type,
                after_type=request.relation_type,
                source_segment_uids=relation.source_segment_uids,
            )
        )
        relation.relation_type = request.relation_type
        relation.confidence = 1.0
        relation.evidence_code = "human_correction"
        relation.corrected_by_user_id = auth_context.user_id
        relation.corrected_at = datetime.datetime.now(datetime.timezone.utc)
        await db.commit()
    citations = await _citation_map(db, relations, auth_context)
    return _relation_response(relation, source, target, citations)
