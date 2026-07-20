"""Authenticated bounded validation for DiskSage reclaim-plan evidence."""

import json

from fastapi import APIRouter, HTTPException, Request
from pydantic import ValidationError

from api.bounded_json import read_bounded_body, validate_unique_json_object_keys
from services.reclaim_plan import (
    DiskSageReclaimPlanEnvelope,
    ReclaimPlanValidationResponse,
    reclaim_plan_validation_response,
)


router = APIRouter(prefix="/api/reclaim-plan", tags=["reclaim-plan"])

MAX_DISKSAGE_RECLAIM_PLAN_BODY_BYTES = 10 * 1024 * 1024
RECLAIM_PLAN_TOO_LARGE_ERROR = "disksage_reclaim_plan_too_large"
RECLAIM_PLAN_INVALID_ERROR = "disksage_reclaim_plan_invalid"


@router.post("/validate", response_model=ReclaimPlanValidationResponse)
async def validate_disksage_reclaim_plan(
    request: Request,
) -> ReclaimPlanValidationResponse:
    """Validate report consistency without reading or mutating submitted paths."""

    body = await read_bounded_body(
        request,
        max_body_bytes=MAX_DISKSAGE_RECLAIM_PLAN_BODY_BYTES,
        too_large_error=RECLAIM_PLAN_TOO_LARGE_ERROR,
    )
    try:
        validate_unique_json_object_keys(body)
        envelope = DiskSageReclaimPlanEnvelope.model_validate_json(body)
    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
        RecursionError,
        ValidationError,
        ValueError,
    ):
        raise HTTPException(
            status_code=422,
            detail=RECLAIM_PLAN_INVALID_ERROR,
        ) from None
    return reclaim_plan_validation_response(envelope)
