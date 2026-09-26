"""Owner-scoped, source-cited calendar event conflicts."""

from __future__ import annotations

import datetime
import hashlib
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from api.auth import AuthContext, get_auth_context
from db.models import (
    EventRelationCorrectionRecord,
    EventRelationRecord,
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


class EventSourceResponse(BaseModel):
    event_uid: str
    title: str
    starts_at: datetime.datetime
    ends_at: datetime.datetime
    email_id: int | None
    source_segment_uids: list[str]


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
                    *_event_scope(SourceEventRecord, auth_context, visibility_scope),
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
            if (
                source.source_event_key == target.source_event_key
                and source.starts_at == target.starts_at
                and source.ends_at == target.ends_at
            ):
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
        source=EventSourceResponse(
            event_uid=source.event_uid,
            title=source.title,
            starts_at=source.starts_at,
            ends_at=source.ends_at,
            email_id=source.email_id,
            source_segment_uids=source.source_segment_uids,
        ),
        target=EventSourceResponse(
            event_uid=target.event_uid,
            title=target.title,
            starts_at=target.starts_at,
            ends_at=target.ends_at,
            email_id=target.email_id,
            source_segment_uids=target.source_segment_uids,
        ),
    )


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
            *_event_scope(source, auth_context, visibility_scope),
            *_event_scope(target, auth_context, visibility_scope),
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
    return [_relation_response(relation, source, target) for relation, source, target in relations]


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
    return _relation_response(relation, source, target)
