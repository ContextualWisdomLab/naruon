"""Authenticated API surface for deterministic calendar conflict decisions."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from services.calendar_conflict_policy import (
    CalendarCommitment,
    CalendarConflictDecision,
    CommitmentStatus,
    evaluate_calendar_conflicts,
)

router = APIRouter(prefix="/api/calendar/conflicts", tags=["calendar"])
MAX_EXISTING_COMMITMENTS = 500


class CalendarCommitmentPayload(BaseModel):
    """One bounded calendar commitment accepted by the decision endpoint."""

    model_config = ConfigDict(extra="forbid")

    commitment_id: str = Field(min_length=1, max_length=256)
    start_at: AwareDatetime
    end_at: AwareDatetime
    status: CommitmentStatus


class CalendarConflictRequest(BaseModel):
    """Candidate commitment plus existing evidence used for one decision."""

    model_config = ConfigDict(extra="forbid")

    proposed: CalendarCommitmentPayload
    existing: list[CalendarCommitmentPayload] = Field(
        default_factory=list,
        max_length=MAX_EXISTING_COMMITMENTS,
    )


class CalendarConflictEvidence(BaseModel):
    """Conflict evidence returned to the customer for explicit resolution."""

    commitment_id: str
    start_at: AwareDatetime
    end_at: AwareDatetime
    status: CommitmentStatus


class CalendarConflictResponse(BaseModel):
    """Buyer-visible decision, evidence, policy version, and next action."""

    decision_code: Literal["available", "blocked", "review_required"]
    reason_code: str
    conflicts: list[CalendarConflictEvidence]
    recommended_action: str
    policy_version: str


def _to_commitment(payload: CalendarCommitmentPayload) -> CalendarCommitment:
    """Convert a validated transport payload into deterministic policy evidence."""
    return CalendarCommitment(
        commitment_id=payload.commitment_id,
        start_at=payload.start_at,
        end_at=payload.end_at,
        status=payload.status,
    )


def _to_response(decision: CalendarConflictDecision) -> CalendarConflictResponse:
    """Convert the policy decision into the stable public response envelope."""
    return CalendarConflictResponse(
        decision_code=decision.decision_code,
        reason_code=decision.reason_code,
        conflicts=[
            CalendarConflictEvidence(
                commitment_id=conflict.commitment_id,
                start_at=conflict.start_at,
                end_at=conflict.end_at,
                status=conflict.status,
            )
            for conflict in decision.conflicts
        ],
        recommended_action=decision.recommended_action,
        policy_version=decision.policy_version,
    )


@router.post("/evaluate", response_model=CalendarConflictResponse)
def evaluate_calendar_conflict_request(
    request: CalendarConflictRequest,
) -> CalendarConflictResponse:
    """Evaluate double-booking risk without mutating any provider calendar."""
    try:
        proposed = _to_commitment(request.proposed)
        existing = [_to_commitment(item) for item in request.existing]
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return _to_response(evaluate_calendar_conflicts(proposed, existing))
