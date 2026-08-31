"""Authenticated API surface for deterministic calendar conflict decisions."""

from __future__ import annotations

import datetime
from typing import Literal, Self

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator
from pydantic_core import PydanticCustomError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request
from starlette.responses import Response

from api.auth import AuthContext, get_auth_context
from db.models import CalendarConflictJudgment
from db.session import get_db
from services.calendar_conflict_ics import (
    parse_existing_calendar_commitments_from_ics,
    parse_proposed_calendar_commitment_from_ics,
)
from services.calendar_conflict_judgment_service import (
    CORRECTION_INCOHERENT_ERROR_CODE,
    CalendarConflictCorrectionIncoherentError,
    CalendarConflictJudgmentNotFoundError,
    CalendarConflictUnsupportedValueError,
    apply_correction,
    create_judgment,
    get_judgment,
    list_judgments,
    validate_correction_coherence,
)
from services.calendar_conflict_policy import (
    MAX_EXISTING_COMMITMENTS,
    CalendarCommitment,
    CalendarConflictDecision,
    CalendarPolicyValidationError,
    CommitmentStatus,
    evaluate_calendar_conflicts,
)

MAX_PROPOSED_ICS_CHARS = 65_536
MAX_EXISTING_ICS_CHARS = 262_144
POLICY_VALIDATION_HTTP_STATUS = 422
# Matches api.ontology's SOURCE_IDENTIFIER_PATTERN: these ids are opaque
# RFC 5322-ish message/thread identifiers, not free text.
SOURCE_IDENTIFIER_PATTERN = r"^[\w\.\-\+@_<>]+$"
REQUEST_INVALID_ERROR_CODE = "calendar_request_invalid"
PROPOSED_SOURCE_MISSING_ERROR_CODE = "calendar_proposed_source_missing"
PROPOSED_SOURCE_REQUIRED_DETAIL = "Provide exactly one of proposed or proposed_ics"


class CalendarConflictAPIRoute(APIRoute):
    """Keep request-model failures on the stable calendar conflict error envelope."""

    def get_route_handler(self):
        """Wrap the FastAPI handler so validation uses CalendarConflictErrorResponse."""
        original_route_handler = super().get_route_handler()

        async def calendar_conflict_route_handler(request: Request) -> Response:
            try:
                return await original_route_handler(request)
            except RequestValidationError as exc:
                return _request_validation_error_response(exc)

        return calendar_conflict_route_handler


router = APIRouter(
    prefix="/api/calendar/conflicts",
    tags=["calendar"],
    route_class=CalendarConflictAPIRoute,
)


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
            # A typed error (not a plain ValueError) so the wrapping
            # RequestValidationError carries a stable machine-readable
            # errors()[i]["type"] -- _request_validation_error_response
            # dispatches on that, never on this rendered message's wording.
            raise PydanticCustomError(
                PROPOSED_SOURCE_MISSING_ERROR_CODE, PROPOSED_SOURCE_REQUIRED_DETAIL
            )
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


def _request_validation_error_response(exc: RequestValidationError) -> JSONResponse:
    """Map FastAPI request validation onto the existing error_code envelope.

    Dispatches on each error's ``type`` -- the stable identifier a
    ``PydanticCustomError`` (or Pydantic's own built-in error types) carries
    independently of its rendered ``msg`` -- never on message wording, so a
    future change to either error's phrasing can never silently misroute
    this to the wrong error_code.
    """
    error_types = {str(error.get("type", "")) for error in exc.errors()}
    if PROPOSED_SOURCE_MISSING_ERROR_CODE in error_types:
        error = CalendarConflictErrorResponse(
            error_code=PROPOSED_SOURCE_MISSING_ERROR_CODE,
            detail=PROPOSED_SOURCE_REQUIRED_DETAIL,
        )
    elif CORRECTION_INCOHERENT_ERROR_CODE in error_types:
        error = CalendarConflictErrorResponse(
            error_code=CORRECTION_INCOHERENT_ERROR_CODE,
            detail="status_code and decision_code disagree about whether the "
            "decision changed",
        )
    else:
        error = CalendarConflictErrorResponse(
            error_code=REQUEST_INVALID_ERROR_CODE,
            detail="Calendar conflict request fields are malformed",
        )
    return JSONResponse(
        status_code=POLICY_VALIDATION_HTTP_STATUS,
        content=error.model_dump(),
    )


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


