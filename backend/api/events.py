"""Owner-scoped, source-cited calendar event conflicts."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import AuthContext, get_auth_context
from db.models import SourceEventRecord
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
    organization_id = auth_context.organization_id
    organization_filter = (
        SourceEventRecord.organization_id == organization_id
        if organization_id is not None
        else SourceEventRecord.organization_id.is_(None)
    )
    # ponytail: compare only the 100 newest owner-visible events; use an
    # indexed time-window candidate query when the event ledger grows.
    events = (
        (
            await db.execute(
                select(SourceEventRecord)
                .where(
                    SourceEventRecord.user_id == auth_context.user_id,
                    organization_filter,
                    SourceEventRecord.workspace_id == auth_context.workspace_id,
                    SourceEventRecord.visibility_scope == visibility_scope,
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
