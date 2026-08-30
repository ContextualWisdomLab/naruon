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
# A human correction that changes decision_code always replaces reason_code
# and recommended_action together, so a caller can never observe a decision
# paired with a reason/action that describes a different decision.
CORRECTED_DECISION_REASON_CODE = "corrected_by_human_review"
_MAX_JUDGMENTS_PER_LIST = 200


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
        .limit(_MAX_JUDGMENTS_PER_LIST)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def _get_scoped_judgment(
    db: AsyncSession,
    *,
    judgment_uid: str,
    user_id: str,
    organization_id: str | None,
    for_update: bool = False,
) -> CalendarConflictJudgment:
    stmt = select(CalendarConflictJudgment).where(
        CalendarConflictJudgment.judgment_uid == judgment_uid,
        CalendarConflictJudgment.user_id == user_id,
        _organization_filter(organization_id),
    )
    if for_update:
        # Serialize concurrent corrections to the same judgment: without this,
        # two concurrent apply_correction calls can both read the same prior
        # state, both record a "before" snapshot that matches, and race on
        # which correction's decision/status the row ends up with.
        stmt = stmt.with_for_update()
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
        "reason_code": judgment.reason_code,
        "recommended_action": judgment.recommended_action,
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
        for_update=True,
    )
    before_json = _judgment_snapshot(judgment)
    if decision_code is not None:
        # Replace reason_code/recommended_action together with decision_code
        # so a later read can never pair a corrected decision with the
        # original decision's now-stale reason and instruction. The original
        # values are never lost -- they are exactly what before_json above
        # already captured.
        judgment.decision_code = decision_code
        judgment.reason_code = CORRECTED_DECISION_REASON_CODE
        judgment.recommended_action = (
            rationale or "A human reviewer corrected this decision."
        )
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
