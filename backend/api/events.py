"""Owner-scoped, source-cited calendar event conflicts."""

from __future__ import annotations

import datetime
import hashlib
import re
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import and_, func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from api.auth import AuthContext, get_auth_context
from db.models import (
    EventRelationCorrectionRecord,
    EventRelationRecord,
    ContentSegmentRecord,
    CalendarSourceDocumentRecord,
    Email,
    SourceEventRecord,
)
from db.session import get_db
from services.calendar_conflict_policy import (
    CalendarCommitment,
    CalendarPolicyValidationError,
    evaluate_calendar_conflicts,
)
from services.calendar_conflict_ics import parse_calendar_source_events_from_ics
from services.content_graph import parse_content

router = APIRouter(prefix="/api/events", tags=["events"])
_PAGE_SIZE = 100
_PAIR_CURSOR = re.compile(r"event_[0-9a-f]{32}:event_[0-9a-f]{32}\Z")
_RELATION_CURSOR = re.compile(r"erel_[0-9a-f]{32}\Z")


class EventConflictResponse(BaseModel):
    source_event_uid: str
    target_event_uid: str
    reason_code: Literal["occupied_interval_overlap"]
    source_segment_uids: list[str]
    target_segment_uids: list[str]


class EventConflictPageResponse(BaseModel):
    items: list[EventConflictResponse]
    next_cursor: str | None


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
    document_id: str | None
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


class EventRelationPageResponse(BaseModel):
    items: list[EventRelationResponse]
    next_cursor: str | None


class EventReconcilePageResponse(BaseModel):
    processed_conflicts: int
    next_cursor: str | None


class EventRelationCorrectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    relation_type: RelationType


class CalendarSourceUploadRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ics_text: str = Field(min_length=1, max_length=262_144)
    visibility_scope: Literal["personal", "organization"]


class CalendarSourceListItem(BaseModel):
    document_id: str
    visibility_scope: Literal["personal", "organization"]
    created_at: datetime.datetime


class CalendarSourceListResponse(BaseModel):
    items: list[CalendarSourceListItem]
    next_cursor: str | None


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
    document_scope = [
        CalendarSourceDocumentRecord.document_id == model.calendar_document_id,
        CalendarSourceDocumentRecord.user_id == auth_context.user_id,
        CalendarSourceDocumentRecord.workspace_id == auth_context.workspace_id,
        CalendarSourceDocumentRecord.organization_id == auth_context.organization_id,
        CalendarSourceDocumentRecord.visibility_scope == visibility_scope,
    ]
    return (
        *_event_scope(model, auth_context, visibility_scope),
        or_(
            and_(
                model.source_kind == "email_calendar_attachment",
                select(Email.id).where(*email_scope).exists(),
            ),
            and_(
                model.source_kind == "workspace_calendar_document",
                model.email_id.is_(None),
                model.source_record_uid == model.calendar_document_id,
                select(CalendarSourceDocumentRecord.document_id)
                .where(*document_scope)
                .exists(),
            ),
        ),
    )


def _commitment(event: SourceEventRecord) -> CalendarCommitment:
    return CalendarCommitment(
        commitment_id=event.event_uid,
        start_at=event.starts_at,
        end_at=event.ends_at,
        status=event.status_code,
    )