def _resolve_commitments(
    request: CalendarConflictRequest,
) -> tuple[CalendarCommitment, list[CalendarCommitment]]:
    """Parse the proposed/existing commitments, raising on any policy violation."""
    proposed_payload = request.proposed
    if request.proposed_ics is not None:
        proposed = parse_proposed_calendar_commitment_from_ics(request.proposed_ics)
    elif proposed_payload is not None:
        proposed = _to_commitment(proposed_payload)
    else:
        raise CalendarPolicyValidationError(
            "calendar_proposed_source_missing",
            PROPOSED_SOURCE_REQUIRED_DETAIL,
        )
    existing = [_to_commitment(item) for item in request.existing]
    if request.existing_ics is not None:
        existing.extend(parse_existing_calendar_commitments_from_ics(request.existing_ics))
    if len(existing) > MAX_EXISTING_COMMITMENTS:
        raise CalendarPolicyValidationError(
            "calendar_existing_batch_exceeded",
            "existing evidence exceeds the bounded commitment batch",
        )
    return proposed, existing


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
        proposed, existing = _resolve_commitments(request)
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


class CalendarConflictJudgeRequest(CalendarConflictRequest):
    """An `/evaluate` request whose decision should be persisted as a judgment."""

    source_thread_id: str | None = Field(
        default=None, max_length=512, pattern=SOURCE_IDENTIFIER_PATTERN
    )
    source_message_id: str | None = Field(
        default=None, max_length=512, pattern=SOURCE_IDENTIFIER_PATTERN
    )


class CalendarConflictJudgmentResponse(BaseModel):
    """A persisted conflict decision, correctable by a human reviewer."""

    judgment_uid: str
    proposed_commitment_id: str
    source_thread_id: str | None
    source_message_id: str | None
    decision_code: Literal["available", "blocked", "review_required"]
    reason_code: str
    conflicts: list[CalendarConflictEvidence]
    recommended_action: str
    policy_version: str
    status_code: Literal["proposed", "confirmed", "overridden", "dismissed"]
    created_at: datetime.datetime
    updated_at: datetime.datetime


class CalendarConflictCorrectionRequest(BaseModel):
    """A human correction/confirmation applied to one persisted judgment."""

    model_config = ConfigDict(extra="forbid")

    correction_action: str = Field(min_length=1, max_length=64)
    decision_code: Literal["available", "blocked", "review_required"] | None = None
    status_code: Literal["confirmed", "overridden", "dismissed"]
    rationale: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def require_coherent_status_and_decision(self) -> Self:
        """Reject a status_code/decision_code pair the service would also reject.

        Checked here too (not only in apply_correction) so a mismatched
        request fails fast with a specific error_code instead of a 500 or a
        generic one -- re-raised as a typed PydanticCustomError carrying the
        service exception's own stable error_code (not a plain ValueError),
        so the wrapping RequestValidationError's errors()[i]["type"] stays
        that exact code independent of str(exc)'s wording.
        """
        try:
            validate_correction_coherence(
                status_code=self.status_code, decision_code=self.decision_code
            )
        except CalendarConflictCorrectionIncoherentError as exc:
            raise PydanticCustomError(exc.error_code, str(exc)) from exc
        return self


class CalendarConflictCorrectionResponse(BaseModel):
    """The recorded before/after audit trail for one correction."""

    correction_uid: str
    judgment_uid: str
    correction_action: str
    before_json: dict[str, object]
    after_json: dict[str, object]
    rationale: str | None
    actor_user_id: str
    created_at: datetime.datetime


def _judgment_response(
    judgment: CalendarConflictJudgment,
) -> CalendarConflictJudgmentResponse:
    return CalendarConflictJudgmentResponse(
        judgment_uid=judgment.judgment_uid,
        proposed_commitment_id=judgment.proposed_commitment_id,
        source_thread_id=judgment.source_thread_id,
        source_message_id=judgment.source_message_id,
        decision_code=judgment.decision_code,
        reason_code=judgment.reason_code,
        conflicts=[
            CalendarConflictEvidence(
                commitment_id=conflict["commitment_id"],
                start_at=conflict["start_at"],
                end_at=conflict["end_at"],
                status=conflict["status"],
            )
            for conflict in judgment.conflicts_json
        ],
        recommended_action=judgment.recommended_action,
        policy_version=judgment.policy_version,
        status_code=judgment.status_code,
        created_at=judgment.created_at,
        updated_at=judgment.updated_at,
    )


