"""Persist `evaluate_calendar_conflicts` decisions and human corrections to them."""

from __future__ import annotations

import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import CalendarConflictCorrection, CalendarConflictJudgment
from services.calendar_conflict_policy import CalendarConflictDecision

ALLOWED_DECISION_CODES = frozenset({"available", "blocked", "review_required"})
ALLOWED_STATUS_CODES = frozenset({"proposed", "confirmed", "overridden", "dismissed"})


class CalendarConflictJudgmentNotFoundError(ValueError):
    """Raised when a judgment_uid does not resolve inside the caller's own scope."""


def _utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def _conflicts_to_json(decision: CalendarConflictDecision) -> list[dict[str, Any]]:
    return [
        {
            "commitment_id": conflict.commitment_id,
            "start_at": conflict.start_at.isoformat(),
            "end_at": conflict.end_at.isoformat(),
            "status": conflict.status,
        }
        for conflict in decision.conflicts
    ]


def _organization_filter(organization_id: str | None):
    if organization_id is not None:
        return CalendarConflictJudgment.organization_id == organization_id
    return CalendarConflictJudgment.organization_id.is_(None)


async def create_judgment(
    db: AsyncSession,
    *,
    user_id: str,
    organization_id: str | None,
    proposed_commitment_id: str,
    source_thread_id: str | None,
    source_message_id: str | None,
    decision: CalendarConflictDecision,
) -> CalendarConflictJudgment:
    """Persist one deterministic conflict decision as a correctable judgment record."""
    judgment = CalendarConflictJudgment(
        user_id=user_id,
        organization_id=organization_id,
        proposed_commitment_id=proposed_commitment_id,
        source_thread_id=source_thread_id,
        source_message_id=source_message_id,
        decision_code=decision.decision_code,
        reason_code=decision.reason_code,
        recommended_action=decision.recommended_action,
        policy_version=decision.policy_version,
        conflicts_json=_conflicts_to_json(decision),
    )
    db.add(judgment)
    await db.flush()
    return judgment


async def list_judgments(
    db: AsyncSession,
    *,
    user_id: str,
    organization_id: str | None,
    source_thread_id: str | None = None,
) -> list[CalendarConflictJudgment]:
    """List persisted judgments in the caller's own scope, newest first."""
    filters = [
        CalendarConflictJudgment.user_id == user_id,
        _organization_filter(organization_id),
    ]
    if source_thread_id is not None:
        filters.append(CalendarConflictJudgment.source_thread_id == source_thread_id)
    stmt = (
        select(CalendarConflictJudgment)
        .where(*filters)
        .order_by(CalendarConflictJudgment.created_at.desc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def _get_scoped_judgment(
    db: AsyncSession,
    *,
    judgment_uid: str,
    user_id: str,
    organization_id: str | None,
) -> CalendarConflictJudgment:
    stmt = select(CalendarConflictJudgment).where(
        CalendarConflictJudgment.judgment_uid == judgment_uid,
        CalendarConflictJudgment.user_id == user_id,
        _organization_filter(organization_id),
    )
    result = await db.execute(stmt)
    judgment = result.scalar_one_or_none()
    if judgment is None:
        raise CalendarConflictJudgmentNotFoundError(
            "Calendar conflict judgment is outside the requested scope"
        )
    return judgment


def _judgment_snapshot(judgment: CalendarConflictJudgment) -> dict[str, Any]:
    return {
        "decision_code": judgment.decision_code,
        "status_code": judgment.status_code,
    }


async def apply_correction(
    db: AsyncSession,
    *,
    judgment_uid: str,
    user_id: str,
    organization_id: str | None,
    actor_user_id: str,
    correction_action: str,
    decision_code: str | None,
    status_code: str,
    rationale: str | None,
) -> CalendarConflictCorrection:
    """Record a human override/confirmation of a persisted conflict judgment."""
    if status_code not in ALLOWED_STATUS_CODES:
        raise ValueError(f"Unsupported calendar conflict status_code: {status_code!r}")
    if decision_code is not None and decision_code not in ALLOWED_DECISION_CODES:
        raise ValueError(f"Unsupported calendar conflict decision_code: {decision_code!r}")

    judgment = await _get_scoped_judgment(
        db,
        judgment_uid=judgment_uid,
        user_id=user_id,
        organization_id=organization_id,
    )
    before_json = _judgment_snapshot(judgment)
    if decision_code is not None:
        judgment.decision_code = decision_code
    judgment.status_code = status_code
    judgment.updated_at = _utcnow()
    after_json = _judgment_snapshot(judgment)

    correction = CalendarConflictCorrection(
        judgment=judgment,
        user_id=user_id,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        correction_action=correction_action,
        before_json=before_json,
        after_json=after_json,
        rationale=rationale,
    )
    db.add(correction)
    await db.flush()
    return correction