@router.post("/sources/ics", response_model=list[EventSourceResponse])
async def upload_calendar_source(
    request: CalendarSourceUploadRequest,
    auth_context: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
) -> list[EventSourceResponse]:
    if (
        request.visibility_scope == "organization"
        and auth_context.organization_id is None
    ):
        raise HTTPException(status_code=422, detail="Organization scope is unavailable")
    try:
        events = parse_calendar_source_events_from_ics(request.ics_text)
    except CalendarPolicyValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.error_code) from exc

    document = CalendarSourceDocumentRecord(
        user_id=auth_context.user_id,
        workspace_id=auth_context.workspace_id,
        organization_id=auth_context.organization_id,
        visibility_scope=request.visibility_scope,
        content=request.ics_text,
    )
    db.add(document)
    await db.flush()
    graph = parse_content(
        source_kind="calendar_document",
        source_record_uid=document.document_id,
        content=request.ics_text,
        content_type="text/calendar",
    )
    records = []
    citations: dict[tuple[str, str], str] = {}
    for index, event in enumerate(events, start=1):
        segment_rows = [
            segment
            for segment in graph.segments
            if f"/vevent[{index}]/" in segment.segment_path
        ]
        properties = {
            segment.safe_text_content.partition(":")[0].split(";", 1)[0]
            for segment in segment_rows
        }
        if not {"UID", "DTSTART"} <= properties or not (
            {"DTEND", "DURATION"} & properties
        ):
            raise HTTPException(
                status_code=422, detail="Calendar evidence is incomplete"
            )
        cited_segments = [
            segment
            for segment in segment_rows
            if segment.safe_text_content.partition(":")[0].split(";", 1)[0]
            in {"UID", "DTSTART", "DTEND", "DURATION", "SUMMARY", "LOCATION", "STATUS"}
        ]
        event_uid = (
            "event_"
            + hashlib.sha256(
                f"{document.document_id}\0{event.commitment.commitment_id}".encode()
            ).hexdigest()[:32]
        )
        record = SourceEventRecord(
            event_uid=event_uid,
            user_id=auth_context.user_id,
            organization_id=auth_context.organization_id,
            workspace_id=auth_context.workspace_id,
            visibility_scope=request.visibility_scope,
            source_kind="workspace_calendar_document",
            source_record_uid=document.document_id,
            source_event_key=event.commitment.commitment_id,
            calendar_document_id=document.document_id,
            event_type="calendar_event",
            title=event.title,
            status_code=event.commitment.status,
            starts_at=event.commitment.start_at,
            ends_at=event.commitment.end_at,
            location_text=event.location,
            source_segment_uids=[
                segment.content_segment_uid for segment in cited_segments
            ],
        )
        records.append(record)
        citations.update(
            {
                (
                    document.document_id,
                    segment.content_segment_uid,
                ): segment.safe_text_content
                for segment in cited_segments
            }
        )
    db.add_all(records)
    await db.commit()
    return [_event_source_response(record, citations) for record in records]


@router.get("/sources", response_model=CalendarSourceListResponse)
async def list_calendar_sources(
    after: str | None = Query(default=None, max_length=40),
    auth_context: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
) -> CalendarSourceListResponse:
    statement = select(CalendarSourceDocumentRecord).where(
        CalendarSourceDocumentRecord.user_id == auth_context.user_id,
        CalendarSourceDocumentRecord.workspace_id == auth_context.workspace_id,
        CalendarSourceDocumentRecord.organization_id == auth_context.organization_id,
    )
    if after is not None:
        statement = statement.where(CalendarSourceDocumentRecord.document_id > after)
    documents = (
        (
            await db.execute(
                statement.order_by(CalendarSourceDocumentRecord.document_id).limit(21)
            )
        )
        .scalars()
        .all()
    )
    return CalendarSourceListResponse(
        items=[
            CalendarSourceListItem(
                document_id=document.document_id,
                visibility_scope=document.visibility_scope,
                created_at=document.created_at,
            )
            for document in documents[:20]
        ],
        next_cursor=documents[19].document_id if len(documents) > 20 else None,
    )