@router.post(
    "/judgments",
    response_model=CalendarConflictJudgmentResponse,
    responses={POLICY_VALIDATION_HTTP_STATUS: {"model": CalendarConflictErrorResponse}},
)
async def create_calendar_conflict_judgment(
    request: CalendarConflictJudgeRequest,
    auth_ctx: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
) -> CalendarConflictJudgmentResponse | JSONResponse:
    """Evaluate a conflict decision and persist it as a correctable judgment."""
    try:
        proposed, existing = _resolve_commitments(request)
    except CalendarPolicyValidationError as exc:
        error = CalendarConflictErrorResponse(
            error_code=exc.error_code,
            detail=str(exc),
        )
        return JSONResponse(
            status_code=POLICY_VALIDATION_HTTP_STATUS,
            content=error.model_dump(),
        )

    decision = evaluate_calendar_conflicts(proposed, existing)
    judgment = await create_judgment(
        db,
        user_id=auth_ctx.user_id,
        organization_id=auth_ctx.organization_id,
        workspace_id=auth_ctx.workspace_id,
        proposed_commitment_id=proposed.commitment_id,
        source_thread_id=request.source_thread_id,
        source_message_id=request.source_message_id,
        decision=decision,
    )
    await db.commit()
    return _judgment_response(judgment)


@router.get(
    "/judgments",
    response_model=list[CalendarConflictJudgmentResponse],
)
async def list_calendar_conflict_judgments(
    source_thread_id: str | None = Query(
        default=None, max_length=512, pattern=SOURCE_IDENTIFIER_PATTERN
    ),
    auth_ctx: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
) -> list[CalendarConflictJudgmentResponse]:
    """List persisted conflict judgments in the caller's own scope."""
    judgments = await list_judgments(
        db,
        user_id=auth_ctx.user_id,
        organization_id=auth_ctx.organization_id,
        workspace_id=auth_ctx.workspace_id,
        source_thread_id=source_thread_id,
    )
    return [_judgment_response(judgment) for judgment in judgments]


@router.get(
    "/judgments/{judgment_uid}",
    response_model=CalendarConflictJudgmentResponse,
)
async def get_calendar_conflict_judgment(
    judgment_uid: str,
    auth_ctx: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
) -> CalendarConflictJudgmentResponse:
    """Fetch one judgment by uid, even if it has fallen out of the list bound."""
    try:
        judgment = await get_judgment(
            db,
            judgment_uid=judgment_uid,
            user_id=auth_ctx.user_id,
            organization_id=auth_ctx.organization_id,
            workspace_id=auth_ctx.workspace_id,
        )
    except CalendarConflictJudgmentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _judgment_response(judgment)


@router.post(
    "/judgments/{judgment_uid}/corrections",
    response_model=CalendarConflictCorrectionResponse,
)
async def correct_calendar_conflict_judgment(
    judgment_uid: str,
    request: CalendarConflictCorrectionRequest,
    auth_ctx: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
) -> CalendarConflictCorrectionResponse | JSONResponse:
    """Record a human override/confirmation of one persisted judgment."""
    try:
        correction = await apply_correction(
            db,
            judgment_uid=judgment_uid,
            user_id=auth_ctx.user_id,
            organization_id=auth_ctx.organization_id,
            workspace_id=auth_ctx.workspace_id,
            actor_user_id=auth_ctx.user_id,
            correction_action=request.correction_action,
            decision_code=request.decision_code,
            status_code=request.status_code,
            rationale=request.rationale,
        )
        await db.commit()
    except CalendarConflictJudgmentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except CalendarConflictUnsupportedValueError as exc:
        # Unreachable through this route today (status_code/decision_code are
        # already Literal-typed on CalendarConflictCorrectionRequest, so
        # FastAPI rejects an unsupported value before this handler runs) --
        # kept as defense-in-depth so the service's own ALLOWED_* checks can
        # never surface as an unhandled 500 if the two ever drift apart.
        error = CalendarConflictErrorResponse(error_code=exc.error_code, detail=str(exc))
        return JSONResponse(
            status_code=POLICY_VALIDATION_HTTP_STATUS,
            content=error.model_dump(),
        )
    except CalendarConflictCorrectionIncoherentError as exc:
        # Also unreachable through this route today (CalendarConflictCorrectionRequest's
        # own model_validator already runs this exact check before this handler
        # runs) -- kept as defense-in-depth for the same reason as the
        # CalendarConflictUnsupportedValueError clause above: apply_correction's
        # own internal validate_correction_coherence() call must never surface
        # as an unhandled 500 if it and the request-model check ever drift apart.
        error = CalendarConflictErrorResponse(error_code=exc.error_code, detail=str(exc))
        return JSONResponse(
            status_code=POLICY_VALIDATION_HTTP_STATUS,
            content=error.model_dump(),
        )
    return CalendarConflictCorrectionResponse(
        correction_uid=correction.correction_uid,
        judgment_uid=judgment_uid,
        correction_action=correction.correction_action,
        before_json=correction.before_json,
        after_json=correction.after_json,
        rationale=correction.correction_rationale,
        actor_user_id=correction.actor_user_id,
        created_at=correction.created_at,
    )
