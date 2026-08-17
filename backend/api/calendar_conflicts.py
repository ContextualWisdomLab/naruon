"""Authenticated API surface for deterministic calendar conflict decisions."""

from __future__ import annotations

from typing import Literal, Self

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from services.calendar_conflict_ics import (
    parse_existing_calendar_commitments_from_ics,
    parse_proposed_calendar_commitment_from_ics,
)
from services.calendar_conflict_policy import (
    CalendarCommitment,
    CalendarConflictDecision,
    CalendarPolicyValidationError,
    CommitmentStatus,
    evaluate_calendar_conflicts,
)

router = APIRouter(prefix="/api/calendar/conflicts", tags=["calendar"])
MAX_EXISTING_COMMITMENTS = 500
MAX_PROPOSED_ICS_CHARS = 65_536
MAX_EXISTING_ICS_CHARS = 262_144
POLICY_VALIDATION_HTTP_STATUS = 422


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

    proposed: CalendarCommitmentPayload | None = None
    existing: list[CalendarCommitmentPayload] = Field(
        default_factory=list,
        max_length=MAX_EXISTING_COMMITMENTS,
    )
    proposed_ics: str | None = Field(default=None, min_length=1, max_length=MAX_PROPOSED_ICS_CHARS)
    existing_ics: str | None = Field(default=None, min_length=1, max_length=MAX_EXISTING_ICS_CHARS)

    @model_validator(mode="after")
    def require_exactly_one_proposed_source(self) -> Self:
        """Accept either a structured proposal or exactly one proposed VEVENT."""
        has_proposed = self.proposed is not None
        has_proposed_ics = self.proposed_ics is not None
        if has_proposed == has_proposed_ics:
            raise ValueError("Provide exactly one of proposed or proposed_ics")
        return self


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


class CalendarConflictErrorResponse(BaseModel):
    """Stable machine code plus safe explanation for policy validation failures."""

    error_code: str
    detail: str


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


@router.post(
    "/evaluate",
    response_model=CalendarConflictResponse,
    responses={POLICY_VALIDATION_HTTP_STATUS: {"model": CalendarConflictErrorResponse}},
)
def evaluate_calendar_conflict_request(
    request: CalendarConflictRequest,
) -> CalendarConflictResponse | JSONResponse:
    """Evaluate double-booking risk without mutating any provider calendar."""
    try:
        if request.proposed_ics is not None:
            proposed = parse_proposed_calendar_commitment_from_ics(request.proposed_ics)
        else:
            assert request.proposed is not None
            proposed = _to_commitment(request.proposed)
        existing = [_to_commitment(item) for item in request.existing]
        if request.existing_ics is not None:
            existing.extend(parse_existing_calendar_commitments_from_ics(request.existing_ics))
        if len(existing) > MAX_EXISTING_COMMITMENTS:
            raise CalendarPolicyValidationError(
                "calendar_existing_batch_exceeded",
                "existing evidence exceeds the bounded commitment batch",
            )
    except CalendarPolicyValidationError as exc:
        error = CalendarConflictErrorResponse(
            error_code=exc.error_code,
            detail=str(exc),
        )
        return JSONResponse(
            status_code=POLICY_VALIDATION_HTTP_STATUS,
            content=error.model_dump(),
        )

    return _to_response(evaluate_calendar_conflicts(proposed, existing))