@router.get("/sources/{document_id}")
async def download_calendar_source(
    document_id: str,
    auth_context: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
) -> Response:
    document = (
        await db.execute(
            select(CalendarSourceDocumentRecord).where(
                CalendarSourceDocumentRecord.document_id == document_id,
                CalendarSourceDocumentRecord.user_id == auth_context.user_id,
                CalendarSourceDocumentRecord.workspace_id == auth_context.workspace_id,
                CalendarSourceDocumentRecord.organization_id
                == auth_context.organization_id,
            )
        )
    ).scalar_one_or_none()
    if document is None:
        raise HTTPException(status_code=404, detail="Calendar source not found")
    return Response(
        content=document.content,
        media_type="text/calendar",
        headers={
            "Content-Disposition": 'attachment; filename="calendar.ics"',
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.delete("/sources/{document_id}", status_code=204)
async def delete_calendar_source(
    document_id: str,
    auth_context: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
) -> Response:
    document = (
        await db.execute(
            select(CalendarSourceDocumentRecord).where(
                CalendarSourceDocumentRecord.document_id == document_id,
                CalendarSourceDocumentRecord.user_id == auth_context.user_id,
                CalendarSourceDocumentRecord.workspace_id == auth_context.workspace_id,
                CalendarSourceDocumentRecord.organization_id
                == auth_context.organization_id,
            )
        )
    ).scalar_one_or_none()
    if document is None:
        raise HTTPException(status_code=404, detail="Calendar source not found")
    await db.delete(document)
    await db.commit()
    return Response(status_code=204)


@router.get("/overlaps", response_model=EventConflictPageResponse)
async def list_event_conflicts(
    visibility_scope: Literal["personal", "organization"] = Query(),
    auth_context: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
    after: str | None = None,
) -> EventConflictPageResponse:
    if after is not None and _PAIR_CURSOR.fullmatch(after) is None:
        raise HTTPException(status_code=422, detail="Invalid overlap cursor")
    source = aliased(SourceEventRecord)
    target = aliased(SourceEventRecord)
    # ponytail: btree scope/time indexes serve bounded pages; use a range
    # index if dense calendars make this join scan too many candidates.
    statement = (
        select(source, target)
        .join(
            target,
            and_(
                source.event_uid < target.event_uid,
                source.starts_at < target.ends_at,
                target.starts_at < source.ends_at,
                source.source_event_key != target.source_event_key,
            ),
        )
        .where(
            *_source_event_scope(source, auth_context, visibility_scope),
            *_source_event_scope(target, auth_context, visibility_scope),
            source.event_type == "calendar_event",
            target.event_type == "calendar_event",
            source.status_code.in_(("confirmed", "tentative", "desired")),
            target.status_code.in_(("confirmed", "tentative", "desired")),
            func.json_array_length(source.source_segment_uids) > 0,
            func.json_array_length(target.source_segment_uids) > 0,
        )
    )
    if after is not None:
        source_uid, target_uid = after.split(":", 1)
        statement = statement.where(
            or_(
                source.event_uid > source_uid,
                and_(source.event_uid == source_uid, target.event_uid > target_uid),
            )
        )
    pairs = (
        await db.execute(
            statement.order_by(source.event_uid, target.event_uid).limit(_PAGE_SIZE + 1)
        )
    ).all()
    conflicts: list[EventConflictResponse] = []
    for source_event, target_event in pairs[:_PAGE_SIZE]:
        decision = evaluate_calendar_conflicts(
            _commitment(source_event), [_commitment(target_event)]
        )
        if decision.conflicts:
            conflicts.append(
                EventConflictResponse(
                    source_event_uid=source_event.event_uid,
                    target_event_uid=target_event.event_uid,
                    reason_code="occupied_interval_overlap",
                    source_segment_uids=source_event.source_segment_uids,
                    target_segment_uids=target_event.source_segment_uids,
                )
            )
    last = pairs[_PAGE_SIZE - 1] if len(pairs) > _PAGE_SIZE else None
    return EventConflictPageResponse(
        items=conflicts,
        next_cursor=f"{last[0].event_uid}:{last[1].event_uid}" if last else None,
    )


def _relation_response(
    relation: EventRelationRecord,
    source: SourceEventRecord,
    target: SourceEventRecord,
    citation_map: dict[tuple[str, str], str],
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
    citation_map: dict[tuple[str, str], str],
) -> EventSourceResponse:
    citations = []
    for segment_uid in event.source_segment_uids:
        source_text = citation_map.get((event.source_record_uid, segment_uid))
        if source_text is None:
            continue
        property_header, _, value = source_text.partition(":")
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
        document_id=event.calendar_document_id,
        source_segment_uids=event.source_segment_uids,
        citations=citations,
    )


async def _citation_map(
    db: AsyncSession,
    rows: list[tuple[EventRelationRecord, SourceEventRecord, SourceEventRecord]],
    auth_context: AuthContext,
) -> dict[tuple[str, str], str]:
    events = [event for _, source, target in rows for event in (source, target)]
    email_ids = {event.email_id for event in events if event.email_id is not None}
    segment_uids = {uid for event in events for uid in event.source_segment_uids}
    if not segment_uids:
        return {}
    citations: dict[tuple[str, str], str] = {}
    if email_ids:
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
        citations.update(
            {
                (
                    segment.source_record_uid,
                    segment.content_segment_uid,
                ): segment.safe_text_content
                for segment in segments
            }
        )
    document_ids = {
        event.calendar_document_id
        for event in events
        if event.calendar_document_id is not None
    }
    if document_ids:
        documents = (
            (
                await db.execute(
                    select(CalendarSourceDocumentRecord).where(
                        CalendarSourceDocumentRecord.document_id.in_(document_ids),
                        CalendarSourceDocumentRecord.user_id == auth_context.user_id,
                        CalendarSourceDocumentRecord.workspace_id
                        == auth_context.workspace_id,
                        CalendarSourceDocumentRecord.organization_id
                        == auth_context.organization_id,
                    )
                )
            )
            .scalars()
            .all()
        )
        for document in documents:
            # ponytail: reparse the bounded file for citations; persist its
            # segments when document-backed relation reads grow large.
            graph = parse_content(
                source_kind="calendar_document",
                source_record_uid=document.document_id,
                content=document.content,
                content_type="text/calendar",
            )
            citations.update(
                {
                    (
                        document.document_id,
                        segment.content_segment_uid,
                    ): segment.safe_text_content
                    for segment in graph.segments
                    if segment.content_segment_uid in segment_uids
                }
            )
    return citations


async def _scoped_relations(
    db: AsyncSession,
    auth_context: AuthContext,
    visibility_scope: str,
    relation_uid: str | None = None,
    *,
    for_update: bool = False,
    after: str | None = None,
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
        if after is not None:
            statement = statement.where(EventRelationRecord.relation_uid > after)
        statement = statement.order_by(EventRelationRecord.relation_uid).limit(
            _PAGE_SIZE + 1
        )
    return list((await db.execute(statement)).all())


@router.get("/relations", response_model=EventRelationPageResponse)
async def list_event_relations(
    visibility_scope: Literal["personal", "organization"] = Query(),
    auth_context: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
    after: str | None = None,
) -> EventRelationPageResponse:
    if after is not None and _RELATION_CURSOR.fullmatch(after) is None:
        raise HTTPException(status_code=422, detail="Invalid relation cursor")
    relations = await _scoped_relations(db, auth_context, visibility_scope, after=after)
    page = relations[:_PAGE_SIZE]
    citations = await _citation_map(db, page, auth_context)
    return EventRelationPageResponse(
        items=[
            _relation_response(relation, source, target, citations)
            for relation, source, target in page
        ],
        next_cursor=page[-1][0].relation_uid if len(relations) > _PAGE_SIZE else None,
    )


@router.post("/relations/reconcile", response_model=EventReconcilePageResponse)
async def reconcile_event_relations(
    visibility_scope: Literal["personal", "organization"] = Query(),
    auth_context: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
    after: str | None = None,
) -> EventReconcilePageResponse:
    overlaps = await list_event_conflicts(visibility_scope, auth_context, db, after)
    for overlap in overlaps.items:
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
    return EventReconcilePageResponse(
        processed_conflicts=len(overlaps.items), next_cursor=overlaps.next_cursor
    )


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
